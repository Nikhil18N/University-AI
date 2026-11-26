"""Reply to a message and edit the latest typed message (v4.17.1).

Business rules for the chat's message actions, kept out of the route handler:
  * a referenced or edited message must belong to the student's own conversation (session ownership);
  * replying gives the agent the referenced message and, for a fee card, that card's own estimate (and whether a
    newer estimate exists), so "what does this amount include?" is answered about THAT estimate;
  * only the latest typed student message can be edited (buttons may have been tapped after it), and only while
    the state from before it is known; editing restores that state and replaces the message and everything after
    it (archived: marked superseded, never deleted); the chat then replays the later button choices that the new
    answer still offers. If that turn or any later one completed an external action (a callback or visit request),
    the message cannot be edited, so editing never repeats or silently undoes it.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.conversation import Conversation
from app.models.message import Message

_FEE_CARDS = ("fee_summary", "calculate_fee", "fee_plan", "concession_fee", "fee_structure_detailed",
              "detailed_fee_structure", "fee_breakdown")
_CARD_KEYS = ("program", "course", "academic_year", "scholarship_percent", "scholarship", "first_year_total",
              "first_year_total_payable", "payable_confirmed", "payable_after_approval", "sem1_total_payable",
              "sem2_total_payable", "semester_1", "semester_2", "semesters", "hostel", "transport", "concession",
              "pending", "full_course_total", "course_total", "category")


_ACTION_DONE = ("This message started a request to the admissions team, which editing can't undo. "
                "Please send a new message instead.")


class MessageActionError(Exception):
    """A reply or edit that cannot be done; the message is shown to the student as it is."""


def _uuid(value) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


async def _owned_messages(db, session_id: str, conversation_id) -> list[Message]:
    conv_uuid = _uuid(conversation_id)
    if conv_uuid is None:
        raise MessageActionError("That message is not in this conversation.")
    owner = (await db.execute(select(Conversation.session_id).where(Conversation.id == conv_uuid))).scalar()
    if owner != session_id:
        raise MessageActionError("That message is not in this conversation.")
    rows = (await db.execute(select(Message).where(Message.conversation_id == conv_uuid)
                             .order_by(Message.created_at))).scalars().all()
    return [m for m in rows if not (m.metadata_ or {}).get("superseded")]


def _card_brief(card: dict) -> dict:
    data = card.get("data") if isinstance(card.get("data"), dict) else card
    return {"type": card.get("type"), **{k: data[k] for k in _CARD_KEYS if isinstance(data, dict) and data.get(k)
                                       not in (None, "", [])}}


async def reply_context(session_id: str, conversation_id, message_id) -> dict:
    """The referenced message (text and fee cards), checked to be in the student's conversation."""
    target = _uuid(message_id)
    async with async_session_factory() as db:
        msgs = await _owned_messages(db, session_id, conversation_id)
    idx = next((i for i, m in enumerate(msgs) if m.id == target), None)
    if idx is None:
        raise MessageActionError("That message is not in this conversation.")
    m = msgs[idx]
    cards = [c for c in (m.metadata_ or {}).get("cards") or [] if isinstance(c, dict) and c.get("type") in _FEE_CARDS]
    newer_estimate = any(
        any(isinstance(c, dict) and c.get("type") in _FEE_CARDS for c in (later.metadata_ or {}).get("cards") or [])
        for later in msgs[idx + 1:] if later.role == "assistant")
    return {"message_id": str(m.id), "role": m.role, "text": (m.content or "")[:1500],
            "fee_cards": [_card_brief(c) for c in cards][:2],
            "is_latest_estimate": bool(cards) and not newer_estimate}


async def prepare_edit(session_id: str, conversation_id, message_id, snapshot: dict | None) -> dict:
    """Check the edit is allowed; archive the edited message and everything after it. Returns the snapshot to restore."""
    target = _uuid(message_id)
    async with async_session_factory() as db:
        msgs = await _owned_messages(db, session_id, conversation_id)
        idx = next((i for i, m in enumerate(msgs) if m.id == target and m.role == "user"), None)
        if idx is None:
            raise MessageActionError("Only your latest message can be edited.")
        original = msgs[idx]
        if (original.metadata_ or {}).get("source") not in (None, "typed"):
            # a button / card option the bot offered: choose again from the options instead
            raise MessageActionError("Only a message you typed can be edited.")
        later_users = [m for m in msgs[idx + 1:] if m.role == "user"]
        if any((m.metadata_ or {}).get("source") != "button" for m in later_users):
            raise MessageActionError("Only your latest message can be edited.")   # something was typed after it
        if any((m.metadata_ or {}).get("action_done") for m in [original, *later_users]) or (
                snapshot and snapshot.get("turn_id") == str(target) and snapshot.get("action_done")):
            raise MessageActionError(_ACTION_DONE)
        if not snapshot:
            raise MessageActionError("This message can no longer be edited. Please send a new message instead.")
        if snapshot.get("turn_id") != str(target):
            raise MessageActionError("Only your latest message can be edited.")
        # the edited message and everything after it is replaced (archived, never deleted); the chat replays the
        # buttons tapped after it when the new answer still offers them
        for m in msgs[idx:]:
            m.metadata_ = {**(m.metadata_ or {}), "superseded": True, "superseded_by_edit": True}
        await db.commit()
    return snapshot
