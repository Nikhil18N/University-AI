"""Video and social media service — contextually recommends official SR University YouTube & Instagram media."""

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


# Topics where video is strictly irrelevant / noise / inappropriate
_STRICT_NO_VIDEO_KEYWORDS = (
    "attendance",
    "condonation",
    "detention",
    "exam fee",
    "hall ticket",
    "grading system",
    "cgpa",
    "sgpa",
    "credit transfer",
    "backlog",
    "supplementary",
    "malpractice",
    "contact number",
    "email id",
    "phone number",
    "ifsc",
    "bank account",
    "refund",
    "cutoff",
    "cut-off",
    "minimum marks",
    "percentage required",
    "eligibility criteria",
    "board score",
    "fee breakdown",
    "bus fee",
    "route number",
)

# Explicit cues that the user wants to watch or see visual content
_EXPLICIT_VIDEO_CUES = (
    "video",
    "videos",
    "watch",
    "youtube",
    "yt",
    "insta",
    "instagram",
    "reel",
    "reels",
    "tour",
    "walkthrough",
    "drone",
    "look like",
    "how does it look",
    "see the campus",
    "see the hostel",
    "visual",
    "clip",
    "shorts",
)

_INSTAGRAM_CUES = ("instagram", "insta", "reel", "reels")
_YOUTUBE_CUES = ("youtube", "yt", "channel")


def get_relevant_videos(
    user_message: str,
    answer: str,
    sources: list[dict] | None = None,
    limit: int = 2,
) -> list[dict]:
    """Determine whether video recommendations should be shown and return matching media.

    Guarantees:
    - Never shows media on greetings, strict rules, fees, cutoffs, or error fallbacks.
    - Always shows when the user explicitly asks for videos/reels/tours.
    - Selectively shows on primary exploratory questions about campus, hostels, SRiX, fests, or sports.
    - Prioritizes Instagram when asked for reels/insta, YouTube when asked for videos/yt.
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

    # 2. Check for Explicit Request & Platform Preference
    is_explicit = any(cue in msg_lower for cue in _EXPLICIT_VIDEO_CUES)
    wants_instagram = any(cue in msg_lower for cue in _INSTAGRAM_CUES)
    wants_youtube = any(cue in msg_lower for cue in _YOUTUBE_CUES)

    # 3. Calculate match scores
    scores: list[tuple[float, dict]] = []

    for v in videos:
        score = 0.0
        platform = v.get("platform", "youtube")
        keywords = v.get("keywords", [])
        title_lower = v.get("title", "").lower()
        desc_lower = v.get("description", "").lower()
        category_lower = v.get("category", "").lower()

        # Platform preference boost
        if wants_instagram:
            if platform == "instagram":
                score += 5.0
            else:
                score -= 2.0
        elif wants_youtube:
            if platform == "youtube":
                score += 5.0
            else:
                score -= 2.0

        # Check keyword matches in user message
        for kw in keywords:
            if kw in msg_lower:
                score += 3.5
            elif kw in ans_lower:
                score += 0.8

        # Check category match
        for cat_word in category_lower.split():
            if len(cat_word) > 3 and cat_word in msg_lower:
                score += 2.5

        # Check title word match
        if any(w in msg_lower for w in title_lower.split() if len(w) > 3):
            score += 2.0

        # Check source document alignment
        if sources:
            for s in sources:
                src_title = (s.get("title") or "").lower()
                if "campus" in src_title and "campus" in category_lower:
                    score += 1.5
                elif "hostel" in src_title and "hostel" in category_lower:
                    score += 1.5
                elif "placement" in src_title and "placement" in category_lower:
                    score += 1.5

        scores.append((score, v))

    # Sort descending by score
    scores.sort(key=lambda x: x[0], reverse=True)

    # 4. Selection based on intent and threshold
    if is_explicit:
        # If user explicitly asked for videos/reels, return top matches
        matched = [v for s, v in scores if s > 0]
        if matched:
            return matched[:limit]
        # Generic explicit request like "show me videos" -> return top showcase videos
        return [v for s, v in scores][:limit]

    # For implicit exploratory questions, require a solid relevance score (threshold = 3.5)
    # e.g., asking "How is the campus life and hostels?" or "Tell me about SRiX"
    threshold = 3.5
    matched = [v for s, v in scores if s >= threshold]
    if matched:
        return matched[:limit]

    return []


def create_video_card(videos: list[dict], is_explicit: bool = False) -> dict:
    """Format structured video & social media recommendation card."""
    has_insta = any(v.get("platform") == "instagram" for v in videos)
    has_youtube = any(v.get("platform") == "youtube" for v in videos)

    if has_insta and has_youtube:
        title = "Official SR University Media & Tours"
    elif has_insta:
        title = "Official SR University Instagram Reels"
    else:
        title = "Official SR University Video Tours" if is_explicit else "Related Campus Videos"

    return {
        "type": "video_recommendations",
        "title": title,
        "channel_name": "SR University Official",
        "channel_url": "https://www.youtube.com/@SRUniversity/videos",
        "instagram_url": "https://www.instagram.com/sr_university/",
        "instagram_handle": "@sr_university",
        "videos": videos,
    }
