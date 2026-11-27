"""Memory controls for public, browser-session conversations."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_session_id
from app.db.session import get_db
from app.schemas.memory import (
    ConversationSummaryResponse,
    MemoryDeleteRequest,
    MemoryItem,
    MemoryWriteRequest,
    PendingAgentTaskResponse,
)
from app.schemas.finance import FinanceCalculationHistoryItem
from app.services import conversation_service, memory_service
from app.services.calculation_service import (
    delete_session_calculations,
    list_session_calculations,
)
from app.services.agent_task_service import cancel_pending_task, list_pending_tasks
from app.security import SESSION_ID_PATTERN

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


@router.get("/pending-tasks", response_model=list[PendingAgentTaskResponse])
async def get_pending_agent_tasks(
    session_id: str = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
) -> list[PendingAgentTaskResponse]:
    """Return unfinished clarification tasks owned by this browser session."""
    return [
        PendingAgentTaskResponse(
            conversation_id=task.conversation_id,
            task_type=task.task_type,
            original_query=task.original_query,
            missing_inputs=task.missing_inputs,
            status=task.status,
            updated_at=task.updated_at,
        )
        for task in await list_pending_tasks(db, session_id)
    ]


@router.delete("/pending-tasks/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_pending_agent_task(
    conversation_id: UUID,
    session_id: str = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Cancel a clarification task owned by this browser session."""
    if not await cancel_pending_task(db, conversation_id, session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending task not found",
        )


@router.get("/calculations", response_model=list[FinanceCalculationHistoryItem])
async def get_calculation_history(
    session_id: str = Depends(get_session_id),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Return finance calculations for the current browser session only."""
    return await list_session_calculations(db, session_id, limit)


@router.delete("/calculations", status_code=status.HTTP_204_NO_CONTENT)
async def delete_calculation_history(
    session_id: str = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete all finance calculation history owned by this browser session."""
    await delete_session_calculations(db, session_id)


@router.get("", response_model=list[MemoryItem])
async def get_memory(
    session_id: str = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
) -> list[MemoryItem]:
    return await memory_service.list_memory(db, session_id)


@router.post("", response_model=MemoryItem, status_code=status.HTTP_201_CREATED)
async def store_memory(
    request: MemoryWriteRequest,
    db: AsyncSession = Depends(get_db),
) -> MemoryItem:
    return await memory_service.save_memory(
        db, request.session_id, request.key, request.value, request.consent
    )


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def forget_memory(
    key: str,
    request: MemoryDeleteRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    if not await memory_service.delete_memory(db, request.session_id, key):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")


@router.get("/conversations/{conversation_id}/summary", response_model=ConversationSummaryResponse)
async def get_conversation_summary(
    conversation_id: UUID,
    session_id: str = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
) -> ConversationSummaryResponse:
    summary = await memory_service.get_summary(db, UUID(conversation_id), session_id)
    if summary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Summary not found")
    return ConversationSummaryResponse(
        conversation_id=summary.conversation_id,
        summary=summary.summary,
        updated_at=summary.updated_at,
    )
