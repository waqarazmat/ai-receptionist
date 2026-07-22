import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ApiKeyProvider
from app.models.org_api_keys import OrgApiKey
from app.security.encryption import decrypt_api_key

logger = structlog.get_logger()

ModelTier = Literal["fast", "quality"]

# The set of supported providers. Also the FAST-tier selection order — the
# first provider with an active key wins. Haiku is the cheapest classifier, so
# Anthropic stays first for fast. Other modules import this as the "is any LLM
# provider configured?" membership set, so it must list every provider.
PROVIDER_PRIORITY = [ApiKeyProvider.anthropic, ApiKeyProvider.openai, ApiKeyProvider.cohere]

# QUALITY-tier selection order — OpenAI first so customer-facing replies use
# gpt-4o-mini when an OpenAI key exists, falling back to Claude Sonnet, then
# Cohere. Deliberately different from the fast-tier order above.
QUALITY_PROVIDER_PRIORITY = [ApiKeyProvider.openai, ApiKeyProvider.anthropic, ApiKeyProvider.cohere]

FAST_MODELS: dict[ApiKeyProvider, str] = {
    # claude-3-5-haiku-20241022 was tried per explicit request but 404s
    # ("not_found_error") against the real test key — see project memory
    # project_real_llm_key for the account this was verified against.
    # claude-haiku-4-5-20251001 is confirmed working with the same key.
    ApiKeyProvider.anthropic: "claude-haiku-4-5-20251001",
    ApiKeyProvider.openai: "gpt-4o-mini",
    ApiKeyProvider.cohere: "command-r7b-12-2024",
}
QUALITY_MODELS: dict[ApiKeyProvider, str] = {
    # OpenAI is the PRIMARY quality model (gpt-4o-mini); Anthropic/Cohere are
    # fallbacks reached only when no OpenAI key is configured (see
    # QUALITY_PROVIDER_PRIORITY).
    ApiKeyProvider.openai: "gpt-4o-mini",
    ApiKeyProvider.anthropic: "claude-sonnet-5",
    ApiKeyProvider.cohere: "command-r-plus-08-2024",
}

MAX_RESPONSE_TOKENS = 1024


class LLMProviderError(Exception):
    """The configured provider's API call failed. Callers should degrade
    gracefully (root CLAUDE.md rule #8) rather than let this become a 500."""


class NoLLMProviderConfiguredError(Exception):
    """The org has no active API key for any supported LLM provider."""


@dataclass
class OrgLLMClient:
    provider: ApiKeyProvider
    model: str
    api_key: str
    # Persistent SDK instance for this (provider, api_key). Instantiated once
    # by _build_sdk in get_org_llm_client so its underlying httpx pool + TLS
    # session survives across every turn in the same call (the voice channel
    # caches OrgLLMClient on _CallState.llm_client_future). Without this, each
    # turn's `AsyncAnthropic(api_key=...)` inside _stream_anthropic opened a
    # fresh HTTP client + TLS handshake to api.anthropic.com (~50-150 ms).
    sdk: Any = field(default=None, repr=False)


def _build_sdk(provider: ApiKeyProvider, api_key: str) -> Any:
    """Construct the provider SDK once. Imports are lazy so unused providers
    don't cost anything at startup."""
    if provider == ApiKeyProvider.anthropic:
        from anthropic import AsyncAnthropic

        return AsyncAnthropic(api_key=api_key)
    if provider == ApiKeyProvider.openai:
        from openai import AsyncOpenAI

        return AsyncOpenAI(api_key=api_key)
    if provider == ApiKeyProvider.cohere:
        from cohere import AsyncClient

        return AsyncClient(api_key=api_key)
    raise ValueError(f"Unsupported provider: {provider}")


async def get_org_llm_clients(
    db: AsyncSession, org_id: uuid.UUID, model_tier: ModelTier = "fast"
) -> list[OrgLLMClient]:
    """Return EVERY configured provider for the org in priority order.

    Used by stream_llm_with_fallback below to keep the call alive when the
    primary provider errors before the first token. Callers that only need
    the primary can still use get_org_llm_client() which is a thin wrapper.
    """
    result = await db.execute(
        select(OrgApiKey).where(
            OrgApiKey.org_id == org_id,
            OrgApiKey.is_active.is_(True),
            OrgApiKey.provider.in_(PROVIDER_PRIORITY),
        )
    )
    keys_by_provider = {row.provider: row for row in result.scalars().all()}

    if model_tier == "quality":
        priority, models = QUALITY_PROVIDER_PRIORITY, QUALITY_MODELS
    else:
        priority, models = PROVIDER_PRIORITY, FAST_MODELS

    clients: list[OrgLLMClient] = []
    for provider in priority:
        key_row = keys_by_provider.get(provider)
        if key_row is None:
            continue
        api_key = decrypt_api_key(str(org_id), key_row.encrypted_key)
        sdk = _build_sdk(provider, api_key)
        clients.append(OrgLLMClient(provider=provider, model=models[provider], api_key=api_key, sdk=sdk))

    if not clients:
        raise NoLLMProviderConfiguredError(f"No LLM provider configured for org {org_id}")
    return clients


async def get_org_llm_client(db: AsyncSession, org_id: uuid.UUID, model_tier: ModelTier = "fast") -> OrgLLMClient:
    """Legacy single-client accessor — returns the first (primary) configured
    provider. Prefer get_org_llm_clients() + stream_llm_with_fallback() for
    new callsites so a primary outage doesn't kill the call."""
    return (await get_org_llm_clients(db, org_id, model_tier))[0]


def _sdk(client: OrgLLMClient) -> Any:
    """Lazy fallback in case an OrgLLMClient was ever built without pre-warming
    (older callsites, tests, direct construction). Production path always sets
    `client.sdk` in get_org_llm_client."""
    if client.sdk is None:
        client.sdk = _build_sdk(client.provider, client.api_key)
    return client.sdk


async def _call_anthropic(client: OrgLLMClient, messages: list[dict], system_prompt: str) -> str:
    response = await _sdk(client).messages.create(
        model=client.model,
        max_tokens=MAX_RESPONSE_TOKENS,
        system=system_prompt,
        messages=messages,
    )
    return "".join(block.text for block in response.content if block.type == "text")


async def _call_openai(client: OrgLLMClient, messages: list[dict], system_prompt: str) -> str:
    response = await _sdk(client).chat.completions.create(
        model=client.model,
        max_tokens=MAX_RESPONSE_TOKENS,
        messages=[{"role": "system", "content": system_prompt}, *messages],
    )
    return response.choices[0].message.content or ""


async def _call_cohere(client: OrgLLMClient, messages: list[dict], system_prompt: str) -> str:
    chat_history = [
        {"role": "USER" if m["role"] == "user" else "CHATBOT", "message": m["content"]} for m in messages[:-1]
    ]
    response = await _sdk(client).chat(
        model=client.model,
        message=messages[-1]["content"] if messages else "",
        preamble=system_prompt,
        chat_history=chat_history,
    )
    return response.text


_PROVIDER_HANDLERS = {
    ApiKeyProvider.anthropic: _call_anthropic,
    ApiKeyProvider.openai: _call_openai,
    ApiKeyProvider.cohere: _call_cohere,
}


async def call_llm(client: OrgLLMClient, messages: list[dict], system_prompt: str) -> str:
    """Unified call across providers. Raises LLMProviderError on any failure —
    it does not crash the process, but it also doesn't silently return text,
    so callers can decide how to degrade for the customer."""
    handler = _PROVIDER_HANDLERS.get(client.provider)
    if handler is None:
        raise LLMProviderError(f"Unsupported provider: {client.provider}")

    logger.info("llm_call", provider=client.provider.value, model=client.model)
    try:
        return await handler(client, messages, system_prompt)
    except Exception as exc:
        logger.warning("llm_call_failed", provider=client.provider.value, model=client.model, error=str(exc))
        raise LLMProviderError(f"{client.provider.value} call failed: {exc}") from exc


async def _stream_anthropic(client: OrgLLMClient, messages: list[dict], system_prompt: str) -> AsyncIterator[str]:
    # Prompt caching: send `system` as a structured block with cache_control
    # ephemeral so Anthropic caches the (identical, per-org) system prompt
    # across turns. Cached prefix cuts TTFT ~40-70% on Haiku for a fixed
    # ~375-token system message. OpenAI's equivalent (automatic prompt caching
    # for prompts >=1024 tokens) requires no client-side change — the SDK
    # object we now hold persistently is enough. Cohere has no equivalent.
    system_blocks = [{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}]
    async with _sdk(client).messages.stream(
        model=client.model,
        max_tokens=MAX_RESPONSE_TOKENS,
        system=system_blocks,
        messages=messages,
    ) as stream:
        async for token in stream.text_stream:
            yield token
        # After the stream drains, `stream.get_final_message()` exposes the
        # usage object with cache_creation_input_tokens (first hit, wrote to
        # cache) and cache_read_input_tokens (subsequent turns, read from
        # cache). Non-fatal if the SDK version doesn't populate these.
        try:
            final = await stream.get_final_message()
            usage = getattr(final, "usage", None)
            if usage is not None:
                created = getattr(usage, "cache_creation_input_tokens", 0) or 0
                read = getattr(usage, "cache_read_input_tokens", 0) or 0
                logger.info(
                    "voice_prompt_cache_hit",
                    provider="anthropic",
                    model=client.model,
                    hit=bool(read and not created),
                    cache_read_tokens=read,
                    cache_write_tokens=created,
                    input_tokens=getattr(usage, "input_tokens", 0),
                )
        except Exception as exc:  # noqa: BLE001 — never fail a turn on telemetry
            logger.debug("voice_prompt_cache_hit_probe_failed", error=str(exc))


async def _stream_openai(client: OrgLLMClient, messages: list[dict], system_prompt: str) -> AsyncIterator[str]:
    stream = await _sdk(client).chat.completions.create(
        model=client.model,
        max_tokens=MAX_RESPONSE_TOKENS,
        messages=[{"role": "system", "content": system_prompt}, *messages],
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


async def _stream_cohere(client: OrgLLMClient, messages: list[dict], system_prompt: str) -> AsyncIterator[str]:
    chat_history = [
        {"role": "USER" if m["role"] == "user" else "CHATBOT", "message": m["content"]} for m in messages[:-1]
    ]
    stream = _sdk(client).chat_stream(
        model=client.model,
        message=messages[-1]["content"] if messages else "",
        preamble=system_prompt,
        chat_history=chat_history,
    )
    async for event in stream:
        if getattr(event, "event_type", None) == "text-generation":
            yield event.text


_STREAM_HANDLERS = {
    ApiKeyProvider.anthropic: _stream_anthropic,
    ApiKeyProvider.openai: _stream_openai,
    ApiKeyProvider.cohere: _stream_cohere,
}


async def stream_llm(client: OrgLLMClient, messages: list[dict], system_prompt: str) -> AsyncIterator[str]:
    """Token-by-token variant of call_llm, for streaming to a live socket.

    Raises LLMProviderError if the stream fails — including partway through,
    after some tokens have already been yielded. Callers iterating with
    `async for` should be ready to catch that mid-stream.
    """
    handler = _STREAM_HANDLERS.get(client.provider)
    if handler is None:
        raise LLMProviderError(f"Unsupported provider: {client.provider}")

    logger.info("llm_stream", provider=client.provider.value, model=client.model)
    try:
        async for token in handler(client, messages, system_prompt):
            yield token
    except Exception as exc:
        logger.warning("llm_stream_failed", provider=client.provider.value, model=client.model, error=str(exc))
        raise LLMProviderError(f"{client.provider.value} stream failed: {exc}") from exc


async def stream_llm_with_fallback(
    clients: list[OrgLLMClient], messages: list[dict], system_prompt: str
) -> AsyncIterator[str]:
    """Try each client in `clients` in order. If the primary raises BEFORE
    yielding any tokens, seamlessly try the next. Once a token has been
    yielded, we're committed — a mid-stream failure propagates as
    LLMProviderError so the caller can render whatever text arrived so far
    (see how retell_handler's response builder appends a fallback message
    to `collected` on failure).

    Rationale: an Anthropic outage in the middle of a call shouldn't kill the
    conversation if the org has an OpenAI key too. Provider status pages
    show ~4-6 outages per year each; without fallback, that's ~10 hours of
    outage per year exposed to end users. With fallback the outages have to
    line up in the same 30s window.
    """
    if not clients:
        raise NoLLMProviderConfiguredError("stream_llm_with_fallback called with no clients")

    last_error: Exception | None = None
    for idx, client in enumerate(clients):
        handler = _STREAM_HANDLERS.get(client.provider)
        if handler is None:
            last_error = LLMProviderError(f"Unsupported provider: {client.provider}")
            continue

        logger.info(
            "llm_stream_fallback_attempt",
            provider=client.provider.value,
            model=client.model,
            attempt=idx + 1,
            fallback=idx > 0,
        )
        yielded_any = False
        try:
            async for token in handler(client, messages, system_prompt):
                yielded_any = True
                yield token
            # Provider finished successfully — done.
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if yielded_any:
                # Mid-stream failure — we've already committed to this provider
                # (the client has partial output). Fall through to LLMProviderError.
                logger.warning(
                    "llm_stream_failed_mid_stream",
                    provider=client.provider.value,
                    model=client.model,
                    error=str(exc),
                )
                raise LLMProviderError(
                    f"{client.provider.value} stream failed mid-response: {exc}"
                ) from exc
            # No tokens yet — try the next client.
            logger.warning(
                "llm_stream_fallback_next",
                provider=client.provider.value,
                model=client.model,
                remaining=len(clients) - idx - 1,
                error=str(exc),
            )
            continue

    # All providers exhausted before any token.
    raise LLMProviderError(f"All {len(clients)} providers failed. Last error: {last_error}")


def parse_json_response(raw: str) -> dict:
    """LLMs love to wrap JSON in markdown code fences — strip those before parsing."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    return json.loads(cleaned)
