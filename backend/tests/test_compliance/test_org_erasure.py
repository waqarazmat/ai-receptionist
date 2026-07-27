"""Tests for GDPR Article 17 hard-delete (org erasure) and the erase endpoint."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from app.services.org_service import erase_organization


# ── Unit tests: erase_organization service function ──────────────────────────


@pytest.mark.asyncio
async def test_erase_organization_deletes_knowledge_chunks():
    """KnowledgeChunk rows (including pgvector embeddings) must be deleted."""
    executed_statements = []
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=lambda stmt: executed_statements.append(stmt))
    db.commit = AsyncMock()

    org_id = uuid.uuid4()
    await erase_organization(db, org_id)

    # Collect the string representations of what was executed
    statement_strs = [str(s) for s in executed_statements]

    # At least one statement must target knowledge_chunks
    assert any("knowledge_chunks" in s for s in statement_strs), (
        "erase_organization must DELETE from knowledge_chunks — "
        "deleting the row is the only way to remove the pgvector embedding"
    )


@pytest.mark.asyncio
async def test_erase_organization_deletes_in_fk_order():
    """Children must be deleted before parents to avoid FK violations.

    Required order (children first):
      escalations → appointments → messages → conversations → contacts
      → knowledge_chunks → knowledge_bases → channel_configs → org_api_keys
      → users (deactivated) → organization
    """
    table_sequence = []
    db = AsyncMock()

    def capture(stmt):
        s = str(stmt)
        for table in (
            "escalations", "appointments", "messages", "conversations",
            "contacts", "knowledge_chunks", "knowledge_bases",
            "channel_configs", "org_api_keys", "organizations",
        ):
            if table in s and table not in table_sequence:
                table_sequence.append(table)
        return MagicMock()

    db.execute = AsyncMock(side_effect=capture)
    db.commit = AsyncMock()

    await erase_organization(db, uuid.uuid4())

    # Verify children appear before parents
    def pos(t):
        return table_sequence.index(t) if t in table_sequence else -1

    assert pos("escalations") < pos("conversations"), "escalations must be deleted before conversations"
    assert pos("appointments") < pos("conversations"), "appointments must be deleted before conversations"
    assert pos("messages") < pos("conversations"), "messages must be deleted before conversations"
    assert pos("conversations") < pos("contacts"), "conversations must be deleted before contacts"
    assert pos("knowledge_chunks") < pos("knowledge_bases"), "knowledge_chunks must be deleted before knowledge_bases"
    assert pos("organizations") > pos("knowledge_bases"), "organization row must be deleted last"


@pytest.mark.asyncio
async def test_erase_organization_commits():
    """erase_organization must commit — a rollback would leave data intact."""
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock())
    db.commit = AsyncMock()

    await erase_organization(db, uuid.uuid4())

    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_erase_organization_deactivates_users_not_deletes():
    """Users must be deactivated (not deleted) to preserve audit_log FK refs."""
    executed_statements = []
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=lambda stmt: executed_statements.append(stmt))
    db.commit = AsyncMock()

    await erase_organization(db, uuid.uuid4())

    statement_strs = [str(s) for s in executed_statements]

    # There must NOT be a DELETE FROM users statement
    assert not any("DELETE" in s and "users" in s for s in statement_strs), (
        "Users must not be hard-deleted — audit_log has FK refs to users. "
        "Deactivate them (is_active=False, org_id=None) instead."
    )

    # There must be an UPDATE on users that sets is_active / org_id
    assert any("users" in s for s in statement_strs), (
        "erase_organization must update users to deactivate them"
    )


# ── Tests: confirm_name validation on the erase API endpoint ─────────────────


@pytest.mark.asyncio
async def test_erase_endpoint_returns_409_on_name_mismatch():
    """confirm_name mismatch must raise HTTP 409 before any deletion occurs.

    We test the route handler directly (bypassing the ASGI stack, which is
    wrapped by Socket.IO and can't hold dependency_overrides) by calling the
    handler function with mocked arguments.
    """
    from fastapi import HTTPException
    from app.api.super_admin.organizations import erase_organization as erase_handler
    from app.schemas.organization import OrgEraseRequest

    org_id = uuid.uuid4()
    mock_org = MagicMock()
    mock_org.id = org_id
    mock_org.name = "City Dental"

    mock_db = AsyncMock()
    mock_request = MagicMock()
    mock_request.client = None
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()

    body = OrgEraseRequest(confirm_name="WRONG NAME")

    with patch(
        "app.api.super_admin.organizations.org_service.get_organization",
        new_callable=AsyncMock, return_value=mock_org,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await erase_handler(
                org_id=org_id,
                body=body,
                request=mock_request,
                current_user=mock_user,
                db=mock_db,
            )

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT, (
        f"Expected 409 for name mismatch, got {exc_info.value.status_code}"
    )
