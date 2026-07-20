import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EscalationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    conversation_id: uuid.UUID
    contact_name: str
    reason: str
    priority: str
    status: str
    assigned_to: uuid.UUID | None
    created_at: datetime
    resolved_at: datetime | None


class EscalationListResponse(BaseModel):
    escalations: list[EscalationResponse]
