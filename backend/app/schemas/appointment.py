import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AppointmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    contact_id: uuid.UUID
    contact_name: str
    channel: str
    conversation_id: uuid.UUID | None
    service_name: str
    start_time: datetime
    end_time: datetime
    status: str
    google_event_id: str | None
    notes: str | None


class AppointmentListResponse(BaseModel):
    appointments: list[AppointmentResponse]
