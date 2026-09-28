"""Chat API routes — fully public, no authentication required."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_llm_provider, get_rag_service
from app.db.session import get_db
from app.providers.base import LLMProvider
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])


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
) -> ChatResponse:
    """Send a chat message and receive an AI response.

    - Pass `conversation_id: null` to start a new conversation.
    - Pass an existing `conversation_id` to continue.
    - `session_id` is a browser-generated UUID for tracking conversations.
    """
    try:
        return await chat_service.handle_chat(db, request, llm, rag)
    except Exception as e:
        logger.error("Chat error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong processing your message. Please try again.",
        )


@router.get(
    "/conversations",
    response_model=list[ConversationSummary],
)
async def list_conversations(
    session_id: str = Query(..., min_length=1, max_length=64),
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
    session_id: str = Query(..., min_length=1, max_length=64),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetail:
    """Get a conversation with all messages."""
    detail = await conversation_service.get_conversation(
        db, conversation_id, session_id
    )
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return detail


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
async def delete_conversation(
    conversation_id: UUID,
    session_id: str = Query(..., min_length=1, max_length=64),
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
) -> FeedbackResponse:
    """Submit user feedback (thumbs up/down and optional comment)."""
    return await conversation_service.create_feedback(db, request)
