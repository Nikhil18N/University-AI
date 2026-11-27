"""Chat API routes — fully public, no authentication required."""

import logging
from uuid import UUID

from typing import Any
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_embedding_provider, get_llm_provider, get_rag_service, get_redis, get_session_id
from app.db.session import get_db
from app.providers.base import LLMProvider
from app.providers.embedding_base import EmbeddingProvider
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationSummary,
    FeedbackRequest,
    FeedbackResponse,
)
from app.schemas.common import ErrorResponse
from app.services import chat_service, conversation_service
from app.services.rag_service import RAGService
from app import security
from app.security import SESSION_ID_PATTERN

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])


async def _enforce_ai_limits(http_request: Request | None, session_id: str) -> None:
    """HTTP 429 when the student, their network or the server's daily budget is over the limit."""
    if http_request is not None:
        refusal = await security.ai_turn_refusal(http_request, session_id, scope="chat")
    else:
        from app.sru_agent import memory as agent_memory
        refusal = None if await agent_memory.allow_request(f"chat:{session_id}") else security.BUSY_MESSAGE
    if refusal:
        raise HTTPException(status_code=429, detail=refusal)


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={500: {"model": ErrorResponse}},
)
async def send_message(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    llm: LLMProvider = Depends(get_llm_provider),
    rag: RAGService = Depends(get_rag_service),
    redis: Any = Depends(get_redis),
    http_request: Request = None,
) -> ChatResponse:
    """Send a chat message and receive an AI response.

    - Pass `conversation_id: null` to start a new conversation.
    - Pass an existing `conversation_id` to continue.
    - `session_id` is a browser-generated UUID for tracking conversations.
    """
    # Same limits as the agent endpoint (per student, per IP, daily budget): this route also
    # consumes model capacity.
    await _enforce_ai_limits(http_request, request.session_id)

    try:
        return await chat_service.handle_chat(db, request, llm, rag, redis_client=redis)
    except Exception as e:
        logger.error("Chat error: %s", e, exc_info=True)
        err_msg = str(e)
        if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
            detail = "AI model rate limit reached. Please wait a moment and try again."
        elif not security.docs_enabled():
            # Production: never name internal services, hosts or ports in an error.
            detail = "Something went wrong processing your message. Please try again."
        elif "11434" in err_msg or ("ConnectError" in type(e).__name__ and "embedding" in err_msg.lower()):
            detail = "Could not connect to Ollama embedding service. Please run 'ollama serve' to enable document retrieval."
        elif "5433" in err_msg or "ConnectionRefusedError" in type(e).__name__:
            detail = "Database service unreachable. Please ensure PostgreSQL is running."
        else:
            detail = "Something went wrong processing your message. Please try again."
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
        )


@router.post("/chat/stream")
async def send_message_stream(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    llm: LLMProvider = Depends(get_llm_provider),
    rag: RAGService = Depends(get_rag_service),
    redis: Any = Depends(get_redis),
    http_request: Request = None,
) -> StreamingResponse:
    """Send a chat message and stream tokens via Server-Sent Events (SSE)."""
    # Same limits as the agent endpoint: this route also spends Gemini quota.
    await _enforce_ai_limits(http_request, request.session_id)
    return StreamingResponse(
        chat_service.handle_chat_stream(db, request, llm, rag, redis_client=redis),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/conversations",
    response_model=list[ConversationSummary],
)
async def list_conversations(
    session_id: str = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationSummary]:
    """List all conversations for a session."""
    return await conversation_service.list_conversations(db, session_id)


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetail,
    responses={404: {"model": ErrorResponse}},
)
async def get_conversation(
    conversation_id: UUID,
    session_id: str = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
    x_admin_key: str | None = Header(None, alias="X-Admin-Key"),
    http_request: Request = None,
) -> ConversationDetail:
    """Get a conversation with all messages.

    Staff may open any conversation by sending the admin key in the X-Admin-Key header. The key is
    checked exactly like the admin routes (constant time, failed-attempt limit, audit log). A key in
    the URL is never accepted: URLs end up in browser history, logs and shared links.
    """
    is_admin = False
    if x_admin_key:
        from app.api.v1.deps import verify_admin_key
        await verify_admin_key(http_request if http_request is not None else x_admin_key, x_admin_key)
        is_admin = True

    detail = await conversation_service.get_conversation(
        db, conversation_id, session_id, is_admin=is_admin
    )
    if detail is None:
        from app.sru_agent import memory as agent_memory
        history = await agent_memory.get_history(session_id, str(conversation_id))
        if not history and str(conversation_id):
            history = await agent_memory.get_history(session_id)
        if history:
            import uuid as _uuid
            from datetime import datetime, timezone
            from app.schemas.chat import MessageResponse
            now = datetime.now(timezone.utc)
            messages = [
                MessageResponse(
                    id=_uuid.uuid4(),
                    role="assistant" if h.get("role") == "model" else (h.get("role") or "user"),
                    content=h.get("text") or "",
                    suggestions=[],
                    cards=[],
                    created_at=now,
                )
                for h in history
            ]
            return ConversationDetail(
                id=conversation_id,
                title="Chat",
                messages=messages,
                created_at=now,
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return detail



@router.get(
    "/shared/{conversation_id}",
    response_model=ConversationDetail,
    responses={404: {"model": ErrorResponse}},
)
async def get_shared_conversation(
    conversation_id: UUID,
    session_id: str = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetail:
    """Get a conversation with all messages. Requires session_id verification to prevent IDOR data leakage."""
    detail = await conversation_service.get_shared_conversation(db, conversation_id, session_id=session_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shared conversation not found",
        )
    return detail


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
async def delete_conversation(
    conversation_id: UUID,
    session_id: str = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a conversation and all its messages."""
    deleted = await conversation_service.delete_conversation(
        db, conversation_id, session_id
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_feedback(
    request: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    embeddings: EmbeddingProvider = Depends(get_embedding_provider),
) -> FeedbackResponse:
    """Submit user feedback (thumbs up/down and optional comment) on one of your own answers."""
    result = await conversation_service.create_feedback(db, request, embeddings)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )
    return result
