"""Tests for EmailService and send_otp_email.

The SMTP transport is always mocked — these tests never open a real socket.
"""

from email.mime.multipart import MIMEMultipart
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.utils.email import EmailDeliveryError, EmailService, send_otp_email


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_settings(**overrides):
    """Return a settings mock with all SMTP fields set to valid defaults.

    Fallback fields are explicitly None so _fallback_provider() returns None
    unless a test deliberately sets them via _mock_settings_with_fallback().
    MagicMock returns a truthy object for any unset attribute, which would
    make _fallback_provider() think a fallback is configured when it isn't.
    """
    defaults = dict(
        SMTP_HOST="smtp.example.com",
        SMTP_PORT=587,
        SMTP_USERNAME="user@example.com",
        SMTP_PASSWORD="secret",
        SMTP_FROM_ADDRESS="noreply@example.com",
        SMTP_FROM_NAME="Test Platform",
        SMTP_USE_TLS=True,
        # Fallback explicitly disabled
        SMTP_HOST_FALLBACK=None,
        SMTP_PORT_FALLBACK=587,
        SMTP_USERNAME_FALLBACK=None,
        SMTP_PASSWORD_FALLBACK=None,
        SMTP_FROM_ADDRESS_FALLBACK=None,
    )
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _mock_settings_with_fallback(**primary_overrides):
    """Settings mock with both primary and fallback providers configured."""
    mock = _mock_settings(**primary_overrides)
    mock.SMTP_HOST_FALLBACK = "smtp.fallback.example.com"
    mock.SMTP_PORT_FALLBACK = 587
    mock.SMTP_USERNAME_FALLBACK = "fallback_user"
    mock.SMTP_PASSWORD_FALLBACK = "fallback_secret"
    mock.SMTP_FROM_ADDRESS_FALLBACK = "noreply-fallback@example.com"
    return mock


# ── send_otp_email ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_otp_email_addresses_correct_recipient():
    """The To header must match the recipient passed to send_otp_email."""
    captured: list[MIMEMultipart] = []

    with (
        patch("app.utils.email.aiosmtplib.send", AsyncMock(
            side_effect=lambda msg, **kw: captured.append(msg)
        )),
        patch("app.utils.email.settings", _mock_settings()),
    ):
        await send_otp_email("alice@example.com", "123456")

    assert len(captured) == 1
    assert captured[0]["To"] == "alice@example.com"


@pytest.mark.asyncio
async def test_send_otp_email_embeds_code_in_both_parts():
    """Both the HTML and plain-text parts must contain the OTP code."""
    captured: list[MIMEMultipart] = []

    with (
        patch("app.utils.email.aiosmtplib.send", AsyncMock(
            side_effect=lambda msg, **kw: captured.append(msg)
        )),
        patch("app.utils.email.settings", _mock_settings()),
    ):
        await send_otp_email("bob@example.com", "987654")

    parts = captured[0].get_payload()
    decoded = [p.get_payload(decode=True).decode("utf-8") for p in parts]
    assert all("987654" in part for part in decoded), (
        "OTP code must appear in every MIME part (plain-text and HTML)"
    )


@pytest.mark.asyncio
async def test_send_otp_email_subject():
    """Subject line must be the standard 'Your verification code'."""
    captured: list[MIMEMultipart] = []

    with (
        patch("app.utils.email.aiosmtplib.send", AsyncMock(
            side_effect=lambda msg, **kw: captured.append(msg)
        )),
        patch("app.utils.email.settings", _mock_settings()),
    ):
        await send_otp_email("carol@example.com", "000000")

    assert captured[0]["Subject"] == "Your verification code"


@pytest.mark.asyncio
async def test_send_otp_email_uses_correct_smtp_credentials():
    """aiosmtplib.send must be called with the settings values."""
    smtp_calls: list[dict] = []

    with (
        patch("app.utils.email.aiosmtplib.send", AsyncMock(
            side_effect=lambda msg, **kw: smtp_calls.append(kw)
        )),
        patch("app.utils.email.settings", _mock_settings(
            SMTP_HOST="smtp.mailgun.org",
            SMTP_PORT=587,
            SMTP_USERNAME="mg_user",
            SMTP_PASSWORD="mg_pass",
        )),
    ):
        await send_otp_email("dave@example.com", "111222")

    assert smtp_calls[0]["hostname"] == "smtp.mailgun.org"
    assert smtp_calls[0]["port"] == 587
    assert smtp_calls[0]["username"] == "mg_user"
    assert smtp_calls[0]["password"] == "mg_pass"


# ── EmailService — retry logic ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_email_retries_on_transient_failure():
    """A transient SMTPException on the first attempt must trigger a retry."""
    import aiosmtplib

    call_count = 0

    async def flaky_send(msg, **kw):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise aiosmtplib.SMTPException("temporary relay error")

    with (
        patch("app.utils.email.aiosmtplib.send", side_effect=flaky_send),
        patch("app.utils.email.settings", _mock_settings()),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        svc = EmailService()
        await svc.send_email("eve@example.com", "Test", "<p>Hi</p>")

    assert call_count == 2, "Should have succeeded on the second attempt"


@pytest.mark.asyncio
async def test_send_email_raises_after_all_retries_exhausted():
    """When all three attempts fail, EmailDeliveryError must be raised."""
    import aiosmtplib

    async def always_fail(msg, **kw):
        raise aiosmtplib.SMTPException("relay down")

    with (
        patch("app.utils.email.aiosmtplib.send", side_effect=always_fail),
        patch("app.utils.email.settings", _mock_settings()),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        svc = EmailService()
        with pytest.raises(EmailDeliveryError, match="failed after"):
            await svc.send_email("frank@example.com", "Test", "<p>Hi</p>")


@pytest.mark.asyncio
async def test_auth_failure_is_not_retried():
    """SMTPAuthenticationError must raise immediately — retrying would just
    lock the account on the relay side."""
    import aiosmtplib

    call_count = 0

    async def auth_fail(msg, **kw):
        nonlocal call_count
        call_count += 1
        raise aiosmtplib.SMTPAuthenticationError(535, "authentication failed")

    with (
        patch("app.utils.email.aiosmtplib.send", side_effect=auth_fail),
        patch("app.utils.email.settings", _mock_settings()),
    ):
        svc = EmailService()
        with pytest.raises(EmailDeliveryError, match="authentication failed"):
            await svc.send_email("grace@example.com", "Test", "<p>Hi</p>")

    assert call_count == 1, "Auth failures must not be retried"


# ── EmailService — misconfiguration guard ─────────────────────────────────────

@pytest.mark.asyncio
async def test_send_email_raises_when_smtp_not_configured():
    """If SMTP_HOST or SMTP_FROM_ADDRESS is missing, fail fast with a clear
    error rather than a cryptic connection refused."""
    svc = EmailService()

    with patch("app.utils.email.settings", _mock_settings(SMTP_HOST=None)):
        with pytest.raises(EmailDeliveryError, match="not configured"):
            await svc.send_email("henry@example.com", "Test", "<p>Hi</p>")

    with patch("app.utils.email.settings", _mock_settings(SMTP_FROM_ADDRESS=None)):
        with pytest.raises(EmailDeliveryError, match="not configured"):
            await svc.send_email("ivan@example.com", "Test", "<p>Hi</p>")


# ── EmailService — template rendering ─────────────────────────────────────────

def test_render_otp_template_contains_code():
    """The OTP template must interpolate the otp_code variable."""
    svc = EmailService()
    html = svc.render("otp.html", otp_code="555666")
    assert "555666" in html


def test_render_missing_template_raises():
    """Asking for a nonexistent template must raise EmailDeliveryError, not
    a raw Jinja2 TemplateNotFound."""
    svc = EmailService()
    with pytest.raises(EmailDeliveryError, match="not found"):
        svc.render("does_not_exist.html")


# ── EmailService — failover ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fallback_used_when_primary_exhausts_retries():
    """After the primary exhausts all retries, the fallback must be tried and
    the send must succeed.  The success log must carry provider='fallback'."""
    import aiosmtplib

    call_hosts: list[str] = []

    async def route_by_host(msg, **kw):
        hostname = kw["hostname"]
        call_hosts.append(hostname)
        if hostname == "smtp.example.com":
            raise aiosmtplib.SMTPException("primary down")

    log_events: list[dict] = []

    with (
        patch("app.utils.email.aiosmtplib.send", side_effect=route_by_host),
        patch("app.utils.email.settings", _mock_settings_with_fallback()),
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch("app.utils.email.logger") as mock_logger,
    ):
        mock_logger.info = MagicMock(side_effect=lambda ev, **kw: log_events.append({"event": ev, **kw}))
        mock_logger.warning = MagicMock()
        mock_logger.error = MagicMock()

        svc = EmailService()
        await svc.send_email("zara@example.com", "Test", "<p>Hi</p>")

    assert call_hosts.count("smtp.example.com") == 3
    assert call_hosts.count("smtp.fallback.example.com") == 1

    success_events = [e for e in log_events if e["event"] == "email_sent"]
    assert len(success_events) == 1
    assert success_events[0]["provider"] == "fallback"


@pytest.mark.asyncio
async def test_fallback_used_when_primary_auth_fails():
    """An auth failure on the primary must also trigger the fallback (the
    fallback has different credentials, so it may succeed)."""
    import aiosmtplib

    call_hosts: list[str] = []

    async def route_by_host(msg, **kw):
        hostname = kw["hostname"]
        call_hosts.append(hostname)
        if hostname == "smtp.example.com":
            raise aiosmtplib.SMTPAuthenticationError(535, "bad credentials")

    log_events: list[dict] = []

    with (
        patch("app.utils.email.aiosmtplib.send", side_effect=route_by_host),
        patch("app.utils.email.settings", _mock_settings_with_fallback()),
        patch("app.utils.email.logger") as mock_logger,
    ):
        mock_logger.info = MagicMock(side_effect=lambda ev, **kw: log_events.append({"event": ev, **kw}))
        mock_logger.warning = MagicMock()
        mock_logger.error = MagicMock()

        svc = EmailService()
        await svc.send_email("yusuf@example.com", "Test", "<p>Hi</p>")

    assert call_hosts.count("smtp.example.com") == 1
    assert call_hosts.count("smtp.fallback.example.com") == 1

    success_events = [e for e in log_events if e["event"] == "email_sent"]
    assert len(success_events) == 1
    assert success_events[0]["provider"] == "fallback"


@pytest.mark.asyncio
async def test_raises_when_both_providers_fail():
    """If both the primary (all retries) and the fallback fail, EmailDeliveryError
    must be raised — not silently swallowed."""
    import aiosmtplib

    async def always_fail(msg, **kw):
        raise aiosmtplib.SMTPException(f"{kw['hostname']} is down")

    with (
        patch("app.utils.email.aiosmtplib.send", side_effect=always_fail),
        patch("app.utils.email.settings", _mock_settings_with_fallback()),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        svc = EmailService()
        with pytest.raises(EmailDeliveryError, match="Both SMTP providers failed"):
            await svc.send_email("xander@example.com", "Test", "<p>Hi</p>")
