"""Pydantic schemas for prospective student leads and admissions inquiries."""

import re
from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class LeadCreate(BaseModel):
    """Payload to capture a prospective student lead."""

    name: str = Field(..., min_length=2, max_length=255, description="Full name of prospective student")
    phone: str = Field(..., min_length=10, max_length=20, description="Contact phone or mobile number")
    email: str | None = Field(None, max_length=255, description="Optional email address")
    program_interest: str | None = Field(None, max_length=255, description="Program/branch interested in")
    score: str | None = Field(None, max_length=100, description="Marks, percentage, or rank")
    exam_type: str | None = Field(None, max_length=100, description="Board or qualifying exam (Inter, CBSE, JEE, etc.)")
    source: str = Field("chat_inquiry", max_length=50, description="Lead source: chat_inquiry or scholarship_calculator")
    conversation_id: UUID | None = Field(None, description="Associated chat conversation ID")
    metadata: dict | None = Field(None, description="Optional additional context")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 2:
            raise ValueError("Student name must be at least 2 characters")
        return cleaned

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        clean = re.sub(r"[^\d+]", "", v)
        digits = re.sub(r"[^\d]", "", v)
        if len(digits) < 10:
            raise ValueError("Phone number must contain at least 10 digits")
        return clean


class LeadStatusUpdate(BaseModel):
    """Payload to update conversion status of a lead."""

    status: str = Field(..., description="Lead status: interested, contacted, applied, enrolled, rejected")


class LeadResponse(BaseModel):
    """Full prospective lead record."""

    id: UUID
    name: str
    phone: str
    email: str | None = None
    program_interest: str | None = None
    score: str | None = None
    exam_type: str | None = None
    source: str
    conversation_id: UUID | None = None
    status: str
    created_at: datetime
    metadata: dict | None = Field(None, validation_alias=AliasChoices("metadata_", "metadata"))

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class LeadListResponse(BaseModel):
    """Paginated list of prospective student leads."""

    total: int
    items: list[LeadResponse]


class LeadStatsResponse(BaseModel):
    """Summary KPI metrics for admissions leads."""

    total_leads: int
    chat_leads: int
    calculator_leads: int
    today_leads: int
    enrolled_leads: int
