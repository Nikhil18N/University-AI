"""Conversation service — CRUD for conversations and messages."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.feedback import Feedback
from app.schemas.chat import (
    ConversationDetail,
    ConversationSummary,
    FeedbackRequest,
    FeedbackResponse,
    MessageResponse,
    SourceReference,
)

logger = logging.getLogger(__name__)


async def list_conversations(
    db: AsyncSession, session_id: str
) -> list[ConversationSummary]:
    """List all conversations for a session, newest first."""
    stmt = (
        select(Conversation)
        .where(Conversation.session_id == session_id)
        .order_by(Conversation.updated_at.desc())
    )
    result = await db.execute(stmt)
    conversations = result.scalars().all()

    return [
        ConversationSummary(
            id=c.id,
            title=c.title,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in conversations
    ]


async def get_conversation(
    db: AsyncSession, conversation_id: uuid.UUID, session_id: str
) -> ConversationDetail | None:
    """Get a conversation with all messages. Verifies session ownership."""
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.id == conversation_id,
            Conversation.session_id == session_id,
        )
    )
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()

    if conv is None:
        return None

    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        messages=[
            MessageResponse(
                id=m.id,
                role=m.role,
                content=m.content,
                sources=_parse_sources(m.sources),
                model=m.model,
                created_at=m.created_at,
            )
            for m in conv.messages
        ],
        created_at=conv.created_at,
    )


async def get_or_create_conversation(
    db: AsyncSession,
    session_id: str,
    conversation_id: uuid.UUID | None = None,
) -> Conversation:
    """Find an existing conversation or create a new one."""
    if conversation_id:
        stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.session_id == session_id,
        )
        result = await db.execute(stmt)
        conv = result.scalar_one_or_none()
        if conv:
            return conv

    # Create new conversation
    conv = Conversation(session_id=session_id)
    db.add(conv)
    await db.flush()
    return conv


async def add_message(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    model: str | None = None,
    sources: list[dict] | None = None,
) -> Message:
    """Add a message to a conversation."""
    msg = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        model=model,
        sources=sources,
    )
    db.add(msg)
    await db.flush()
    return msg


async def get_recent_messages(
    db: AsyncSession, conversation_id: uuid.UUID, limit: int = 10
) -> list[dict[str, str]]:
    """Get recent messages formatted for the LLM context window."""
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    messages = list(reversed(result.scalars().all()))

    return [{"role": m.role, "content": m.content} for m in messages]


async def update_conversation_title(
    db: AsyncSession, conversation_id: uuid.UUID, title: str
) -> None:
    """Update the conversation title."""
    stmt = select(Conversation).where(Conversation.id == conversation_id)
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()
    if conv:
        conv.title = title[:255]


async def delete_conversation(
    db: AsyncSession, conversation_id: uuid.UUID, session_id: str
) -> bool:
    """Delete a conversation. Returns True if found and deleted."""
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.session_id == session_id,
    )
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()
    if conv is None:
        return False
    await db.delete(conv)
    return True


def _parse_sources(sources_data: dict | list | None) -> list[SourceReference] | None:
    """Parse stored source JSON into SourceReference objects."""
    if not sources_data:
        return None
    if isinstance(sources_data, dict):
        sources_data = sources_data.get("sources", [])
    return [SourceReference(**s) for s in sources_data]


async def create_feedback(
    db: AsyncSession, request: FeedbackRequest
) -> FeedbackResponse:
    """Store user feedback for a message."""
    feedback = Feedback(
        session_id=request.session_id,
        conversation_id=request.conversation_id,
        message_id=request.message_id,
        rating=request.rating,
        comment=request.comment,
    )
    db.add(feedback)
    await db.flush()
    return FeedbackResponse(id=feedback.id, status="received")
