import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select

from app.booking.google_calendar import GoogleCalendarClient, GoogleCalendarError
from app.db.engine import async_session_maker
from app.db.redis import redis_client
from app.models.enums import ApiKeyProvider, UserRole
from app.models.org_api_keys import OrgApiKey
from app.models.organization import Organization
from app.models.user import User
from app.services.audit_service import log_action

logger = structlog.get_logger()

BOOKING_DEGRADED_KEY_PREFIX = "booking_degraded"
# Cleared automatically if health checks stop failing and the key stops
# being refreshed — a org that fixes its calendar sharing doesn't stay
# flagged forever even if this task somehow stops running for it.
BOOKING_DEGRADED_TTL_SECONDS = 60 * 60 * 2


def _booking_degraded_key(org_id: uuid.UUID) -> str:
    return f"{BOOKING_DEGRADED_KEY_PREFIX}:{org_id}"


async def is_booking_degraded(org_id: uuid.UUID) -> bool:
    return bool(await redis_client.exists(_booking_degraded_key(org_id)))


async def check_google_calendar_health(ctx: dict) -> dict:
    """Arq job — for every active org with calendar_enabled and a configured
    Google Calendar, verifies the service account can still reach it (the
    org may have unshared the calendar, deleted it, etc). Failures are
    flagged in Redis (so the booking flow's own degrade-gracefully path has
    a fast signal, though it already catches GoogleCalendarError directly
    too) and recorded as an audit log entry — which the super admin
    dashboard already surfaces via its "recent activity" feed keyed on
    target_type="organization", so no new dashboard plumbing is needed.
    """
    checked = 0
    failed = 0

    async with async_session_maker() as db:
        system_user = (
            await db.execute(select(User).where(User.role == UserRole.super_admin))
        ).scalars().first()

        orgs = (await db.execute(select(Organization).where(Organization.is_active.is_(True)))).scalars().all()

        for org in orgs:
            if not (org.booking_config or {}).get("calendar_enabled"):
                continue

            key_row = (
                await db.execute(
                    select(OrgApiKey).where(
                        OrgApiKey.org_id == org.id,
                        OrgApiKey.provider == ApiKeyProvider.google_calendar,
                        OrgApiKey.is_active.is_(True),
                    )
                )
            ).scalar_one_or_none()
            if key_row is None:
                continue

            checked += 1
            try:
                client = await GoogleCalendarClient.for_org(db, org.id)
                await client.test_connection()
                await redis_client.delete(_booking_degraded_key(org.id))
                key_row.last_verified_at = datetime.now(timezone.utc)
            except GoogleCalendarError as exc:
                failed += 1
                logger.error("google_calendar_health_check_failed", org_id=str(org.id), error=str(exc))
                await redis_client.set(_booking_degraded_key(org.id), str(exc), ex=BOOKING_DEGRADED_TTL_SECONDS)
                if system_user is not None:
                    await log_action(
                        db,
                        user_id=system_user.id,
                        action="health_check.google_calendar_failed",
                        target_type="organization",
                        target_id=org.id,
                        details={"error": str(exc)},
                    )

        await db.commit()

    logger.info("google_calendar_health_sweep_complete", checked=checked, failed=failed)
    return {"checked": checked, "failed": failed}
