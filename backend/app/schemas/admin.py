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
    cards: list[dict] | None = None
    suggestions: list[str] | None = None
    metadata: dict | None = None
    created_at: datetime


class AdminStudentSummary(BaseModel):
    """Who the student is, for the admissions team (v4.15.1): from the profile the chat saved and the leads."""
    name: str | None = None
    phone: str | None = None
    program: str | None = None
    marks: str | None = None
    scholarship_percent: float | None = None
    request: str | None = None          # "callback" / "campus_visit" when one was made
    lead_status: str | None = None
    is_parent: bool | None = None


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
    student: AdminStudentSummary | None = None


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
    student: AdminStudentSummary | None = None


class PromoteExemplarRequest(BaseModel):
    message_id: UUID
    question: str
    answer: str


class PromoteExemplarResponse(BaseModel):
    success: bool
    message: str


class AgentRunItem(BaseModel):
    id: UUID
    conversation_id: UUID
    message_id: UUID | None = None
    route: str
    tool: str | None = None
    reason: str
    status: str
    step_count: int
    created_at: datetime


class AgentRunListResponse(BaseModel):
    items: list[AgentRunItem]
    total: int


class CalculationScenarioItem(BaseModel):
    id: UUID
    conversation_id: UUID
    message_id: UUID | None = None
    calculation_type: str
    status: str
    inputs: dict
    result: dict
    source_text: str | None = None
    created_at: datetime


class CalculationScenarioListResponse(BaseModel):
    items: list[CalculationScenarioItem]
    total: int


class AdminJobResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    result: dict | list | str | int | float | bool | None = None
    error: str | None = None


class AdminJobListResponse(BaseModel):
    items: list[AdminJobResponse]
    total: int


