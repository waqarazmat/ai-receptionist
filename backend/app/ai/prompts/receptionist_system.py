from app.ai.prompts.health_adjacent_guardrail import HEALTH_ADJACENT_GUARDRAIL
from app.ai.prompts.legal_guardrail import LEGAL_GUARDRAIL
from app.ai.prompts.medical_guardrail import MEDICAL_GUARDRAIL

# Maps business_vertical value → guardrail text to inject.
# Verticals not listed here get no guardrail (general / real_estate / other).
_VERTICAL_GUARDRAILS: dict[str, str] = {
    "medical":    MEDICAL_GUARDRAIL,
    "dental":     MEDICAL_GUARDRAIL,
    "veterinary": MEDICAL_GUARDRAIL,
    "legal":      LEGAL_GUARDRAIL,
    "gym":        HEALTH_ADJACENT_GUARDRAIL,
    "salon":      HEALTH_ADJACENT_GUARDRAIL,
    "spa":        HEALTH_ADJACENT_GUARDRAIL,
}


def get_system_prompt(org_config: dict, voice_mode: bool = False) -> str:
    """Build the full system prompt from an org's saved config.

    org_config keys (all optional except org_name):
        org_name: str
        greeting: str | None
        personality: str | None
        escalation_rules: str | None
        custom_system_prompt: str | None — free-form org-authored block (from
            the setup wizard's Custom System Prompt field). Injected verbatim
            after the structured sections but BEFORE the knowledge context, so
            it can add brand-voice rules, industry guardrails, or overrides
            the generic guidelines. Empty/None = skipped.
        knowledge_context: str  — retrieved chunks, already formatted, "" if none
        customer_name: str | None

    voice_mode: the caller is a phone call (Retell), not text chat — the
    customer hears this response spoken aloud via TTS, with no screen to
    glance back at, so it adds guidelines against anything that only makes
    sense written down (lists, markdown, long sentences).
    """
    org_name = org_config.get("org_name") or "the business"
    personality = org_config.get("personality") or "friendly, professional, and helpful"
    greeting = org_config.get("greeting") or f"Hi! Welcome to {org_name}."
    escalation_rules = (
        org_config.get("escalation_rules")
        or "Escalate to a human whenever the customer explicitly asks for one, or seems upset."
    )
    custom_system_prompt = (org_config.get("custom_system_prompt") or "").strip()
    knowledge_context = org_config.get("knowledge_context") or ""
    customer_name = org_config.get("customer_name")

    lines = [
        f"You are the AI receptionist for {org_name}.",
        "",
        f"Personality and tone: {personality}",
        "",
    ]

    # The greeting is spoken as the response_id=0 opening frame before the LLM
    # is ever called on a voice call, so re-injecting it into the system prompt
    # is dead weight for that channel. Text channels (webchat/WhatsApp) still
    # need it — the LLM produces the first turn there.
    if not voice_mode:
        lines += [
            f"Your greeting style (use naturally, don't repeat verbatim every message): {greeting}",
            "",
        ]

    lines += [
        f"Escalation rules — when to hand off to a human: {escalation_rules}",
        "",
        "Guidelines:",
        # Merged from two previously-overlapping bullets: the "only answer
        # from the knowledge below" rule and the "never invent prices/hours/
        # policies" rule are the same guardrail phrased two ways — one bullet
        # covers both without weakening either.
        "- Only answer from the knowledge provided below — never invent prices, hours, or policies. "
        "If you don't know, say so honestly and offer to connect them with staff.",
        "- Keep responses concise and conversational — this is a chat, not an essay.",
    ]

    # Reply-language matching (text/WhatsApp only — the voice channel enforces a
    # specific language via its own menu instruction appended downstream, so we
    # don't add a conflicting rule here). Lets the knowledge base be in one
    # language while the customer is served in theirs: the multilingual embedding
    # model retrieves the right chunks across languages, and this makes the LLM
    # answer in the customer's language regardless of the knowledge's language.
    if not voice_mode:
        lines.append(
            "- Reply in the SAME language the customer is using (Dutch, French, English, etc.). "
            "The reference knowledge below may be written in a different language — use it anyway "
            "and answer in the customer's language."
        )

    if customer_name:
        lines.append(f"- The customer's name is {customer_name}. Use it naturally, not in every message.")

    if voice_mode:
        # Compressed from two bullets to one. Load-bearing content is
        # preserved: no lists/markdown/headings, 1-2 short sentences, and
        # numbers/times spelled the way a person would speak them.
        lines.append(
            "- This is a live phone call — no lists, markdown, bullet points, or headings; "
            "keep replies to one or two short sentences; speak numbers, times, and prices as "
            "a person would say them (e.g. \"nine AM\", not \"9:00 AM\")."
        )
        lines.append(
            "- Call termination: when the caller explicitly asks to hang up or end the call "
            "(\"hang up\", \"end the call\", \"that's all\", \"goodbye\" etc.), give ONE brief "
            "polite farewell (e.g. \"Goodbye, have a great day!\") and then append the exact "
            "text [END_CALL] on a new line — this signals the system to disconnect. "
            "Also append [END_CALL] after a natural conversation conclusion: when you have fully "
            "resolved the caller's inquiry (answered their question, confirmed a booking) and "
            "exchanged a farewell, add [END_CALL] at the end of your goodbye response. "
            "Do NOT generate a second goodbye or keep the conversation open after [END_CALL]."
        )

    # Per-vertical guardrail — injected BEFORE the org's custom_system_prompt
    # so org-authored text still wins on conflicts, but the safety restriction
    # is always present and cannot be omitted by leaving custom_system_prompt blank.
    vertical = org_config.get("business_vertical") or "general"
    guardrail = _VERTICAL_GUARDRAILS.get(str(vertical).lower())
    if guardrail:
        lines += ["", guardrail]

    if custom_system_prompt:
        # Injected verbatim so orgs can add brand-voice rules or overrides.
        # Placed AFTER the guardrail so it wins on tone/style but cannot
        # override the safety restriction above (the LLM sees the guardrail
        # earlier and the instruction not to diagnose is unambiguous).
        lines += ["", "Additional instructions from the business:", custom_system_prompt]

    if knowledge_context:
        lines += ["", "Relevant knowledge for this conversation:", knowledge_context]
    else:
        lines += [
            "",
            "No specific knowledge was found for this question — be honest that you're not sure "
            "and offer to connect them with staff.",
        ]

    return "\n".join(lines)
