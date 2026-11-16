"""Video service — pure dense semantic vector recommendations for official SR University YouTube media.

Zero keyword matching:
All relevance and topic boundaries (including natural exclusion of bus facilities,
attendance rules, exam grading, etc.) are governed strictly by ChromaDB dense cosine distance.
"""

from __future__ import annotations
import hashlib
import json
import logging
from pathlib import Path
import re

logger = logging.getLogger(__name__)

_VIDEOS_FILE = Path(__file__).resolve().parent.parent / "data" / "university_videos.json"
_CACHED_VIDEOS: list[dict] | None = None

VIDEO_SEMANTIC_COLLECTION = "university_videos_semantic"

# Strict semantic distance thresholds for pure cosine similarity (1 - cosine_similarity)
DEFAULT_MAX_SEMANTIC_DISTANCE = 0.28  # Slightly relaxed from 0.25 to improve recall
EXPLICIT_MAX_SEMANTIC_DISTANCE = 0.38  # Relaxed when user explicitly asks for video

# ---------------------------------------------------------------------------
# Single source-of-truth for explicit video intent detection.
# chat_service and card_service must import and call is_explicit_video_query()
# rather than maintaining their own keyword lists.
# ---------------------------------------------------------------------------
_EXPLICIT_VIDEO_CUES = (
    "video",
    "videos",
    "youtube",
    "yt",
    "shorts",
    "watch a video",
    "show me a video",
    "show a video",
    "video tour",
    "video walkthrough",
    "campus tour",
    "hostel tour",
    "campus walkthrough",
    "hostel walkthrough",
    "drone video",
    "see the campus",
    "see the hostel",
    "see the rooms",
    "see the lab",
    "what does the campus look like",
    "what does the hostel look like",
    "drone view",
    "visual",
    "clip",
    "shorts",
    "short",
    "show me",
    "can i see",
)

_VIDEO_TOPIC_CUES = (
    "university",
    "campus",
    "college",
    "sru",
    "hostel",
    "accommodation",
    "hostel life",
    "placement",
    "recruiter",
    "career",
    "job",
    "sports",
    "athletics",
    "club",
    "clubs",
    "startup",
    "startups",
    "srix",
    "incubator",
    "innovation",
    "cultural",
    "culture",
    "fest",
    "festival",
    "event",
    "events",
    "library",
)

_VIDEO_TOPIC_EXCLUSIONS = (
    "fee",
    "fees",
    "cost",
    "scholarship",
    "admission",
    "eligibility",
    "cutoff",
    "percentage",
    "marks",
    "attendance",
    "exam",
    "examination",
    "syllabus",
    "curriculum",
    "transport",
    "bus",
    "application",
)

_VIDEO_OFFER_REGEX = re.compile(
    r"(?:watch\s+(?:a\s+)?(?:short\s+)?video|video\s+tour|video\s+walkthrough|\(yes\s*/\s*no\))",
    re.I,
)

# Broader affirmative regex — covers natural language affirmatives
_AFFIRMATIVE_VIDEO_REGEX = re.compile(
    r"^\s*(?:"
    r"yes|yeah|yep|sure|definitely|absolutely|ok|okay|"
    r"show\s+me|yes[,\s]+please|please\s+show|why\s+not|"
    r"go\s+ahead|sounds\s+good|let'?s\s+(?:go|see|watch)|"
    r"yes\s+show|show\s+it|show\s+me\s+(?:the\s+)?video|"
    r"i\s+want\s+to\s+(?:see|watch)|"
    r"🎥\s*yes[,\s]+(?:watch|show)\s+video|watch\s+video|show\s+video"
    r")[.!?\s]*$",
    re.I,
)

# Broader negative regex — covers natural language declines
_NEGATIVE_VIDEO_REGEX = re.compile(
    r"^\s*(?:"
    r"no|nope|no[,\s]+thanks|nah|not\s+now|no\s+need|don'?t|"
    r"skip|not\s+interested|i'?m\s+(?:good|fine|ok|alright)|"
    r"pass|that'?s\s+(?:ok|okay|fine|alright)|"
    r"❌\s*no[,\s]+thanks"
    r")[.!?\s]*$",
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


def _compute_videos_hash(videos: list[dict]) -> str:
    """Compute a stable SHA-256 hash of the full video catalog for change detection."""
    canonical = json.dumps(videos, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


async def sync_video_vectors(embedding_provider=None) -> int:
    """Ensure all curated university videos are embedded and indexed in ChromaDB.

    Uses content-hash comparison instead of count-only check, so edits to
    video titles/keywords in the JSON file trigger a full re-sync automatically.
    """
    try:
        collection = _get_video_collection()
        if not collection:
            return 0
        videos = load_videos()
        if not videos:
            return 0

        new_hash = _compute_videos_hash(videos)
        stored_hash = (collection.metadata or {}).get("content_hash", "")
        if stored_hash == new_hash and collection.count() == len(videos):
            logger.info(
                "ChromaDB '%s' collection has %d video vectors. Up to date (hash match).",
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
        # Store the new hash in collection metadata so the next startup skips re-sync
        try:
            curr_meta = dict(collection.metadata or {})
            curr_meta["content_hash"] = new_hash
            curr_meta.pop("hnsw:space", None)
            collection.modify(metadata=curr_meta)
        except Exception as meta_err:
            logger.debug("Could not persist content_hash to ChromaDB metadata: %s", meta_err)
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


def is_video_topic_query(message: str) -> bool:
    """Return whether the question is within an approved university media topic."""
    msg_lower = message.lower().strip()
    if any(cue in msg_lower for cue in _VIDEO_TOPIC_EXCLUSIONS):
        return False
    return any(cue in msg_lower for cue in _VIDEO_TOPIC_CUES)


def has_recent_video_offer(
    recent_messages: list[dict],
    lookback: int = 20,
) -> bool:
    """Return whether the recent conversation already offered or showed a video."""
    for message in reversed(recent_messages[-lookback:]):
        if message.get("role") != "assistant":
            continue
        metadata = message.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        if metadata.get("video_offer") or any(
            isinstance(card, dict) and card.get("type") == "video_recommendations"
            for card in metadata.get("cards", [])
            if isinstance(metadata.get("cards"), list)
        ):
            return True
    return False


def should_retrieve_video_matches(
    user_message: str,
    intent: str,
    recent_messages: list[dict],
    contextual_offer_allowed: bool,
) -> bool:
    """Gate expensive video retrieval to explicit requests or one contextual offer."""
    if is_explicit_video_query(user_message) and is_video_topic_query(user_message):
        return True
    return (
        intent == "UNIVERSITY"
        and contextual_offer_allowed
        and not has_recent_video_offer(recent_messages)
    )


def should_display_videos(message: str) -> bool:
    """Return True if message naturally welcomes visual video recommendations (campus, hostel, fests, placements, facilities)."""
    if is_explicit_video_query(message):
        return True

    msg = message.lower()

    # Disallow video displays on purely transactional, numerical, or regulatory queries
    disallowed_keywords = (
        "fee", "fees", "cost", "scholarship", "cutoff", "percentage", "marks", "rank",
        "eligibility", "eligible", "syllabus", "curriculum", "transport", "bus", "route",
        "instagram", "attendance", "rules", "regulations", "mistake", "wrong",
    )
    if any(k in msg for k in disallowed_keywords):
        return False

    facility_keywords = (
        "campus", "campus life", "hostel", "hostels", "hostel rooms", "dining", "mess",
        "srix", "incubator", "sports", "grounds", "labs", "infrastructure", "infra",
        "facility", "facilities", "amenities", "tour", "walkthrough", "glimpse", "view",
        "life at sru", "fest", "events", "activities", "placement", "placements",
        "about sru", "tell me about sru", "about sr university", "why sru",
        "what is sru", "about sr", "know about sru", "what is sr university",
        "tell me about the university", "describe sru", "overview of sru",
    )
    return any(k in msg for k in facility_keywords)


_EVENT_FEST_KEYWORDS = (
    "fest", "fests", "bathukamma", "sparkill", "sparkrill", "ramp walk",
    "singer", "concert", "performance", "swagatam", "freshers", "celebration",
    "celebrations", "annual day", "sports day", "cultural", "navadhara",
)


def is_event_or_fest_video(video: dict) -> bool:
    """Return True if video is an event, fest, or festival celebration rather than campus tour/living."""
    title = (video.get("title") or "").lower()
    keywords = [str(k).lower() for k in video.get("keywords", [])]
    if any(k in title for k in _EVENT_FEST_KEYWORDS):
        return True
    if any(any(k in kw for k in _EVENT_FEST_KEYWORDS) for kw in keywords):
        return True
    return False


def is_about_sru_or_campus_query(message: str) -> bool:
    """Return True if message asks generally about SRU, university overview, or campus life without focusing on a specific sub-topic like hostels, fests, or placements."""
    msg = message.lower().strip()

    # If the user specifically asks for hostels, dining, mess, rooms -> NOT a generic about-sru query
    if any(k in msg for k in ("hostel", "hostels", "mess", "dining", "room", "rooms", "boarding", "stay", "accommodation", "food")):
        return False

    # If the user specifically asks for fests, events, celebrations, concerts -> NOT a generic about-sru query
    if any(k in msg for k in ("fest", "fests", "event", "events", "celebration", "celebrations", "sparkrill", "sparkill", "navadhara", "bathukamma", "cultural", "ramp walk", "concert", "performance", "swagatam", "freshers", "annual day")):
        return False

    # If the user specifically asks for placements -> NOT a generic about-sru query
    if any(k in msg for k in ("placement", "placements", "package", "packages", "salary", "job", "jobs", "career", "careers", "recruiter", "recruiters", "highest package", "average package", "placed")):
        return False

    # If the user specifically asks for sports -> NOT a generic about-sru query
    if any(k in msg for k in ("sport", "sports", "cricket", "basketball", "athletics", "gym", "football", "badminton", "ground", "grounds")):
        return False

    # If the user specifically asks for startups / incubation -> NOT a generic about-sru query
    if any(k in msg for k in ("startup", "startups", "srix", "incubator", "incubation", "entrepreneur", "entrepreneurship")):
        return False

    # Check for general SRU / campus / university inquiry cues
    about_cues = (
        "about sru", "tell me about sru", "about sr university", "about sr", "what is sru",
        "what is sr university", "know about sru", "tell me about the university",
        "describe sru", "overview of sru", "why sru", "why choose sru", "how is sru",
        "life at sru", "campus life", "campus", "how is the campus", "campus tour",
        "campus walkthrough", "see the campus", "campus facilities", "infrastructure",
        "infra", "sru overview", "about this college", "about this university",
        "about college", "sru details", "sru university", "join sru", "interested in sru",
        "campus environment", "how is the university", "campus glimpse", "campus view",
        "campus look like", "look of campus", "show campus", "walkthrough", "tour the campus",
        "tell me about sru buddy", "tell me about this university",
    )
    if any(cue in msg for cue in about_cues):
        return True
    if msg in ("sru", "campus", "infra", "about", "university", "college", "sr university", "sru buddy"):
        return True
    return False


def get_semantic_videos(
    query_embedding: list[float] | None,
    limit: int = 2,
    max_distance: float = DEFAULT_MAX_SEMANTIC_DISTANCE,
    exclude_categories: set[str] | list[str] | None = None,
    preferred_categories: set[str] | list[str] | None = None,
    exclude_events: bool = False,
    exclude_hostels: bool = False,
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

        n_query = min(max(limit * 8, 30), collection.count())
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_query,
            include=["metadatas", "distances"],
        )
        if not results["metadatas"] or not results["metadatas"][0]:
            return []

        candidates = []
        seen_ids: set[str] = set()
        for meta, dist in zip(results["metadatas"][0], results["distances"][0]):
            if not isinstance(meta, dict):
                continue
            if dist is not None and dist <= max_distance:
                cat = meta.get("category", "")
                if exclude_categories and cat in exclude_categories:
                    continue
                if exclude_hostels and (cat == "Hostels & Living" or "hostel" in meta.get("title", "").lower()):
                    continue
                if exclude_events and is_event_or_fest_video(meta):
                    continue
                vid_id = meta.get("id") or meta.get("url", "")
                if vid_id not in seen_ids:
                    seen_ids.add(vid_id)
                    candidates.append((dist, meta))

        if not candidates:
            return []

        # Sort strictly by cosine distance
        candidates.sort(key=lambda x: x[0])

        # Prioritize preferred categories if specified (e.g. campus tour for about sru)
        if preferred_categories:
            pref = [c for c in candidates if c[1].get("category") in preferred_categories]
            if len(pref) >= limit:
                candidates = pref
            else:
                other = [c for c in candidates if c[1].get("category") not in preferred_categories]
                candidates = pref + other

        # Enforce category diversity when selecting top results
        matched: list[dict] = []
        seen_categories: set[str] = set()

        # First pass: try selecting unique categories among top candidates
        for _, meta in candidates:
            cat = meta.get("category", "")
            if cat not in seen_categories:
                seen_categories.add(cat)
                matched.append(meta)
                if len(matched) == limit:
                    break

        # Second pass: fill remaining slots from candidates if not enough distinct categories
        if len(matched) < limit:
            for _, meta in candidates:
                if meta not in matched:
                    matched.append(meta)
                    if len(matched) == limit:
                        break

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

    is_visual_target = is_explicit or should_display_videos(user_message)
    max_dist = EXPLICIT_MAX_SEMANTIC_DISTANCE if is_visual_target else DEFAULT_MAX_SEMANTIC_DISTANCE

    # Check if this is an "about sru" / general campus query
    is_about_sru = is_about_sru_or_campus_query(user_message)
    is_generic_video = is_explicit and not any(
        k in msg_lower for k in (
            "hostel", "mess", "food", "dining", "room",
            "fest", "event", "celebration", "cultural",
            "placement", "package", "salary", "job",
            "sport", "startup", "srix"
        )
    )
    should_prefer_campus = is_about_sru or is_generic_video

    pref_cats = {"Campus Tour & Infrastructure"} if should_prefer_campus else None
    excl_hostels = should_prefer_campus
    excl_events = should_prefer_campus

    if query_embedding:
        vids = get_semantic_videos(
            query_embedding,
            limit=limit,
            max_distance=max_dist,
            preferred_categories=pref_cats,
            exclude_hostels=excl_hostels,
            exclude_events=excl_events,
        )
        if not vids and is_explicit:
            all_vids = load_videos()
            if should_prefer_campus:
                campus_vids = [v for v in all_vids if v.get("category") == "Campus Tour & Infrastructure"]
                return campus_vids[:limit] if campus_vids else all_vids[:limit]
            return all_vids[:limit] if all_vids else []
        return vids

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
                    return get_semantic_videos(
                        embs[0],
                        limit=limit,
                        max_distance=max_dist,
                        preferred_categories=pref_cats,
                        exclude_hostels=excl_hostels,
                        exclude_events=excl_events,
                    )
        except Exception:
            pass

    return []


_TRAILING_VIDEO_OFFER_PATTERN = re.compile(
    r"\n*(?:Would you like|Do you want|Should we|Feel free to|Let me know if you would like)[^\n?]*video[^\n?]*\??(?:\s*\([^\)]*\))?\s*$",
    re.I,
)


def strip_video_offer_prompt(answer: str) -> str:
    """Remove any trailing video offer question from answer string."""
    return _TRAILING_VIDEO_OFFER_PATTERN.sub("", answer).strip()


def sanitize_answer_video_prompts(answer: str) -> str:
    """Remove any hallucinated video tour prompts when no video is being offered."""
    disclaimer = ""
    cleaned = answer.strip()
    disclaimer_match = re.search(r"(\n*> ⚠️\s*\*May contain inaccuracies[^\n]*\*)\s*$", cleaned, re.I)
    if disclaimer_match:
        disclaimer = disclaimer_match.group(1)
        cleaned = cleaned[:disclaimer_match.start()].strip()

    cleaned = strip_video_offer_prompt(cleaned)
    if disclaimer:
        cleaned = f"{cleaned}\n{disclaimer}"
    return cleaned


def format_video_offer_prompt(answer: str, category_name: str = "this") -> str:
    """Ensure answer ends with a clean Yes/No video offer invitation using the semantically matched video category."""
    offer_question = f"Would you like to watch a short video tour of {category_name}? (Yes / No)"

    disclaimer = ""
    cleaned = answer.strip()

    # Extract trailing disclaimer if already present
    disclaimer_match = re.search(r"(\n*> ⚠️\s*\*May contain inaccuracies[^\n]*\*)\s*$", cleaned, re.I)
    if disclaimer_match:
        disclaimer = disclaimer_match.group(1)
        cleaned = cleaned[:disclaimer_match.start()].strip()

    # Strip any existing video offer so we never duplicate or retain a stale category
    cleaned = strip_video_offer_prompt(cleaned)

    # Also replace any trailing conversational follow-up question so there are never double questions
    trailing_pattern = re.compile(
        r"\n*(?:Would you like|Do you want|Should we|Feel free to|Let me know if you would like)[^\n?]+\?\s*$",
        re.I,
    )
    if trailing_pattern.search(cleaned):
        cleaned = trailing_pattern.sub("", cleaned).strip()

    result = f"{cleaned}\n\n{offer_question}"
    if disclaimer:
        result = f"{result}\n{disclaimer}"
    return result


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
