import asyncio
import json
import uuid
from datetime import datetime

import structlog
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.enums import ApiKeyProvider
from app.models.org_api_keys import OrgApiKey
from app.security.encryption import decrypt_api_key

logger = structlog.get_logger()

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _http_error_reasons(exc: HttpError) -> set[str]:
    """Extracts the `reason` code(s) (e.g. "forbiddenForServiceAccounts")
    from a Google API error body, so callers can branch on the specific
    failure instead of just the HTTP status."""
    try:
        body = json.loads(exc.content)
        return {e.get("reason") for e in body.get("error", {}).get("errors", []) if e.get("reason")}
    except (ValueError, AttributeError, TypeError):
        return set()

_service_account_info_cache: dict | None | object = "_unset"


def _load_service_account_info() -> dict | None:
    """The platform's ONE shared service account as a dict, from whichever
    source is configured (JSON env var preferred over file path). Read once and
    cached — it never changes at runtime.

    Returns None (and logs) when neither source is set or the value can't be
    parsed; callers treat that as "calendar not configured" and degrade
    gracefully rather than 500 (root CLAUDE.md rule #8)."""
    global _service_account_info_cache
    if _service_account_info_cache != "_unset":
        return _service_account_info_cache  # type: ignore[return-value]

    info: dict | None = None
    if settings.GOOGLE_SERVICE_ACCOUNT_JSON:
        # Raw JSON contents in an env var — the deploy-friendly path (a
        # gitignored key file never reaches Railway).
        try:
            info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
        except ValueError as exc:
            logger.warning("service_account_json_parse_failed", error=str(exc))
    elif settings.GOOGLE_SERVICE_ACCOUNT_FILE:
        try:
            with open(settings.GOOGLE_SERVICE_ACCOUNT_FILE, encoding="utf-8") as f:
                info = json.load(f)
        except (OSError, ValueError) as exc:
            logger.warning("service_account_file_read_failed", error=str(exc))

    _service_account_info_cache = info
    return info


def get_service_account_email() -> str | None:
    """The address an org needs to share their Google Calendar with — derived
    from the shared service account key and shown to the org during setup."""
    info = _load_service_account_info()
    return info.get("client_email") if info else None


class GoogleCalendarError(Exception):
    """Calendar isn't configured/shared, or a Calendar API call failed.
    Callers (booking flow, health check) should treat this as 'booking
    degraded' per root CLAUDE.md rule #8 — not a 500."""


class GoogleCalendarClient:
    """Auth is a shared service account (not per-org OAuth) — the JSON key
    file is the same for every org (GOOGLE_SERVICE_ACCOUNT_FILE). What's
    per-org is which calendar to use: the org owner shares their Google
    Calendar with the service account's client_email and gives us that
    calendar's ID, stored encrypted in org_api_keys (provider=google_calendar,
    reusing the generic "encrypted secret string" column for a calendar ID
    instead of an LLM API key)."""

    def __init__(self, org_id: uuid.UUID, calendar_id: str):
        info = _load_service_account_info()
        if info is None:
            raise GoogleCalendarError(
                "Google service account is not configured "
                "(set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE)"
            )

        self.org_id = org_id
        self.calendar_id = calendar_id
        try:
            credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
            self._service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        except (ValueError, KeyError) as exc:
            raise GoogleCalendarError(f"Failed to load service account credentials: {exc}") from exc

    @classmethod
    async def for_org(cls, db: AsyncSession, org_id: uuid.UUID) -> "GoogleCalendarClient":
        key_row = (
            await db.execute(
                select(OrgApiKey).where(
                    OrgApiKey.org_id == org_id,
                    OrgApiKey.provider == ApiKeyProvider.google_calendar,
                    OrgApiKey.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if key_row is None:
            raise GoogleCalendarError(f"No Google Calendar configured for org {org_id}")

        calendar_id = decrypt_api_key(str(org_id), key_row.encrypted_key)
        logger.info("google_calendar_client_configured", org_id=str(org_id), calendar_id=calendar_id)
        return cls(org_id, calendar_id)

    @staticmethod
    def _run(fn):
        """google-api-python-client is fully synchronous (httplib2-based) —
        run it in a thread so it doesn't block the event loop, same pattern
        as the embedding model in app.ai.embeddings."""
        return asyncio.to_thread(fn)

    async def get_free_busy(self, date_start: datetime, date_end: datetime) -> list[dict]:
        def _call() -> list[dict]:
            body = {
                "timeMin": date_start.isoformat(),
                "timeMax": date_end.isoformat(),
                "items": [{"id": self.calendar_id}],
            }
            logger.info(
                "google_calendar_freebusy_request",
                org_id=str(self.org_id),
                calendar_id=self.calendar_id,
                time_min=body["timeMin"],
                time_max=body["timeMax"],
            )
            response = self._service.freebusy().query(body=body).execute()
            calendar = response.get("calendars", {}).get(self.calendar_id, {})
            if calendar.get("errors"):
                logger.error(
                    "google_calendar_freebusy_error",
                    org_id=str(self.org_id),
                    calendar_id=self.calendar_id,
                    response=response,
                )
                raise GoogleCalendarError(f"Free/busy query error: {calendar['errors']}")
            return calendar.get("busy", [])

        try:
            return await self._run(_call)
        except HttpError as exc:
            logger.error(
                "google_calendar_freebusy_failed",
                org_id=str(self.org_id),
                calendar_id=self.calendar_id,
                status=exc.resp.status if exc.resp else None,
                error=str(exc),
            )
            raise GoogleCalendarError(f"Free/busy query failed: {exc}") from exc

    async def create_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        attendee_email: str | None = None,
        time_zone: str | None = None,
    ) -> str:
        def _build_event(include_attendee: bool) -> dict:
            event: dict = {
                "summary": summary,
                "start": {"dateTime": start.isoformat()},
                "end": {"dateTime": end.isoformat()},
            }
            if time_zone:
                # Explicit IANA timeZone alongside the offset-bearing dateTime —
                # belt-and-suspenders against DST edge cases, and what Google
                # Calendar shows as the event's "native" timezone in its UI.
                event["start"]["timeZone"] = time_zone
                event["end"]["timeZone"] = time_zone
            if attendee_email and include_attendee:
                event["attendees"] = [{"email": attendee_email}]
            elif attendee_email:
                # Personal (non-Workspace) Google accounts reject service-account
                # attendee invites outright (403 forbiddenForServiceAccounts) —
                # Domain-Wide Delegation, the only fix, is a Workspace-only
                # feature and unavailable here. Keep the email visible on the
                # event instead of silently dropping it.
                event["description"] = f"Booked for: {attendee_email}"
            return event

        def _insert(event: dict) -> dict:
            logger.info(
                "google_calendar_create_event_request",
                org_id=str(self.org_id),
                calendar_id=self.calendar_id,
                event_payload=event,
            )
            return self._service.events().insert(calendarId=self.calendar_id, body=event).execute()

        def _call() -> str:
            event = _build_event(include_attendee=True)
            try:
                created = _insert(event)
            except HttpError as exc:
                reasons = _http_error_reasons(exc)
                if attendee_email and "forbiddenForServiceAccounts" in reasons:
                    logger.warning(
                        "google_calendar_attendee_invite_forbidden",
                        org_id=str(self.org_id),
                        calendar_id=self.calendar_id,
                        error=str(exc),
                    )
                    event = _build_event(include_attendee=False)
                    try:
                        created = _insert(event)
                    except HttpError as retry_exc:
                        logger.error(
                            "google_calendar_create_event_failed",
                            org_id=str(self.org_id),
                            calendar_id=self.calendar_id,
                            event_payload=event,
                            status=retry_exc.resp.status if retry_exc.resp else None,
                            error=str(retry_exc),
                        )
                        raise
                else:
                    logger.error(
                        "google_calendar_create_event_failed",
                        org_id=str(self.org_id),
                        calendar_id=self.calendar_id,
                        event_payload=event,
                        status=exc.resp.status if exc.resp else None,
                        error=str(exc),
                    )
                    raise
            logger.info(
                "google_calendar_create_event_success",
                org_id=str(self.org_id),
                calendar_id=self.calendar_id,
                event_id=created.get("id"),
                html_link=created.get("htmlLink"),
                response=created,
            )
            return created["id"]

        try:
            return await self._run(_call)
        except HttpError as exc:
            raise GoogleCalendarError(f"Event creation failed: {exc}") from exc

    async def cancel_event(self, event_id: str) -> bool:
        def _call() -> bool:
            self._service.events().delete(calendarId=self.calendar_id, eventId=event_id).execute()
            return True

        try:
            return await self._run(_call)
        except HttpError as exc:
            if exc.resp.status == 404 or exc.resp.status == 410:
                # Already gone (deleted directly on the calendar, etc.) —
                # from the caller's perspective the event is cancelled either way.
                return False
            raise GoogleCalendarError(f"Event cancellation failed: {exc}") from exc

    async def test_connection(self) -> bool:
        """Used by the health check. Raises GoogleCalendarError with a clear
        message on any failure (calendar unshared, deleted, credentials
        invalid/expired) rather than returning False, so the health check can
        log and store the specific reason."""

        def _call() -> bool:
            self._service.calendars().get(calendarId=self.calendar_id).execute()
            return True

        try:
            return await self._run(_call)
        except HttpError as exc:
            raise GoogleCalendarError(f"Connection test failed: {exc}") from exc
