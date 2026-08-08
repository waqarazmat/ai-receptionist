import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_db_session, require_super_admin
from app.channels.voice import retell_provisioner
from app.models.user import User
from app.schemas.knowledge_base import (
    BulkImportRequest,
    BulkImportResult,
    ClearKnowledgeBaseResult,
    DocumentUploadResult,
    WebsiteCrawlRequest,
    WebsiteCrawlResult,
)
from app.schemas.organization import OrganizationResponse
from app.schemas.setup_wizard import (
    ApiKeysStep,
    BasicInfoStep,
    BookingConfigStep,
    ChannelConfigStep,
    KnowledgeBaseStep,
    SetupStateResponse,
    StaffAccessStep,
    SystemPromptsStep,
    VoiceConfigStep,
    WhatsappConfigStep,
    WorkingHoursStep,
)
from app.services import knowledge_base_service, org_service, setup_wizard_service
from app.services.audit_service import log_action

router = APIRouter()


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _domain_from_url(url: str) -> str:
    netloc = urlparse(url).netloc
    return netloc[4:] if netloc.startswith("www.") else netloc


async def _run_website_crawl(
    db: AsyncSession,
    org_id: uuid.UUID,
    kb_id: uuid.UUID,
    kb_name: str,
    url: str,
) -> WebsiteCrawlResult:
    import_result = await knowledge_base_service.import_from_website(db, org_id, kb_id, url)
    return WebsiteCrawlResult(
        knowledge_base_id=kb_id,
        knowledge_base_name=kb_name,
        **import_result,
    )


@router.get("/organizations/{org_id}/setup", response_model=SetupStateResponse)
async def get_setup_state(
    org_id: uuid.UUID, db: AsyncSession = Depends(get_admin_db_session)
) -> SetupStateResponse:
    try:
        return await setup_wizard_service.get_setup_state(db, org_id)
    except org_service.OrganizationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")


@router.put("/organizations/{org_id}/setup/basic-info", response_model=OrganizationResponse)
async def save_basic_info(
    org_id: uuid.UUID,
    body: BasicInfoStep,
    request: Request,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db_session),
) -> OrganizationResponse:
    org = await setup_wizard_service.save_basic_info(db, org_id, body)
    await log_action(
        db,
        user_id=current_user.id,
        action="setup_wizard.basic_info",
        target_type="organization",
        target_id=org_id,
        details=body.model_dump(),
        ip_address=_client_ip(request),
    )
    return org


@router.put("/organizations/{org_id}/setup/working-hours", response_model=OrganizationResponse)
async def save_working_hours(
    org_id: uuid.UUID,
    body: WorkingHoursStep,
    request: Request,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db_session),
) -> OrganizationResponse:
    org = await setup_wizard_service.save_working_hours(db, org_id, body)
    await log_action(
        db,
        user_id=current_user.id,
        action="setup_wizard.working_hours",
        target_type="organization",
        target_id=org_id,
        details=body.model_dump(mode="json"),
        ip_address=_client_ip(request),
    )
    return org


@router.put("/organizations/{org_id}/setup/channels", response_model=OrganizationResponse)
async def save_channels(
    org_id: uuid.UUID,
    body: ChannelConfigStep,
    request: Request,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db_session),
) -> OrganizationResponse:
    org = await setup_wizard_service.save_channels(db, org_id, body)
    await log_action(
        db,
        user_id=current_user.id,
        action="setup_wizard.channels",
        target_type="organization",
        target_id=org_id,
        details=body.model_dump(),
        ip_address=_client_ip(request),
    )
    return org


@router.post("/organizations/{org_id}/setup/api-keys", status_code=status.HTTP_201_CREATED)
async def save_api_key(
    org_id: uuid.UUID,
    body: ApiKeysStep,
    request: Request,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db_session),
) -> dict:
    key_row = await setup_wizard_service.save_api_key(db, org_id, body)
    # Never log the plaintext or encrypted key — only which provider was configured.
    await log_action(
        db,
        user_id=current_user.id,
        action="setup_wizard.api_key",
        target_type="organization",
        target_id=org_id,
        details={"provider": body.provider.value},
        ip_address=_client_ip(request),
    )
    return {"provider": key_row.provider.value, "is_active": key_row.is_active}


@router.put("/organizations/{org_id}/setup/whatsapp-config")
async def save_whatsapp_config(
    org_id: uuid.UUID,
    body: WhatsappConfigStep,
    request: Request,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db_session),
) -> dict:
    config = await setup_wizard_service.save_whatsapp_config(db, org_id, body)
    # phone_number and phone_number_id are both non-secret Meta routing values,
    # safe to log (unlike access tokens, which go through the api-keys path).
    await log_action(
        db,
        user_id=current_user.id,
        action="setup_wizard.whatsapp_config",
        target_type="organization",
        target_id=org_id,
        details={"phone_number": body.phone_number, "phone_number_id": body.phone_number_id},
        ip_address=_client_ip(request),
    )
    return {
        "phone_number": config.config.get("phone_number"),
        "phone_number_id": config.config.get("phone_number_id"),
    }


@router.put("/organizations/{org_id}/setup/voice-config")
async def save_voice_config(
    org_id: uuid.UUID,
    body: VoiceConfigStep,
    request: Request,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db_session),
) -> dict:
    config = await setup_wizard_service.save_voice_config(db, org_id, body)
    agent_id = config.config.get("retell_agent_id")
    await log_action(
        db,
        user_id=current_user.id,
        action="setup_wizard.voice_config",
        target_type="organization",
        target_id=org_id,
        details={"retell_agent_id": agent_id},
        ip_address=_client_ip(request),
    )

    # Auto-configure the agent in Retell so the super admin never touches
    # Retell's dashboard. Provisioning failure is non-fatal: the agent id is
    # already saved above; we just warn so it can be set by hand if needed.
    org = await org_service.get_organization(db, org_id)
    keywords = await knowledge_base_service.build_boosted_keywords(db, org_id, org.name)
    result: dict = {"retell_agent_id": agent_id, "provisioned": False}
    try:
        provision = await retell_provisioner.provision_agent(str(org_id), agent_id, boosted_keywords=keywords)
        result["provisioned"] = True
        result["llm_websocket_url"] = provision["llm_websocket_url"]
        result["webhook_url"] = provision["webhook_url"]
    except retell_provisioner.RetellProvisioningError as exc:
        result["warning"] = (
            f"Agent ID saved but auto-configuration failed: {exc} "
            "You may need to manually set the Custom LLM URL in Retell's dashboard."
        )
    return result


@router.put("/organizations/{org_id}/setup/knowledge-base", response_model=OrganizationResponse)
async def save_knowledge_base(
    org_id: uuid.UUID,
    body: KnowledgeBaseStep,
    request: Request,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db_session),
) -> OrganizationResponse:
    org = await setup_wizard_service.save_knowledge_base(db, org_id, body)
    await log_action(
        db,
        user_id=current_user.id,
        action="setup_wizard.knowledge_base",
        target_type="organization",
        target_id=org_id,
        details={"name": body.name, "chunk_count": len(body.chunks)},
        ip_address=_client_ip(request),
    )
    return org


@router.delete(
    "/organizations/{org_id}/setup/knowledge-base/chunks", response_model=ClearKnowledgeBaseResult
)
async def clear_knowledge_base_wizard(
    org_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db_session),
) -> ClearKnowledgeBaseResult:
    """Delete ALL knowledge chunks for an org (manual, crawled, and uploaded).
    Destructive and not reversible — the UI confirms first. Audit-logged."""
    try:
        await org_service.get_organization(db, org_id)
    except org_service.OrganizationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    deleted = await knowledge_base_service.clear_knowledge_base(db, org_id)

    await log_action(
        db,
        user_id=current_user.id,
        action="setup_wizard.knowledge_base_clear",
        target_type="organization",
        target_id=org_id,
        details={"chunks_deleted": deleted},
        ip_address=_client_ip(request),
    )
    return ClearKnowledgeBaseResult(chunks_deleted=deleted)


_MAX_DOC_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB — plenty for a clinic's docs


@router.post("/organizations/{org_id}/setup/knowledge-base/upload", response_model=DocumentUploadResult)
async def upload_knowledge_base_document(
    org_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db_session),
) -> DocumentUploadResult:
    """Ingest an uploaded PDF/DOCX/TXT/MD into the org's knowledge base: extract
    text, chunk it, embed, and ADD the chunks (existing ones are kept)."""
    try:
        await org_service.get_organization(db, org_id)
    except org_service.OrganizationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    filename = file.filename or "document"
    if not filename.lower().endswith(knowledge_base_service.SUPPORTED_DOC_EXTENSIONS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Upload a PDF, DOCX, TXT, or MD file.",
        )
    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The file is empty.")
    if len(data) > _MAX_DOC_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large (max {_MAX_DOC_UPLOAD_BYTES // (1024 * 1024)} MB).",
        )

    kb = await knowledge_base_service.get_or_create_org_knowledge_base(db, org_id)
    result = await knowledge_base_service.ingest_document(db, org_id, kb.id, filename, data)

    if result["chunks_created"] > 0:
        org = await org_service.get_organization(db, org_id)
        org.setup_progress = {**(org.setup_progress or {}), "knowledge_base": True}
        await db.commit()

    await log_action(
        db,
        user_id=current_user.id,
        action="setup_wizard.knowledge_base_upload",
        target_type="organization",
        target_id=org_id,
        details={"filename": filename, **result},
        ip_address=_client_ip(request),
    )
    return DocumentUploadResult(
        knowledge_base_id=kb.id,
        knowledge_base_name=kb.name,
        filename=filename,
        chunks_created=result["chunks_created"],
        errors=result["errors"],
    )


@router.post("/organizations/{org_id}/setup/knowledge-base/crawl", response_model=WebsiteCrawlResult)
async def crawl_knowledge_base_wizard(
    org_id: uuid.UUID,
    body: WebsiteCrawlRequest,
    request: Request,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db_session),
) -> WebsiteCrawlResult:
    try:
        await org_service.get_organization(db, org_id)
    except org_service.OrganizationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    if body.knowledge_base_id is None:
        kb = await knowledge_base_service.create_knowledge_base(db, org_id, f"Website - {_domain_from_url(body.url)}")
    else:
        try:
            kb = await knowledge_base_service.get_knowledge_base(db, org_id, body.knowledge_base_id)
        except knowledge_base_service.KnowledgeBaseNotFoundError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")

    result = await _run_website_crawl(db, org_id, kb.id, kb.name, body.url)

    if result.chunks_created > 0:
        org = await org_service.get_organization(db, org_id)
        org.setup_progress = {**(org.setup_progress or {}), "knowledge_base": True}
        await db.commit()

    await log_action(
        db,
        user_id=current_user.id,
        action="setup_wizard.knowledge_base_crawl",
        target_type="organization",
        target_id=org_id,
        details=result.model_dump(mode="json"),
        ip_address=_client_ip(request),
    )
    return result


@router.post(
    "/organizations/{org_id}/knowledge-base/import",
    response_model=BulkImportResult,
    status_code=status.HTTP_201_CREATED,
)
async def bulk_import_knowledge_base(
    org_id: uuid.UUID,
    body: BulkImportRequest,
    request: Request,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db_session),
) -> BulkImportResult:
    """Bulk-import KB chunks from a text payload (CSV / Markdown / plain text).

    Client-side parses the uploaded file (PDF/CSV/MD) into a text string and
    POSTs it here. Keeps this endpoint deterministic and heavy parsing deps
    (pypdf, etc.) out of the backend."""
    try:
        await org_service.get_organization(db, org_id)
    except org_service.OrganizationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    if body.knowledge_base_id is None:
        kb = await knowledge_base_service.get_or_create_org_knowledge_base(db, org_id)
    else:
        try:
            kb = await knowledge_base_service.get_knowledge_base(db, org_id, body.knowledge_base_id)
        except knowledge_base_service.KnowledgeBaseNotFoundError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")

    result = await knowledge_base_service.bulk_import_chunks(
        db, org_id, kb.id, body.format, body.content
    )
    if result["chunks_created"] > 0:
        org = await org_service.get_organization(db, org_id)
        org.setup_progress = {**(org.setup_progress or {}), "knowledge_base": True}
        await db.commit()

    await log_action(
        db,
        user_id=current_user.id,
        action="knowledge_base.bulk_import",
        target_type="knowledge_base",
        target_id=kb.id,
        details={"format": body.format, "chunks_created": result["chunks_created"]},
        ip_address=_client_ip(request),
    )
    return BulkImportResult(
        knowledge_base_id=kb.id,
        knowledge_base_name=kb.name,
        chunks_created=result["chunks_created"],
        errors=result.get("errors", []),
    )


@router.post("/organizations/{org_id}/knowledge-base/{kb_id}/crawl", response_model=WebsiteCrawlResult)
async def crawl_knowledge_base(
    org_id: uuid.UUID,
    kb_id: uuid.UUID,
    body: WebsiteCrawlRequest,
    request: Request,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db_session),
) -> WebsiteCrawlResult:
    try:
        kb = await knowledge_base_service.get_knowledge_base(db, org_id, kb_id)
    except knowledge_base_service.KnowledgeBaseNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")

    result = await _run_website_crawl(db, org_id, kb.id, kb.name, body.url)

    await log_action(
        db,
        user_id=current_user.id,
        action="knowledge_base.crawl",
        target_type="knowledge_base",
        target_id=kb_id,
        details=result.model_dump(mode="json"),
        ip_address=_client_ip(request),
    )
    return result


@router.put("/organizations/{org_id}/setup/booking", response_model=OrganizationResponse)
async def save_booking_config(
    org_id: uuid.UUID,
    body: BookingConfigStep,
    request: Request,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db_session),
) -> OrganizationResponse:
    org = await setup_wizard_service.save_booking_config(db, org_id, body)
    await log_action(
        db,
        user_id=current_user.id,
        action="setup_wizard.booking",
        target_type="organization",
        target_id=org_id,
        details=body.model_dump(),
        ip_address=_client_ip(request),
    )
    return org


@router.put("/organizations/{org_id}/setup/system-prompts", response_model=OrganizationResponse)
async def save_system_prompts(
    org_id: uuid.UUID,
    body: SystemPromptsStep,
    request: Request,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db_session),
) -> OrganizationResponse:
    org = await setup_wizard_service.save_system_prompts(db, org_id, body)
    await log_action(
        db,
        user_id=current_user.id,
        action="setup_wizard.system_prompts",
        target_type="organization",
        target_id=org_id,
        details=body.model_dump(),
        ip_address=_client_ip(request),
    )
    return org


@router.put("/organizations/{org_id}/setup/staff")
async def save_staff(
    org_id: uuid.UUID,
    body: StaffAccessStep,
    request: Request,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db_session),
) -> dict:
    users = await setup_wizard_service.save_staff(db, org_id, body)
    await log_action(
        db,
        user_id=current_user.id,
        action="setup_wizard.staff",
        target_type="organization",
        target_id=org_id,
        details={"emails": body.emails},
        ip_address=_client_ip(request),
    )
    return {"emails": [u.email for u in users]}


@router.post("/organizations/{org_id}/setup/activate", response_model=OrganizationResponse)
async def activate_organization(
    org_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db_session),
) -> OrganizationResponse:
    try:
        org = await org_service.activate_organization(db, org_id)
    except org_service.OrganizationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    except org_service.OrganizationNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await log_action(
        db,
        user_id=current_user.id,
        action="setup_wizard.activate",
        target_type="organization",
        target_id=org_id,
        ip_address=_client_ip(request),
    )
    return org
