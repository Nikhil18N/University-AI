"""Stateless flow, video, marks-form, and variation helpers for the SRU agent."""

import hashlib
import re

from . import fee_coordinator, fee_intake, fee_journey, fees, memory

_INFO_CARDS = {"placement_highlights", "hostel_facilities", "campus_tour", "curriculum"}
_VIDEO_CARDS = {"video_recommendations", "get_university_videos", "event_highlights"}
_ASKS_MARKS = re.compile(
    r"\b(?:what|which|share|enter|send|tell\s+me|type|give\s+me)\b[^?\n]{0,70}\b(?:marks|percentage|score|aggregate)\b[^?\n]*\?"
    r"|\bwhat\s+percentage\s+did\s+you\s+(?:score|get)\b",
    re.I,
)
_MARKS_CARD_TYPES = {"counsellor_marks_input", "academic_details_form", "fee_scholarship_form"}


def _vary(options: list[str], *seed) -> str:
    """Deterministically pick one natural phrasing variation for a line."""
    key = "|".join(str(x) for x in seed)
    return options[int(hashlib.md5(key.encode()).hexdigest(), 16) % len(options)]


def _other_program_named(message: str, conv_state: dict) -> bool:
    """True when a student asks about a different programme during an active fee evaluation."""
    named = fees.find_program(message or "")
    current = fees.find_program(str((conv_state.get(fee_journey.KEY) or {}).get("program") or ""))
    return bool(named and current and named != current and not fee_journey._SWITCH.search(message or ""))


def _open_step(profile: dict, conv_state: dict) -> dict | None:
    """Delegate to fee_coordinator.open_step."""
    return fee_coordinator.open_step(profile, conv_state)


async def _with_topic_videos(message: str, text: str, cards: list, session_id: str, conversation_id) -> list:
    """Attach up to 2 official SRU videos for informational topics, once per topic per chat."""
    from app.services import video_service

    types = {c.get("type") for c in cards if isinstance(c, dict)}
    if types & _VIDEO_CARDS:
        vids = [
            v
            for c in cards
            if isinstance(c, dict) and c.get("type") in _VIDEO_CARDS
            for v in ((c.get("data") or c).get("videos") or [])
            if isinstance(v, dict)
        ]
        if vids:
            state = await memory.get_conversation_state(session_id, conversation_id)
            topic = video_service.video_topic(message) or vids[0].get("category")
            await memory.update_conversation_state(
                session_id,
                conversation_id,
                video_topics=(list(state.get("video_topics") or []) + ([topic] if topic else []))[-12:],
                videos_shown=(list(state.get("videos_shown") or []) + [v.get("id") for v in vids])[-30:],
            )
        return cards
    if types - _INFO_CARDS:
        return cards
    if re.search(r"(?:^|\n)\s*Step\s+\d|\bwhich\s+(?:programme|program|board|branch)\b", text or "", re.I):
        return cards
    state = await memory.get_conversation_state(session_id, conversation_id)
    if state.get("fee_intake", {}) and (state.get("fee_intake") or {}).get("waiting_for") not in (None, "done"):
        return cards
    topics = list(state.get("video_topics") or [])
    shown = set(state.get("videos_shown") or [])
    topic = video_service.video_topic(message)
    if not topic or topic in topics:
        return cards
    topic, vids = video_service.topic_videos(message, exclude=shown, limit=2)
    if not vids:
        return cards
    await memory.update_conversation_state(
        session_id,
        conversation_id,
        video_topics=(topics + [topic])[-12:],
        videos_shown=(list(shown) + [v["id"] for v in vids])[-30:],
    )
    return cards + [video_service.create_video_card(vids, topic=topic)]


async def _offer_fee_chart(session_id, conversation_id, cards) -> bool:
    """True once per conversation when a fee card includes hostel or transport."""
    if not any(
        isinstance(c, dict)
        and c.get("type") == "calculate_fee"
        and isinstance(c.get("data"), dict)
        and (c["data"].get("has_hostel") or c["data"].get("transport_per_year"))
        for c in cards or ()
    ):
        return False
    state = await memory.get_conversation_state(session_id, conversation_id)
    if state.get("fee_chart_offered"):
        return False
    await memory.update_conversation_state(session_id, conversation_id, fee_chart_offered=True, offer="fee_chart")
    return True


def _with_marks_form(text: str, cards: list, session_id: str = "", profile: dict | None = None) -> list:
    """Attach a marks-input card whenever the reply asks for marks or percentage."""
    if any(isinstance(c, dict) and c.get("type") in _MARKS_CARD_TYPES for c in cards):
        return cards
    if not _ASKS_MARKS.search(text or "") or (
        re.search(r"\b(?:rank|percentile)\b[^?\n]*\?\s*$", text or "", re.I)
        and not re.search(r"\bmarks\b", text or "", re.I)
    ):
        return cards
    if re.search(r"which\s+board|where\s+are\s+you\s+in\s+intermediate|which\s+group", text or "", re.I):
        return cards
    mx = None
    b_key = (profile or {}).get("board_key")
    m = re.search(r"\(out\s+of\s+(\d{3,4})\)", text or "")
    if m:
        mx = int(m.group(1))
    elif b_key:
        mx = fee_intake.get_max_marks(b_key, (profile or {}).get("academic_stage") or "completed")
    elif re.search(r"\bpercentage\b", text or "", re.I) and not re.search(r"\bmarks\b", text or "", re.I):
        mx = 100
    card = {
        "type": "counsellor_marks_input",
        "title": "Enter your marks",
        "max_marks": mx,
        "step_label": "Your marks",
        "hint": "You can also type them, e.g. 870 out of 1000 or 87%.",
    }
    if b_key:
        card["board_key"] = b_key
    return cards + [card]
