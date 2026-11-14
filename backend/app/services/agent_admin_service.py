"""Administrative queries for bounded agent execution audits."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentRun
from app.schemas.admin import AgentRunItem, AgentRunListResponse


async def list_agent_runs(
    db: AsyncSession,
    limit: int = 50,
) -> AgentRunListResponse:
    """Return recent agent runs for operational review."""
    total = await db.scalar(select(func.count(AgentRun.id))) or 0
    result = await db.execute(
        select(AgentRun)
        .order_by(AgentRun.created_at.desc())
        .limit(limit)
    )
    items = [
        AgentRunItem(
            id=run.id,
            conversation_id=run.conversation_id,
            message_id=run.message_id,
            route=run.route,
            tool=run.tool,
            reason=run.reason,
            status=run.status,
            step_count=run.step_count,
            created_at=run.created_at,
        )
        for run in result.scalars().all()
    ]
    return AgentRunListResponse(items=items, total=total)
