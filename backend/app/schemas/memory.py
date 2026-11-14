"""Schemas for consented memory and bounded conversation summaries."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


ALLOWED_MEMORY_KEYS = frozenset(
    {"preferred_program", "preferred_language", "hostel_interest", "transport_interest"}
)


class MemoryWriteRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64)
    key: str = Field(..., min_length=1, max_length=64)
    value: str = Field(..., min_length=1, max_length=255)
    consent: bool = Field(
        ..., description="Must be true; memory is never stored implicitly."
    )


class MemoryItem(BaseModel):
    id: UUID
    key: str
    value: str
    consented: bool
    updated_at: datetime


class MemoryDeleteRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64)


class ConversationSummaryResponse(BaseModel):
    conversation_id: UUID
    summary: str
    updated_at: datetime


class PendingAgentTaskResponse(BaseModel):
    conversation_id: UUID
    task_type: str
    original_query: str
    missing_inputs: list[str]
    status: str
    updated_at: datetime
