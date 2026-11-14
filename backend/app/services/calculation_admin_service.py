"""Administrative queries for deterministic calculation history."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calculation import CalculationScenario
from app.schemas.admin import CalculationScenarioItem, CalculationScenarioListResponse


async def list_calculations(
    db: AsyncSession,
    limit: int = 50,
) -> CalculationScenarioListResponse:
    """Return recent calculation scenarios for review."""
    total = await db.scalar(select(func.count(CalculationScenario.id))) or 0
    result = await db.execute(
        select(CalculationScenario)
        .order_by(CalculationScenario.created_at.desc())
        .limit(limit)
    )
    items = [
        CalculationScenarioItem(
            id=item.id,
            conversation_id=item.conversation_id,
            message_id=item.message_id,
            calculation_type=item.calculation_type,
            status=item.status,
            inputs=item.inputs,
            result=item.result,
            source_text=item.source_text,
            created_at=item.created_at,
        )
        for item in result.scalars().all()
    ]
    return CalculationScenarioListResponse(items=items, total=total)
