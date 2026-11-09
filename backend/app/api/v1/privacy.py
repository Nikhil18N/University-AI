"""DPDP privacy endpoints: student right to erasure (delete-my-data)."""

import logging
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.evaluation import EvaluationRecord
from app.models.lead import ProspectiveLead
from app.models.message import Message
from app.schemas.privacy import DeleteMyDataRequest, DeleteMyDataResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/privacy", tags=["privacy"])


@router.post(
    "/delete-my-data",
    response_model=DeleteMyDataResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete all data associated with a session ID or phone number (DPDP erasure)",
)
async def delete_my_data(
    payload: DeleteMyDataRequest,
    db: AsyncSession = Depends(get_db),
) -> DeleteMyDataResponse:
    """Hard-delete all conversation messages, evaluation records, and leads associated with session_id or phone."""
    session_id = payload.session_id.strip() if payload.session_id else None
    phone = payload.phone.strip() if payload.phone else None

    if not session_id and not phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either session_id or phone must be provided to locate and delete data.",
        )

    deleted_convs = 0
    deleted_msgs = 0
    deleted_leads = 0
    deleted_evals = 0

    target_conv_ids: set[UUID] = set()

    # 1. Resolve conversations by session_id
    if session_id:
        conv_stmt = select(Conversation.id).where(Conversation.session_id == session_id)
        res = await db.execute(conv_stmt)
        for cid in res.scalars():
            target_conv_ids.add(cid)

    # 2. Resolve leads and any linked conversations by phone
    if phone:
        # Extract digits for flexible matching
        digits = re.sub(r"\D", "", phone)
        # Search exact or suffix match if at least 10 digits
        lead_stmt = select(ProspectiveLead).where(
            (ProspectiveLead.phone == phone)
            | (ProspectiveLead.phone.ilike(f"%{digits[-10:]}%" if len(digits) >= 10 else f"%{phone}%"))
        )
        leads_res = await db.execute(lead_stmt)
        matching_leads = leads_res.scalars().all()
        for lead in matching_leads:
            if lead.conversation_id:
                target_conv_ids.add(lead.conversation_id)
            await db.delete(lead)
            deleted_leads += 1

    # 3. Delete messages and evaluations linked to identified conversations
    if target_conv_ids:
        # Delete evaluations
        eval_del_stmt = (
            delete(EvaluationRecord)
            .where(EvaluationRecord.conversation_id.in_(target_conv_ids))
        )
        eval_res = await db.execute(eval_del_stmt)
        deleted_evals += eval_res.rowcount or 0

        # Delete messages
        msg_del_stmt = (
            delete(Message)
            .where(Message.conversation_id.in_(target_conv_ids))
        )
        msg_res = await db.execute(msg_del_stmt)
        deleted_msgs += msg_res.rowcount or 0

        # Delete conversations
        conv_del_stmt = (
            delete(Conversation)
            .where(Conversation.id.in_(target_conv_ids))
        )
        conv_res = await db.execute(conv_del_stmt)
        deleted_convs += conv_res.rowcount or 0

    await db.commit()
    logger.info(
        "DPDP Erasure executed: deleted %d convs, %d msgs, %d evals, %d leads for session=%s phone=%s",
        deleted_convs,
        deleted_msgs,
        deleted_evals,
        deleted_leads,
        session_id,
        phone,
    )

    return DeleteMyDataResponse(
        status="success",
        deleted_conversations=deleted_convs,
        deleted_messages=deleted_msgs,
        deleted_leads=deleted_leads,
        deleted_evaluations=deleted_evals,
        message="All associated conversation messages, evaluation records, and leads have been deleted.",
    )
