"""Conversation service — CRUD for conversations and messages."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import exists, select
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
    """List all non-empty conversations for a session, newest first.
    Backfills titles for conversations whose title is stuck as 'New conversation'."""
    first_user_message = (
        select(Message.content)
        .where(
            Message.conversation_id == Conversation.id,
            Message.role == "user",
            Message.content.is_not(None),
        )
        .order_by(Message.created_at.asc(), Message.role.desc())
        .limit(1)
        .scalar_subquery()
    )
    stmt = (
        select(Conversation, first_user_message.label("first_user_message"))
        .where(
            Conversation.session_id == session_id,
            exists(
                select(1).where(Message.conversation_id == Conversation.id)
            ),
        )
        .order_by(Conversation.updated_at.desc())
    )
    result = await db.execute(stmt)
    conversations = result.all()

    summaries: list[ConversationSummary] = []
    titles_updated = False

    for c, first_user_content in conversations:
        # Backfill title if stuck on "New conversation"
        if c.title == "New conversation" or not c.title:
            if first_user_content:
                clean_title = first_user_content.strip()
                if len(clean_title) > 50:
                    clean_title = clean_title[:47].rstrip() + "..."
                if clean_title:
                    c.title = clean_title
                    titles_updated = True

        summaries.append(
            ConversationSummary(
                id=c.id,
                title=c.title,
                created_at=c.created_at or datetime.now(timezone.utc),
                updated_at=c.updated_at or datetime.now(timezone.utc),
            )
        )

    if titles_updated:
        try:
            await db.commit()
        except Exception as err:
            logger.warning("Failed to commit backfilled conversation titles: %s", err)

    return summaries


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
                suggestions=(m.metadata_ or {}).get("suggestions", []),
                cards=(m.metadata_ or {}).get("cards", []),
                flow=(m.metadata_ or {}).get("flow"),
                agent=(m.metadata_ or {}).get("agent"),
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
                sources=_parse_sources(m.sources),
                suggestions=(m.metadata_ or {}).get("suggestions", []),
                cards=(m.metadata_ or {}).get("cards", []),
                flow=(m.metadata_ or {}).get("flow"),
                agent=(m.metadata_ or {}).get("agent"),
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
    title: str | None = None,
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
            if title and (conv.title == "New conversation" or not conv.title):
                conv.title = title
                await db.flush()
            return conv

    # Create new conversation
    conv_title = title or "New conversation"
    conv = Conversation(session_id=session_id, title=conv_title)
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
    created_at: datetime | None = None,
) -> Message:
    """Add a message to a conversation.

    Pass `created_at` when a question and its answer are saved together: the database default is
    the transaction time, which would give both the same timestamp.
    """
    msg = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        model=model,
        sources=sources,
        metadata_=metadata,
    )
    if created_at is not None:
        msg.created_at = created_at
    db.add(msg)
    await db.flush()
    return msg


async def get_recent_messages(
    db: AsyncSession, conversation_id: uuid.UUID, limit: int = 20
) -> list[dict[str, str]]:
    """Get recent messages formatted for the LLM context window."""
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc(), Message.role.asc())
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
        .order_by(Message.created_at.asc(), Message.role.desc())
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

    # Exemplars require human review: do not automatically promote raw user-rated answers
    # to verified_exemplars (promotions are handled via Admin /exemplars/promote).
    try:
        from app.services.exemplar_service import ExemplarService
        from app.providers.embedding_base import EmbeddingProvider

        emb_provider = embeddings if isinstance(embeddings, EmbeddingProvider) else None
        if emb_provider and request.rating == -1:
            # If negatively rated, ensure it is pruned if it was ever in the exemplar store
            exemplar_service = ExemplarService(emb_provider)
            await exemplar_service.remove_exemplar(request.message_id)
    except Exception as e:
        logger.warning("Feedback exemplar pruning check encountered an error: %s", e)

    return FeedbackResponse(id=feedback.id, status="received")

