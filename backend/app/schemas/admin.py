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
    question: str | None = None
    answer: str | None = None
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


class AdminMessageFeedback(BaseModel):
    id: UUID
    rating: int
    comment: str | None = None
    created_at: datetime


class AdminMessageDetail(BaseModel):
    id: UUID
    role: str
    content: str
    model: str | None = None
    sources: list[dict] | None = None
    feedback: AdminMessageFeedback | None = None
    created_at: datetime


class AdminConversationItem(BaseModel):
    id: UUID
    session_id: str
    title: str
    message_count: int
    user_message_count: int
    assistant_message_count: int
    positive_feedback_count: int
    negative_feedback_count: int
    created_at: datetime
    updated_at: datetime
    last_message_preview: str | None = None


class AdminConversationListResponse(BaseModel):
    conversations: list[AdminConversationItem]
    total: int
    page: int
    page_size: int


class AdminConversationDetailResponse(BaseModel):
    id: UUID
    session_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[AdminMessageDetail]


class PromoteExemplarRequest(BaseModel):
    message_id: UUID
    question: str
    answer: str


class PromoteExemplarResponse(BaseModel):
    success: bool
    message: str

