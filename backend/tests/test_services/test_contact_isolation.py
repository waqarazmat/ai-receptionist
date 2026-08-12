"""Regression tests for anonymous-caller contact isolation.

Guards against a data-leak bug where every voice call with no caller ID
(Retell web/test calls, or a withheld number) carried `from_number="unknown"`
and was matched to ONE shared "unknown" contact. Because the voice handler
persists an extracted caller name onto that contact, the first caller's name
(and history) then bled into the next anonymous caller's session — the AI
addressed a brand-new caller by the previous caller's name.

The fix: a caller with no usable caller ID gets a FRESH, unshared contact
(phone = NULL), never the shared "unknown" one.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import Channel
from app.services import contact_service


class TestIsAnonymousNumber:
    @pytest.mark.parametrize("value", ["", "unknown", "UNKNOWN", " Unknown ", "anonymous",
                                       "restricted", "private", "withheld", "blocked", None])
    def test_sentinels_are_anonymous(self, value):
        assert contact_service.is_anonymous_number(value) is True

    @pytest.mark.parametrize("value", ["+15551234567", "0304835964", "whatsapp:+1555", "441234567890"])
    def test_real_numbers_are_not_anonymous(self, value):
        assert contact_service.is_anonymous_number(value) is False


def _mock_db():
    db = MagicMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.mark.asyncio
class TestAnonymousContactIsolation:
    async def test_unknown_phone_never_matches_existing(self):
        """A sentinel phone must NOT run a match query — it goes straight to
        creating a fresh contact, so it can never reuse a shared 'unknown' one."""
        db = _mock_db()
        with patch("app.services.contact_service.uuid"):
            contact = await contact_service.get_or_create_contact_by_phone(
                db, MagicMock(), "unknown", Channel.voice
            )
        # No SELECT-to-match was issued for an anonymous caller.
        db.execute.assert_not_called()
        # A new row was added, with NO phone so it's unmatchable later.
        db.add.assert_called_once()
        added = db.add.call_args[0][0]
        assert added.phone is None
        assert added.name == "unknown"
        assert contact is added

    async def test_two_anonymous_callers_get_distinct_contacts(self):
        """Two separate anonymous calls must produce two different contacts —
        the core isolation guarantee that stops name/history bleed."""
        org_id = MagicMock()
        db1, db2 = _mock_db(), _mock_db()
        c1 = await contact_service.get_or_create_contact_by_phone(db1, org_id, "unknown", Channel.voice)
        c2 = await contact_service.get_or_create_contact_by_phone(db2, org_id, "unknown", Channel.voice)
        assert c1 is not c2
        assert c1.phone is None and c2.phone is None

    async def test_real_number_still_matches_existing_contact(self):
        """A real caller ID must still reuse their existing contact (repeat
        callers), so the fix doesn't break normal CRM linking."""
        db = _mock_db()
        existing = MagicMock(name="existing_contact")
        result = MagicMock()
        result.scalars.return_value.first.return_value = existing
        db.execute.return_value = result

        contact = await contact_service.get_or_create_contact_by_phone(
            db, MagicMock(), "+15551234567", Channel.voice
        )
        db.execute.assert_awaited_once()   # match query DID run
        db.add.assert_not_called()         # reused, not created
        assert contact is existing
