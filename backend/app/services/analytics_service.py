"""Platform-level analytics used by the super-admin dashboard.

Kept in its own service so the existing `dashboard_service.get_dashboard_stats`
(which drives the header KPIs) doesn't have to grow into a monster query.
Everything here rolls up the last 30 days by default — that's the window
that matters for daily operational health without the query getting slow.

If any of these queries ever become expensive (>200 ms), the fix is a
`daily_org_stats` rollup table populated by an Arq cron — but at current
scale (a handful of orgs, tens of thousands of messages) the live COUNT
queries are cheap enough that materializing is premature.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.enums import Channel, EscalationStatus, MessageRole
from app.models.escalation import Escalation
from app.models.message import Message
from app.models.organization import Organization

# Rough per-message cost estimate. Deliberately conservative — real cost
# per org depends on their configured LLM provider, prompt size, response
# length, and cache hit rate. Displayed as a `~` estimate in the UI so
# admins understand it's directional, not billing-grade. Tune these once
# you have real spend data to calibrate against.
COST_PER_AI_MESSAGE_USD = 0.003


def _window_start(days: int = 30) -> datetime:
    """Start of the analytics window, rounded to midnight UTC so the daily
    buckets align cleanly."""
    return (datetime.now(timezone.utc) - timedelta(days=days - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


async def get_platform_analytics(db: AsyncSession, days: int = 30) -> dict:
    """The whole payload the super-admin dashboard fetches in one request."""
    since = _window_start(days)

    # ─── KPI row ─────────────────────────────────────────────────────
    total_messages_window = (
        await db.execute(
            select(func.count(Message.id)).where(Message.created_at >= since)
        )
    ).scalar_one()

    active_orgs = (
        await db.execute(
            select(func.count(Organization.id)).where(Organization.is_active.is_(True))
        )
    ).scalar_one()

    total_conversations_window = (
        await db.execute(
            select(func.count(Conversation.id)).where(Conversation.created_at >= since)
        )
    ).scalar_one() or 1

    total_escalations_window = (
        await db.execute(
            select(func.count(Escalation.id)).where(Escalation.created_at >= since)
        )
    ).scalar_one()

    # Escalation rate is a fraction of conversations that ended up escalating.
    # We divide by max(conversations,1) so an empty period doesn't 0/0 crash.
    escalation_rate = round(
        (total_escalations_window / total_conversations_window) * 100, 1
    )

    # ─── Messages-per-day time series, stacked by channel ─────────────
    # date_trunc('day', created_at) groups messages into daily buckets. We
    # separately select channel so the caller can render a stacked area
    # chart per channel. Postgres returns a row per (day, channel) combo.
    day_col = func.date_trunc("day", Message.created_at).label("day")
    per_day_by_channel = (
        (
            await db.execute(
                select(day_col, Message.channel, func.count(Message.id).label("count"))
                .where(Message.created_at >= since)
                .group_by(day_col, Message.channel)
                .order_by(day_col)
            )
        ).all()
    )
    # Reshape into a wide format: one row per day, columns = channels. Missing
    # (day, channel) combos default to 0 so the chart doesn't have gaps.
    series: dict[str, dict] = {}
    channels_seen: set[str] = set()
    for day, channel, count in per_day_by_channel:
        key = day.date().isoformat()
        series.setdefault(key, {"date": key, "webchat": 0, "whatsapp": 0, "voice": 0})
        series[key][channel.value] = count
        channels_seen.add(channel.value)
    # Fill in any calendar days with zero messages so the x-axis is continuous.
    day_cursor = since.date()
    end = datetime.now(timezone.utc).date()
    while day_cursor <= end:
        key = day_cursor.isoformat()
        series.setdefault(key, {"date": key, "webchat": 0, "whatsapp": 0, "voice": 0})
        day_cursor += timedelta(days=1)
    messages_per_day = sorted(series.values(), key=lambda r: r["date"])

    # ─── Channel breakdown for donut chart ────────────────────────────
    channel_breakdown_rows = (
        (
            await db.execute(
                select(Message.channel, func.count(Message.id).label("count"))
                .where(Message.created_at >= since)
                .group_by(Message.channel)
            )
        ).all()
    )
    channel_breakdown = [
        {"channel": ch.value, "count": cnt} for ch, cnt in channel_breakdown_rows
    ]

    # ─── Per-org rollup for table + top-10 bar chart ──────────────────
    # One SQL round-trip per aggregate would N+1; instead we group everything
    # into three quick queries and merge in Python (cheap for < ~1k orgs).
    org_msg_counts = dict(
        (
            await db.execute(
                select(Message.org_id, func.count(Message.id))
                .where(Message.created_at >= since)
                .group_by(Message.org_id)
            )
        ).all()
    )
    org_ai_msg_counts = dict(
        (
            await db.execute(
                select(Message.org_id, func.count(Message.id))
                .where(Message.created_at >= since, Message.role == MessageRole.ai)
                .group_by(Message.org_id)
            )
        ).all()
    )
    org_conv_counts = dict(
        (
            await db.execute(
                select(Conversation.org_id, func.count(Conversation.id))
                .where(Conversation.created_at >= since)
                .group_by(Conversation.org_id)
            )
        ).all()
    )
    org_esc_counts = dict(
        (
            await db.execute(
                select(Escalation.org_id, func.count(Escalation.id))
                .where(Escalation.created_at >= since)
                .group_by(Escalation.org_id)
            )
        ).all()
    )

    orgs = (await db.execute(select(Organization))).scalars().all()
    per_org: list[dict] = []
    for org in orgs:
        msgs = org_msg_counts.get(org.id, 0)
        ai_msgs = org_ai_msg_counts.get(org.id, 0)
        convos = org_conv_counts.get(org.id, 0) or 0
        escs = org_esc_counts.get(org.id, 0)
        # Divide by max(convos,1) to sidestep 0/0 on orgs with no activity.
        esc_rate = round((escs / max(convos, 1)) * 100, 1) if convos else 0.0
        per_org.append(
            {
                "org_id": str(org.id),
                "org_name": org.name,
                "is_active": org.is_active,
                "messages": msgs,
                "conversations": convos,
                "escalations": escs,
                "escalation_rate_pct": esc_rate,
                # Directional cost estimate — see COST_PER_AI_MESSAGE_USD.
                "estimated_cost_usd": round(ai_msgs * COST_PER_AI_MESSAGE_USD, 2),
            }
        )
    per_org.sort(key=lambda r: r["messages"], reverse=True)

    return {
        "window_days": days,
        "generated_at": datetime.now(timezone.utc),
        "kpis": {
            "total_messages": total_messages_window,
            "active_orgs": active_orgs,
            "total_conversations": (
                total_conversations_window
                if total_conversations_window > 1
                else 0
            ),
            "total_escalations": total_escalations_window,
            "escalation_rate_pct": escalation_rate,
            "avg_messages_per_day": round(total_messages_window / max(days, 1), 1),
            # Sum of estimated cost across every org — matches what per-org
            # rows add up to (Postgres NUMERIC would be more precise; float
            # is fine at this scale).
            "estimated_cost_usd": round(
                sum(row["estimated_cost_usd"] for row in per_org), 2
            ),
        },
        "messages_per_day": messages_per_day,
        "channel_breakdown": channel_breakdown,
        "per_org": per_org,
    }
