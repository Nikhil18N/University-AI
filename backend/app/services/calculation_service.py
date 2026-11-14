"""Persistence helpers for deterministic calculation history."""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.calculation import CalculationScenario
from app.schemas.finance import (
    FinanceCalculationHistoryItem,
    FinanceEstimateRequest,
    FinanceEstimateResponse,
)


async def record_finance_calculation(
    db: AsyncSession,
    conversation_id: UUID,
    message_id: UUID | None,
    request: FinanceEstimateRequest | None,
    result: FinanceEstimateResponse,
    source_text: str,
) -> CalculationScenario:
    """Persist calculation inputs and outputs without storing hidden prompts."""
    scenario = CalculationScenario(
        conversation_id=conversation_id,
        message_id=message_id,
        calculation_type="finance_estimate",
        status=result.status,
        inputs=request.model_dump(mode="json") if request else {},
        result=result.model_dump(mode="json"),
        source_text=source_text[:4000],
    )
    db.add(scenario)
    await db.flush()
    return scenario


async def list_session_calculations(
    db: AsyncSession,
    session_id: str,
    limit: int = 20,
) -> list[FinanceCalculationHistoryItem]:
    """Return only calculations belonging to conversations in this session."""
    result = await db.execute(
        select(CalculationScenario)
        .join(Conversation, CalculationScenario.conversation_id == Conversation.id)
        .where(Conversation.session_id == session_id)
        .order_by(CalculationScenario.created_at.desc())
        .limit(limit)
    )
    return [
        FinanceCalculationHistoryItem(
            id=item.id,
            conversation_id=item.conversation_id,
            message_id=item.message_id,
            status=item.status,
            inputs=item.inputs,
            result=item.result,
            source_text=item.source_text,
            created_at=item.created_at,
        )
        for item in result.scalars().all()
    ]


async def delete_session_calculations(
    db: AsyncSession,
    session_id: str,
) -> int:
    """Delete only calculations owned by conversations in this session."""
    owned_ids = select(Conversation.id).where(Conversation.session_id == session_id)
    result = await db.execute(
        delete(CalculationScenario).where(
            CalculationScenario.conversation_id.in_(owned_ids)
        )
    )
    return int(result.rowcount or 0)
