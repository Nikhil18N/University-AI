"""Typed schemas for deterministic fee and scholarship calculations."""

from decimal import Decimal
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FinanceEstimateRequest(BaseModel):
    """Inputs required to estimate a student's published charges."""

    program: str = Field(..., min_length=1, max_length=120)
    academic_year: str = Field(..., min_length=4, max_length=20)
    score_percent: Decimal | None = Field(None, ge=0, le=100)
    category: str | None = Field(None, max_length=64)
    hostel: bool = False
    transport: bool = False


class FinanceLineItem(BaseModel):
    """One auditable component of an estimate."""

    label: str
    amount: Decimal
    source: str


class FinanceEstimateResponse(BaseModel):
    """Deterministic estimate with explicit confidence and source metadata."""

    status: str
    currency: str = "INR"
    total: Decimal | None = None
    line_items: list[FinanceLineItem] = Field(default_factory=list)
    scholarship_amount: Decimal | None = None
    scholarship_name: str | None = None
    missing_inputs: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class FeeRule(BaseModel):
    program: str = Field(..., min_length=1, max_length=120)
    academic_year: str = Field(..., min_length=4, max_length=20)
    tuition: Decimal = Field(..., ge=0)
    hostel: Decimal | None = Field(None, ge=0)
    transport: Decimal | None = Field(None, ge=0)
    source: str = Field(..., min_length=1, max_length=500)


class ScholarshipRule(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    academic_year: str = Field(..., min_length=4, max_length=20)
    minimum_score_percent: Decimal = Field(..., ge=0, le=100)
    maximum_score_percent: Decimal = Field(..., ge=0, le=100)
    percent: Decimal = Field(..., ge=0, le=100)
    categories: list[str] = Field(default_factory=list)
    source: str = Field(..., min_length=1, max_length=500)


class FinanceCatalog(BaseModel):
    fee_rules: list[FeeRule] = Field(default_factory=list)
    scholarship_rules: list[ScholarshipRule] = Field(default_factory=list)


class FinanceCalculationHistoryItem(BaseModel):
    id: UUID
    conversation_id: UUID
    message_id: UUID | None = None
    status: str
    inputs: dict
    result: dict
    source_text: str | None = None
    created_at: datetime
