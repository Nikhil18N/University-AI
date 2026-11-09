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
                sources=None,  # Do not show sources in responses
                suggestions=(m.metadata_ or {}).get("suggestions", []),
                cards=(m.metadata_ or {}).get("cards", []),
                flow=(m.metadata_ or {}).get("flow"),
                model=m.model,
                created_at=m.created_at,
            )
            for m in conv.messages
        ],
        created_at=conv.created_at,
    )


async def get_shared_conversation(
    db: AsyncSession, conversation_id: uuid.UUID
) -> ConversationDetail | None:
    """Get a conversation with all messages for public shared viewing (read-only snapshot)."""
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id)
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
                sources=None,  # Do not show sources in responses
                suggestions=(m.metadata_ or {}).get("suggestions", []),
                cards=(m.metadata_ or {}).get("cards", []),
                flow=(m.metadata_ or {}).get("flow"),
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
    metadata: dict | None = None,
) -> Message:
    """Add a message to a conversation."""
    msg = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        model=model,
        sources=sources,
        metadata_=metadata,
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

    return [
        {
            "role": m.role,
            "content": m.content,
            "metadata": m.metadata_ if isinstance(m.metadata_, dict) else {},
        }
        for m in messages
    ]


async def get_all_user_messages(
    db: AsyncSession, conversation_id: uuid.UUID, limit: int = 20
) -> list[dict[str, str]]:
    """Get recent user messages to reliably retain student profile slots.

    Fetches at most *limit* messages (default 20) to keep the DB query
    bounded as conversations grow.
    """
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.role == "user")
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()

    return [
        {
            "role": m.role,
            "content": m.content,
            "metadata": m.metadata_ if isinstance(m.metadata_, dict) else {},
        }
        for m in messages
    ]


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
    db: AsyncSession,
    request: FeedbackRequest,
    embeddings: object | None = None,
) -> FeedbackResponse:
    """Store user feedback for a message and update self-improvement exemplar store."""
    feedback = Feedback(
        session_id=request.session_id,
        conversation_id=request.conversation_id,
        message_id=request.message_id,
        rating=request.rating,
        comment=request.comment,
    )
    db.add(feedback)
    await db.flush()

    # Self-improvement loop: Learn from verified positive feedback
    try:
        from app.services.exemplar_service import ExemplarService
        from app.providers.embedding_base import EmbeddingProvider

        emb_provider = embeddings if isinstance(embeddings, EmbeddingProvider) else None
        exemplar_service = ExemplarService(emb_provider)

        if request.rating == 1 and emb_provider:
            # Look up assistant message
            stmt_assistant = select(Message).where(Message.id == request.message_id)
            result = await db.execute(stmt_assistant)
            assistant_msg = result.scalar_one_or_none()

            if assistant_msg:
                # Find the user question that prompted this answer
                stmt_user = (
                    select(Message)
                    .where(
                        Message.conversation_id == assistant_msg.conversation_id,
                        Message.role == "user",
                        Message.created_at <= assistant_msg.created_at,
                    )
                    .order_by(Message.created_at.desc())
                    .limit(1)
                )
                res_user = await db.execute(stmt_user)
                user_msg = res_user.scalar_one_or_none()

                if user_msg and user_msg.content.strip():
                    await exemplar_service.register_exemplar(
                        message_id=assistant_msg.id,
                        question=user_msg.content,
                        answer=assistant_msg.content,
                    )
        elif request.rating == -1:
            # Prune from exemplar store if it was previously saved
            await exemplar_service.remove_exemplar(request.message_id)
    except Exception as e:
        logger.warning("Feedback exemplar registration encountered an error: %s", e)

    return FeedbackResponse(id=feedback.id, status="received")

