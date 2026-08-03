import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth.jwt import create_access_token, create_refresh_token, decode_token
from app.api.auth.otp import generate_otp, store_otp, verify_otp
from app.api.deps import get_current_user
from app.db.engine import get_session
from app.models.user import User
from app.schemas.auth import (
    AccessTokenResponse,
    MessageResponse,
    RefreshRequest,
    RequestOtpRequest,
    TokenResponse,
    VerifyOtpRequest,
)
from app.utils.email import EmailDeliveryError, send_otp_email

logger = structlog.get_logger()
router = APIRouter()

GENERIC_OTP_MESSAGE = "If this email is registered, you'll receive a code."
GENERIC_INVALID_CODE_MESSAGE = "Invalid or expired code."


@router.post("/request-otp", response_model=MessageResponse)
async def request_otp(body: RequestOtpRequest, session: AsyncSession = Depends(get_session)) -> MessageResponse:
    result = await session.execute(
        select(User).where(User.email == body.email, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()

    # Email-enumeration prevention: for a NON-existent (or inactive) email
    # we return the generic response with no side effects. This branch keeps
    # that property.
    if user is None:
        return MessageResponse(message=GENERIC_OTP_MESSAGE)

    code = generate_otp()
    stored = await store_otp(body.email, code)
    if not stored:
        # Hourly OTP request cap hit — same generic message so callers can't
        # tell rate-limiting apart from a fresh send. Rate-limiter already
        # logged the hit internally.
        return MessageResponse(message=GENERIC_OTP_MESSAGE)

    # Real user, OTP in Redis, now try to deliver it. On failure we prefer
    # to surface the error to the caller so they can retry, rather than
    # silently claim success while their inbox stays empty. This does mean
    # an SMTP outage becomes distinguishable from a non-existent-email
    # response (existent-broken -> 502, non-existent -> 200 generic) — an
    # enumeration hint we accept in exchange for a working retry UX. If
    # the enumeration property becomes critical, revisit by queueing sends
    # via Arq and always returning 200 here.
    # TEMPORARY: email delivery failures are swallowed here while we're
    # between email providers (Brevo suspended, new provider not yet
    # configured). REVERT to raising 502 once a working SMTP provider is
    # confirmed — otherwise real users will get a false "success" with no
    # actual OTP email and no way to know why they never received it.
    try:
        await send_otp_email(body.email, code)
    except EmailDeliveryError as exc:
        logger.warning(
            "otp_email_send_failed",
            email=body.email,
            status_code=exc.status_code,
            response_body=exc.body,
        )

    return MessageResponse(message=GENERIC_OTP_MESSAGE)


@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp_endpoint(
    body: VerifyOtpRequest, session: AsyncSession = Depends(get_session)
) -> TokenResponse:
    if not await verify_otp(body.email, body.code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_INVALID_CODE_MESSAGE)

    result = await session.execute(
        select(User).where(User.email == body.email, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_INVALID_CODE_MESSAGE)

    user.last_login = datetime.now(timezone.utc)
    await session.commit()

    org_id = str(user.org_id) if user.org_id else None
    access_token = create_access_token(str(user.id), user.role.value, org_id, user.token_version)
    refresh_token = create_refresh_token(str(user.id), user.token_version)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(body: RefreshRequest, session: AsyncSession = Depends(get_session)) -> AccessTokenResponse:
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    try:
        user_id = uuid.UUID(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    # Token-version check: any refresh token issued BEFORE user.token_version
    # was bumped (via logout or deactivate) is now dead. Rejecting here is
    # what makes the 7-day refresh window collapse to "immediately" for
    # deactivated / logged-out users.
    token_version = payload.get("tv")
    if token_version is None or int(token_version) != user.token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked")

    org_id = str(user.org_id) if user.org_id else None
    access_token = create_access_token(str(user.id), user.role.value, org_id, user.token_version)

    return AccessTokenResponse(access_token=access_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    """Revoke every refresh token that was ever issued to this user by bumping
    their token_version. Access tokens issued in the last 30 min still work
    until they expire — that's the deliberate exposure window for keeping the
    per-request path fast (no DB read per authenticated call)."""
    current_user.token_version = (current_user.token_version or 1) + 1
    await session.commit()
    return MessageResponse(message="Signed out.")
