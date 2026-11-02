"""Video service — detects context relevance and returns official university YouTube videos."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_VIDEOS_FILE = Path(__file__).resolve().parent.parent / "data" / "university_videos.json"
_CACHED_VIDEOS: list[dict] | None = None


def load_videos(force_reload: bool = False) -> list[dict]:
    """Load and cache university video metadata from JSON."""
    global _CACHED_VIDEOS
    if _CACHED_VIDEOS is not None and not force_reload:
        return _CACHED_VIDEOS

    try:
        if _VIDEOS_FILE.exists():
            with open(_VIDEOS_FILE, "r", encoding="utf-8") as f:
                _CACHED_VIDEOS = json.load(f)
                return _CACHED_VIDEOS
        else:
            logger.warning("University videos file not found: %s", _VIDEOS_FILE)
            return []
    except Exception as e:
        logger.error("Error loading university videos: %s", e)
        return []


# Topics where video is strictly irrelevant / inappropriate
_STRICT_NO_VIDEO_KEYWORDS = (
    "attendance",
    "condonation",
    "detention",
    "exam fee",
    "hall ticket",
    "grading system",
    "cgpa calculation",
    "sgpa calculation",
    "credit transfer",
    "backlog",
    "supplementary",
    "malpractice",
    "contact number",
    "email id",
    "ifsc",
    "bank account",
    "deadline",
    "refund policy",
)

# Explicit cues that the user wants to watch or see something
_EXPLICIT_VIDEO_CUES = (
    "video",
    "videos",
    "watch",
    "youtube",
    "tour",
    "walkthrough",
    "drone",
    "look like",
    "how does it look",
    "see the campus",
    "see the hostel",
    "visual",
    "clip",
)


def get_relevant_videos(
    user_message: str,
    answer: str,
    sources: list[dict] | None = None,
    limit: int = 2,
) -> list[dict]:
    """Determine whether video recommendations should be shown and return matching videos.

    Guarantees:
    - Never shows videos on greetings, strict exam/attendance rules, or low-evidence fallbacks.
    - Always shows when the user explicitly asks for videos/tours.
    - Selectively shows on primary exploratory questions about campus, hostels, SRiX, and placements.
    """
    videos = load_videos()
    if not videos:
        return []

    msg_lower = user_message.lower().strip()
    ans_lower = answer.lower()

    # 1. Hard Blacklist Check
    # Greetings / pleasantries
    if msg_lower in ("hi", "hello", "hey", "hola", "good morning", "good evening", "thanks", "thank you", "bye"):
        return []

    # Unverified / error fallback
    if "could not be verified" in ans_lower or "insufficient evidence" in ans_lower:
        return []

    # Strict rule questions where videos are noise
    if any(k in msg_lower for k in _STRICT_NO_VIDEO_KEYWORDS):
        return []

    # 2. Check for Explicit Video Request
    is_explicit = any(cue in msg_lower for cue in _EXPLICIT_VIDEO_CUES)

    # 3. Calculate video match scores
    scores: list[tuple[float, dict]] = []

    for v in videos:
        score = 0.0
        keywords = v.get("keywords", [])
        title_lower = v.get("title", "").lower()
        desc_lower = v.get("description", "").lower()

        # Check keyword matches in user message
        for kw in keywords:
            if kw in msg_lower:
                score += 3.0
            elif kw in ans_lower:
                score += 0.8

        # Check title match
        if any(w in msg_lower for w in title_lower.split() if len(w) > 3):
            score += 2.0

        # Check source document alignment
        if sources:
            for s in sources:
                src_title = (s.get("title") or "").lower()
                if "campus" in src_title and "campus" in v.get("category", "").lower():
                    score += 1.5
                elif "hostel" in src_title and "hostel" in v.get("category", "").lower():
                    score += 1.5
                elif "placement" in src_title and "placement" in v.get("category", "").lower():
                    score += 1.5

        scores.append((score, v))

    # Sort descending by score
    scores.sort(key=lambda x: x[0], reverse=True)

    # 4. Selection based on intent and threshold
    if is_explicit:
        # If user explicitly asked for videos, return top matches (or default campus tour if query was generic)
        matched = [v for s, v in scores if s > 0]
        if matched:
            return matched[:limit]
        # Generic explicit request like "show me videos" -> return top 2 showcase videos
        return videos[:limit]

    # For implicit exploratory questions, require a solid relevance score
    # e.g., asking "How is the campus life and hostels?" or "Tell me about SRiX"
    threshold = 3.0
    matched = [v for s, v in scores if s >= threshold]
    if matched:
        return matched[:limit]

    return []


def create_video_card(videos: list[dict], is_explicit: bool = False) -> dict:
    """Format structured video recommendation card."""
    return {
        "type": "video_recommendations",
        "title": "Official SR University Video Tours" if is_explicit else "Related Campus Videos",
        "channel_name": "SR University Official",
        "channel_url": "https://www.youtube.com/@SRUniversity/videos",
        "videos": videos,
    }

