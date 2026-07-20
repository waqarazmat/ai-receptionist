import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.db.engine import async_session_maker
from app.models.channel_config import ChannelConfig
from app.models.conversation import Conversation
from app.models.enums import Channel, MessageRole
from app.models.organization import Organization
from app.services.conversation_service import get_conversation_messages

router = APIRouter()

DEFAULT_PRIMARY_COLOR = "#4f46e5"


class WidgetConfigResponse(BaseModel):
    primaryColor: str
    secondaryColor: str | None = None
    position: str
    launcherIcon: str
    headerTitle: str
    avatarUrl: str | None
    poweredByVisible: bool
    greetingByLang: dict[str, str]
    responseTimeText: str | None = None
    businessHoursBehavior: str
    preChatFormEnabled: bool
    preChatFields: list[dict]
    suggestedQuestions: list[str] | None = None


class HistoryMessageResponse(BaseModel):
    id: uuid.UUID
    direction: str
    body: str
    createdAt: datetime
    status: str | None = None


class HistoryResponse(BaseModel):
    messages: list[HistoryMessageResponse]


@router.get("/webchat/{org_id}/config", response_model=WidgetConfigResponse)
async def get_webchat_config(org_id: uuid.UUID) -> WidgetConfigResponse:
    """Widget config — fetched by the embeddable widget before it renders, so
    it never flashes default colors. 404 (not a 200 with defaults) whenever
    webchat isn't actually usable for this org, matching the widget's own
    "fetch fails → stay hidden entirely" behavior (root CLAUDE.md rule #8:
    graceful degradation, not a broken-looking widget on a client's site).
    """
    async with async_session_maker() as db:
        org = await db.get(Organization, org_id)
        if org is None or not org.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

        channel_config = (
            await db.execute(
                select(ChannelConfig).where(
                    ChannelConfig.org_id == org_id, ChannelConfig.channel_type == Channel.webchat
                )
            )
        ).scalar_one_or_none()
        if channel_config is None or not channel_config.is_enabled:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webchat not enabled")

        widget_cfg = channel_config.config or {}
        prompts = org.system_prompts or {}

        return WidgetConfigResponse(
            primaryColor=widget_cfg.get("primary_color", DEFAULT_PRIMARY_COLOR),
            secondaryColor=widget_cfg.get("secondary_color"),
            position=widget_cfg.get("position", "bottom-right"),
            launcherIcon=widget_cfg.get("launcher_icon", "chat"),
            headerTitle=widget_cfg.get("header_title") or org.name,
            avatarUrl=widget_cfg.get("avatar_url"),
            poweredByVisible=widget_cfg.get("powered_by_visible", True),
            greetingByLang=widget_cfg.get("greeting_by_lang")
            or {"en": prompts.get("greeting") or f"Hi! Welcome to {org.name}."},
            responseTimeText=widget_cfg.get("response_time_text"),
            businessHoursBehavior=widget_cfg.get("business_hours_behavior", "always_available"),
            # No backend support yet for visitor identification (email capture)
            # — always disabled rather than showing a form that goes nowhere.
            preChatFormEnabled=False,
            preChatFields=[],
            suggestedQuestions=widget_cfg.get("suggested_questions"),
        )


@router.get("/webchat/{org_id}/conversations/{conversation_id}/messages", response_model=HistoryResponse)
async def get_webchat_history(org_id: uuid.UUID, conversation_id: uuid.UUID) -> HistoryResponse:
    """Lets the widget repopulate its chat window after a page reload —
    conversation_id itself is the capability (same trust model the live
    Socket.IO connection already uses: an unguessable UUID v4, scoped to
    org_id as defense in depth), no separate bearer token needed."""
    async with async_session_maker() as db:
        conversation = await db.get(Conversation, conversation_id)
        if conversation is None or conversation.org_id != org_id or conversation.channel != Channel.webchat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

        messages = await get_conversation_messages(db, conversation_id)

    return HistoryResponse(
        messages=[
            HistoryMessageResponse(
                id=m.id,
                direction="outbound" if m.role == MessageRole.customer else "inbound",
                body=m.content,
                createdAt=m.created_at,
                status=m.delivery_status,
            )
            for m in messages
        ]
    )
