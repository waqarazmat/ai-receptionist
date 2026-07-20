import uuid
from datetime import datetime, timezone

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth.jwt import create_access_token, create_refresh_token, decode_token
from app.api.auth.otp import generate_otp, store_otp, verify_otp
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
from app.utils.email import send_otp_email

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

    # Email-enumeration prevention: identical response regardless of whether
    # the email exists, is inactive, or is rate-limited — only the side
    # effects (OTP stored + email sent) differ.
    if user is not None:
        code = generate_otp()
        stored = await store_otp(body.email, code)
        if stored:
            try:
                await send_otp_email(body.email, code)
            except httpx.HTTPError:
                logger.warning("otp_email_send_failed", email=body.email)

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
    access_token = create_access_token(str(user.id), user.role.value, org_id)
    refresh_token = create_refresh_token(str(user.id))

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

    org_id = str(user.org_id) if user.org_id else None
    access_token = create_access_token(str(user.id), user.role.value, org_id)

    return AccessTokenResponse(access_token=access_token)
