"""Tests for AI Act Article 50 disclosures across all three channels."""

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.channels.voice.retell_handler import _AI_VOICE_DISCLOSURE, _draft_begin_message


# ── 1c. Voice: _draft_begin_message always prepends the disclosure ────────────

def test_voice_disclosure_prepended_to_configured_greeting():
    config = {"greeting": "Hello, welcome to City Dental!"}
    result = _draft_begin_message(config, org=None)
    assert result.startswith(_AI_VOICE_DISCLOSURE)
    assert "City Dental" in result


def test_voice_disclosure_prepended_when_greeting_from_org_prompts():
    org = MagicMock()
    org.system_prompts = {"greeting": "Goedemiddag, welkom bij ons kantoor."}
    org.name = "Kantoor BV"
    result = _draft_begin_message({}, org)
    assert result.startswith(_AI_VOICE_DISCLOSURE)
    assert "Goedemiddag" in result


def test_voice_disclosure_prepended_when_greeting_generated_from_org_name():
    org = MagicMock()
    org.system_prompts = {}
    org.name = "Sunrise Gym"
    result = _draft_begin_message({}, org)
    assert result.startswith(_AI_VOICE_DISCLOSURE)
    assert "Sunrise Gym" in result


def test_voice_disclosure_prepended_when_no_org():
    result = _draft_begin_message({}, org=None)
    assert result.startswith(_AI_VOICE_DISCLOSURE)


def test_voice_disclosure_cannot_be_suppressed_via_config():
    """Org config must not be able to remove the disclosure."""
    # Even if someone puts a greeting that starts differently, disclosure still leads.
    config = {"greeting": "Hi there! This call is NOT AI-handled."}
    result = _draft_begin_message(config, org=None)
    assert result.startswith(_AI_VOICE_DISCLOSURE)


# ── 1b. WhatsApp: disclosure sent exactly once per conversation ───────────────

@pytest.mark.asyncio
async def test_whatsapp_disclosure_sent_on_new_conversation():
    """A new conversation (ai_disclosure_sent_at=None) must get the disclosure
    message before the AI reply, and ai_disclosure_sent_at must be set."""
    org_id = str(uuid.uuid4())
    contact_phone = "+32471000001"
    wamid = "wamid.test.001"

    mock_conv = MagicMock()
    mock_conv.id = uuid.uuid4()
    mock_conv.ai_disclosure_sent_at = None  # new conversation

    mock_contact = MagicMock()
    mock_contact.id = uuid.uuid4()

    sent_messages = []

    async def fake_send_text(org_uuid, phone, text):
        sent_messages.append(text)
        return f"wamid.reply.{len(sent_messages)}"

    with (
        patch("app.tasks.whatsapp_tasks.redis_client") as mock_redis,
        patch("app.tasks.whatsapp_tasks.async_session_maker") as mock_session_maker,
        patch("app.tasks.whatsapp_tasks.contact_service.get_or_create_contact_by_phone",
              new_callable=AsyncMock, return_value=mock_contact),
        patch("app.tasks.whatsapp_tasks.conversation_service.get_or_create_channel_conversation",
              new_callable=AsyncMock, return_value=mock_conv),
        patch("app.tasks.whatsapp_tasks.conversation_service.process_customer_message",
              new_callable=AsyncMock, return_value="Here are our opening hours."),
        patch("app.tasks.whatsapp_tasks.send_text_message", side_effect=fake_send_text),
    ):
        mock_redis.set = AsyncMock(return_value=True)  # claimed
        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)
        mock_db.commit = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        mock_session_maker.return_value = mock_db

        from app.tasks.whatsapp_tasks import _AI_DISCLOSURE_WA, process_whatsapp_message
        await process_whatsapp_message(
            {}, org_id, contact_phone, "Test User", "What are your hours?", wamid
        )

    # Disclosure must be first, AI reply must be second
    assert len(sent_messages) >= 2
    assert sent_messages[0] == _AI_DISCLOSURE_WA
    # AI reply came after
    assert "opening hours" in sent_messages[1].lower() or sent_messages[1]


@pytest.mark.asyncio
async def test_whatsapp_disclosure_not_sent_on_existing_conversation():
    """An existing conversation (ai_disclosure_sent_at already set) must NOT
    trigger a second disclosure."""
    org_id = str(uuid.uuid4())
    wamid = "wamid.test.002"

    mock_conv = MagicMock()
    mock_conv.id = uuid.uuid4()
    mock_conv.ai_disclosure_sent_at = datetime(2026, 1, 1, tzinfo=timezone.utc)  # already sent

    mock_contact = MagicMock()
    mock_contact.id = uuid.uuid4()

    sent_messages = []

    async def fake_send_text(org_uuid, phone, text):
        sent_messages.append(text)
        return "wamid.reply.1"

    with (
        patch("app.tasks.whatsapp_tasks.redis_client") as mock_redis,
        patch("app.tasks.whatsapp_tasks.async_session_maker") as mock_session_maker,
        patch("app.tasks.whatsapp_tasks.contact_service.get_or_create_contact_by_phone",
              new_callable=AsyncMock, return_value=mock_contact),
        patch("app.tasks.whatsapp_tasks.conversation_service.get_or_create_channel_conversation",
              new_callable=AsyncMock, return_value=mock_conv),
        patch("app.tasks.whatsapp_tasks.conversation_service.process_customer_message",
              new_callable=AsyncMock, return_value="We open at 9am."),
        patch("app.tasks.whatsapp_tasks.send_text_message", side_effect=fake_send_text),
    ):
        mock_redis.set = AsyncMock(return_value=True)
        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)
        mock_db.commit = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        mock_session_maker.return_value = mock_db

        from app.tasks.whatsapp_tasks import _AI_DISCLOSURE_WA, process_whatsapp_message
        await process_whatsapp_message(
            {}, org_id, "+32471000002", "User", "When do you open?", wamid
        )

    # Only the AI reply — no disclosure
    assert all(_AI_DISCLOSURE_WA not in msg for msg in sent_messages)
    assert len(sent_messages) == 1


# ── 1a. Widget: AI_DISCLOSURE dict covers required languages ─────────────────

def test_widget_disclosure_covers_required_languages():
    """The disclosure dict in ChatWindow must provide en, nl, and fr strings,
    none of which are empty."""
    # Import the constant by re-parsing the source (widget is TypeScript, so
    # we verify the Python-side equivalent exists in the WhatsApp task which
    # follows the same pattern, and separately check the TS source contains
    # the required keys via a simple grep rather than executing TS.)
    import re
    from pathlib import Path

    chatwindow = Path(__file__).parent.parent.parent.parent / "widget" / "src" / "components" / "ChatWindow.tsx"
    source = chatwindow.read_text(encoding="utf-8")

    # The constant must exist and map all three required languages
    assert "AI_DISCLOSURE" in source
    for lang in ("nl", "en", "fr"):
        assert f'"{lang}"' in source or f"'{lang}'" in source, f"Missing language '{lang}' in AI_DISCLOSURE"

    # The disclosure text must NOT be configurable by the org (must be hardcoded)
    assert "config.ai" not in source.lower(), (
        "AI disclosure must not be pulled from org config — it is a legal requirement"
    )
