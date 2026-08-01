import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_db_session, require_super_admin
from app.channels.voice import retell_provisioner
from app.config import settings
from app.models.user import User
from app.schemas.organization import (
    OrgChannelStatusResponse,
    OrgEraseRequest,
    OrganizationCreate,
    OrganizationListResponse,
    OrganizationResponse,
    OrganizationUpdate,
)
from app.schemas.setup_wizard import VoiceConfigStep
from app.services import org_service, setup_wizard_service
from app.services.audit_service import log_action

router = APIRouter()


@router.get("/organizations", response_model=OrganizationListResponse)
async def list_organizations(db: AsyncSession = Depends(get_admin_db_session)) -> OrganizationListResponse:
    organizations = await org_service.list_organizations(db)
    return OrganizationListResponse(organizations=organizations)


@router.post("/organizations", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: OrganizationCreate,
    request: Request,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db_session),
) -> OrganizationResponse:
    org = await org_service.create_organization(db, body)
    await log_action(
        db,
        user_id=current_user.id,
        action="create_organization",
        target_type="organization",
        target_id=org.id,
        details={"name": org.name, "slug": org.slug},
        ip_address=request.client.host if request.client else None,
    )
    return org


@router.get("/organizations/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: uuid.UUID, db: AsyncSession = Depends(get_admin_db_session)
) -> OrganizationResponse:
    try:
        return await org_service.get_organization(db, org_id)
    except org_service.OrganizationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")


@router.get("/organizations/{org_id}/channels", response_model=OrgChannelStatusResponse)
async def get_organization_channel_status(
    org_id: uuid.UUID, db: AsyncSession = Depends(get_admin_db_session)
) -> OrgChannelStatusResponse:
    try:
        return await org_service.get_channel_status(db, org_id)
    except org_service.OrganizationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")


@router.post("/organizations/{org_id}/voice/provision")
async def reprovision_voice_agent(
    org_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db_session),
) -> dict:
    """Re-run Retell auto-provisioning for the org's saved agent. Useful after
    APP_PUBLIC_URL changes (e.g. switching from an ngrok tunnel to Railway) —
    the Test Center's "Re-provision Agent" button hits this."""
    try:
        channel_status = await org_service.get_channel_status(db, org_id)
    except org_service.OrganizationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    agent_id = channel_status.voice.retell_agent_id
    if not agent_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Retell Agent ID is configured for this organization.",
        )

    result: dict = {"retell_agent_id": agent_id, "provisioned": False}
    try:
        provision = await retell_provisioner.provision_agent(str(org_id), agent_id)
        result["provisioned"] = True
        result["llm_websocket_url"] = provision["llm_websocket_url"]
        result["webhook_url"] = provision["webhook_url"]
    except retell_provisioner.RetellProvisioningError as exc:
        result["warning"] = (
            f"Auto-configuration failed: {exc} "
            "You may need to manually set the Custom LLM URL in Retell's dashboard."
        )

    await log_action(
        db,
        user_id=current_user.id,
        action="voice.reprovision_agent",
        target_type="organization",
        target_id=org_id,
        details={"retell_agent_id": agent_id, "provisioned": result["provisioned"]},
        ip_address=request.client.host if request.client else None,
    )
    return result


@router.post("/organizations/{org_id}/voice/create-agent", status_code=status.HTTP_201_CREATED)
async def create_voice_agent(
    org_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db_session),
) -> dict:
    """Create a brand-new Retell agent already wired to this backend and save
    its id to the org's voice config. The Test Center's "Create New Agent"
    button hits this when a hand-made agent misbehaves and we'd rather own the
    full config."""
    try:
        org = await org_service.get_organization(db, org_id)
    except org_service.OrganizationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    try:
        created = await retell_provisioner.create_agent(str(org_id), org.name)
    except retell_provisioner.RetellProvisioningError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Could not create Retell agent: {exc}")

    agent_id = created["agent_id"]
    # Persist the new agent id to the org's voice config so calls route to it
    # and the Test Center shows it (a freshly-created custom-llm agent already
    # points at us, so it's provisioned on arrival).
    await setup_wizard_service.save_voice_config(db, org_id, VoiceConfigStep(retell_agent_id=agent_id))

    await log_action(
        db,
        user_id=current_user.id,
        action="voice.create_agent",
        target_type="organization",
        target_id=org_id,
        details={"retell_agent_id": agent_id, "agent_name": f"{org.name} - AI Receptionist"},
        ip_address=request.client.host if request.client else None,
    )

    return {
        "retell_agent_id": agent_id,
        "provisioned": True,
        "llm_websocket_url": created["llm_websocket_url"],
        "webhook_url": created["webhook_url"],
        "voice_id": retell_provisioner.DEFAULT_VOICE_ID,
    }


@router.post("/organizations/{org_id}/voice/web-call")
async def create_voice_web_call(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_admin_db_session),
    _: User = Depends(require_super_admin),
) -> dict:
    """Create a Retell web-call token for in-browser voice testing.

    Returns an access_token the frontend passes to the retell-client-js-sdk
    to start a browser call — no Retell dashboard login required, so any
    super admin can test regardless of whose Retell account is configured.
    """
    if not settings.RETELL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RETELL_API_KEY is not configured on this platform.",
        )

    try:
        channel_status = await org_service.get_channel_status(db, org_id)
    except org_service.OrganizationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    agent_id = channel_status.voice.retell_agent_id
    if not agent_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Retell agent configured for this organization.",
        )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.retellai.com/v2/create-web-call",
                headers={"Authorization": f"Bearer {settings.RETELL_API_KEY}"},
                json={"agent_id": agent_id},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Could not reach Retell API: {exc}")

    if resp.status_code not in (200, 201):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Retell API error ({resp.status_code}): {resp.text}",
        )

    data = resp.json()
    return {"access_token": data["access_token"], "call_id": data["call_id"]}


@router.put("/organizations/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: uuid.UUID,
    body: OrganizationUpdate,
    request: Request,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db_session),
) -> OrganizationResponse:
    try:
        org = await org_service.update_organization(db, org_id, body)
    except org_service.OrganizationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    await log_action(
        db,
        user_id=current_user.id,
        action="update_organization",
        target_type="organization",
        target_id=org.id,
        details=body.model_dump(exclude_unset=True),
        ip_address=request.client.host if request.client else None,
    )
    return org


@router.delete("/organizations/{org_id}", response_model=OrganizationResponse)
async def delete_organization(
    org_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db_session),
) -> OrganizationResponse:
    try:
        org = await org_service.delete_organization(db, org_id)
    except org_service.OrganizationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    await log_action(
        db,
        user_id=current_user.id,
        action="delete_organization",
        target_type="organization",
        target_id=org.id,
        ip_address=request.client.host if request.client else None,
    )
    return org


@router.delete("/organizations/{org_id}/erase", status_code=status.HTTP_204_NO_CONTENT)
async def erase_organization(
    org_id: uuid.UUID,
    body: OrgEraseRequest,
    request: Request,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db_session),
) -> None:
    """Irreversible GDPR Article 17 hard-erase. Deletes ALL data for this org
    including conversation history, messages, knowledge chunks (and their
    pgvector embeddings), contacts, and API keys.

    Requires the org's exact name in the request body as a confirmation guard.
    The erasure is recorded in the audit log (which is never erased) before
    any data is deleted, so the compliance record survives even if the caller
    disputes the action later.
    """
    try:
        org = await org_service.get_organization(db, org_id)
    except org_service.OrganizationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    if body.confirm_name != org.name:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"confirm_name '{body.confirm_name}' does not match organization name '{org.name}'.",
        )

    # Commit audit entry FIRST — must survive even if the delete fails.
    await log_action(
        db,
        user_id=current_user.id,
        action="org.hard_erase",
        target_type="organization",
        target_id=org_id,
        details={"org_name": org.name, "org_slug": org.slug},
        ip_address=request.client.host if request.client else None,
    )

    await org_service.erase_organization(db, org_id)
