"""Video service — pure dense semantic vector recommendations for official SR University YouTube media.

Zero keyword matching:
All relevance and topic boundaries (including natural exclusion of bus facilities,
attendance rules, exam grading, etc.) are governed strictly by ChromaDB dense cosine distance.
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
import re

logger = logging.getLogger(__name__)

_VIDEOS_FILE = Path(__file__).resolve().parent.parent / "data" / "university_videos.json"
_CACHED_VIDEOS: list[dict] | None = None

VIDEO_SEMANTIC_COLLECTION = "university_videos_semantic"

# Strict semantic distance thresholds for pure cosine similarity (1 - cosine_similarity)
DEFAULT_MAX_SEMANTIC_DISTANCE = 0.25  # High-confidence semantic match
EXPLICIT_MAX_SEMANTIC_DISTANCE = 0.30  # Slightly relaxed when user explicitly asks for video

# Explicit intent cues indicating the user wants to watch a video/tour
_EXPLICIT_VIDEO_CUES = (
    "video",
    "videos",
    "watch",
    "youtube",
    "yt",
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
    "short",
)

_VIDEO_OFFER_REGEX = re.compile(
    r"(?:watch\s+(?:a\s+)?(?:short\s+)?video|video\s+tour|video\s+walkthrough|\(yes\s*/\s*no\))",
    re.I,
)

_AFFIRMATIVE_VIDEO_REGEX = re.compile(
    r"^\s*(?:yes|yeah|yep|sure|show\s+me|yes[,\s]+please|please\s+show|definitely|ok|okay|why\s+not|🎥\s*yes[,\s]+(?:watch|show)\s+video|watch\s+video|show\s+video)[.!?\s]*$",
    re.I,
)

_NEGATIVE_VIDEO_REGEX = re.compile(
    r"^\s*(?:no|nope|no[,\s]+thanks|nah|not\s+now|no\s+need|don'?t|❌\s*no[,\s]+thanks)[.!?\s]*$",
    re.I,
)


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


def _get_video_collection():
    """Retrieve ChromaDB collection for semantic video embeddings."""
    try:
        from app.db.chroma import get_chroma_client

        client = get_chroma_client()
        return client.get_or_create_collection(
            name=VIDEO_SEMANTIC_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
    except Exception as e:
        logger.debug("Could not connect to ChromaDB for video semantic search: %s", e)
        return None


async def sync_video_vectors(embedding_provider=None) -> int:
    """Ensure all curated university videos are embedded and indexed in ChromaDB."""
    try:
        collection = _get_video_collection()
        if not collection:
            return 0
        videos = load_videos()
        if not videos:
            return 0
        if collection.count() == len(videos):
            logger.info(
                "ChromaDB '%s' collection has %d video vectors. Up to date.",
                VIDEO_SEMANTIC_COLLECTION,
                collection.count(),
            )
            return collection.count()

        if not embedding_provider:
            from app.providers.factory import create_embedding_provider

            embedding_provider = create_embedding_provider()

        texts = [
            f"{v['title']}. Category: {v['category']}. Keywords: {', '.join(v.get('keywords', []))}"
            for v in videos
        ]
        embeddings = await embedding_provider.embed(texts)
        ids = [v["id"] for v in videos]
        metadatas = [
            {
                "id": v["id"],
                "platform": "youtube",
                "title": v["title"],
                "category": v["category"],
                "url": v["url"],
                "thumbnail_url": v["thumbnail_url"],
                "type": v.get("type", "video"),
                "channel_name": v.get("channel_name", "SR University Official"),
                "channel_url": v.get("channel_url", "https://www.youtube.com/@SRUniversity/videos"),
            }
            for v in videos
        ]
        collection.upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
        logger.info(
            "Synced %d video vectors into ChromaDB collection '%s'.",
            len(ids),
            VIDEO_SEMANTIC_COLLECTION,
        )
        return collection.count()
    except Exception as e:
        logger.warning("Failed to sync video vectors into ChromaDB: %s", e)
        return 0


def is_explicit_video_query(message: str) -> bool:
    """Return True if message explicitly asks to watch or see videos/tours."""
    msg_lower = message.lower().strip()
    return any(cue in msg_lower for cue in _EXPLICIT_VIDEO_CUES)


def get_semantic_videos(
    query_embedding: list[float] | None,
    limit: int = 2,
    max_distance: float = DEFAULT_MAX_SEMANTIC_DISTANCE,
) -> list[dict]:
    """Retrieve video recommendations purely by dense vector semantic search in ChromaDB.

    Zero keyword dependency:
    - Distance threshold <= max_distance naturally separates conceptually relevant videos
      from topics with no videos (bus facilities, attendance rules, exam condonation, fees).
    """
    if not query_embedding:
        return []

    try:
        collection = _get_video_collection()
        if not collection or collection.count() == 0:
            return []

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(limit + 2, collection.count()),
            include=["metadatas", "distances"],
        )
        if not results["metadatas"] or not results["metadatas"][0]:
            return []

        matched = []
        seen_ids: set[str] = set()
        for meta, dist in zip(results["metadatas"][0], results["distances"][0]):
            if not isinstance(meta, dict):
                continue
            if dist is not None and dist <= max_distance:
                vid_id = meta.get("id") or meta.get("url", "")
                if vid_id not in seen_ids:
                    seen_ids.add(vid_id)
                    matched.append(meta)

        return matched[:limit]
    except Exception as e:
        logger.debug("Semantic video retrieval error: %s", e)
        return []


def get_relevant_videos(
    user_message: str = "",
    answer: str = "",
    sources: list[dict] | None = None,
    limit: int = 2,
    query_embedding: list[float] | None = None,
    is_explicit: bool = False,
) -> list[dict]:
    """Pure semantic video retrieval without any keyword matching.

    Rejection of unrelated topics (transport, attendance, fees, condonation)
    is handled naturally by dense vector distance in ChromaDB.
    """
    msg_lower = user_message.lower().strip()
    ans_lower = answer.lower()

    # Greetings / basic pleasantries
    if msg_lower in ("hi", "hello", "hey", "hola", "good morning", "good evening", "thanks", "thank you", "bye"):
        return []

    # Unverified / error fallback
    if "could not be verified" in ans_lower or "insufficient evidence" in ans_lower:
        return []

    if not is_explicit:
        is_explicit = is_explicit_video_query(user_message)

    max_dist = EXPLICIT_MAX_SEMANTIC_DISTANCE if is_explicit else DEFAULT_MAX_SEMANTIC_DISTANCE

    if query_embedding:
        return get_semantic_videos(query_embedding, limit=limit, max_distance=max_dist)

    # When query_embedding is not precomputed, look up using embedding provider
    if user_message:
        try:
            import asyncio
            from app.providers.factory import create_embedding_provider

            provider = create_embedding_provider()
            loop = asyncio.get_event_loop()
            if not loop.is_running():
                embs = loop.run_until_complete(provider.embed([user_message]))
                if embs:
                    return get_semantic_videos(embs[0], limit=limit, max_distance=max_dist)
        except Exception:
            pass

    return []


def format_video_offer_prompt(answer: str, category_name: str = "this") -> str:
    """Ensure answer ends with a clean Yes/No video offer invitation using the semantically matched video category."""
    offer_question = f"Would you like to watch a short video tour of {category_name}? (Yes / No)"

    if _VIDEO_OFFER_REGEX.search(answer):
        return answer

    trailing_pattern = re.compile(
        r"\n*(?:Would you like|Do you want|Should we|Feel free to|Let me know if you would like)[^\n?]+\?\s*$",
        re.I,
    )
    if trailing_pattern.search(answer):
        cleaned = trailing_pattern.sub("", answer).strip()
        return f"{cleaned}\n\n{offer_question}"

    return f"{answer.rstrip()}\n\n{offer_question}"


def check_video_affirmative_or_negative(
    user_message: str,
    recent_messages: list[dict],
) -> tuple[bool, bool]:
    """Check if user_message confirms or declines a prior video offer."""
    if not recent_messages:
        return False, False

    msg = user_message.strip()

    history = recent_messages
    if history and history[-1].get("role") == "user" and history[-1].get("content") == user_message:
        history = history[:-1]

    last_assistant_msg = None
    for m in reversed(history):
        if m.get("role") == "assistant":
            last_assistant_msg = m
            break

    if not last_assistant_msg:
        if "🎥" in msg and "watch video" in msg.lower():
            return True, False
        return False, False

    assistant_content = last_assistant_msg.get("content", "") if isinstance(last_assistant_msg, dict) else ""
    raw_meta = last_assistant_msg.get("metadata") if isinstance(last_assistant_msg, dict) else {}
    metadata = raw_meta if isinstance(raw_meta, dict) else {}
    suggestions = metadata.get("suggestions") if isinstance(metadata.get("suggestions"), list) else []

    video_offered = (
        bool(_VIDEO_OFFER_REGEX.search(assistant_content))
        or any("video" in str(s).lower() for s in suggestions)
    )

    if not video_offered:
        if "🎥" in msg and "watch video" in msg.lower():
            return True, False
        return False, False

    if _AFFIRMATIVE_VIDEO_REGEX.match(msg):
        return True, False

    if _NEGATIVE_VIDEO_REGEX.match(msg):
        return False, True

    return False, False


def get_post_video_suggestions(category_name: str = "") -> list[str]:
    """Return contextual suggestion chips after video recommendation is shown."""
    return [
        "🍽️ Mess & Food Quality",
        "🕒 Hostel Timings & Rules",
        "💰 Fee Structure",
        "📋 How to Apply",
    ]


def create_video_card(videos: list[dict], is_explicit: bool = False) -> dict:
    """Format structured official YouTube video recommendation card."""
    title = "Official SR University Video Tours" if is_explicit else "Related Campus Videos"

    return {
        "type": "video_recommendations",
        "title": title,
        "channel_name": "SR University Official",
        "channel_url": "https://www.youtube.com/@SRUniversity/videos",
        "videos": videos,
    }
