"""Lead service — business logic for prospective student leads, inquiries, and conversion tracking."""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import ProspectiveLead
from app.schemas.lead import LeadCreate

logger = logging.getLogger(__name__)


async def create_lead(db: AsyncSession, data: LeadCreate) -> ProspectiveLead:
    """Register or update a prospective student lead with deduplication by phone number."""
    clean_phone = data.phone.strip()
    clean_name = data.name.strip()

    # Deduplication check: if lead with identical phone exists, update it gracefully
    existing_stmt = select(ProspectiveLead).where(ProspectiveLead.phone == clean_phone).order_by(ProspectiveLead.created_at.desc())
    res = await db.execute(existing_stmt)
    existing_lead = res.scalars().first()

    if existing_lead:
        existing_lead.name = clean_name
        if data.email:
            existing_lead.email = data.email.strip()
        if data.program_interest:
            existing_lead.program_interest = data.program_interest.strip()
        if data.score:
            existing_lead.score = data.score.strip()
        if data.exam_type:
            existing_lead.exam_type = data.exam_type.strip()
        if data.metadata:
            existing_meta = existing_lead.metadata_ or {}
            existing_meta.update(data.metadata)
            existing_lead.metadata_ = existing_meta
        await db.commit()
        await db.refresh(existing_lead)
        logger.info("Updated existing prospective lead: %s (%s)", existing_lead.name, existing_lead.phone)
        return existing_lead

    lead = ProspectiveLead(
        name=clean_name,
        phone=clean_phone,
        email=data.email.strip() if data.email else None,
        program_interest=data.program_interest.strip() if data.program_interest else None,
        score=data.score.strip() if data.score else None,
        exam_type=data.exam_type.strip() if data.exam_type else None,
        source=data.source,
        conversation_id=data.conversation_id,
        metadata_=data.metadata,
        status="new",
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    logger.info("Captured prospective lead: %s (%s) for %s from %s", lead.name, lead.phone, lead.program_interest, lead.source)
    return lead


async def list_leads(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 50,
    search: str | None = None,
    program: str | None = None,
    source: str | None = None,
    status: str | None = None,
) -> tuple[int, list[ProspectiveLead]]:
    """Retrieve paginated prospective leads with optional filtering and search."""
    stmt = select(ProspectiveLead)

    if search:
        search_pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            (ProspectiveLead.name.ilike(search_pattern))
            | (ProspectiveLead.phone.ilike(search_pattern))
            | (ProspectiveLead.email.ilike(search_pattern))
        )

    if program and program != "all":
        stmt = stmt.where(ProspectiveLead.program_interest.ilike(f"%{program.strip()}%"))

    if source and source != "all":
        if source in ("calculator", "scholarship_calculator"):
            stmt = stmt.where(ProspectiveLead.source.in_(["calculator", "scholarship_calculator"]))
        else:
            stmt = stmt.where(ProspectiveLead.source == source)

    if status and status != "all":
        stmt = stmt.where(ProspectiveLead.status == status)

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Paginate and order by newest first
    offset = (page - 1) * page_size
    stmt = stmt.order_by(ProspectiveLead.created_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(stmt)
    leads = list(result.scalars().all())

    return total, leads


async def get_lead_stats(db: AsyncSession) -> dict:
    """Aggregate KPI statistics on prospective student inquiries."""
    # Total
    total_q = select(func.count(ProspectiveLead.id))
    total = (await db.execute(total_q)).scalar() or 0

    # By source
    chat_q = select(func.count(ProspectiveLead.id)).where(ProspectiveLead.source == "chat_inquiry")
    chat_leads = (await db.execute(chat_q)).scalar() or 0

    calc_q = select(func.count(ProspectiveLead.id)).where(
        ProspectiveLead.source.in_(["calculator", "scholarship_calculator"])
    )
    calculator_leads = (await db.execute(calc_q)).scalar() or 0

    # Today's leads
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_q = select(func.count(ProspectiveLead.id)).where(ProspectiveLead.created_at >= today_start)
    today_leads = (await db.execute(today_q)).scalar() or 0

    # Enrolled conversions
    enrolled_q = select(func.count(ProspectiveLead.id)).where(ProspectiveLead.status == "enrolled")
    enrolled_leads = (await db.execute(enrolled_q)).scalar() or 0

    return {
        "total_leads": total,
        "chat_leads": chat_leads,
        "calculator_leads": calculator_leads,
        "today_leads": today_leads,
        "enrolled_leads": enrolled_leads,
    }


async def update_lead_status(
    db: AsyncSession,
    lead_id: UUID,
    new_status: str,
) -> ProspectiveLead | None:
    """Update admissions status of a lead (interested, contacted, applied, enrolled, rejected)."""
    lead = await db.get(ProspectiveLead, lead_id)
    if not lead:
        return None

    lead.status = new_status
    await db.commit()
    await db.refresh(lead)
    logger.info("Updated lead %s status to %s", lead_id, new_status)
    return lead
