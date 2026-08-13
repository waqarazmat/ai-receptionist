import asyncio
import json
import re
import time
import uuid

import structlog
from fastapi import APIRouter, HTTPException, Request, Response, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.ai.embeddings import embed_text_async
from app.ai.llm_router import (
    LLMProviderError,
    NoLLMProviderConfiguredError,
    get_org_llm_clients,
    stream_llm_with_fallback,
)
from app.ai.prompts.receptionist_system import get_system_prompt
from app.ai.rag_pipeline import ChunkResult, hybrid_search
from app.ai.voice_query_cache import get_cached_chunks, set_cached_chunks
from app.ai.response_generator import FALLBACK_MESSAGE
from app.channels.voice.call_manager import on_call_end, on_call_start
from app.channels.voice.voice_config import get_org_id_for_retell_agent, get_voice_config
from app.db.engine import async_session_maker
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.enums import ApiKeyProvider, Channel, MessageRole
from app.models.org_api_keys import OrgApiKey
from app.models.organization import Organization
from app.config import settings
from app.security.encryption import decrypt_api_key
from app.security.rate_limiter import check_message_rate_limit, increment_message_count
from app.security.webhook_verify import verify_retell_signature
from app.services.booking_service import booking_session_active, clear_booking_session, process_booking_intent
from app.services.conversation_service import (
    STATIC_RATE_LIMIT_MESSAGE,
    add_message,
    create_escalation,
    get_conversation_messages,
)

logger = structlog.get_logger()

# Lightweight keyword trigger to START a booking on voice. Voice deliberately
# skips the analyze_message intent call for latency, so we detect the initial
# booking intent with a cheap regex; once a booking is mid-flow, sticky routing
# (booking_session_active) keeps every subsequent turn in the FSM regardless.
_BOOKING_TRIGGER_RE = re.compile(
    r"\b(book|appointment|schedul|reschedul|reserve|set up a time|make an appointment|come in for)\b",
    re.IGNORECASE,
)


def _is_booking_trigger(text: str) -> bool:
    return bool(_BOOKING_TRIGGER_RE.search(text or ""))


# Explicit "get me a human" detector — same rationale as the booking trigger:
# voice skips the analyze_message intent call, so escalation intent is detected
# with a cheap regex, not an LLM call. Deliberately conservative (requires an
# action verb + a human noun, or "real/live person") to avoid false escalations
# that would wrongly stop the AI from helping.
_ESCALATION_TRIGGER_RE = re.compile(
    r"\b(speak|talk|connect|transfer|put me through)\b[^.?!]{0,30}\b(human|person|someone|agent|representative|rep|staff|manager|team)\b"
    r"|\b(real|actual|live)\s+(person|human|agent)\b"
    r"|\b(get me|need|want)\b[^.?!]{0,15}\b(human|agent|representative)\b",
    re.IGNORECASE,
)

# Spoken acknowledgement when a caller asks for a human. Voice can't do a live
# transfer, so this records the escalation + alerts staff for follow-up while the
# AI stays on the line. Org-agnostic wording (no hardcoded business name).
VOICE_ESCALATION_REPLY = (
    "Of course. I've passed this along to our team and someone will reach out to you shortly. "
    "Is there anything else I can help you with in the meantime?"
)


def _is_escalation_trigger(text: str) -> bool:
    return bool(_ESCALATION_TRIGGER_RE.search(text or ""))


# On-demand language switch — the intro-first flow no longer opens with the IVR
# language menu; the caller hears an introduction and is told they can switch
# language. This detects that request so the menu is presented only when asked.
# Deterministic (regex, no LLM call) to fit the voice latency budget, same as the
# booking/escalation triggers. Two shapes: an explicit "…language" request, or
# naming a language after a switch-context verb ("do you speak French", "in
# Dutch"). Only ever consulted for multi-language orgs.
_LANGUAGE_SWITCH_RE = re.compile(
    r"\b(?:change|switch|different|other|another|pick|choose|select)\b[^.?!]{0,25}\blanguages?\b"
    r"|\blanguages?\b[^.?!]{0,25}\b(?:option|options|menu|choices?|list|settings?)\b"
    r"|\bother\s+languages?\b"
    r"|\b(?:speak|spoken|talk|say(?:\sit)?|prefer|understand|continue|switch\sto|change\sto|in|have|got)\b"
    r"[^.?!]{0,15}\b(?:english|french|fran[cç]ais|spanish|espa[nñ]ol|dutch|nederlands|german|deutsch|"
    r"italian|italiano|portuguese|portugu[eê]s|arabic|turkish|t[uü]rk[cç]e|urdu|hindi|"
    r"chinese|mandarin|russian|polski|polish|japanese)\b",
    re.IGNORECASE,
)


def _is_language_switch_request(text: str) -> bool:
    return bool(_LANGUAGE_SWITCH_RE.search(text or ""))


# Patterns for extracting the caller's name from voice transcripts.
#
# Strategy 1 — user-turn self-introduction phrases (most reliable):
#   "my name is John", "I'm John", "this is John", "it's John", "call me John"
_USER_NAME_RE = re.compile(
    r"(?:my name(?:'?s| is)|i(?:'?m| am)(?: called)?|call me|this is|it'?s)\s+([a-zA-Z]{2,20}(?:\s+[a-zA-Z]{2,20})?)",
    re.IGNORECASE,
)
# Strategy 2 — AI address patterns in the LLM response (very reliable: the AI
# already identified the name and used it).  Includes every common phrase the
# receptionist LLM is likely to use when it first addresses the caller by name.
# The trailing group is optional-or-word-boundary so "Thank you, John" at the
# end of a string still matches (no required trailing char).
_AI_ADDRESS_RE = re.compile(
    r"(?:"
    r"thank(?:s| you)[,!]?|"
    r"you'?re welcome[,!]?|"       # "You're welcome, John" — seen in real calls
    r"hello[,!]?|hi[,!]?|hey[,!]?|"
    r"sure[,!]?|great[,!]?|perfect[,!]?|wonderful[,!]?|"
    r"of course[,!]?|absolutely[,!]?|certainly[,!]?|"
    r"got it[,!]?|noted[,!]?|"
    r"nice to (?:meet|hear from) you[,!]?"
    r")\s+([A-Z][a-z]{1,19}(?:\s+[A-Z][a-z]{1,19})?)(?=[\s!.,?]|$)",
)
# Strategy 3 — AI asked "what is your name?" and the user's NEXT turn is
# short (1-3 words).  Used only when strategies 1 and 2 find nothing.
_AI_ASKS_NAME_RE = re.compile(
    r"(?:your name|get your name|may i have your name|what(?:'?s| is) your name|"
    r"who am i (?:speaking|talking) (?:with|to)|who is this)",
    re.IGNORECASE,
)
# Words that are common false positives for self-intro patterns ("I'm fine").
_NAME_STOPWORDS = frozenset(
    {"fine", "good", "okay", "ok", "here", "there", "not", "in", "out", "on", "at",
     "available", "interested", "calling", "looking", "trying", "just", "also",
     "sorry", "sure", "ready", "back", "home", "done", "free", "actually",
     "calling", "checking", "wondering", "hoping", "thinking"}
)

# Split in two: the call-lifecycle webhook is a genuine one-way signed
# webhook (mounted under /api/public/webhooks/retell, alongside WhatsApp's),
# while the Custom LLM connection is a persistent bidirectional WebSocket,
# not a webhook — mounted directly on the public router at
# /api/public/retell/llm/{org_id}/{call_id} instead.
webhook_router = APIRouter()
ws_router = APIRouter()

RAG_TOP_K = 3
VOICE_REMINDER_TEXT = "Are you still there? I'm happy to keep helping whenever you're ready."

# ── End-call detection ────────────────────────────────────────────────────────
#
# Retell's Custom LLM protocol ends a call by including `"end_call": true` in
# the final response frame.  We trigger this via two fast-path checks (before
# the LLM is called) and one post-stream check (marker the LLM appends).

# Caller explicitly signals they want to hang up right now.
_HANGUP_RE = re.compile(
    r"\b(?:"
    r"hang\s*up|"
    r"end\s+(?:the\s+)?call|"
    r"cut\s+(?:the\s+|this\s+)?call|"
    r"stop\s+(?:the\s+)?call|"
    r"disconnect|"
    r"i(?:'m|\s+am)\s+done|"
    r"that(?:'s|\s+is)\s+all|"
    r"no\s+(?:more|further)\s+questions?|"
    r"gotta\s+go|got\s+to\s+go|need\s+to\s+go"
    r")\b",
    re.IGNORECASE,
)

# Short farewell acknowledgments — trigger end-call when the previous AI turn
# already said goodbye (so the caller is just confirming, not starting over).
_FAREWELL_ACK_WORDS: frozenset[str] = frozenset({
    "ok", "okay", "sure", "alright", "right", "great", "perfect", "thanks",
    "thank you", "cool", "bye", "bye bye", "goodbye", "see you", "cheers",
    "sounds good", "that's all", "that is all", "wonderful", "excellent",
    "got it", "understood",
})

# Goodbye language in a previous AI turn — paired with a farewell ack above
# to detect the "double goodbye" pattern without calling the LLM again.
_GOODBYE_RE = re.compile(
    r"\b(?:"
    r"goodbye|bye(?:\s*bye)?|"
    r"have\s+a\s+(?:great|good|nice|wonderful|lovely)\s+(?:day|evening|night|weekend)|"
    r"take\s+care|see\s+you\s+(?:soon|next|later)|"
    r"thank(?:s|\s+you)\s+for\s+(?:calling|reaching\s+out)|"
    r"don(?:'t)?\s+hesitate\s+to\s+(?:call|reach)|"
    r"feel\s+free\s+to\s+(?:call|reach)"
    r")\b",
    re.IGNORECASE,
)

# Token the LLM appends when it determines the conversation is naturally done.
# Detected after streaming; stripped from the persisted transcript.
_END_CALL_MARKER = "[END_CALL]"


def _is_explicit_hangup(text: str) -> bool:
    """True when the caller's message unambiguously asks to end the call now."""
    return bool(_HANGUP_RE.search(text))


def _is_post_goodbye_ack(message_text: str, transcript: list[dict]) -> bool:
    """True when the last AI turn said goodbye and the caller's reply is a
    short farewell acknowledgment with no new question.

    Uses the live Retell transcript (already in memory) rather than a DB
    history query, so it costs nothing extra on the critical path.
    """
    words = message_text.strip().lower().rstrip("!.,?").strip()
    if words not in _FAREWELL_ACK_WORDS:
        return False
    for turn in reversed(transcript):
        if turn.get("role") in ("assistant", "agent"):
            return bool(_GOODBYE_RE.search(turn.get("content") or ""))
    return False


# ── Language-selection menu (multi-language orgs only) ────────────────────────
#
# Per-language data for the IVR-style opening menu.  Only the four languages
# the platform actively supports are listed.  An org.supported_languages entry
# NOT in this dict is silently skipped when building the menu.
#
# menu_line    — what the caller hears for this option, in that language.
#                {n} is replaced by the option number (1-based).
# disclosure   — AI Act Art. 50 disclosure spoken in that language, after selection.
# instruction  — appended to the LLM system prompt for the rest of the call to
#                enforce language — placed LAST so it overrides everything above it.
# keywords     — words or substrings that indicate the caller chose this language.
#                Positional digit ("1", "2", …) is checked separately before
#                keywords, so these need not include the digit itself.
_LANG_INFO: dict[str, dict] = {
    "en": {
        "menu_line": 'For English, press {n} or say "English".',
        "disclosure": "This call is handled by an AI assistant.",
        "instruction": "You MUST respond ONLY in English.",
        "keywords": {"english", "one"},
    },
    "nl": {
        "menu_line": 'Voor Nederlands, druk {n} of zeg "Nederlands".',
        "disclosure": "Dit gesprek wordt behandeld door een AI-assistent.",
        "instruction": "U MOET uitsluitend in het Nederlands antwoorden.",
        "keywords": {"nederlands", "dutch", "two", "twee"},
    },
    "fr": {
        "menu_line": 'Pour le français, appuyez {n} ou dites "Français".',
        "disclosure": "Cet appel est traité par un assistant IA.",
        "instruction": "Vous DEVEZ répondre UNIQUEMENT en français.",
        "keywords": {"français", "francais", "french", "three", "trois"},
    },
    "de": {
        "menu_line": 'Für Deutsch, drücken Sie {n} oder sagen Sie "Deutsch".',
        "disclosure": "Dieses Gespräch wird von einem KI-Assistenten bearbeitet.",
        "instruction": "Sie MÜSSEN ausschließlich auf Deutsch antworten.",
        "keywords": {"deutsch", "german", "four", "vier"},
    },
    "es": {
        "menu_line": 'Para español, pulse {n} o diga "Español".',
        "disclosure": "Esta llamada es atendida por un asistente de IA.",
        "instruction": "Debes responder ÚNICAMENTE en español.",
        "keywords": {"español", "espanol", "spanish", "five", "cinco"},
    },
    "it": {
        "menu_line": 'Per italiano, premi {n} o dì "Italiano".',
        "disclosure": "Questa chiamata è gestita da un assistente IA.",
        "instruction": "Devi rispondere SOLO in italiano.",
        "keywords": {"italiano", "italian", "six", "sei"},
    },
    "pt": {
        "menu_line": 'Para português, pressione {n} ou diga "Português".',
        "disclosure": "Esta chamada é atendida por um assistente de IA.",
        "instruction": "Você DEVE responder SOMENTE em português.",
        "keywords": {"português", "portugues", "portuguese", "seven", "sete"},
    },
    "ar": {
        "menu_line": 'للعربية، اضغط {n} أو قل "عربي".',
        "disclosure": "هذه المكالمة يعالجها مساعد ذكاء اصطناعي.",
        "instruction": "يجب أن تُجيب باللغة العربية فقط.",
        "keywords": {"عربي", "arabic", "eight", "ثمانية"},
    },
    "tr": {
        "menu_line": 'Türkçe için {n}\'e basın veya "Türkçe" deyin.',
        "disclosure": "Bu çağrı bir yapay zeka asistanı tarafından işlenmektedir.",
        "instruction": "YALNIZCA Türkçe yanıt vermelisiniz.",
        "keywords": {"türkçe", "turkce", "turkish", "nine", "dokuz"},
    },
    "ur": {
        "menu_line": 'اردو کے لیے {n} دبائیں یا "اردو" کہیں۔',
        "disclosure": "یہ کال ایک AI اسسٹنٹ کے ذریعے سنبھالی جا رہی ہے۔",
        "instruction": "آپ کو صرف اردو میں جواب دینا ہوگا۔",
        "keywords": {"اردو", "urdu", "ten", "دس"},
    },
    "hi": {
        "menu_line": 'हिंदी के लिए {n} दबाएं या "हिंदी" कहें।',
        "disclosure": "यह कॉल एक AI असिस्टेंट द्वारा संभाली जा रही है।",
        "instruction": "आपको केवल हिंदी में उत्तर देना होगा।",
        "keywords": {"हिंदी", "hindi", "eleven", "ग्यारह"},
    },
    "zh": {
        "menu_line": '普通话请按{n}或说"中文"。',
        "disclosure": "本次通话由AI助手处理。",
        "instruction": "您必须只用中文回答。",
        "keywords": {"中文", "chinese", "mandarin", "twelve", "十二"},
    },
    "ru": {
        "menu_line": 'Для русского нажмите {n} или скажите "Русский".',
        "disclosure": "Этот звонок обрабатывается ИИ-ассистентом.",
        "instruction": "Вы ДОЛЖНЫ отвечать ТОЛЬКО на русском языке.",
        "keywords": {"русский", "russian", "thirteen", "тринадцать"},
    },
    "pl": {
        "menu_line": 'Dla języka polskiego naciśnij {n} lub powiedz "Polski".',
        "disclosure": "To połączenie jest obsługiwane przez asystenta AI.",
        "instruction": "Musisz odpowiadać WYŁĄCZNIE po polsku.",
        "keywords": {"polski", "polish", "fourteen", "czternaście"},
    },
}


def _build_language_menu(supported_languages: list[str]) -> str:
    """Concatenate one menu sentence per supported language, each spoken in
    that language so every caller hears their own language before selecting."""
    lines = []
    for idx, code in enumerate(supported_languages, start=1):
        info = _LANG_INFO.get(code)
        if info:
            lines.append(info["menu_line"].format(n=idx))
    return " ".join(lines)


def _detect_language_choice(user_input: str, supported_languages: list[str]) -> str | None:
    """Return the ISO 639-1 code chosen by the caller, or None if unclear.

    Accepts spoken/DTMF position numbers ("1", "2", …) and language keywords
    in any supported language.  Position check runs first to short-circuit
    before keyword scanning, which avoids cross-language ambiguity.
    """
    normalized = user_input.strip().lower()
    for idx, code in enumerate(supported_languages, start=1):
        info = _LANG_INFO.get(code)
        if not info:
            continue
        if str(idx) in normalized:
            return code
        if any(kw in normalized for kw in info["keywords"]):
            return code
    return None


def _lang_disclosure(language: str) -> str:
    """AI Act Art. 50 disclosure text in the given language."""
    return _LANG_INFO.get(language, _LANG_INFO["en"])["disclosure"]


# English disclosure constant — imported by compliance tests and any caller
# that needs the canonical English string directly.
_AI_VOICE_DISCLOSURE: str = _LANG_INFO["en"]["disclosure"]


def _lang_instruction(language: str) -> str:
    """System-prompt language-enforcement string for the given language."""
    return _LANG_INFO.get(language, _LANG_INFO["en"])["instruction"]


def _language_fallback(supported: list[str]) -> str:
    """Fallback language for timeout / unrecognised menu input.

    English is preferred because it is always in the AI's training data.
    If the org genuinely doesn't support English, we fall back to their
    first configured language rather than refusing to proceed.
    """
    return "en" if "en" in supported else supported[0]


# On-demand language-switch phrasing (intro-first flow). Kept in a parallel dict
# so the primary _LANG_INFO menu/disclosure/keyword data stays untouched.
#   switch_invite — one-line offer appended to the opening greeting, spoken in the
#                   org's default language ("you can switch language anytime").
#   menu_prompt   — lead-in spoken in the CURRENT language right before the menu,
#                   when a caller actually asks to change language.
#   resume        — short confirmation spoken in the NEW language after a switch
#                   (the caller was already introduced/disclosed at call start,
#                   so we don't repeat the full greeting).
_LANG_SWITCH_TEXT: dict[str, dict[str, str]] = {
    "en": {"switch_invite": "You can also switch language at any time — just ask.",
           "menu_prompt": "Sure — which language would you like?",
           "resume": "Great. How can I help you?"},
    "nl": {"switch_invite": "U kunt ook op elk moment van taal wisselen — vraag er gerust naar.",
           "menu_prompt": "Natuurlijk — welke taal wilt u?",
           "resume": "Prima. Hoe kan ik u helpen?"},
    "fr": {"switch_invite": "Vous pouvez aussi changer de langue à tout moment — demandez simplement.",
           "menu_prompt": "Bien sûr — quelle langue souhaitez-vous ?",
           "resume": "Parfait. Comment puis-je vous aider ?"},
    "de": {"switch_invite": "Sie können jederzeit die Sprache wechseln — fragen Sie einfach.",
           "menu_prompt": "Natürlich — welche Sprache möchten Sie?",
           "resume": "Sehr gut. Wie kann ich Ihnen helfen?"},
    "es": {"switch_invite": "También puede cambiar de idioma en cualquier momento — solo pídalo.",
           "menu_prompt": "Claro — ¿qué idioma prefiere?",
           "resume": "Perfecto. ¿En qué puedo ayudarle?"},
    "it": {"switch_invite": "Può anche cambiare lingua in qualsiasi momento — basta chiedere.",
           "menu_prompt": "Certo — quale lingua preferisce?",
           "resume": "Perfetto. Come posso aiutarla?"},
    "pt": {"switch_invite": "Também pode mudar de idioma a qualquer momento — é só pedir.",
           "menu_prompt": "Claro — que idioma prefere?",
           "resume": "Ótimo. Como posso ajudá-lo?"},
    "ar": {"switch_invite": "يمكنك أيضًا تغيير اللغة في أي وقت — فقط اطلب ذلك.",
           "menu_prompt": "بالطبع — ما اللغة التي تفضلها؟",
           "resume": "رائع. كيف يمكنني مساعدتك؟"},
    "tr": {"switch_invite": "İstediğiniz zaman dili de değiştirebilirsiniz — sadece söyleyin.",
           "menu_prompt": "Tabii — hangi dili istersiniz?",
           "resume": "Harika. Size nasıl yardımcı olabilirim?"},
    "ur": {"switch_invite": "آپ کسی بھی وقت زبان بھی تبدیل کر سکتے ہیں — بس کہہ دیں۔",
           "menu_prompt": "ضرور — آپ کون سی زبان چاہتے ہیں؟",
           "resume": "بہت اچھا۔ میں آپ کی کیسے مدد کر سکتا ہوں؟"},
    "hi": {"switch_invite": "आप किसी भी समय भाषा भी बदल सकते हैं — बस कहिए।",
           "menu_prompt": "ज़रूर — आप कौन सी भाषा चाहते हैं?",
           "resume": "बढ़िया। मैं आपकी कैसे मदद कर सकता हूँ?"},
    "zh": {"switch_invite": "您也可以随时切换语言——只需告诉我。",
           "menu_prompt": "当然——您想要哪种语言？",
           "resume": "好的。有什么可以帮您？"},
    "ru": {"switch_invite": "Вы также можете сменить язык в любой момент — просто скажите.",
           "menu_prompt": "Конечно — какой язык вы хотите?",
           "resume": "Отлично. Чем я могу помочь?"},
    "pl": {"switch_invite": "Możesz też w każdej chwili zmienić język — wystarczy poprosić.",
           "menu_prompt": "Oczywiście — jaki język Pan/Pani wybiera?",
           "resume": "Świetnie. Jak mogę pomóc?"},
}


def _switch_invite(language: str) -> str:
    return _LANG_SWITCH_TEXT.get(language, _LANG_SWITCH_TEXT["en"])["switch_invite"]


def _menu_prompt(language: str) -> str:
    return _LANG_SWITCH_TEXT.get(language, _LANG_SWITCH_TEXT["en"])["menu_prompt"]


def _resume_line(language: str) -> str:
    return _LANG_SWITCH_TEXT.get(language, _LANG_SWITCH_TEXT["en"])["resume"]


# ── Multilingual intro-first opening + automatic language mirroring ───────────
#
# For orgs that support more than one language, the caller now hears a short
# introduction spoken in EACH supported language (capped, see below), followed
# by an invitation to simply continue in whichever language they prefer. From
# then on the LLM mirrors the caller's language automatically — no IVR menu, no
# "press 1 for English". The old on-demand menu still exists as a manual
# override (a caller can say "can you switch to French"), but the default,
# expected path is: speak your language, and the assistant speaks it back.

# Human-readable language names, used to tell the LLM which languages to expect
# in the mirroring instruction. Falls back to the raw ISO code if unlisted.
_LANG_ENGLISH_NAME: dict[str, str] = {
    "en": "English", "nl": "Dutch", "fr": "French", "de": "German", "es": "Spanish",
    "it": "Italian", "pt": "Portuguese", "ar": "Arabic", "tr": "Turkish", "ur": "Urdu",
    "hi": "Hindi", "zh": "Chinese", "ru": "Russian", "pl": "Polish",
}

# Per-language intro copy for the multilingual opening. `greeting` takes the org
# name; `choose_prompt` asks which language the caller would like — it takes the
# {langs} list of available languages, AND invites the caller to just ask their
# question, so someone who ignores the choice is never trapped in a menu.
# Languages not listed here fall back to English so the intro is always well-formed.
_LANG_INTRO: dict[str, dict[str, str]] = {
    "en": {
        "greeting": "Hi, thank you for calling {org}. I can help you book an appointment or answer questions about our services.",
        "choose_prompt": "I can help you in {langs}. Which language would you prefer? You can also just go ahead and ask your question.",
    },
    "nl": {
        "greeting": "Hallo, bedankt voor uw telefoontje naar {org}. Ik kan u helpen een afspraak te maken of vragen over onze diensten te beantwoorden.",
        "choose_prompt": "Ik kan u helpen in {langs}. Welke taal heeft uw voorkeur? U kunt ook gewoon meteen uw vraag stellen.",
    },
    "fr": {
        "greeting": "Bonjour, merci d'avoir appelé {org}. Je peux vous aider à prendre rendez-vous ou répondre à vos questions sur nos services.",
        "choose_prompt": "Je peux vous aider en {langs}. Quelle langue préférez-vous ? Vous pouvez aussi poser directement votre question.",
    },
    "de": {
        "greeting": "Hallo, danke für Ihren Anruf bei {org}. Ich kann Ihnen helfen, einen Termin zu buchen oder Fragen zu unseren Leistungen zu beantworten.",
        "choose_prompt": "Ich kann Ihnen auf {langs} helfen. Welche Sprache möchten Sie? Sie können auch einfach Ihre Frage stellen.",
    },
    "es": {
        "greeting": "Hola, gracias por llamar a {org}. Puedo ayudarle a reservar una cita o responder preguntas sobre nuestros servicios.",
        "choose_prompt": "Puedo ayudarle en {langs}. ¿Qué idioma prefiere? También puede hacer su pregunta directamente.",
    },
}

def _draft_multilingual_begin_message(org: "Organization | None", supported_languages: list[str]) -> str:
    """Opening utterance for a multi-language org. The introduction (AI-Act
    disclosure + greeting) is spoken ONCE, in English — or the org's first
    language if it doesn't support English — and ends with a prompt asking which
    language the caller would like, listing every supported language by its
    English name ("Dutch, English, French") and inviting them to just ask their
    question. The intro is deliberately NOT repeated in every language: doing so
    made the opening long and repetitive.

    The disclosure (AI Act Art. 50) still leads the utterance and is NOT
    overridable."""
    org_name = (org.name if org and org.name else None) or "our office"
    langs = ", ".join(_LANG_ENGLISH_NAME.get(code, code) for code in supported_languages) or "English"

    # Speak the intro in English (the common lingua franca), falling back to the
    # org's first language only if English isn't supported.
    intro_lang = _language_fallback(supported_languages) if supported_languages else "en"
    intro = _LANG_INTRO.get(intro_lang, _LANG_INTRO["en"])
    disclosure = _lang_disclosure(intro_lang)
    greeting = intro["greeting"].format(org=org_name)
    prompt = intro["choose_prompt"].format(langs=langs)
    return f"{disclosure} {greeting} {prompt}"


def _mirror_language_instruction(supported_languages: list[str]) -> str:
    """System-prompt clause telling the LLM to auto-detect and mirror the
    caller's language. Replaces the old hard single-language lock: instead of
    forcing one language, the assistant follows whatever the caller speaks,
    among the org's supported set. Covers ALL supported languages, not just the
    ones spoken in the (capped) intro."""
    names = [_LANG_ENGLISH_NAME.get(code, code) for code in supported_languages] or ["English"]
    lang_list = ", ".join(names)
    default_name = names[0]
    return (
        "LANGUAGE HANDLING: This caller may speak any of these languages: "
        f"{lang_list}. Detect the language of the caller's most recent message and "
        "ALWAYS reply in that same language. If the caller switches language mid-call, "
        "switch with them on the very next reply. If their language is genuinely "
        f"unclear (for example a one-word answer or just a name), reply in {default_name}. "
        "Never announce or comment on the language switch — simply respond naturally in "
        "the caller's language."
    )


# Codes in the 4000-4999 range are reserved for application use per RFC 6455.
WS_CLOSE_VOICE_NOT_CONFIGURED = 4404
WS_CLOSE_AGENT_MISMATCH = 4403

_HISTORY_ROLE_MAP = {MessageRole.customer: "user", MessageRole.ai: "assistant"}

# Keep raw-payload logs bounded — a transcript array grows unboundedly over a
# long call, and we don't want a single event to dump kilobytes per turn.
_MAX_LOG_CHARS = 800


def _truncate_json(obj: object) -> str:
    text = json.dumps(obj, default=str)
    if len(text) <= _MAX_LOG_CHARS:
        return text
    return f"{text[:_MAX_LOG_CHARS]}...(+{len(text) - _MAX_LOG_CHARS} chars)"


class _Sender:
    """Serializes every server→Retell frame behind one lock so concurrent tasks
    (the receive loop's ping_pong echoes + a background turn's streamed tokens)
    can never interleave a half-written frame — Starlette's WebSocket.send_json
    is not safe to call from two coroutines at once.

    The lock is acquired PER FRAME, not for a whole streamed response: that's
    deliberate, so a ping_pong echo (or an interruption's close frame) can slip
    in between two streamed tokens and keep the connection alive while the LLM
    is still producing output."""

    def __init__(self, websocket: WebSocket, org_id: uuid.UUID, call_id: str) -> None:
        self._ws = websocket
        self._org_id = org_id
        self._call_id = call_id
        self._lock = asyncio.Lock()

    async def send(self, payload: dict, *, log: bool = True) -> None:
        async with self._lock:
            if log:
                logger.info(
                    "voice_ws_send",
                    org_id=str(self._org_id),
                    call_id=self._call_id,
                    response_type=payload.get("response_type"),
                    payload=_truncate_json(payload),
                )
            await self._ws.send_json(payload)

    async def send_chunk(self, response_id: int | None, content: str, content_complete: bool) -> None:
        # Per-token streaming frames aren't logged individually (too chatty).
        await self.send(
            {
                "response_type": "response",
                "response_id": response_id,
                "content": content,
                "content_complete": content_complete,
            },
            log=False,
        )

    async def send_shortcut(self, response_id: int | None, text: str) -> None:
        await self.send(
            {"response_type": "response", "response_id": response_id, "content": text, "content_complete": True}
        )

    async def send_end_call_shortcut(self, response_id: int | None, text: str) -> None:
        """Send a complete response and signal Retell to terminate the call.

        Retell's Custom LLM protocol ends a call by including `end_call: true`
        in any response frame — no separate API call or agent-side function
        registration needed for Custom LLM agents.
        """
        await self.send(
            {
                "response_type": "response",
                "response_id": response_id,
                "content": text,
                "content_complete": True,
                "end_call": True,
            }
        )

    async def send_response_close(self, response_id: int | None) -> None:
        """Empty, complete frame that tells Retell an interrupted response is
        done, so it stops waiting on that response_id before the next one."""
        await self.send(
            {"response_type": "response", "response_id": response_id, "content": "", "content_complete": True}
        )


class _CallState:
    """Per-connection mutable state shared between the receive loop and the
    background turn/reminder/call_details tasks. `conversation_lock` guards the
    get-or-create of this call's Conversation so concurrent tasks (a lazily-
    creating turn racing the call_details event) don't each insert one —
    on_call_start is idempotent but not concurrency-safe on its own.

    The per-call caches (org_name/org_prompts/contact_name/llm_client_future)
    exist so that a multi-turn call pays for the DB reads + API-key decrypt
    once at connect time, not on every response_required turn."""

    def __init__(self) -> None:
        self.conversation_id: uuid.UUID | None = None
        self.greeting_saved: bool = False
        self.conversation_lock: asyncio.Lock = asyncio.Lock()
        # Populated once by voice_llm_websocket at accept from data it already
        # loaded — no extra DB round-trip on the critical path.
        self.org_name: str | None = None
        self.org_prompts: dict = {}
        # Set from the call_details event the moment Retell sends it. Used by
        # _ensure_conversation in _handle_turn so turns don't race and create
        # a contact with name/phone="unknown" if call_details hasn't committed yet.
        self.from_number: str | None = None
        # Contact is fixed for the whole call — resolved from the conversation
        # on first turn under contact_lock, cached thereafter.
        self.contact_name: str | None = None
        self.contact_fetched: bool = False
        self.contact_lock: asyncio.Lock = asyncio.Lock()
        # Primed as a background task at accept (see _prime_llm_client). Turns
        # await the future — instant if priming already resolved, else waits.
        self.llm_client_future: asyncio.Future | None = None
        # Language-selection state (multi-language orgs only).
        # `language_phase` stays True until the caller makes a valid choice;
        # `selected_language` is the ISO 639-1 code used for the rest of the
        # call; `org_supported_languages` is the org's configured list.
        self.language_phase: bool = False
        self.selected_language: str = "en"
        self.org_supported_languages: list[str] = ["en"]
        # True only for the call-OPEN language choice (the intro asks "which
        # language?"). Distinguishes it from the on-demand switch menu: on the
        # opening prompt, a caller who ignores the choice and just asks a
        # question must be ANSWERED, not sent a "how can I help?" resume line.
        self.initial_language_prompt: bool = False
        # Safety-net timer spawned when the language menu is presented.
        # Cancelled as soon as the caller makes any selection (valid or invalid).
        self.language_timeout_task: asyncio.Task | None = None


async def _ensure_conversation(
    state: _CallState, org_id: uuid.UUID, call_id: str, from_number: str
) -> uuid.UUID:
    """Get-or-create this call's conversation exactly once across all tasks."""
    if state.conversation_id is not None:
        return state.conversation_id
    async with state.conversation_lock:
        if state.conversation_id is not None:
            return state.conversation_id
        async with async_session_maker() as db:
            conversation = await on_call_start(db, org_id, call_id, from_number)
            state.conversation_id = conversation.id
    return state.conversation_id


async def _prime_llm_client(state: _CallState, org_id: uuid.UUID, call_id: str) -> None:
    """Background: decrypt the org's fast-tier API key and build an LLM client
    once at WebSocket accept, so the first turn doesn't pay for it. Turns read
    the result via `state.llm_client_future`. Errors are stored on the future
    so the turn handler can degrade gracefully."""
    if state.llm_client_future is None:
        return
    t0 = time.monotonic()
    try:
        async with async_session_maker() as db:
            # Prime the FULL fallback list (primary + secondaries) so a
            # provider outage mid-call can fail over on the next turn.
            clients = await get_org_llm_clients(db, org_id, model_tier="fast")
        logger.info(
            "voice_llm_client_ms",
            org_id=str(org_id),
            call_id=call_id,
            latency_ms=round((time.monotonic() - t0) * 1000),
            providers=[c.provider.value for c in clients],
        )
        if not state.llm_client_future.done():
            state.llm_client_future.set_result(clients)
    except Exception as exc:  # noqa: BLE001 — propagate to the awaiting turn
        if not state.llm_client_future.done():
            state.llm_client_future.set_exception(exc)


async def _ensure_contact_name(state: _CallState, conversation_id: uuid.UUID) -> str | None:
    """Resolve the contact for this call exactly once, then cache. Contact
    doesn't change mid-call, so this is a per-turn round-trip we can skip on
    every turn after the first."""
    if state.contact_fetched:
        return state.contact_name
    async with state.contact_lock:
        if state.contact_fetched:
            return state.contact_name
        t0 = time.monotonic()
        async with async_session_maker() as db:
            conversation = await db.get(Conversation, conversation_id)
            if conversation and conversation.contact_id:
                contact = await db.get(Contact, conversation.contact_id)
                if contact:
                    state.contact_name = contact.name
        state.contact_fetched = True
        logger.info(
            "voice_contact_db_ms",
            conversation_id=str(conversation_id),
            latency_ms=round((time.monotonic() - t0) * 1000),
        )
    return state.contact_name


async def _fetch_prior_history(conversation_id: uuid.UUID, call_id: str) -> list[dict]:
    """Read prior conversation history in its own session so it can run in
    parallel with the RAG session (SQLAlchemy async sessions are not safe to
    share across concurrent coroutines)."""
    t0 = time.monotonic()
    async with async_session_maker() as db:
        rows = await get_conversation_messages(db, conversation_id)
    history = [
        {"role": _HISTORY_ROLE_MAP[m.role], "content": m.content}
        for m in rows
        if m.role in _HISTORY_ROLE_MAP
    ]
    logger.info(
        "voice_history_db_ms",
        call_id=call_id,
        latency_ms=round((time.monotonic() - t0) * 1000),
        count=len(history),
    )
    return history


async def _run_rag(org_id: uuid.UUID, call_id: str, message_text: str) -> list:
    """Embed the query (CPU, off event loop via to_thread) then hybrid-search
    on its own session so it runs in parallel with history_fetch. Splits the
    two phases so we can log embed vs search time separately.

    A normalized-string cache lookup runs FIRST — on hit we skip both the
    embedding (~50-200ms CPU) and the pgvector+FTS round-trip (~30-150ms).
    The semantic (embedding-cosine) tier the audit sketched isn't worth it
    here: comparing embeddings still requires embedding the incoming query,
    which is the tall pole we're trying to avoid on voice. Revisit only if
    the string layer's hit rate turns out too low in practice.
    """
    cache_start = time.monotonic()
    cached = await get_cached_chunks(str(org_id), message_text)
    if cached is not None:
        logger.info(
            "voice_semantic_cache_hit",
            org_id=str(org_id),
            call_id=call_id,
            hit=True,
            latency_ms=round((time.monotonic() - cache_start) * 1000),
            chunks=len(cached),
        )
        # Reconstitute ChunkResult so the caller's shape assumptions hold.
        # chunk_id isn't read downstream, so a nil UUID is fine.
        return [
            ChunkResult(chunk_id=uuid.UUID(int=0), content=item["content"], score=float(item.get("score", 0.0)))
            for item in cached
        ]
    logger.info(
        "voice_semantic_cache_hit",
        org_id=str(org_id),
        call_id=call_id,
        hit=False,
        latency_ms=round((time.monotonic() - cache_start) * 1000),
    )

    t0 = time.monotonic()
    query_embedding = await embed_text_async(message_text)
    embed_ms = round((time.monotonic() - t0) * 1000)
    logger.info("voice_embed_ms", org_id=str(org_id), call_id=call_id, latency_ms=embed_ms)

    t1 = time.monotonic()
    async with async_session_maker() as db:
        chunks = await hybrid_search(db, org_id, message_text, query_embedding, top_k=RAG_TOP_K)
    logger.info(
        "voice_rag_ms",
        org_id=str(org_id),
        call_id=call_id,
        latency_ms=round((time.monotonic() - t1) * 1000),
        chunks=len(chunks),
    )

    # Await the cache write before returning: a fire-and-forget task races the
    # next turn (a caller repeating the exact same phrase within ~150ms would
    # miss the cache because the SET hadn't landed yet — TEST 1 turn 2 caught
    # this). The write is one Redis SET (~1-5ms colocated, ~150ms here), well
    # under the LLM call cost that follows, so the added block is fine. Errors
    # are swallowed inside set_cached_chunks so this can never fail a turn.
    await set_cached_chunks(str(org_id), message_text, chunks)
    return chunks


async def _persist_customer_message(conversation_id: uuid.UUID, message_text: str, call_id: str) -> None:
    """Write the customer's message on its own session in parallel with the
    read paths. History for the LLM is built manually (prior_history + this
    message), so the LLM call doesn't have to wait for this write."""
    t0 = time.monotonic()
    async with async_session_maker() as db:
        await add_message(db, conversation_id, MessageRole.customer, message_text, Channel.voice)
    logger.info(
        "voice_persist_customer_db_ms",
        call_id=call_id,
        latency_ms=round((time.monotonic() - t0) * 1000),
    )


def _draft_begin_message(config: dict, org: "Organization | None", language: str = "en") -> str:
    """Build the opening utterance spoken right after the config frame — the
    first thing every caller hears, in the org's default language. Multi-language
    orgs additionally get a one-line switch-language invitation appended by the
    caller (see the call-open block); the menu itself is on-demand, not up front.

    The AI-identity disclosure (AI Act Art. 50) is unconditionally prepended
    and is NOT overridable via org config — it is a legal requirement.
    """
    disclosure = _lang_disclosure(language)
    greeting = (config.get("greeting") or "").strip()
    if not greeting:
        prompt_greeting = ((org.system_prompts or {}).get("greeting") if org else None) or ""
        if prompt_greeting.strip():
            greeting = prompt_greeting.strip()
        elif org and org.name:
            greeting = f"Hello, thank you for calling {org.name}. How can I help you today?"
        else:
            greeting = "Hello, thank you for calling. How can I help you today?"
    return f"{disclosure} {greeting}"


# ---------------------------------------------------------------------------
# Call lifecycle webhook — POST, HMAC-verified (root CLAUDE.md rule #3).
# Separate from the LLM WebSocket below: Retell's Custom LLM WebSocket
# protocol has no per-message signature scheme of its own (see
# app/security/webhook_verify.py), so call_started/call_ended are the one
# place a real HMAC check applies for this channel. The WebSocket instead
# trusts the org_id embedded in its own connection URL (see the route below)
# plus an agent_id cross-check against the org's configured Retell agent.
# ---------------------------------------------------------------------------


async def _get_active_retell_key(org_id: uuid.UUID) -> str | None:
    async with async_session_maker() as db:
        row = (
            await db.execute(
                select(OrgApiKey).where(
                    OrgApiKey.org_id == org_id,
                    OrgApiKey.provider == ApiKeyProvider.retell,
                    OrgApiKey.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
    if row is not None:
        return decrypt_api_key(str(org_id), row.encrypted_key)
    # All agents run under a single Retell account — all webhooks are signed
    # with the same platform key, so the org doesn't need its own key stored.
    return settings.RETELL_API_KEY


@webhook_router.post("/retell")
async def receive_retell_webhook(request: Request) -> Response:
    body = await request.body()
    signature = request.headers.get("x-retell-signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    call = payload.get("call") or {}
    event = payload.get("event")
    agent_id = call.get("agent_id")
    call_id = call.get("call_id")
    if not agent_id or not call_id:
        # Nothing we can act on (and nothing to route by) — still 200 so
        # Retell doesn't retry a payload shape we'll never be able to handle.
        return Response(status_code=status.HTTP_200_OK)

    async with async_session_maker() as db:
        org_id = await get_org_id_for_retell_agent(db, agent_id)
        if org_id is None:
            # Unrecognized agent_id isn't a signature failure — same as
            # WhatsApp's unknown phone_number_id, ack without acting so
            # Retell doesn't burn retries on a routing key we'll never claim.
            logger.warning("retell_webhook_unknown_agent", agent_id=agent_id)
            return Response(status_code=status.HTTP_200_OK)

        api_key = await _get_active_retell_key(org_id)
        if (
            not signature
            or not api_key
            or not verify_retell_signature(body, signature, api_key)
        ):
            logger.warning("retell_webhook_invalid_signature", org_id=str(org_id))
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

        if event == "call_started":
            from_number = call.get("from_number") or "unknown"
            await on_call_start(db, org_id, call_id, from_number)
        elif event == "call_ended":
            duration_ms = call.get("duration_ms")
            duration_seconds = int(duration_ms / 1000) if isinstance(duration_ms, (int, float)) else None
            await on_call_end(db, call_id, duration_seconds)
        # call_analyzed and anything else: signature already verified above,
        # just nothing further to do with it yet.

    return Response(status_code=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Contact-name extraction helpers
# ---------------------------------------------------------------------------


def _extract_name_from_transcript(transcript: list[dict], ai_response: str) -> str | None:
    """Try to find the caller's real name from the transcript or the AI's response.

    Three strategies, in order of reliability:
    1. User self-introduction in any turn ("my name is John", "I'm John", …)
    2. AI addresses the caller by name in the current response ("You're welcome, John")
    3. Previous AI turn asked for the caller's name AND the user's reply is 1-3 words
    Returns a title-cased name string, or None if nothing was found.
    """
    # Strategy 1 — user self-introduction phrases
    for turn in reversed(transcript):
        if turn.get("role") != "user":
            continue
        m = _USER_NAME_RE.search(turn.get("content") or "")
        if m:
            candidate = m.group(1).strip().title()
            if candidate.lower() not in _NAME_STOPWORDS:
                return candidate

    # Strategy 2 — AI addresses caller by name in the current response
    m = _AI_ADDRESS_RE.search(ai_response)
    if m:
        return m.group(1).strip()

    # Strategy 3 — previous AI turn asked "what's your name?" and the
    # immediately following user turn is a short reply (likely just the name).
    for i, turn in enumerate(transcript):
        if turn.get("role") not in ("agent", "assistant"):
            continue
        if not _AI_ASKS_NAME_RE.search(turn.get("content") or ""):
            continue
        # Look for the next user turn after this agent turn
        for j in range(i + 1, len(transcript)):
            next_turn = transcript[j]
            if next_turn.get("role") != "user":
                continue
            words = (next_turn.get("content") or "").strip().split()
            if 1 <= len(words) <= 3:
                candidate = " ".join(w.title() for w in words)
                if candidate.lower() not in _NAME_STOPWORDS:
                    return candidate
            break  # only check the immediately following user turn

    return None


async def _maybe_update_contact_name(
    state: _CallState,
    conversation_id: uuid.UUID,
    transcript: list[dict],
    ai_response: str,
) -> None:
    """Best-effort: if the contact is still recorded as 'unknown' or as their
    raw phone number, extract a real name from the transcript and persist it.

    Also updates the in-memory state cache so the system prompt on the next
    turn of this same call shows the correct name immediately.
    """
    # Skip if we already have a real name (not phone number, not "unknown").
    current = state.contact_name
    phone = state.from_number
    if current and current != "unknown" and current != phone:
        return

    name = _extract_name_from_transcript(transcript, ai_response)
    if not name:
        return

    try:
        async with async_session_maker() as db:
            conv = await db.get(Conversation, conversation_id)
            if conv and conv.contact_id:
                contact = await db.get(Contact, conv.contact_id)
                if contact and (
                    contact.name in (None, "unknown")
                    or contact.name == (phone or "")
                ):
                    contact.name = name
                    await db.commit()
                    # Update the state cache so subsequent turns on this call
                    # see the correct name without a DB re-fetch.
                    state.contact_name = name
                    logger.info(
                        "voice_contact_name_updated",
                        conversation_id=str(conversation_id),
                        name=name,
                    )
    except Exception:  # noqa: BLE001 — name update is best-effort, never fail a turn
        logger.warning("voice_contact_name_update_failed", conversation_id=str(conversation_id))


# ---------------------------------------------------------------------------
# Custom LLM WebSocket — the live per-call conversation loop.
# ---------------------------------------------------------------------------


async def _present_language_menu(sender: _Sender, state: _CallState, response_id: int | None) -> None:
    """Speak the on-demand language menu: a short lead-in in the caller's current
    language, then one option line per supported language (each in its own
    language). Flips the call into `language_phase` so the caller's next turn is
    parsed as a menu choice, and arms the silence safety-net timer.

    Unlike the old call-open menu, this is reached only when a caller explicitly
    asks to switch language, so no disclosure is (re)spoken — that already went
    out with the opening greeting."""
    prompt = _menu_prompt(state.selected_language)
    menu = _build_language_menu(state.org_supported_languages)
    state.language_phase = True
    await sender.send_shortcut(response_id, f"{prompt} {menu}")
    # Arm the silence safety-net. Held on state so it isn't GC'd and can be
    # cancelled the moment a selection arrives.
    state.language_timeout_task = asyncio.create_task(
        _run_language_menu_timeout(sender, state)
    )


async def _run_language_menu_timeout(
    sender: _Sender,
    state: _CallState,
    delay: float = 5.5,
) -> None:
    """Safety-net: if the caller goes silent on the on-demand language menu for
    `delay` seconds, quietly abandon the switch and resume in the CURRENT
    language rather than looping the menu.

    Fires when the caller doesn't respond at all (confusion, background noise
    that stops Retell triggering reminder_required in time). The
    `reminder_required` path in the WebSocket loop handles the common case where
    Retell detects silence and notifies us; this task is the backup.
    """
    try:
        await asyncio.sleep(delay)
    except asyncio.CancelledError:
        return  # Caller selected before the timer fired — nothing to do.

    if not state.language_phase:
        return  # Already resolved by response_required or reminder_required.

    state.language_phase = False
    # No response_required is in flight — send as a spontaneous agent utterance.
    await sender.send_shortcut(None, _resume_line(state.selected_language))


async def _handle_language_selection(
    sender: _Sender,
    org_id: uuid.UUID,
    call_id: str,
    response_id: int | None,
    transcript: list[dict],
    state: _CallState,
) -> None:
    """Resolve the caller's language choice — for both the call-OPEN prompt (the
    intro asks "which language?") and the on-demand switch menu.

    A short reply naming a language ("Dutch", "in English", "two") is treated as
    the pick: switch `selected_language`, clear the phase, and speak a short
    confirmation in the chosen language.

    If the reply ISN'T a clean pick, behaviour depends on which prompt this is:
      - Call-open prompt (`initial_language_prompt`): the caller skipped the
        choice and just asked something — ANSWER it (route to a normal turn; the
        LLM mirrors their language), so no one is trapped in a menu.
      - On-demand menu, or silence: keep the current language and speak a brief
        resume line rather than looping the menu.
    """
    if not state.language_phase:
        return  # Concurrent timeout task already resolved this.

    initial = state.initial_language_prompt
    user_turns = [t for t in transcript if t.get("role") == "user"]
    user_input = (user_turns[-1].get("content") or "").strip() if user_turns else ""

    chosen = _detect_language_choice(user_input, state.org_supported_languages)
    # A short reply IS the pick; a longer utterance that merely mentions a
    # language ("do you have someone who speaks French about my crown?") is a
    # real question, not a menu selection.
    is_pick = chosen is not None and len(user_input.split()) <= 4

    # Cancel the safety-net timer + leave the language phase — resolved now.
    if state.language_timeout_task and not state.language_timeout_task.done():
        state.language_timeout_task.cancel()
    state.language_phase = False
    state.initial_language_prompt = False

    if is_pick:
        state.selected_language = chosen
        resume = _resume_line(chosen)
        await sender.send_shortcut(response_id, resume)
        logger.info(
            "language_switched",
            org_id=str(org_id),
            channel="voice",
            call_id=call_id,
            language=chosen,
        )
        # Persist the confirmation as an AI message so the switch shows in history.
        conversation_id = await _ensure_conversation(state, org_id, call_id, state.from_number or "unknown")
        async with async_session_maker() as db:
            await add_message(db, conversation_id, MessageRole.ai, resume, Channel.voice)
        return

    if initial and user_input:
        # Call-open prompt: caller ignored the choice and asked a real question.
        # Don't drop it — note any detected language, then answer normally.
        if chosen is not None:
            state.selected_language = chosen
        logger.info("language_prompt_skipped_answering", org_id=str(org_id), call_id=call_id)
        await _handle_turn(sender, org_id, call_id, response_id, transcript, state)
        return

    # On-demand menu miss, or silence: keep the current language, brief resume.
    reason = "timeout" if not user_input else "invalid_input"
    logger.info(
        "language_menu_unresolved",
        org_id=str(org_id),
        call_id=call_id,
        reason=reason,
        language=state.selected_language,
    )
    await sender.send_shortcut(response_id, _resume_line(state.selected_language))


async def _run_language_selection(
    sender: _Sender,
    org_id: uuid.UUID,
    call_id: str,
    response_id: int | None,
    transcript: list[dict],
    state: _CallState,
) -> None:
    """Thin wrapper around _handle_language_selection — mirrors _run_turn's
    pattern so CancelledError propagates and other exceptions are logged rather
    than silently swallowed by the fire-and-forget task mechanism."""
    try:
        await _handle_language_selection(
            sender, org_id, call_id, response_id, transcript, state
        )
    except asyncio.CancelledError:
        logger.info("voice_ws_lang_select_cancelled", org_id=str(org_id), call_id=call_id)
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "voice_ws_lang_select_error", org_id=str(org_id), call_id=call_id, error=str(exc)
        )


async def _run_call_details(
    org_id: uuid.UUID, call_id: str, from_number: str, greeting: str, state: _CallState
) -> None:
    """Background: register the call + persist the already-spoken greeting.
    Runs off the receive loop because on_call_start hits the (possibly slow,
    remote) DB, and the loop must stay free to echo ping_pong."""
    conversation_id = await _ensure_conversation(state, org_id, call_id, from_number)
    if greeting and not state.greeting_saved:
        async with state.conversation_lock:
            if not state.greeting_saved:
                async with async_session_maker() as db:
                    # Guard on message count so an auto-reconnect (which re-runs
                    # call_details) doesn't double-record the greeting.
                    existing = await get_conversation_messages(db, conversation_id)
                    if not existing:
                        await add_message(db, conversation_id, MessageRole.ai, greeting, Channel.voice)
                state.greeting_saved = True


async def _run_reminder(
    sender: _Sender, org_id: uuid.UUID, call_id: str, response_id: int | None, state: _CallState
) -> None:
    """Background: speak the silence-nudge, then persist it. Sending first keeps
    the caller engaged before the (slower) DB write."""
    await sender.send_shortcut(response_id, VOICE_REMINDER_TEXT)
    if state.conversation_id is not None:
        async with async_session_maker() as db:
            await add_message(db, state.conversation_id, MessageRole.ai, VOICE_REMINDER_TEXT, Channel.voice)


async def _run_turn(
    sender: _Sender,
    org_id: uuid.UUID,
    call_id: str,
    response_id: int | None,
    transcript: list[dict],
    state: _CallState,
) -> None:
    """Background wrapper around _handle_turn: lets CancelledError propagate (an
    interruption cancels the task) but logs any other exception, since a
    fire-and-forget task's exception would otherwise vanish silently."""
    try:
        await _handle_turn(sender, org_id, call_id, response_id, transcript, state)
    except asyncio.CancelledError:
        logger.info("voice_ws_turn_cancelled", org_id=str(org_id), call_id=call_id, response_id=response_id)
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "voice_ws_turn_error", org_id=str(org_id), call_id=call_id, response_id=response_id, error=str(exc)
        )


async def _handle_turn(
    sender: _Sender,
    org_id: uuid.UUID,
    call_id: str,
    response_id: int | None,
    transcript: list[dict],
    state: _CallState,
) -> None:
    """Handles one `response_required` turn: RAG (top-3) + a single streamed
    fast-tier LLM call, grounded by whatever knowledge was found. Deliberately
    skips the analyze_message safety+intent classification call that
    webchat/WhatsApp use — that's a full extra sequential LLM round-trip,
    incompatible with this channel's sub-500ms budget. The system prompt's
    existing "if you don't know, say so and offer to connect them with staff"
    guideline (app/ai/prompts/receptionist_system.py) is what handles
    low-confidence answers here instead of a programmatic RAG-empty escalation
    check — an empty RAG result also legitimately covers plain greetings/
    small talk, which a hard escalate-on-empty rule would wrongly flag.

    Runs as a background task (see _run_turn) so the WebSocket receive loop
    stays free to echo Retell's ping_pong while this does its slow DB + LLM
    work. If the caller speaks again mid-turn, this task is cancelled.
    """
    start = time.monotonic()

    user_turns = [t for t in transcript if t.get("role") == "user"]
    if not user_turns:
        return
    message_text = (user_turns[-1].get("content") or "").strip()
    if not message_text:
        return

    # ── End-call fast paths ───────────────────────────────────────────────────
    # Both checks use only data already in memory (the transcript Retell sent
    # us), so they cost nothing extra on the critical path — no DB, no LLM.

    # Path A: Caller explicitly asked to hang up ("end the call", "hang up"…).
    # Skip the LLM entirely — reply immediately with a brief goodbye and signal
    # Retell to disconnect.
    if _is_explicit_hangup(message_text):
        goodbye = "Of course. Goodbye, and have a great day!"
        await sender.send_end_call_shortcut(response_id, goodbye)
        logger.info(
            "call_ended_by_agent",
            org_id=str(org_id),
            call_id=call_id,
            reason="explicit_request",
        )
        conversation_id = await _ensure_conversation(state, org_id, call_id, state.from_number or "unknown")
        async with async_session_maker() as db:
            await add_message(db, conversation_id, MessageRole.customer, message_text, Channel.voice)
            await add_message(db, conversation_id, MessageRole.ai, goodbye, Channel.voice)
        return

    # Path B: "Double goodbye" — the AI already said goodbye in the previous
    # turn, and the caller replied with a short acknowledgment ("okay", "bye",
    # "thanks"…) rather than a new question.  End the call immediately instead
    # of generating a second unprompted goodbye and waiting for more input.
    if _is_post_goodbye_ack(message_text, transcript):
        await sender.send_end_call_shortcut(response_id, "Goodbye!")
        logger.info(
            "call_ended_by_agent",
            org_id=str(org_id),
            call_id=call_id,
            reason="natural_conclusion",
        )
        conversation_id = await _ensure_conversation(state, org_id, call_id, state.from_number or "unknown")
        async with async_session_maker() as db:
            await add_message(db, conversation_id, MessageRole.customer, message_text, Channel.voice)
            await add_message(db, conversation_id, MessageRole.ai, "Goodbye!", Channel.voice)
        return

    conversation_id = await _ensure_conversation(state, org_id, call_id, state.from_number or "unknown")

    # Rate limit + rate-limited fallback path run on their own short-lived
    # session — they're pure Redis + a tiny DB write, no reason to hold a
    # connection across the whole turn.
    ratelimit_start = time.monotonic()
    if not await check_message_rate_limit(str(org_id)):
        logger.warning("org_message_rate_limit_exceeded", org_id=str(org_id), channel="voice")
        await sender.send_shortcut(response_id, STATIC_RATE_LIMIT_MESSAGE)
        async with async_session_maker() as db:
            await add_message(db, conversation_id, MessageRole.customer, message_text, Channel.voice)
            await add_message(db, conversation_id, MessageRole.ai, STATIC_RATE_LIMIT_MESSAGE, Channel.voice)
        return
    await increment_message_count(str(org_id))
    logger.info(
        "voice_ratelimit_ms",
        org_id=str(org_id),
        call_id=call_id,
        latency_ms=round((time.monotonic() - ratelimit_start) * 1000),
    )

    # ── Escalation fast path ──────────────────────────────────────────────────
    # Explicit "get me a human" → record an escalation + notify staff, then speak
    # a canned acknowledgement. Deterministic (regex, no LLM call), so it fits the
    # voice latency budget. Checked before booking so a caller mid-booking who
    # asks for a person still escalates. Voice can't do a live transfer, so this
    # flags it for human follow-up and the AI stays on the line meanwhile.
    if _is_escalation_trigger(message_text):
        await clear_booking_session(conversation_id)
        async with async_session_maker() as db:
            await create_escalation(db, org_id, conversation_id, reason=message_text)
            await add_message(db, conversation_id, MessageRole.customer, message_text, Channel.voice)
            await add_message(
                db, conversation_id, MessageRole.ai, VOICE_ESCALATION_REPLY, Channel.voice
            )
        await sender.send_shortcut(response_id, VOICE_ESCALATION_REPLY)
        logger.info("voice_escalation_created", org_id=str(org_id), call_id=call_id)
        return

    # ── Language-switch fast path ─────────────────────────────────────────────
    # Multi-language orgs: the opening greeting invited the caller to switch
    # language anytime. When they ask, present the on-demand menu (deterministic
    # regex, no LLM) and flip into language_phase so their next turn is parsed as
    # a choice. Checked before booking so "can you speak French?" mid-booking is
    # honored — the booking session isn't cleared, so it resumes after the switch.
    if len(state.org_supported_languages) > 1 and _is_language_switch_request(message_text):
        await _present_language_menu(sender, state, response_id)
        async with async_session_maker() as db:
            await add_message(db, conversation_id, MessageRole.customer, message_text, Channel.voice)
        logger.info("voice_language_menu_shown", org_id=str(org_id), call_id=call_id)
        return

    # ── Booking fast path ─────────────────────────────────────────────────────
    # Structured appointment booking runs through the same FSM as chat/WhatsApp.
    # Once a booking is mid-flow we stay in it (sticky); otherwise a lightweight
    # keyword trigger starts one. Either way we skip RAG/LLM generation and speak
    # the FSM's next prompt as a single complete utterance. The FSM's own
    # extraction handles free-text service/date/time; on voice the collected
    # email is used for the appointment reminder emails.
    booking_active = await booking_session_active(conversation_id)
    if booking_active or _is_booking_trigger(message_text):
        async with async_session_maker() as db:
            conv = await db.get(Conversation, conversation_id)
            contact_id = conv.contact_id if conv else None
            reply = (
                await process_booking_intent(
                    db, org_id, conversation_id, contact_id, message_text, channel="voice"
                )
                if contact_id is not None
                else FALLBACK_MESSAGE
            )
        await sender.send_shortcut(response_id, reply)
        full_text = reply
        async with async_session_maker() as db:
            await add_message(db, conversation_id, MessageRole.customer, message_text, Channel.voice)
            await add_message(db, conversation_id, MessageRole.ai, full_text, Channel.voice)
        logger.info(
            "voice_booking_turn",
            org_id=str(org_id),
            call_id=call_id,
            response_id=response_id,
            booking_active=booking_active,
        )
        return

    # Independent work, in parallel:
    #   - fetch prior history            (own session — Postgres read)
    #   - embed + hybrid_search          (own session — CPU + Postgres read)
    #   - resolve contact_name once      (own session — no-op after first turn)
    # The LLM client is already primed by _prime_llm_client at accept, so we
    # just await its future — instant on turns after the priming completes.
    #
    # `persist_customer` is fired here but DELIBERATELY not in the gather:
    # history is built manually (prior_history + current user turn) so the
    # LLM call doesn't need the write to have committed. Blocking the gather
    # on a ~2s Postgres write was the tall pole in TEST 2. The task is
    # awaited later, right before we log turn_complete, so the message is
    # guaranteed persisted before the next turn — and if the process exits
    # mid-turn, an exception here still surfaces via the awaited final wait.
    llm_client_future = state.llm_client_future
    history_task = asyncio.create_task(_fetch_prior_history(conversation_id, call_id))
    rag_task = asyncio.create_task(_run_rag(org_id, call_id, message_text))
    persist_customer_task = asyncio.create_task(_persist_customer_message(conversation_id, message_text, call_id))
    contact_task = asyncio.create_task(_ensure_contact_name(state, conversation_id))
    # The LLM-client future is set once at accept; if priming errored, awaiting
    # this future will raise the original exception here.
    client_task = asyncio.ensure_future(llm_client_future) if llm_client_future is not None else None

    tasks_to_gather = [history_task, rag_task, contact_task]
    if client_task is not None:
        tasks_to_gather.append(client_task)
    results = await asyncio.gather(*tasks_to_gather, return_exceptions=True)

    # Unpack + surface errors in the right order (LLM-client + RAG matter most;
    # a failed history/persist is degraded but not fatal).
    prior_history = results[0] if not isinstance(results[0], BaseException) else []
    if isinstance(results[1], BaseException):
        logger.exception("voice_rag_failed", org_id=str(org_id), call_id=call_id, error=str(results[1]))
        chunks = []
    else:
        chunks = results[1]
    contact_name = results[2] if not isinstance(results[2], BaseException) else None

    if client_task is not None:
        client_result = results[3]
        if isinstance(client_result, NoLLMProviderConfiguredError):
            logger.warning("no_llm_provider_configured", org_id=str(org_id), error=str(client_result))
            await sender.send_shortcut(response_id, FALLBACK_MESSAGE)
            async with async_session_maker() as db:
                await add_message(db, conversation_id, MessageRole.ai, FALLBACK_MESSAGE, Channel.voice)
            return
        if isinstance(client_result, BaseException):
            logger.exception("voice_llm_client_failed", org_id=str(org_id), call_id=call_id, error=str(client_result))
            await sender.send_shortcut(response_id, FALLBACK_MESSAGE)
            async with async_session_maker() as db:
                await add_message(db, conversation_id, MessageRole.ai, FALLBACK_MESSAGE, Channel.voice)
            return
        # client_result is now a LIST[OrgLLMClient] (primary + fallbacks).
        clients = client_result
    else:
        # Priming was never scheduled (shouldn't happen post-accept), do it
        # synchronously as a fallback so the turn still works.
        client_start = time.monotonic()
        try:
            async with async_session_maker() as db:
                clients = await get_org_llm_clients(db, org_id, model_tier="fast")
        except NoLLMProviderConfiguredError as exc:
            logger.warning("no_llm_provider_configured", org_id=str(org_id), error=str(exc))
            await sender.send_shortcut(response_id, FALLBACK_MESSAGE)
            async with async_session_maker() as db:
                await add_message(db, conversation_id, MessageRole.ai, FALLBACK_MESSAGE, Channel.voice)
            return
        logger.info(
            "voice_llm_client_ms",
            org_id=str(org_id),
            call_id=call_id,
            latency_ms=round((time.monotonic() - client_start) * 1000),
            source="fallback_sync",
            providers=[c.provider.value for c in clients],
        )

    # Build history for the LLM: prior turns + the current user message. We
    # append manually so we don't have to wait for the customer-persist round-
    # trip to commit before reading history back.
    history = (prior_history + [{"role": "user", "content": message_text}])[-8:]

    knowledge_context = "\n\n".join(f"- {chunk.content}" for chunk in chunks)
    system_prompt = get_system_prompt(
        {
            "org_name": state.org_name,
            "greeting": state.org_prompts.get("greeting"),
            "personality": state.org_prompts.get("personality"),
            "escalation_rules": state.org_prompts.get("escalation_rules"),
            "custom_system_prompt": state.org_prompts.get("system_prompt"),
            "knowledge_context": knowledge_context,
            "customer_name": contact_name,
        },
        voice_mode=True,
    )
    # For multi-language orgs, append the language-MIRRORING instruction LAST so
    # it overrides the rest of the prompt. The assistant follows whatever
    # language the caller actually speaks (among the org's supported set) rather
    # than being locked to one — so a Dutch caller is answered in Dutch, an
    # English caller in English, with no menu. Single-language orgs skip this
    # (there's only one language to speak, so no instruction is needed).
    if len(state.org_supported_languages) > 1:
        system_prompt = f"{system_prompt}\n\n{_mirror_language_instruction(state.org_supported_languages)}"

    collected: list[str] = []
    first_token_at: float | None = None
    first_frame_sent_at: float | None = None
    try:
        async for token in stream_llm_with_fallback(clients, history, system_prompt):
            if first_token_at is None:
                first_token_at = time.monotonic()
                logger.info(
                    "voice_first_token_latency_ms",
                    org_id=str(org_id),
                    call_id=call_id,
                    latency_ms=round((first_token_at - start) * 1000),
                )
            collected.append(token)
            await sender.send_chunk(response_id, token, content_complete=False)
            if first_frame_sent_at is None:
                first_frame_sent_at = time.monotonic()
                # Measures LLM-first-token → frame-actually-on-the-wire, i.e.
                # the sender lock + JSON serialization + Starlette send_json.
                logger.info(
                    "voice_first_frame_sent_ms",
                    org_id=str(org_id),
                    call_id=call_id,
                    latency_ms=round((first_frame_sent_at - first_token_at) * 1000),
                )
    except LLMProviderError as exc:
        logger.warning("voice_stream_failed", org_id=str(org_id), call_id=call_id, error=str(exc))
        if not collected:
            collected.append(FALLBACK_MESSAGE)
            await sender.send_chunk(response_id, FALLBACK_MESSAGE, content_complete=False)

    # ── End-call marker check (LLM-driven natural conclusion) ────────────────
    # The system prompt instructs the LLM to append [END_CALL] when it decides
    # the conversation is naturally complete (e.g. booking confirmed + goodbye
    # exchanged).  We detect the marker after full collection, strip it from the
    # persisted text, and include `end_call: true` in the close frame.
    #
    # The marker may have been streamed to Retell's TTS buffer already, but
    # `end_call: true` on the close frame terminates the call before the audio
    # is synthesised — so the caller never hears "[END CALL]".
    full_text = "".join(collected)
    natural_end = full_text.rstrip().endswith(_END_CALL_MARKER)
    if natural_end:
        full_text = full_text.rstrip()[: -len(_END_CALL_MARKER)].rstrip()

    if natural_end:
        await sender.send(
            {
                "response_type": "response",
                "response_id": response_id,
                "content": "",
                "content_complete": True,
                "end_call": True,
            }
        )
        logger.info(
            "call_ended_by_agent",
            org_id=str(org_id),
            call_id=call_id,
            reason="natural_conclusion",
        )
    else:
        await sender.send_chunk(response_id, "", content_complete=True)

    logger.info(
        "voice_ws_send_response",
        org_id=str(org_id),
        call_id=call_id,
        response_id=response_id,
        content=_truncate_json(full_text),
    )

    persist_ai_start = time.monotonic()
    async with async_session_maker() as db:
        await add_message(db, conversation_id, MessageRole.ai, full_text, Channel.voice)
    logger.info(
        "voice_persist_ai_db_ms",
        call_id=call_id,
        latency_ms=round((time.monotonic() - persist_ai_start) * 1000),
    )

    # Flush the fire-and-forget customer-message write before the turn ends.
    # By this point the write has been running concurrently through RAG, LLM,
    # and AI-persist, so it's almost always already done and this awaits a
    # resolved task in microseconds. But awaiting here guarantees the message
    # is durable before the next response_required can be processed — and if
    # it failed, we surface the error rather than silently losing the write.
    persist_customer_wait_start = time.monotonic()
    try:
        await persist_customer_task
    except Exception as exc:  # noqa: BLE001 — degrade, don't kill the call
        logger.warning("voice_persist_customer_failed", org_id=str(org_id), call_id=call_id, error=str(exc))
    logger.info(
        "voice_persist_customer_wait_ms",
        call_id=call_id,
        latency_ms=round((time.monotonic() - persist_customer_wait_start) * 1000),
    )

    # Best-effort: if the contact is still named "unknown" or their phone number,
    # try to extract a real name from the transcript. Runs as a fire-and-forget
    # task so it never adds latency to the turn.
    asyncio.create_task(
        _maybe_update_contact_name(state, conversation_id, transcript, full_text)
    )

    logger.info(
        "voice_turn_complete",
        org_id=str(org_id),
        call_id=call_id,
        total_latency_ms=round((time.monotonic() - start) * 1000),
    )


@ws_router.websocket("/llm/{org_id}/{call_id}")
async def voice_llm_websocket(websocket: WebSocket, org_id: uuid.UUID, call_id: str) -> None:
    await websocket.accept()
    logger.info("voice_ws_connected", org_id=str(org_id), call_id=call_id)

    async with async_session_maker() as db:
        config = await get_voice_config(db, org_id)
        org = await db.get(Organization, org_id) if config is not None else None
    if config is None:
        logger.warning("voice_ws_not_configured", org_id=str(org_id), call_id=call_id)
        await websocket.close(code=WS_CLOSE_VOICE_NOT_CONFIGURED)
        return

    sender = _Sender(websocket, org_id, call_id)
    state = _CallState()

    # Populate per-call cache from data already loaded above — the turn handler
    # would otherwise re-query these on every response_required.
    state.org_name = org.name if org else None
    state.org_prompts = (org.system_prompts if org else None) or {}

    # Language configuration — default to ["en"] if the column is missing/empty
    # (guards against orgs created before the migration ran).
    supported_languages: list[str] = (
        (org.supported_languages if org else None) or ["en"]
    )
    state.org_supported_languages = supported_languages
    state.selected_language = supported_languages[0]  # default; updated after selection

    # 1. Config frame — MUST be the first thing sent, or Retell won't start
    # streaming transcripts. response_id here just mirrors the reference impl.
    await sender.send(
        {
            "response_type": "config",
            "config": {"auto_reconnect": True, "call_details": True, "transcript_with_tool_calls": False},
            "response_id": 1,
        }
    )

    # 2. Opening utterance — what the agent says first (response_id 0).
    #
    #    Intro-first flow: EVERY caller hears the AI-disclosure + greeting
    #    immediately. Single-language orgs get the greeting in that one language.
    #    Multi-language orgs get a MULTILINGUAL intro — disclosure + greeting
    #    spoken in each supported language (capped) — ending with a spoken prompt
    #    asking which language the caller would like (listing them by name), which
    #    also invites them to just ask their question. The caller's next turn is
    #    parsed as a language choice (see _handle_language_selection); a caller
    #    who ignores it and asks something is answered, and from there the LLM
    #    mirrors their language (see _mirror_language_instruction).
    if len(supported_languages) > 1:
        opening = _draft_multilingual_begin_message(org, supported_languages)
        # The caller's first turn answers "which language?" — route it through the
        # selection handler. initial_language_prompt=True so a caller who skips the
        # choice and just asks a question gets ANSWERED, not sent a resume line.
        state.language_phase = True
        state.initial_language_prompt = True
    else:
        opening = _draft_begin_message(config, org, language=supported_languages[0])
    greeting = opening

    await sender.send(
        {"response_type": "response", "response_id": 0, "content": opening, "content_complete": True}
    )

    logger.info(
        "ai_disclosure_sent",
        org_id=str(org_id),
        channel="voice",
        call_id=call_id,
        language=supported_languages[0],
    )

    # All slow work (DB / RAG / LLM) runs in background tasks so this loop never
    # blocks — Retell drops the call if ping_pong echoes stall for a few seconds.
    active_turn: asyncio.Task | None = None
    active_response_id: int | None = None
    background_tasks: set[asyncio.Task] = set()

    def spawn(coro) -> asyncio.Task:
        task = asyncio.create_task(coro)
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)
        return task

    # Prime the LLM client in the background right after greeting is on the
    # wire. On typical calls the caller takes at least a second or two to start
    # speaking, so by the time the first response_required arrives the future
    # is usually already resolved — the turn just awaits it (instant).
    state.llm_client_future = asyncio.get_running_loop().create_future()
    spawn(_prime_llm_client(state, org_id, call_id))

    # NB: the language-selection menu is no longer presented at call open — it
    # appears on demand when a caller asks to switch language (see _handle_turn).
    # The safety-net silence timer for it is therefore spawned at that point, not
    # here.

    try:
        while True:
            try:
                event = await websocket.receive_json()
            except (json.JSONDecodeError, ValueError):
                logger.warning("voice_ws_recv_bad_json", org_id=str(org_id), call_id=call_id)
                continue

            interaction_type = event.get("interaction_type")
            # NB: don't pass a kwarg named `event` to structlog — it's reserved
            # for the log message (the first positional arg) and collides.
            logger.info(
                "voice_ws_recv",
                org_id=str(org_id),
                call_id=call_id,
                interaction_type=interaction_type,
                raw=_truncate_json(event),
            )

            if interaction_type == "ping_pong":
                # Retell's liveness check — it pings ~every 2s and expects the
                # timestamp echoed back. This MUST stay on the receive loop (not
                # a task) and the loop must never block, or Retell tears the
                # connection down mid-call.
                await sender.send({"response_type": "ping_pong", "timestamp": event.get("timestamp")})
                continue

            if interaction_type == "call_details":
                call = event.get("call") or {}
                if call.get("agent_id") != config["retell_agent_id"]:
                    logger.warning(
                        "voice_ws_agent_mismatch",
                        org_id=str(org_id),
                        call_id=call_id,
                        agent_id=call.get("agent_id"),
                        expected=config["retell_agent_id"],
                    )
                    await websocket.close(code=WS_CLOSE_AGENT_MISMATCH)
                    return
                from_number = call.get("from_number") or "unknown"
                # Cache on state immediately so _handle_turn's _ensure_conversation
                # uses the real number even if _run_call_details hasn't committed yet.
                state.from_number = from_number
                logger.info("voice_ws_call_started", org_id=str(org_id), call_id=call_id, from_number=from_number)
                # DB work off the loop (on_call_start can be slow on a remote DB).
                spawn(_run_call_details(org_id, call_id, from_number, greeting, state))
                continue

            if interaction_type == "update_only":
                continue

            if interaction_type == "reminder_required":
                response_id = event.get("response_id")
                if state.language_phase:
                    # Caller was silent on the on-demand language menu — Retell's
                    # own silence detection fired before our asyncio timer. Route
                    # through _run_language_selection with an empty transcript so
                    # _handle_language_selection sees no input and resumes in the
                    # current language (logging reason="timeout").
                    spawn(
                        _run_language_selection(
                            sender, org_id, call_id, response_id, [], state
                        )
                    )
                else:
                    spawn(_run_reminder(sender, org_id, call_id, response_id, state))
                continue

            if interaction_type == "response_required":
                response_id = event.get("response_id")
                transcript = event.get("transcript") or []
                # Interruption: the caller spoke again while we were still
                # answering. Cancel the in-flight turn and close out its
                # response_id before starting the new one. Awaiting the cancelled
                # task only waits for cancellation to unwind (fast), not for the
                # LLM — so the loop stays responsive.
                if active_turn is not None and not active_turn.done():
                    active_turn.cancel()
                    try:
                        await active_turn
                        interrupted = False
                    except asyncio.CancelledError:
                        interrupted = True
                    if interrupted:
                        await sender.send_response_close(active_response_id)
                active_response_id = response_id
                if state.language_phase:
                    # On-demand language menu is open: parse the caller's choice,
                    # switch language + confirm, or resume the current language.
                    active_turn = spawn(
                        _run_language_selection(
                            sender, org_id, call_id, response_id, transcript, state
                        )
                    )
                else:
                    active_turn = spawn(_run_turn(sender, org_id, call_id, response_id, transcript, state))
                continue

            logger.info(
                "voice_ws_unhandled_interaction",
                org_id=str(org_id),
                call_id=call_id,
                interaction_type=interaction_type,
            )

    except WebSocketDisconnect:
        logger.info("voice_ws_disconnected", org_id=str(org_id), call_id=call_id)
    except Exception as exc:  # noqa: BLE001 — last-resort so one bad turn doesn't kill the call silently
        logger.exception("voice_ws_error", org_id=str(org_id), call_id=call_id, error=str(exc))
    finally:
        # Cancel any still-running turn/reminder/call_details tasks so they don't
        # dangle after the socket is gone. The on-demand language-menu timeout is
        # created outside `background_tasks` (from a turn handler), so cancel it
        # explicitly too — otherwise it could fire and send on a closed socket.
        if state.language_timeout_task and not state.language_timeout_task.done():
            state.language_timeout_task.cancel()
        for task in list(background_tasks):
            task.cancel()
        if background_tasks:
            await asyncio.gather(*background_tasks, return_exceptions=True)
