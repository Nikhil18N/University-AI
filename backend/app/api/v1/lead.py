"""Public API router for prospective student lead registration and inquiries."""

import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.lead import LeadCreate, LeadResponse
from app.services import lead_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])


@router.post(
    "",
    response_model=LeadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a prospective student lead",
)
async def register_lead(
    data: LeadCreate,
    db: AsyncSession = Depends(get_db),
) -> LeadResponse:
    """Register prospective student details (name, phone, interest) from chat or scholarship calculator."""
    lead = await lead_service.create_lead(db, data)
    return LeadResponse.model_validate(lead)
