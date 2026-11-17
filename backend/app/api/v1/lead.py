"""Public API router for prospective student lead registration and inquiries."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.lead import LeadCreate, LeadResponse
from app.services import lead_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])

# This endpoint is public (the website posts to it), so one address may only create a
# limited number of leads per minute. Stops a script from flooding the admissions team.
LEADS_PER_MINUTE = 30


def _client_address(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return (request.client.host if request.client else "unknown")[:64]


@router.post(
    "",
    response_model=LeadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a prospective student lead",
)
async def register_lead(
    data: LeadCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> LeadResponse:
    """Register prospective student details (name, phone, interest) from chat or scholarship calculator."""
    from app.sru_agent import memory

    if not await memory.allow_request(f"lead:{_client_address(request)}", limit=LEADS_PER_MINUTE):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="Too many requests. Please try again in a minute.")
    lead = await lead_service.create_lead(db, data)
    return LeadResponse.model_validate(lead)
