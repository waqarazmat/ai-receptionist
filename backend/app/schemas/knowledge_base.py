import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class WebsiteCrawlRequest(BaseModel):
    url: str
    knowledge_base_id: uuid.UUID | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        return value


class WebsiteCrawlResult(BaseModel):
    knowledge_base_id: uuid.UUID
    knowledge_base_name: str
    provider: str
    pages_crawled: int
    chunks_created: int
    replaced_chunks: int
    errors: list[str]


class ChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    title: str | None
    content: str
    source_url: str | None
    updated_at: datetime


class ChunkListResponse(BaseModel):
    knowledge_base_id: uuid.UUID | None
    knowledge_base_name: str | None
    chunks: list[ChunkResponse]


class ChunkCreateRequest(BaseModel):
    title: str | None = None
    content: str


class ChunkUpdateRequest(BaseModel):
    title: str | None = None
    content: str


class BulkImportRequest(BaseModel):
    """Bulk-import KB chunks from a plain text payload. Callers send CSV
    (one row per chunk) or Markdown (split on top-level headings). File
    parsing happens client-side; the API accepts plain text so this endpoint
    stays deterministic and testable without file-multipart machinery."""
    format: str  # "csv" | "markdown" | "text"
    content: str
    knowledge_base_id: uuid.UUID | None = None


class BulkImportResult(BaseModel):
    knowledge_base_id: uuid.UUID
    knowledge_base_name: str
    chunks_created: int
    errors: list[str] = []


class DocumentUploadResult(BaseModel):
    """Result of ingesting an uploaded PDF/DOCX/TXT/MD into the KB."""
    knowledge_base_id: uuid.UUID
    knowledge_base_name: str
    filename: str
    chunks_created: int
    errors: list[str] = []


class ClearKnowledgeBaseResult(BaseModel):
    chunks_deleted: int
