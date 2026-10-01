"""Chat request/response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Incoming chat message."""

    conversation_id: UUID | None = Field(
        None, description="Existing conversation ID, or null to start a new one"
    )
    session_id: str = Field(
        ..., min_length=1, max_length=64, description="Browser-generated session UUID"
    )
    message: str = Field(
        ..., min_length=1, max_length=4000, description="User message text"
    )


class SourceReference(BaseModel):
    """A source citation returned with RAG answers."""

    document_id: str
    title: str
    section: str | None = None
    page: int | None = None
    page_url: str | None = None
    department: str | None = None
    effective_date: str | None = None


class ChatResponse(BaseModel):
    """Response to a chat message."""

    conversation_id: UUID
    message_id: UUID
    answer: str
    sources: list[SourceReference] = Field(default_factory=list)
    model: str | None = None


class MessageResponse(BaseModel):
    """A single message in a conversation."""

    id: UUID
    role: str
    content: str
    sources: list[SourceReference] | None = None
    model: str | None = None
    created_at: datetime


class ConversationSummary(BaseModel):
    """Summary of a conversation for the sidebar."""

    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(BaseModel):
    """Full conversation with all messages."""

    id: UUID
    title: str
    messages: list[MessageResponse]
    created_at: datetime


class FeedbackRequest(BaseModel):
    """Feedback on an assistant response."""

    session_id: str = Field(..., min_length=1, max_length=64)
    conversation_id: UUID
    message_id: UUID
    rating: int = Field(..., ge=-1, le=1, description="1 for thumbs up, -1 for thumbs down")
    comment: str | None = Field(None, max_length=1000)


class FeedbackResponse(BaseModel):
    """Feedback submission confirmation."""

    id: UUID
    status: str = "received"
