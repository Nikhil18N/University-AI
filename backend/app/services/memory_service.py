"""Session-owned memory and bounded summary persistence."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.memory import ConversationSummary, UserMemory
from app.schemas.memory import ALLOWED_MEMORY_KEYS, MemoryItem


def build_extractive_summary(messages: list[dict], max_chars: int = 2000) -> str:
    """Create a bounded, non-generative summary from recent conversation turns."""
    lines: list[str] = []
    for message in messages[-8:]:
        role = message.get("role", "unknown").capitalize()
        content = " ".join(str(message.get("content", "")).split())
        if content:
            lines.append(f"{role}: {content}")
    summary = "\n".join(lines)
    return summary[:max_chars]


def validate_memory_key(key: str) -> str:
    """Allow only non-sensitive preference slots."""
    normalized = key.strip().casefold()
    if normalized not in ALLOWED_MEMORY_KEYS:
        raise HTTPException(
            status_code=422,
            detail="This memory type is not supported.",
        )
    return normalized


async def list_memory(db: AsyncSession, session_id: str) -> list[MemoryItem]:
    result = await db.execute(
        select(UserMemory)
        .where(UserMemory.session_id == session_id, UserMemory.consented.is_(True))
        .order_by(UserMemory.updated_at.desc())
    )
    return [
        MemoryItem(
            id=item.id,
            key=item.memory_key,
            value=item.memory_value,
            consented=item.consented,
            updated_at=item.updated_at,
        )
        for item in result.scalars().all()
    ]


async def get_memory_context(db: AsyncSession, session_id: str) -> str:
    """Format consented preferences for the current session's prompt context."""
    items = await list_memory(db, session_id)
    if not items:
        return ""
    return "Consented user preferences:\n" + "\n".join(
        f"- {item.key}: {item.value}" for item in items
    )


async def save_memory(
    db: AsyncSession,
    session_id: str,
    key: str,
    value: str,
    consent: bool,
) -> MemoryItem:
    if not consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit consent is required before storing memory.",
        )
    normalized_key = validate_memory_key(key)
    result = await db.execute(
        select(UserMemory).where(
            UserMemory.session_id == session_id,
            UserMemory.memory_key == normalized_key,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        item = UserMemory(
            session_id=session_id,
            memory_key=normalized_key,
            memory_value=value.strip(),
            consented=True,
        )
        db.add(item)
    else:
        item.memory_value = value.strip()
        item.consented = True
    await db.flush()
    await db.refresh(item)
    return MemoryItem(
        id=item.id,
        key=item.memory_key,
        value=item.memory_value,
        consented=item.consented,
        updated_at=item.updated_at,
    )


async def delete_memory(db: AsyncSession, session_id: str, key: str) -> bool:
    normalized_key = validate_memory_key(key)
    result = await db.execute(
        delete(UserMemory).where(
            UserMemory.session_id == session_id,
            UserMemory.memory_key == normalized_key,
        )
    )
    return bool(result.rowcount)


async def get_summary(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    session_id: str,
) -> ConversationSummary | None:
    result = await db.execute(
        select(ConversationSummary)
        .join(Conversation, ConversationSummary.conversation_id == Conversation.id)
        .where(
            ConversationSummary.conversation_id == conversation_id,
            Conversation.session_id == session_id,
        )
    )
    return result.scalar_one_or_none()


async def save_summary(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    summary: str,
) -> ConversationSummary:
    result = await db.execute(
        select(ConversationSummary).where(
            ConversationSummary.conversation_id == conversation_id
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        record = ConversationSummary(conversation_id=conversation_id, summary=summary)
        db.add(record)
    else:
        record.summary = summary
    await db.flush()
    return record
