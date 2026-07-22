"""Billing analytics — cost breakdowns for the super-admin billing page
and the per-org billing page.

Uses `app.billing.costs` for the cost model and `app.billing.usage` for
current-month usage counters. Costs are ESTIMATES computed from AI-message
counts × per-provider rates × per-channel surcharges. Real token-count
tracking would move this from "estimate" to "billing-grade" and is a
future change (add `input_tokens`/`output_tokens` columns to Message, write
them from the LLM response usage field, sum those instead of estimating).
"""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import usage as usage_tracker
from app.billing.costs import (
    CHANNEL_EXTRA_COST_PER_MSG,
    DEFAULT_INPUT_TOKENS_PER_MSG,
    DEFAULT_MODEL_BY_PROVIDER,
    DEFAULT_OUTPUT_TOKENS_PER_MSG,
    LLM_INPUT_PRICE_PER_1K,
    LLM_OUTPUT_PRICE_PER_1K,
    estimate_msg_cost,
    get_active_provider,
)
from app.billing.plans import get_plan
from app.models.enums import ApiKeyProvider, Channel, MessageRole
from app.models.message import Message
from app.models.org_api_keys import OrgApiKey
from app.models.organization import Organization


def _window_start(days: int = 30) -> datetime:
    return (datetime.now(timezone.utc) - timedelta(days=days - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


async def _providers_by_org(db: AsyncSession) -> dict[uuid.UUID, ApiKeyProvider]:
    """Map org_id → highest-priority active LLM provider. Used as the
    per-message pricing basis when we compute cost. Returned as a plain
    dict for cheap in-memory joining downstream."""
    llm_providers = {
        ApiKeyProvider.anthropic,
        ApiKeyProvider.openai,
        ApiKeyProvider.cohere,
    }
    rows = (
        await db.execute(
            select(OrgApiKey.org_id, OrgApiKey.provider).where(
                OrgApiKey.is_active.is_(True),
                OrgApiKey.provider.in_(llm_providers),
            )
        )
    ).all()
    by_org: dict[uuid.UUID, list[ApiKeyProvider]] = defaultdict(list)
    for org_id, provider in rows:
        by_org[org_id].append(provider)
    return {org_id: get_active_provider(providers) for org_id, providers in by_org.items()}


async def get_platform_billing(
    db: AsyncSession, days: int = 30, org_id: uuid.UUID | None = None
) -> dict:
    """Rich billing view for the super-admin billing page.

    When `org_id` is None → all orgs, aggregated (for the platform overview).
    When `org_id` is set → single-org breakdown (for the org-selector view).
    Same response shape either way so the frontend renders one component.
    """
    since = _window_start(days)
    providers_map = await _providers_by_org(db)

    # ─── Base AI-message counts ──────────────────────────────────────
    base_filter = [Message.created_at >= since, Message.role == MessageRole.ai]
    if org_id is not None:
        base_filter.append(Message.org_id == org_id)

    # Total AI messages by (org, channel) — this is the atom we compute
    # every rollup from.
    msg_rows = (
        await db.execute(
            select(Message.org_id, Message.channel, func.count(Message.id))
            .where(*base_filter)
            .group_by(Message.org_id, Message.channel)
        )
    ).all()

    # ─── Assemble the breakdowns ─────────────────────────────────────
    # Cost by provider (aggregate across all orgs in scope)
    by_provider: dict[str, float] = defaultdict(float)
    # Cost by channel
    by_channel: dict[str, dict[str, float]] = defaultdict(
        lambda: {"llm_usd": 0.0, "external_usd": 0.0, "total_usd": 0.0, "messages": 0}
    )
    # Per-org roll-up for the table
    per_org: dict[uuid.UUID, dict] = defaultdict(
        lambda: {
            "messages": 0,
            "llm_usd": 0.0,
            "external_usd": 0.0,
            "total_usd": 0.0,
            "by_channel": defaultdict(lambda: {"messages": 0, "total_usd": 0.0}),
        }
    )
    total_llm = 0.0
    total_external = 0.0
    total_messages = 0

    for m_org_id, channel, n in msg_rows:
        provider = providers_map.get(m_org_id, ApiKeyProvider.anthropic)
        cost = estimate_msg_cost(provider, channel, n)

        by_provider[provider.value] += cost.llm_input_usd + cost.llm_output_usd
        by_channel[channel.value]["llm_usd"] += cost.llm_input_usd + cost.llm_output_usd
        by_channel[channel.value]["external_usd"] += cost.external_api_usd
        by_channel[channel.value]["total_usd"] += cost.total_usd
        by_channel[channel.value]["messages"] += n

        org_row = per_org[m_org_id]
        org_row["messages"] += n
        org_row["llm_usd"] += cost.llm_input_usd + cost.llm_output_usd
        org_row["external_usd"] += cost.external_api_usd
        org_row["total_usd"] += cost.total_usd
        org_row["by_channel"][channel.value]["messages"] += n
        org_row["by_channel"][channel.value]["total_usd"] += cost.total_usd

        total_llm += cost.llm_input_usd + cost.llm_output_usd
        total_external += cost.external_api_usd
        total_messages += n

    # ─── Daily time series (cost per day) ────────────────────────────
    # date_trunc('day') buckets by UTC calendar day; we compute cost per
    # (day, channel) bucket so the stacked chart can render channel splits.
    day_col = func.date_trunc("day", Message.created_at).label("day")
    daily_rows = (
        await db.execute(
            select(day_col, Message.org_id, Message.channel, func.count(Message.id))
            .where(*base_filter)
            .group_by(day_col, Message.org_id, Message.channel)
            .order_by(day_col)
        )
    ).all()
    series: dict[str, dict] = {}
    for day, m_org_id, channel, n in daily_rows:
        key = day.date().isoformat()
        series.setdefault(
            key, {"date": key, "webchat": 0.0, "whatsapp": 0.0, "voice": 0.0, "total": 0.0}
        )
        provider = providers_map.get(m_org_id, ApiKeyProvider.anthropic)
        cost = estimate_msg_cost(provider, channel, n).total_usd
        series[key][channel.value] += round(cost, 4)
        series[key]["total"] += round(cost, 4)
    # Fill zero-days so the chart's x-axis is continuous.
    day_cursor = since.date()
    end = datetime.now(timezone.utc).date()
    while day_cursor <= end:
        key = day_cursor.isoformat()
        series.setdefault(
            key, {"date": key, "webchat": 0.0, "whatsapp": 0.0, "voice": 0.0, "total": 0.0}
        )
        day_cursor += timedelta(days=1)
    daily = sorted(series.values(), key=lambda r: r["date"])
    for d in daily:
        for k in ("webchat", "whatsapp", "voice", "total"):
            d[k] = round(d[k], 4)

    # ─── Enrich per-org rows with org name + plan for the table ──────
    org_ids_in_scope = list(per_org.keys())
    if org_ids_in_scope:
        orgs = (
            await db.execute(select(Organization).where(Organization.id.in_(org_ids_in_scope)))
        ).scalars().all()
        org_by_id = {o.id: o for o in orgs}
    else:
        org_by_id = {}
    per_org_list: list[dict] = []
    for oid, row in per_org.items():
        org = org_by_id.get(oid)
        provider = providers_map.get(oid, ApiKeyProvider.anthropic)
        per_org_list.append(
            {
                "org_id": str(oid),
                "org_name": org.name if org else "(deleted org)",
                "plan": org.plan.value if org else "free",
                "primary_provider": provider.value,
                "messages": row["messages"],
                "llm_usd": round(row["llm_usd"], 4),
                "external_usd": round(row["external_usd"], 4),
                "total_usd": round(row["total_usd"], 4),
                "by_channel": {
                    ch: {"messages": v["messages"], "total_usd": round(v["total_usd"], 4)}
                    for ch, v in row["by_channel"].items()
                },
            }
        )
    per_org_list.sort(key=lambda r: r["total_usd"], reverse=True)

    return {
        "window_days": days,
        "generated_at": datetime.now(timezone.utc),
        "org_id": str(org_id) if org_id else None,
        "totals": {
            "messages": total_messages,
            "llm_usd": round(total_llm, 2),
            "external_usd": round(total_external, 2),
            "total_usd": round(total_llm + total_external, 2),
        },
        "by_provider": [
            {"provider": p, "total_usd": round(v, 4)}
            for p, v in sorted(by_provider.items(), key=lambda x: x[1], reverse=True)
        ],
        "by_channel": [
            {
                "channel": ch,
                "messages": v["messages"],
                "llm_usd": round(v["llm_usd"], 4),
                "external_usd": round(v["external_usd"], 4),
                "total_usd": round(v["total_usd"], 4),
            }
            for ch, v in by_channel.items()
        ],
        "daily": daily,
        "per_org": per_org_list,
        # Reference data — the frontend renders a "how this is computed" note.
        "pricing_notes": {
            "input_tokens_per_msg": DEFAULT_INPUT_TOKENS_PER_MSG,
            "output_tokens_per_msg": DEFAULT_OUTPUT_TOKENS_PER_MSG,
            "channel_extra_usd_per_msg": {
                ch.value: v for ch, v in CHANNEL_EXTRA_COST_PER_MSG.items()
            },
            "provider_model_map": {
                p.value: m for p, m in DEFAULT_MODEL_BY_PROVIDER.items()
            },
            "model_input_price_per_1k": LLM_INPUT_PRICE_PER_1K,
            "model_output_price_per_1k": LLM_OUTPUT_PRICE_PER_1K,
        },
    }


async def get_org_billing(db: AsyncSession, org_id: uuid.UUID) -> dict:
    """The org's OWN billing view — current plan + this-month usage +
    running estimated cost. Called from /api/org/billing/current."""
    org = await db.get(Organization, org_id)
    if org is None:
        return {}
    plan = get_plan(org.plan)
    current_usage = await usage_tracker.get_current_usage(str(org_id))

    # Costs for the current calendar month — window from month start to now.
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    days_in_window = max((now - month_start).days + 1, 1)
    breakdown = await get_platform_billing(db, days=days_in_window, org_id=org_id)

    return {
        "plan": {
            "key": plan.key.value,
            "display_name": plan.display_name,
            "monthly_message_quota": plan.monthly_message_quota,
            "price_usd_monthly": plan.price_usd_monthly,
            "features": list(plan.features),
        },
        "usage": {
            "messages_this_month": current_usage,
            "quota": plan.monthly_message_quota,
            "percent_used": round(
                (current_usage / max(plan.monthly_message_quota, 1)) * 100, 1
            ),
        },
        "current_month_costs": breakdown["totals"],
        "by_channel": breakdown["by_channel"],
        "daily": breakdown["daily"],
        "pricing_notes": breakdown["pricing_notes"],
    }
