"""Schemas for DPDP privacy endpoints (delete-my-data)."""

from pydantic import BaseModel, Field


class DeleteMyDataRequest(BaseModel):
    session_id: str | None = Field(
        default=None,
        description="Browser session ID associated with student chats",
    )
    phone: str | None = Field(
        default=None,
        description="Phone number submitted during inquiry or lead capture",
    )


class DeleteMyDataResponse(BaseModel):
    status: str = "success"
    deleted_conversations: int = 0
    deleted_messages: int = 0
    deleted_leads: int = 0
    deleted_evaluations: int = 0
    message: str = "Associated user data has been purged."

