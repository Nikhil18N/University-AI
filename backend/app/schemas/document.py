"""Document upload/response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentUploadRequest(BaseModel):
    """Metadata submitted alongside a document upload."""

    title: str = Field(..., min_length=1, max_length=500)
    document_type: str = Field(..., min_length=1, max_length=100)
    department: str | None = None
    effective_date: datetime | None = None
    publication_date: datetime | None = None


class DocumentResponse(BaseModel):
    """Document metadata returned to the client."""

    id: UUID
    title: str
    document_type: str
    department: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    active_version: int | None = None
    chunk_count: int | None = None


class DocumentListResponse(BaseModel):
    """List of documents."""

    documents: list[DocumentResponse]
    total: int
