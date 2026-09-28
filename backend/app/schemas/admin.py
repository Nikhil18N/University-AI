"""Admin dashboard schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class FeedbackItem(BaseModel):
    id: UUID
    session_id: str
    conversation_id: UUID
    message_id: UUID
    rating: int
    comment: str | None = None
    created_at: datetime


class FeedbackListResponse(BaseModel):
    items: list[FeedbackItem]
    total: int


class AdminStatsResponse(BaseModel):
    total_documents: int
    active_documents: int
    total_conversations: int
    total_messages: int
    positive_feedback: int
    negative_feedback: int
