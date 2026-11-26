"""Post-processing constants and helpers for sru_agent responses."""
from __future__ import annotations

import hashlib
import re

from . import memory

CARD_TOOLS = {
    "calculate_fee",
    "check_eligibility",
    "request_counsellor_callback",
    "request_campus_visit_callback",
    "get_contact_and_apply_links",
    "get_university_videos",
    "find_faculty",
}
FEE_TOOLS = {"calculate_fee", "compare_programs", "get_program_info", "get_special_concessions"}
INFO_CARDS = {"placement_highlights", "hostel_facilities", "campus_tour", "curriculum"}
VIDEO_CARDS = {"video_recommendations", "get_university_videos", "event_highlights"}
HAS_MD_TABLE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)+\|?\s*$", re.MULTILINE)


def vary(options: list[str], *seed) -> str:
    """Deterministic per-turn wording variation."""
    key = "|".join(str(x) for x in seed)
    return options[int(hashlib.md5(key.encode()).hexdigest(), 16) % len(options)]


async def with_topic_videos(message: str, text: str, cards: list, session_id: str, conversation_id) -> list:
    """Attach up to 2 official SRU videos on the topic asked, at most once per topic per chat."""
    from app.services import video_service

    types_set = {c.get("type") for c in cards if isinstance(c, dict)}
    if types_set & VIDEO_CARDS:
        vids = [
            v
            for c in cards
            if isinstance(c, dict) and c.get("type") in VIDEO_CARDS
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
    if types_set - INFO_CARDS:
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
