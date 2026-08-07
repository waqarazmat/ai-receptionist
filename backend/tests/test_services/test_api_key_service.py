"""Unit tests for per-org (tenant-isolated) API key resolution.

Covers the isolation contract: an org's own key is always preferred; the
platform key is used ONLY when ALLOW_PLATFORM_KEY_FALLBACK is on; under strict
isolation an org with no key resolves to None (caller degrades, never borrows).
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import ApiKeyProvider
from app.services import api_key_service


def _db_returning(row):
    """A mock AsyncSession whose single .execute().scalar_one_or_none() == row."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    return db


def _settings(**over):
    base = dict(
        ALLOW_PLATFORM_KEY_FALLBACK=True,
        GROQ_API_KEY=None,
        OPENAI_API_KEY=None,
        DEEPGRAM_API_KEY=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


class TestGetOrgApiKey:
    @pytest.mark.asyncio
    async def test_returns_decrypted_org_key(self):
        row = MagicMock(encrypted_key="enc-blob")
        db = _db_returning(row)
        with patch("app.services.api_key_service.decrypt_api_key", return_value="org-key") as dec:
            key = await api_key_service.get_org_api_key(db, uuid.uuid4(), ApiKeyProvider.groq)
        assert key == "org-key"
        dec.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_org_has_no_row(self):
        db = _db_returning(None)
        key = await api_key_service.get_org_api_key(db, uuid.uuid4(), ApiKeyProvider.groq)
        assert key is None


class TestResolveProviderKey:
    @pytest.mark.asyncio
    async def test_org_key_preferred_over_platform(self):
        """Even with a platform key set, the org's own key wins — no sharing."""
        db = _db_returning(MagicMock(encrypted_key="enc"))
        with patch("app.services.api_key_service.decrypt_api_key", return_value="org-groq-key"), \
             patch("app.services.api_key_service.settings", _settings(GROQ_API_KEY="PLATFORM")):
            key = await api_key_service.resolve_provider_key(db, uuid.uuid4(), "groq")
        assert key == "org-groq-key"

    @pytest.mark.asyncio
    async def test_platform_fallback_used_when_allowed_and_no_org_key(self):
        db = _db_returning(None)
        with patch("app.services.api_key_service.settings", _settings(GROQ_API_KEY="PLATFORM-GROQ")):
            key = await api_key_service.resolve_provider_key(db, uuid.uuid4(), "groq")
        assert key == "PLATFORM-GROQ"

    @pytest.mark.asyncio
    async def test_strict_isolation_returns_none_when_no_org_key(self):
        """ALLOW_PLATFORM_KEY_FALLBACK off → an unconfigured org gets None, never
        the shared platform key."""
        db = _db_returning(None)
        with patch("app.services.api_key_service.settings",
                   _settings(GROQ_API_KEY="PLATFORM-GROQ", ALLOW_PLATFORM_KEY_FALLBACK=False)):
            key = await api_key_service.resolve_provider_key(db, uuid.uuid4(), "groq")
        assert key is None

    @pytest.mark.asyncio
    async def test_openai_provider_maps_to_openai_platform_key(self):
        db = _db_returning(None)
        with patch("app.services.api_key_service.settings", _settings(OPENAI_API_KEY="PLATFORM-OPENAI")):
            key = await api_key_service.resolve_provider_key(db, uuid.uuid4(), "openai")
        assert key == "PLATFORM-OPENAI"

    @pytest.mark.asyncio
    async def test_deepgram_provider_maps_to_deepgram_platform_key(self):
        db = _db_returning(None)
        with patch("app.services.api_key_service.settings", _settings(DEEPGRAM_API_KEY="PLATFORM-DG")):
            key = await api_key_service.resolve_provider_key(db, uuid.uuid4(), "deepgram")
        assert key == "PLATFORM-DG"

    @pytest.mark.asyncio
    async def test_unknown_provider_returns_none(self):
        db = _db_returning(None)
        with patch("app.services.api_key_service.settings", _settings(GROQ_API_KEY="X")):
            key = await api_key_service.resolve_provider_key(db, uuid.uuid4(), "nonsense")
        assert key is None

    @pytest.mark.asyncio
    async def test_no_org_key_and_no_platform_key_returns_none(self):
        db = _db_returning(None)
        with patch("app.services.api_key_service.settings", _settings()):  # all keys None
            key = await api_key_service.resolve_provider_key(db, uuid.uuid4(), "groq")
        assert key is None
