"""Chat request/response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field
from app.security import SESSION_ID_PATTERN


class ChatRequest(BaseModel):
    """Incoming chat message."""

    conversation_id: UUID | None = Field(
        None, description="Existing conversation ID, or null to start a new one"
    )
    session_id: str = Field(
        ..., min_length=16, max_length=64, pattern=SESSION_ID_PATTERN, description="Browser-generated session UUID"
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
    message_id: UUID | None = None
    answer: str
    sources: list[SourceReference] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    cards: list[dict] = Field(default_factory=list)
    flow: dict | None = None
    agent: dict | None = None
    model: str | None = None


class MessageResponse(BaseModel):
    """A single message in a conversation."""

    id: UUID
    role: str
    content: str
    sources: list[SourceReference] | None = None
    suggestions: list[str] = Field(default_factory=list)
    cards: list[dict] = Field(default_factory=list)
    flow: dict | None = None
    agent: dict | None = None
    # v4.17.1: the student edited this message / replied to an earlier message (its id)
    edited: bool = False
    reply_to: str | None = None
    # how the student sent it ("typed" / "button") and whether it started an admissions request (not editable)
    source: str | None = None
    action_done: bool = False
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

    session_id: str = Field(..., min_length=16, max_length=64, pattern=SESSION_ID_PATTERN)
    conversation_id: UUID
    message_id: UUID
    rating: int = Field(..., ge=-1, le=1, description="1 for thumbs up, -1 for thumbs down")
    comment: str | None = Field(None, max_length=1000)


class FeedbackResponse(BaseModel):
    """Feedback submission confirmation."""

    id: UUID
    status: str = "received"


class ConversationRecoveryContext(BaseModel):
    """Structured information for recovering a previous student conversation."""

    has_resumable_conversation: bool
    conversation_id: str | None = None
    title: str | None = None
    last_active_at: datetime | None = None
    student_name: str | None = None
    topic: str | None = None
    program_name: str | None = None
    board_name: str | None = None
    academic_stage: str | None = None
    score_text: str | None = None
    assessment_status: str = "none"  # "completed" | "in_progress" | "none"
    scholarship_percent: float | None = None
    scholarship_label: str | None = None
    is_projected: bool = False
    welcome_message: str | None = None
    total_messages: int = 0
    workflow_step: str | None = None
    # Memory choice (v4.8.0): minutes since the last message of that conversation, the threshold, and whether
    # the student should be asked "continue or start new" (True) or the conversation simply continues (False).
    inactive_minutes: float | None = None
    resume_after_minutes: int = 30
    offer_choice: bool = False
    last_user_message: str | None = None


class ResetSessionRequest(BaseModel):
    """Request to reset active conversation state while preserving identity and history."""

    session_id: str = Field(..., min_length=16, max_length=64, pattern=SESSION_ID_PATTERN)
    conversation_id: str | None = None


class ResetSessionResponse(BaseModel):
    """Response confirming session conversation reset."""

    status: str = "ok"
    session_id: str
    active_conversation_id: str | None = None
    new_conversation_id: str | None = None

