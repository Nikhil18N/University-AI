"""Admin service — business logic for conversation inspection, bulk training export, and model improvement."""

import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import Conversation
from app.models.feedback import Feedback
from app.models.message import Message
from app.providers.embedding_base import EmbeddingProvider
from app.schemas.admin import (
    AdminConversationDetailResponse,
    AdminConversationItem,
    AdminConversationListResponse,
    AdminMessageDetail,
    AdminMessageFeedback,
)
from app.services.exemplar_service import ExemplarService

logger = logging.getLogger(__name__)


def _parse_sources_to_dict(sources_data: dict | list | None) -> list[dict] | None:
    """Parse stored sources JSON into serializable list of dictionaries."""
    if not sources_data:
        return None
    if isinstance(sources_data, dict):
        sources_data = sources_data.get("sources", [])
    if isinstance(sources_data, list):
        parsed = []
        for s in sources_data:
            if isinstance(s, dict):
                parsed.append(s)
            elif hasattr(s, "model_dump"):
                parsed.append(s.model_dump())
        return parsed
    return None


def _build_conversations_filter(
    search: str | None = None,
    feedback_filter: str | None = None,
):
    """Build reusable filter conditions for conversations."""
    conditions = []

    if search and search.strip():
        term = f"%{search.strip()}%"
        matching_msg_convs = select(Message.conversation_id).where(
            Message.content.ilike(term)
        )
        conditions.append(
            (Conversation.title.ilike(term))
            | (Conversation.session_id.ilike(term))
            | (Conversation.id.in_(matching_msg_convs))
        )

    if feedback_filter:
        flt = feedback_filter.strip().lower()
        if flt == "positive":
            convs_with_pos = select(Feedback.conversation_id).where(Feedback.rating == 1)
            conditions.append(Conversation.id.in_(convs_with_pos))
        elif flt == "negative":
            convs_with_neg = select(Feedback.conversation_id).where(Feedback.rating == -1)
            conditions.append(Conversation.id.in_(convs_with_neg))
        elif flt == "any":
            convs_with_fb = select(Feedback.conversation_id)
            conditions.append(Conversation.id.in_(convs_with_fb))
        elif flt == "none":
            convs_with_fb = select(Feedback.conversation_id)
            conditions.append(~Conversation.id.in_(convs_with_fb))

    return conditions


async def list_all_conversations(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 50,
    search: str | None = None,
    feedback_filter: str | None = None,
) -> AdminConversationListResponse:
    """List all conversations with fast batch metrics calculation and flexible pagination."""
    page = max(1, page)
    page_size = min(max(1, page_size), 1000)
    offset = (page - 1) * page_size

    stmt = select(Conversation)
    for cond in _build_conversations_filter(search, feedback_filter):
        stmt = stmt.where(cond)

    # Total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.scalar(count_stmt)) or 0

    # Paginated conversations
    stmt = stmt.order_by(desc(Conversation.updated_at)).offset(offset).limit(page_size)
    result = await db.execute(stmt)
    conversations = result.scalars().all()

    if not conversations:
        return AdminConversationListResponse(
            conversations=[],
            total=total,
            page=page,
            page_size=page_size,
        )

    conv_ids = [c.id for c in conversations]

    # Batch message counts
    msg_counts_stmt = (
        select(
            Message.conversation_id,
            func.count(Message.id).label("total_msgs"),
            func.count(func.nullif(Message.role != "user", True)).label("user_msgs"),
            func.count(func.nullif(Message.role != "assistant", True)).label("assistant_msgs"),
        )
        .where(Message.conversation_id.in_(conv_ids))
        .group_by(Message.conversation_id)
    )
    msg_res = await db.execute(msg_counts_stmt)
    msg_map = {row.conversation_id: row for row in msg_res}

    # Batch feedback counts
    fb_counts_stmt = (
        select(
            Feedback.conversation_id,
            func.count(func.nullif(Feedback.rating != 1, True)).label("pos_fb"),
            func.count(func.nullif(Feedback.rating != -1, True)).label("neg_fb"),
        )
        .where(Feedback.conversation_id.in_(conv_ids))
        .group_by(Feedback.conversation_id)
    )
    fb_res = await db.execute(fb_counts_stmt)
    fb_map = {row.conversation_id: row for row in fb_res}

    # Batch last messages
    # Subquery for latest message id per conversation
    latest_msg_subq = (
        select(
            Message.conversation_id,
            func.max(Message.created_at).label("max_created"),
        )
        .where(Message.conversation_id.in_(conv_ids))
        .group_by(Message.conversation_id)
        .subquery()
    )
    latest_msg_stmt = select(Message.conversation_id, Message.content).join(
        latest_msg_subq,
        (Message.conversation_id == latest_msg_subq.c.conversation_id)
        & (Message.created_at == latest_msg_subq.c.max_created),
    )
    latest_res = await db.execute(latest_msg_stmt)
    latest_map = {row.conversation_id: row.content for row in latest_res}

    conv_items: list[AdminConversationItem] = []
    for c in conversations:
        m_counts = msg_map.get(c.id)
        f_counts = fb_map.get(c.id)
        last_msg = latest_map.get(c.id)
        preview = (last_msg[:120] + "...") if last_msg and len(last_msg) > 120 else last_msg

        conv_items.append(
            AdminConversationItem(
                id=c.id,
                session_id=c.session_id,
                title=c.title or "Untitled Conversation",
                message_count=m_counts.total_msgs if m_counts else 0,
                user_message_count=m_counts.user_msgs if m_counts else 0,
                assistant_message_count=m_counts.assistant_msgs if m_counts else 0,
                positive_feedback_count=f_counts.pos_fb if f_counts else 0,
                negative_feedback_count=f_counts.neg_fb if f_counts else 0,
                created_at=c.created_at,
                updated_at=c.updated_at,
                last_message_preview=preview,
            )
        )

    return AdminConversationListResponse(
        conversations=conv_items,
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_conversation_detail(
    db: AsyncSession, conversation_id: UUID
) -> AdminConversationDetailResponse | None:
    """Retrieve full conversation transcript with messages, sources, and user feedback."""
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id)
    )
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()
    if conv is None:
        return None

    # Fetch feedback for all messages in this conversation
    fb_stmt = select(Feedback).where(Feedback.conversation_id == conversation_id)
    fb_result = await db.execute(fb_stmt)
    feedback_map: dict[UUID, Feedback] = {
        fb.message_id: fb for fb in fb_result.scalars().all()
    }

    message_details: list[AdminMessageDetail] = []
    for m in conv.messages:
        fb = feedback_map.get(m.id)
        fb_schema = (
            AdminMessageFeedback(
                id=fb.id,
                rating=fb.rating,
                comment=fb.comment,
                created_at=fb.created_at,
            )
            if fb
            else None
        )

        message_details.append(
            AdminMessageDetail(
                id=m.id,
                role=m.role,
                content=m.content,
                model=m.model,
                sources=_parse_sources_to_dict(m.sources),
                feedback=fb_schema,
                created_at=m.created_at,
            )
        )

    return AdminConversationDetailResponse(
        id=conv.id,
        session_id=conv.session_id,
        title=conv.title or "Untitled Conversation",
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=message_details,
    )


async def delete_conversation_by_admin(
    db: AsyncSession, conversation_id: UUID
) -> bool:
    """Delete a conversation and all its messages."""
    stmt = select(Conversation).where(Conversation.id == conversation_id)
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()
    if conv is None:
        return False

    await db.delete(conv)
    await db.commit()
    return True


async def promote_qa_exemplar(
    embeddings: EmbeddingProvider,
    message_id: UUID,
    question: str,
    answer: str,
) -> bool:
    """Register verified Q&A into ChromaDB verified_exemplars collection."""
    service = ExemplarService(embeddings)
    return await service.register_exemplar(
        message_id=message_id,
        question=question,
        answer=answer,
    )


async def export_all_conversations_markdown(
    db: AsyncSession,
    search: str | None = None,
    feedback_filter: str | None = None,
) -> str:
    """Export ALL student conversations into a unified Markdown document formatted for AI training and evaluation."""
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .order_by(desc(Conversation.created_at))
    )

    for cond in _build_conversations_filter(search, feedback_filter):
        stmt = stmt.where(cond)

    result = await db.execute(stmt)
    conversations = result.scalars().all()

    # Pre-fetch feedback
    fb_res = await db.execute(select(Feedback))
    feedback_map = {f.message_id: f for f in fb_res.scalars().all()}

    lines: list[str] = [
        "# University AI Companion — Student Conversation Training Dataset",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"**Total Conversations:** {len(conversations)}",
        "**Purpose:** Fine-tuning, prompt optimization, RAG retrieval verification, and benchmark evaluation.",
        "\n---\n",
    ]

    for idx, conv in enumerate(conversations, 1):
        lines.append(f"## [{idx}/{len(conversations)}] Conversation: {conv.title or 'Untitled'}")
        lines.append(f"- **Conversation ID:** `{conv.id}`")
        lines.append(f"- **Session ID:** `{conv.session_id}`")
        lines.append(f"- **Started At:** {conv.created_at.strftime('%Y-%m-%d %H:%M:%S') if conv.created_at else 'N/A'}")
        lines.append(f"- **Total Messages:** {len(conv.messages)}")
        lines.append("\n### Dialogue Transcript\n")

        if not conv.messages:
            lines.append("*(No messages in this conversation)*\n")
            lines.append("---\n")
            continue

        for msg in conv.messages:
            timestamp = msg.created_at.strftime('%H:%M:%S') if msg.created_at else ''
            if msg.role == "user":
                lines.append(f"**👤 Student** ({timestamp}):\n{msg.content}\n")
            else:
                model_info = f" [{msg.model}]" if msg.model else ""
                lines.append(f"**🤖 AI Companion{model_info}** ({timestamp}):\n{msg.content}\n")

                # Sources
                sources = _parse_sources_to_dict(msg.sources)
                if sources:
                    lines.append("*Retrieved Sources:*")
                    for s in sources:
                        title = s.get("title", "Unknown document")
                        page = f" (page {s.get('page')})" if s.get("page") else ""
                        dept = f" [{s.get('department')}]" if s.get("department") else ""
                        lines.append(f"- {title}{page}{dept}")
                    lines.append("")

                # Feedback
                fb = feedback_map.get(msg.id)
                if fb:
                    fb_str = "👍 Helpful" if fb.rating == 1 else "👎 Inaccurate"
                    comment_str = f' — "{fb.comment}"' if fb.comment else ""
                    lines.append(f"*Student Rating:* {fb_str}{comment_str}\n")

        lines.append("---\n")

    return "\n".join(lines)


async def export_all_conversations_json(
    db: AsyncSession,
    search: str | None = None,
    feedback_filter: str | None = None,
) -> str:
    """Export ALL student conversations into JSON format for direct LLM training pipelines."""
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .order_by(desc(Conversation.created_at))
    )

    for cond in _build_conversations_filter(search, feedback_filter):
        stmt = stmt.where(cond)

    result = await db.execute(stmt)
    conversations = result.scalars().all()

    fb_res = await db.execute(select(Feedback))
    feedback_map = {f.message_id: f for f in fb_res.scalars().all()}

    output = []
    for conv in conversations:
        msgs = []
        for m in conv.messages:
            fb = feedback_map.get(m.id)
            msgs.append({
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "model": m.model,
                "sources": _parse_sources_to_dict(m.sources),
                "feedback": {
                    "rating": fb.rating,
                    "comment": fb.comment,
                } if fb else None,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            })
        output.append({
            "conversation_id": str(conv.id),
            "session_id": conv.session_id,
            "title": conv.title,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            "messages": msgs,
        })

    return json.dumps(output, indent=2)
