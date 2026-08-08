import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm_router import (
    LLMProviderError,
    NoLLMProviderConfiguredError,
    OrgLLMClient,
    call_llm,
    get_org_llm_clients,
)
from app.ai.prompts.receptionist_system import get_system_prompt
from app.ai.rag_pipeline import ChunkResult
from app.models.organization import Organization

logger = structlog.get_logger()

FALLBACK_MESSAGE = (
    "We're experiencing a brief technical issue on our end — please call us directly and "
    "our team will be happy to help."
)
ESCALATION_MESSAGE = "I've let our team know you'd like to speak with someone — they'll be with you shortly."
DEFAULT_OFF_TOPIC_MESSAGE = "I'm sorry, I can only help with questions related to our business."

# Only these message roles feed back into the LLM as conversation turns.
_HISTORY_ROLE_MAP = {"customer": "user", "ai": "assistant"}

# Appended to the system prompt when the reply will be SPOKEN aloud (a WhatsApp
# voice-note answer). Keeps answers short and TTS-friendly so they're spoken back
# as audio instead of tripping the length cap and falling to text — and so the AI
# never dictates bullet points/asterisks, which sound wrong read aloud. Placed
# last so it takes precedence over the org's formatting habits.
_VOICE_STYLE_INSTRUCTION = (
    "\n\nIMPORTANT — your reply will be spoken aloud as a voice message. Keep it "
    "short and natural: at most 2-3 sentences of plain conversational speech. Do "
    "NOT use bullet points, numbered lists, asterisks, bold, or any markdown — "
    "they sound wrong when read aloud. If there is more to cover, give a brief "
    "spoken summary and offer to go into detail or send it in writing."
)


@dataclass
class GenerationPlan:
    """Either a ready-to-send shortcut (escalation/off-topic/no-provider-configured),
    or everything needed to actually call an LLM. Exactly one of `shortcut_text`
    or `clients` is set. Shared by generate_response (non-streaming) and the
    webchat handler (streaming) so the prompt-building logic isn't duplicated.

    `clients` is the ordered fallback list — primary at index 0. Both the
    streaming and non-streaming paths iterate through it if the primary
    errors before returning any text (see stream_llm_with_fallback)."""

    shortcut_text: str | None = None
    clients: list[OrgLLMClient] | None = None
    messages: list[dict] | None = None
    system_prompt: str | None = None


async def build_generation_plan(
    db: AsyncSession,
    org_id: uuid.UUID,
    intent: str,
    chunks: list[ChunkResult],
    conversation_history: list[dict],
    contact_name: str | None = None,
    reply_channel: str = "text",
) -> GenerationPlan:
    if intent == "escalation_request":
        return GenerationPlan(shortcut_text=ESCALATION_MESSAGE)

    org = await db.get(Organization, org_id)
    prompts = (org.system_prompts if org else None) or {}

    if intent == "off_topic":
        return GenerationPlan(shortcut_text=prompts.get("off_topic_response") or DEFAULT_OFF_TOPIC_MESSAGE)

    knowledge_context = "\n\n".join(f"- {chunk.content}" for chunk in chunks)
    system_prompt = get_system_prompt(
        {
            "org_name": org.name if org else None,
            "greeting": prompts.get("greeting"),
            "personality": prompts.get("personality"),
            "escalation_rules": prompts.get("escalation_rules"),
            "custom_system_prompt": prompts.get("system_prompt"),
            "knowledge_context": knowledge_context,
            "customer_name": contact_name,
        }
    )

    # Spoken reply (WhatsApp voice note): keep it short + TTS-friendly.
    if reply_channel == "voice":
        system_prompt += _VOICE_STYLE_INSTRUCTION

    history_messages = [
        {"role": _HISTORY_ROLE_MAP[m["role"]], "content": m["content"]}
        for m in conversation_history[-8:]
        if m.get("role") in _HISTORY_ROLE_MAP and m.get("content")
    ]
    if not history_messages:
        history_messages = [{"role": "user", "content": "Hello"}]

    try:
        clients = await get_org_llm_clients(db, org_id, model_tier="quality")
    except NoLLMProviderConfiguredError as exc:
        logger.warning("no_llm_provider_configured", org_id=str(org_id), error=str(exc))
        return GenerationPlan(shortcut_text=FALLBACK_MESSAGE)

    return GenerationPlan(clients=clients, messages=history_messages, system_prompt=system_prompt)


async def generate_response(
    db: AsyncSession,
    org_id: uuid.UUID,
    intent: str,
    chunks: list[ChunkResult],
    conversation_history: list[dict],
    contact_name: str | None = None,
    reply_channel: str = "text",
) -> str:
    plan = await build_generation_plan(
        db, org_id, intent, chunks, conversation_history, contact_name, reply_channel
    )
    if plan.shortcut_text is not None:
        return plan.shortcut_text

    # Non-streaming path — iterate the fallback list ourselves. call_llm
    # is a single-provider call, so we short-circuit on the first success.
    last_error: LLMProviderError | None = None
    for client in plan.clients or []:
        try:
            return await call_llm(client, messages=plan.messages, system_prompt=plan.system_prompt)
        except LLMProviderError as exc:
            last_error = exc
            logger.warning(
                "response_generation_fallback",
                org_id=str(org_id),
                provider=client.provider.value,
                error=str(exc),
            )
    logger.warning("response_generation_failed", org_id=str(org_id), intent=intent, error=str(last_error))
    return FALLBACK_MESSAGE
