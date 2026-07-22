"""Cost model for LLM + external-API usage.

We do NOT currently store per-message provider info in the DB (adding that
would be a schema change + a full write-path audit). So costs here are
computed as an ESTIMATE: for each org, look at their active LLM provider
config, use the priority provider's rates, and multiply by observed AI
message counts. The UI surfaces these as `~$X.XX` with an "estimate" badge.

Rates are per-1K-tokens and assume a rough tokens-per-message envelope.
Tune these once you have real token-count data from LLM response metadata.
"""

from dataclasses import dataclass

from app.models.enums import ApiKeyProvider, Channel


# Per-1K-tokens pricing in USD, as of the model versions used in this project.
# Update quarterly or when providers announce changes. Kept as a plain dict
# (not env vars) so tuning is a code change with a diff / review trail.
LLM_INPUT_PRICE_PER_1K: dict[str, float] = {
    "claude-haiku-4-5-20251001": 0.0008,
    "claude-sonnet-5": 0.003,
    "gpt-4o-mini": 0.00015,
    "gpt-4o": 0.0025,
    "command-r7b-12-2024": 0.00015,
    "command-r-plus-08-2024": 0.0025,
}
LLM_OUTPUT_PRICE_PER_1K: dict[str, float] = {
    "claude-haiku-4-5-20251001": 0.004,
    "claude-sonnet-5": 0.015,
    "gpt-4o-mini": 0.0006,
    "gpt-4o": 0.010,
    "command-r7b-12-2024": 0.0006,
    "command-r-plus-08-2024": 0.010,
}

# Envelope: how many input/output tokens a typical AI message consumes.
# System prompt ~350 tokens + history ~500 + user turn ~50 = ~900 input.
# Output typically 40-120 tokens for chat, 20-60 for voice.
DEFAULT_INPUT_TOKENS_PER_MSG = 900
DEFAULT_OUTPUT_TOKENS_PER_MSG = 80

# Per-channel additional external-API costs paid to third parties.
# These stack on top of the LLM cost above.
CHANNEL_EXTRA_COST_PER_MSG: dict[Channel, float] = {
    Channel.webchat: 0.0,  # no third-party surcharge — direct WebSocket
    Channel.whatsapp: 0.005,  # Meta conversation-based pricing, roughly
    Channel.voice: 0.09,  # Retell + TTS is by far the tallest pole per turn
}

# Best model to price by, for each provider. Matches FAST_MODELS in
# llm_router.py — voice always uses the fast tier; webchat uses quality
# but the fast tier is a fine estimation proxy for total-cost visualization.
DEFAULT_MODEL_BY_PROVIDER: dict[ApiKeyProvider, str] = {
    ApiKeyProvider.anthropic: "claude-haiku-4-5-20251001",
    ApiKeyProvider.openai: "gpt-4o-mini",
    ApiKeyProvider.cohere: "command-r7b-12-2024",
}


@dataclass
class CostBreakdown:
    """Everything the billing UI needs about the estimated spend for one
    (org, provider, channel, time window) combination."""
    llm_input_usd: float
    llm_output_usd: float
    external_api_usd: float
    total_usd: float


def estimate_msg_cost(
    provider: ApiKeyProvider,
    channel: Channel,
    n_ai_messages: int,
) -> CostBreakdown:
    """Rough LLM + channel-surcharge cost for `n_ai_messages` AI messages."""
    model = DEFAULT_MODEL_BY_PROVIDER.get(provider, "gpt-4o-mini")
    in_price = LLM_INPUT_PRICE_PER_1K.get(model, 0.0005)
    out_price = LLM_OUTPUT_PRICE_PER_1K.get(model, 0.002)

    input_tokens = n_ai_messages * DEFAULT_INPUT_TOKENS_PER_MSG
    output_tokens = n_ai_messages * DEFAULT_OUTPUT_TOKENS_PER_MSG

    llm_input = (input_tokens / 1000.0) * in_price
    llm_output = (output_tokens / 1000.0) * out_price
    external = n_ai_messages * CHANNEL_EXTRA_COST_PER_MSG.get(channel, 0.0)

    return CostBreakdown(
        llm_input_usd=round(llm_input, 4),
        llm_output_usd=round(llm_output, 4),
        external_api_usd=round(external, 4),
        total_usd=round(llm_input + llm_output + external, 4),
    )


def get_active_provider(providers: list[ApiKeyProvider]) -> ApiKeyProvider:
    """Highest-priority active provider — matches PROVIDER_PRIORITY in
    llm_router.py so the cost estimate reflects the same fallback order the
    runtime actually uses."""
    priority = [ApiKeyProvider.anthropic, ApiKeyProvider.openai, ApiKeyProvider.cohere]
    for p in priority:
        if p in providers:
            return p
    # Fallback if nothing configured — costs will be zero anyway.
    return ApiKeyProvider.anthropic
