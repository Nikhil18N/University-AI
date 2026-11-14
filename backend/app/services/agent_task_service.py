"""Persistence helpers for resumable clarification tasks."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_task import PendingAgentTask


async def get_pending_task(
    db: AsyncSession,
    conversation_id: UUID,
    session_id: str,
) -> PendingAgentTask | None:
    result = await db.execute(
        select(PendingAgentTask)
        .where(
            PendingAgentTask.conversation_id == conversation_id,
            PendingAgentTask.session_id == session_id,
            PendingAgentTask.status == "pending",
        )
        .order_by(PendingAgentTask.updated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def save_pending_task(
    db: AsyncSession,
    conversation_id: UUID,
    session_id: str,
    task_type: str,
    original_query: str,
    missing_inputs: list[str],
) -> PendingAgentTask:
    task = await get_pending_task(db, conversation_id, session_id)
    if task is None:
        task = PendingAgentTask(
            conversation_id=conversation_id,
            session_id=session_id,
            task_type=task_type,
            original_query=original_query,
            missing_inputs=missing_inputs,
            status="pending",
        )
        db.add(task)
    else:
        task.original_query = original_query
        task.missing_inputs = missing_inputs
    await db.flush()
    return task


async def complete_pending_task(db: AsyncSession, task: PendingAgentTask) -> None:
    task.status = "completed"
    await db.flush()


async def list_pending_tasks(
    db: AsyncSession,
    session_id: str,
) -> list[PendingAgentTask]:
    result = await db.execute(
        select(PendingAgentTask)
        .where(
            PendingAgentTask.session_id == session_id,
            PendingAgentTask.status == "pending",
        )
        .order_by(PendingAgentTask.updated_at.desc())
    )
    return list(result.scalars().all())


async def cancel_pending_task(
    db: AsyncSession,
    conversation_id: UUID,
    session_id: str,
) -> bool:
    task = await get_pending_task(db, conversation_id, session_id)
    if task is None:
        return False
    task.status = "cancelled"
    await db.flush()
    return True
