"""Persistence helpers for bounded agent execution audits."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentRun
from app.services.agent_service import AgentDecision


async def record_agent_run(
    db: AsyncSession,
    conversation_id: UUID,
    message_id: UUID | None,
    decision: AgentDecision,
    status: str,
) -> AgentRun:
    """Persist the decision after policy validation and tool execution."""
    run = AgentRun(
        conversation_id=conversation_id,
        message_id=message_id,
        route=decision.route.value,
        tool=decision.tool,
        reason=decision.reason,
        status=status,
        step_count=1,
    )
    db.add(run)
    await db.flush()
    return run
