"""Lasting storage for what the admissions agent knows about a student.

The agent keeps profiles and recent messages in Redis (or server memory), which forget after
24 hours or a restart. These functions put the same information in PostgreSQL so that:
  * a returning student is still known (name, mobile number, course, marks),
  * Settings > My details shows the same values the chat uses,
  * a chat reopened later still has its context.

Profiles are stored in the existing `user_memories` table, one row per field, with the key
prefix "agent." (no new table, no migration).
"""
import json
import logging
import uuid

from sqlalchemy import delete, select

from app.db.session import async_session_factory
from app.models.lead import ProspectiveLead
from app.models.memory import UserMemory

logger = logging.getLogger(__name__)

PREFIX = "agent."
# Small facts only. The last fee estimate is recalculated on demand, so it is not stored.
DURABLE_KEYS = ("name", "phone", "program_interest", "percent", "board", "eapcet_rank", "jee_percentile",
                "ib_score", "city", "is_parent", "language", "phone_saved", "last_lead_id",
                "last_lead_type", "last_lead_key", "open_request")
_last_saved: dict[str, dict] = {}


def _durable(profile: dict) -> dict:
    out = {}
    for key in DURABLE_KEYS:
        value = profile.get(key)
        if value in (None, ""):
            continue
        encoded = json.dumps(value, ensure_ascii=False)
        if len(encoded) <= 255:
            out[key] = encoded
    return out


async def load_profile(session_id: str) -> dict:
    async with async_session_factory() as db:
        rows = (await db.execute(
            select(UserMemory).where(UserMemory.session_id == session_id,
                                     UserMemory.memory_key.like(PREFIX + "%")))).scalars().all()
    profile = {}
    for row in rows:
        try:
            profile[row.memory_key[len(PREFIX):]] = json.loads(row.memory_value)
        except (TypeError, ValueError):
            continue
    _last_saved[session_id] = _durable(profile)
    return profile


async def save_profile(session_id: str, profile: dict) -> None:
    wanted = _durable(profile)
    before = _last_saved.get(session_id)
    if before == wanted:
        return  # nothing changed: no database round trip
    async with async_session_factory() as db:
        rows = (await db.execute(
            select(UserMemory).where(UserMemory.session_id == session_id,
                                     UserMemory.memory_key.like(PREFIX + "%")))).scalars().all()
        existing = {row.memory_key[len(PREFIX):]: row for row in rows}
        for key, encoded in wanted.items():
            row = existing.get(key)
            if row is None:
                db.add(UserMemory(id=uuid.uuid4(), session_id=session_id, memory_key=PREFIX + key,
                                  memory_value=encoded, consented=True))
            elif row.memory_value != encoded:
                row.memory_value = encoded
        gone = [PREFIX + key for key in existing if key not in wanted]
        if gone:
            await db.execute(delete(UserMemory).where(UserMemory.session_id == session_id,
                                                      UserMemory.memory_key.in_(gone)))
        await db.commit()
    _last_saved[session_id] = wanted
    if len(_last_saved) > 5000:  # keep the change-detection cache small
        for key in list(_last_saved)[:1000]:
            _last_saved.pop(key, None)


async def load_history(session_id: str, conversation_id: str) -> list:
    """The last messages of a saved conversation, in the shape the agent's memory uses."""
    from app.models.conversation import Conversation
    from app.services import conversation_service

    try:
        conv_uuid = uuid.UUID(str(conversation_id))
    except (TypeError, ValueError):
        return []
    async with async_session_factory() as db:
        owner = (await db.execute(select(Conversation.session_id).where(Conversation.id == conv_uuid))).scalar()
        if owner != session_id:
            return []  # never read another student's conversation
        messages = await conversation_service.get_recent_messages(db, conv_uuid, limit=12)
    return [{"role": "user" if m["role"] == "user" else "model", "text": m["content"]}
            for m in messages if m.get("content")]


async def update_lead_contact(lead_id: str, name: str | None = None, phone: str | None = None) -> bool:
    """The student corrected their name or mobile number: fix the saved callback / visit request too."""
    try:
        lead_uuid = uuid.UUID(str(lead_id))
    except (TypeError, ValueError):
        return False
    async with async_session_factory() as db:
        lead = await db.get(ProspectiveLead, lead_uuid)
        if lead is None:
            return False
        meta = dict(lead.metadata_ or {})
        if phone and phone != lead.phone:
            meta["previous_phone"] = lead.phone
            lead.phone = phone
        if name and name != lead.name:
            lead.name = name
        lead.metadata_ = meta
        await db.commit()
    logger.info("Lead %s contact details updated by the student", lead_id)
    return True
