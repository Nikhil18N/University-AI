"""Video service — contrastive dense semantic vector recommendations for SR University YouTube media."""

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
VIDEO_NEGATIVE_COLLECTION = "university_videos_negative"

# Strict semantic distance thresholds for cosine distance (1 - cosine_similarity)
DEFAULT_MAX_SEMANTIC_DISTANCE = 0.24   # Passive offer threshold (high confidence)
EXPLICIT_MAX_SEMANTIC_DISTANCE = 0.31  # Explicit video request threshold
NEGATIVE_VETO_DISTANCE = 0.22          # Hard veto if query is closer than this to a negative policy intent
CONTRASTIVE_MARGIN = 0.03              # Required margin: d_pos <= d_neg - CONTRASTIVE_MARGIN

# Global negative policy/transactional intents indexed into ChromaDB for contrastive vetoing
GLOBAL_NEGATIVE_INTENTS: list[dict[str, str]] = [
    {
        "id": "neg_fees_tuition",
        "category": "ALL",
        "text": "What is the B.Tech CSE ECE hostel bus transport exam tuition fee structure per semester year refund late fine?",
    },
    {
        "id": "neg_attendance_rules",
        "category": "ALL",
        "text": "Minimum 75% attendance rule detention condonation fee medical certificate shortage backlog supplementary revaluation.",
    },
    {
        "id": "neg_hostel_policy",
        "category": "Hostels & Living",
        "text": "What is the hostel curfew in-time out-time outpass rule warden permission late entry fine and annual hostel fee?",
    },
    {
        "id": "neg_admission_cutoff",
        "category": "ALL",
        "text": "What is the EAMCET JEE Mains cutoff rank 12th percentage eligibility criteria scholarship slab tuition waiver?",
    },
    {
        "id": "neg_transport_routes",
        "category": "ALL",
        "text": "College bus route timings pickup stops Warangal Hanamkonda Kazipet transport fee incharge phone number.",
    },
    {
        "id": "neg_exam_grading",
        "category": "ALL",
        "text": "Exam timetable hall ticket release date CGPA SGPA grading system passing marks credit structure syllabus PDF.",
    },
]

# Word-boundary regex for explicit video/visual requests (fixes 'yt' in 'python' and 'short' in 'shortage')
_EXPLICIT_VIDEO_REGEX = re.compile(
    r"\b(?:"
    r"videos?|watch|youtube|yt|walkthroughs?|drone|clips?|shorts|vlogs?|reels?|"
    r"(?:campus|hostel|agri|agriculture|lab|library|srix|sports|virtual|full|night)\s+tours?|"
    r"tour\s+of\s+(?:the\s+)?(?:campus|hostels?|labs?|srix|university|college|block)|"
    r"how\s+does\s+(?:the\s+)?(?:campus|hostel|mess|food|room|lab|university|it)\s+look|"
    r"what\s+does\s+(?:the\s+)?(?:campus|hostel|mess|food|room|lab|university|it)\s+look\s+like|"
    r"see\s+the\s+(?:campus|hostels?|labs?|rooms?|infrastructure|mess|dining)"
    r")\b",
    re.IGNORECASE,
)

# Policy, fee, and regulatory queries that must NEVER trigger a passive video offer
_DISALLOWED_PASSIVE_VIDEO_REGEX = re.compile(
    r"\b(?:"
    r"fees?|tuition|cost|price|charges?|refunds?|scholarships?|waivers?|concessions?|deposit|"
    r"attendance|detained|detention|condonation|condone|backlogs?|revaluation|supplementary|supply|"
    r"cutoffs?|ranks?|eligibility|eligible|marks?|percentages?|cgpa|sgpa|gpa|scores?|"
    r"curfew|in-?time|out-?time|outpass|inpass|fines?|penalt(?:y|ies)|rules?|regulations?|policies|policy|"
    r"syllabus|curriculums?|credits?|timetables?|schedules?|deadlines?|dates?|hall\s*tickets?|"
    r"bus\s+routes?|transport|how\s+to\s+apply|application\s+process|documents?\s+required|"
    r"vs|compare|comparison|difference\s+between|mistake|wrong"
    r")\b",
    re.IGNORECASE,
)

# Topics that naturally welcome a passive "Would you like to watch a short video tour?" prompt
_VISUAL_TOPIC_WELCOME_REGEX = re.compile(
    r"\b(?:"
    r"campus\s+life|campus\s+tour|campus\s+facilities|infrastructure|green\s+campus|night\s+view|"
    r"hostel\s+life|hostel\s+rooms?|hostel\s+facilities|hostel\s+food|mess\s+food|dining|"
    r"srix|incubator|innovation\s+hub|startup|project\s+expo|pragathi|yantra|hackathon|"
    r"sparkrill|navadhara|bathukamma|swagatam|lumina|freshers|cultural\s+fest|sports\s+day|sports\s+facilities|"
    r"agriculture\s+block|agri\s+campus|astra\s+school|international\s+students?|iep|study\s+abroad|"
    r"placements?\s+success|highest\s+package|microsoft|paypal|jpmorgan|cisco|amazon\s+internship|"
    r"parent\s+testimonials?|student\s+reviews?|student\s+experience"
    r")\b",
    re.IGNORECASE,
)

_VIDEO_OFFER_REGEX = re.compile(
    r"(?:watch\s+(?:a\s+)?(?:short\s+)?video|video\s+tour|video\s+walkthrough|\(yes\s*/\s*no\))",
    re.I,
)

_AFFIRMATIVE_VIDEO_REGEX = re.compile(
    r"^\s*(?:yes|yeah|yep|yup|sure|show\s+me|yes[,\s]+please|please\s+show|definitely|ok|okay|why\s+not|🎥\s*yes[,\s]+(?:watch|show)\s+video|watch\s+video|show\s+video)[.!?\s]*$",
    re.I,
)

_NEGATIVE_VIDEO_REGEX = re.compile(
    r"^\s*(?:no|nope|no[,\s]+thanks|nah|not\s+now|no\s+need|don'?t|❌\s*no[,\s]+thanks)[.!?\s]*$",
    re.I,
)

_TRAILING_VIDEO_OFFER_PATTERN = re.compile(
    r"\n*(?:Would you like|Do you want|Should we|Feel free to|Let me know if you would like)[^\n?]*video[^\n?]*\??(?:\s*\([^\)]*\))?\s*$",
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
        logger.warning("University videos file not found: %s", _VIDEOS_FILE)
        return []
    except Exception as e:
        logger.error("Error loading university videos: %s", e)
        return []


def _get_video_collection(name: str = VIDEO_SEMANTIC_COLLECTION):
    """Retrieve ChromaDB collection for semantic video embeddings."""
    try:
        from app.db.chroma import get_chroma_client

        client = get_chroma_client()
        if hasattr(client, "get_or_create_collection"):
            return client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
        return None
    except Exception as e:
        logger.debug("Could not connect to ChromaDB collection '%s': %s", name, e)
        return None


def _build_positive_document(v: dict) -> str:
    """Build a clean, high-signal semantic document for embedding without repetitive boilerplate."""
    clean_title = re.sub(
        r"\s*\|\s*(?:No\.?\s*1|Best|Top)?\s*(?:Private\s+)?University.*$",
        "",
        v.get("title", ""),
        flags=re.IGNORECASE,
    ).strip()
    keywords = ", ".join(v.get("keywords", []))
    pos_intents = ". ".join(v.get("positive_intents", []))
    base = f"{clean_title}. Category: {v.get('category', '')}. Topics: {keywords}."
    return f"{base} {pos_intents}".strip() if pos_intents else base


async def sync_video_vectors(embedding_provider=None, force: bool = False) -> int:
    """Ensure all curated university videos and contrastive negative anchors are indexed in ChromaDB."""
    try:
        pos_collection = _get_video_collection(VIDEO_SEMANTIC_COLLECTION)
        neg_collection = _get_video_collection(VIDEO_NEGATIVE_COLLECTION)
        if not pos_collection:
            return 0

        videos = load_videos(force_reload=force)
        if not videos:
            return 0

        catalog_hash = hashlib.sha256(
            json.dumps(videos, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]

        existing = pos_collection.get(limit=1, include=["metadatas"])
        existing_hash = (
            existing["metadatas"][0].get("catalog_hash")
            if existing and existing.get("metadatas") and existing["metadatas"]
            else None
        )

        if not force and pos_collection.count() == len(videos) and existing_hash == catalog_hash:
            logger.info(
                "ChromaDB '%s' collection has %d up-to-date video vectors (hash=%s).",
                VIDEO_SEMANTIC_COLLECTION,
                pos_collection.count(),
                catalog_hash,
            )
            return pos_collection.count()

        if not embedding_provider:
            from app.providers.factory import create_embedding_provider

            embedding_provider = create_embedding_provider()

        # 1. Upsert positive video representations
        texts = [_build_positive_document(v) for v in videos]
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
                "catalog_hash": catalog_hash,
            }
            for v in videos
        ]
        pos_collection.upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)

        # 2. Build and upsert negative intent anchors (global + per-video negative_intents)
        if neg_collection:
            neg_entries: list[dict[str, str]] = list(GLOBAL_NEGATIVE_INTENTS)
            for v in videos:
                for idx, neg_text in enumerate(v.get("negative_intents", [])):
                    neg_entries.append(
                        {
                            "id": f"neg_{v['id']}_{idx}",
                            "category": v.get("category", "ALL"),
                            "video_id": v["id"],
                            "text": neg_text,
                        }
                    )
            neg_texts = [n["text"] for n in neg_entries]
            neg_embs = await embedding_provider.embed(neg_texts)
            neg_ids = [n["id"] for n in neg_entries]
            neg_metas = [
                {
                    "id": n["id"],
                    "category": n.get("category", "ALL"),
                    "video_id": n.get("video_id", ""),
                }
                for n in neg_entries
            ]
            neg_collection.upsert(ids=neg_ids, embeddings=neg_embs, documents=neg_texts, metadatas=neg_metas)

        logger.info(
            "Synced %d positive video vectors into '%s'.",
            len(ids),
            VIDEO_SEMANTIC_COLLECTION,
        )
        return pos_collection.count()
    except Exception as e:
        logger.warning("Failed to sync video vectors into ChromaDB: %s", e)
        return 0


def is_explicit_video_query(message: str) -> bool:
    """Return True if message explicitly asks to watch or see videos/tours."""
    return bool(_EXPLICIT_VIDEO_REGEX.search(message or ""))


def should_offer_video_tour(message: str) -> bool:
    """Return True only if the user query naturally welcomes a visual or campus tour offer."""
    if not message:
        return False
    if is_explicit_video_query(message):
        return True
    if _DISALLOWED_PASSIVE_VIDEO_REGEX.search(message):
        return False
    return bool(_VISUAL_TOPIC_WELCOME_REGEX.search(message))


def _compute_negative_distances(query_embedding: list[float]) -> tuple[float, dict[str, float], dict[str, float]]:
    """Return (min_global_neg_dist, per_category_neg_dist, per_video_neg_dist)."""
    neg_collection = _get_video_collection(VIDEO_NEGATIVE_COLLECTION)
    if not neg_collection or neg_collection.count() == 0:
        return 1.0, {}, {}

    try:
        res = neg_collection.query(
            query_embeddings=[query_embedding],
            n_results=min(6, neg_collection.count()),
            include=["metadatas", "distances"],
        )
        if not res["metadatas"] or not res["metadatas"][0]:
            return 1.0, {}, {}

        min_global = 1.0
        cat_neg: dict[str, float] = {}
        vid_neg: dict[str, float] = {}

        for meta, dist in zip(res["metadatas"][0], res["distances"][0]):
            if dist is None or not isinstance(meta, dict):
                continue
            cat = meta.get("category", "ALL")
            vid_id = meta.get("video_id", "")
            if vid_id:
                vid_neg[vid_id] = min(vid_neg.get(vid_id, 1.0), dist)
            elif cat == "ALL":
                min_global = min(min_global, dist)
            else:
                cat_neg[cat] = min(cat_neg.get(cat, 1.0), dist)

        return min_global, cat_neg, vid_neg
    except Exception:
        return 1.0, {}, {}


def get_semantic_videos(
    query_embedding: list[float] | None,
    limit: int = 2,
    max_distance: float = DEFAULT_MAX_SEMANTIC_DISTANCE,
    is_explicit: bool = False,
) -> list[dict]:
    """Retrieve video recommendations using contrastive dense vector search in ChromaDB."""
    if not query_embedding:
        return []

    try:
        collection = _get_video_collection(VIDEO_SEMANTIC_COLLECTION)
        if not collection or collection.count() == 0:
            return []

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(limit + 4, collection.count()),
            include=["metadatas", "distances"],
        )
        if not results["metadatas"] or not results["metadatas"][0]:
            return []

        min_global_neg, cat_neg_map, vid_neg_map = _compute_negative_distances(query_embedding)

        # Hard global negative veto for passive queries (e.g. fees, attendance, exam rules)
        if not is_explicit and min_global_neg <= NEGATIVE_VETO_DISTANCE:
            logger.debug("Contrastive veto triggered: min_global_neg=%.3f", min_global_neg)
            return []

        matched = []
        seen_ids: set[str] = set()
        for meta, d_pos in zip(results["metadatas"][0], results["distances"][0]):
            if not isinstance(meta, dict) or d_pos is None:
                continue
            if d_pos > max_distance:
                continue

            vid_id = meta.get("id") or meta.get("url", "")
            cat = meta.get("category", "")

            # Applicable negative distance for this specific video
            d_neg = min(
                min_global_neg,
                cat_neg_map.get(cat, 1.0),
                vid_neg_map.get(vid_id, 1.0),
            )

            # Contrastive margin check on passive queries: positive match must clearly beat negative boundary
            if not is_explicit and (d_neg <= NEGATIVE_VETO_DISTANCE or d_pos > (d_neg - CONTRASTIVE_MARGIN)):
                logger.debug(
                    "Contrastive filter rejected video '%s' (d_pos=%.3f, d_neg=%.3f)",
                    vid_id,
                    d_pos,
                    d_neg,
                )
                continue

            if vid_id not in seen_ids:
                seen_ids.add(vid_id)
                clean_meta = {k: v for k, v in meta.items() if k != "catalog_hash"}
                matched.append(clean_meta)

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
    """Contrastive semantic video retrieval with policy/transactional guardrails."""
    msg_lower = user_message.lower().strip()
    ans_lower = answer.lower()

    if msg_lower in ("hi", "hello", "hey", "hola", "good morning", "good evening", "thanks", "thank you", "bye"):
        return []

    if "could not be verified" in ans_lower or "insufficient evidence" in ans_lower:
        return []

    if not is_explicit:
        is_explicit = is_explicit_video_query(user_message)

    # Block passive video matches on fee/regulation/cutoff/attendance questions
    if not is_explicit and _DISALLOWED_PASSIVE_VIDEO_REGEX.search(user_message):
        return []

    max_dist = EXPLICIT_MAX_SEMANTIC_DISTANCE if is_explicit else DEFAULT_MAX_SEMANTIC_DISTANCE

    if query_embedding:
        return get_semantic_videos(
            query_embedding,
            limit=limit,
            max_distance=max_dist,
            is_explicit=is_explicit,
        )

    return []


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
    """Ensure answer ends with a clean Yes/No video offer invitation using the matched video category."""
    offer_question = f"Would you like to watch a short video tour of {category_name}? (Yes / No)"

    disclaimer = ""
    cleaned = answer.strip()

    disclaimer_match = re.search(r"(\n*> ⚠️\s*\*May contain inaccuracies[^\n]*\*)\s*$", cleaned, re.I)
    if disclaimer_match:
        disclaimer = disclaimer_match.group(1)
        cleaned = cleaned[:disclaimer_match.start()].strip()

    cleaned = strip_video_offer_prompt(cleaned)

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
        bool(metadata.get("video_offer"))
        or bool(_VIDEO_OFFER_REGEX.search(assistant_content))
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
    cat_lower = category_name.lower()
    if "hostel" in cat_lower:
        return [
            "🍽️ Mess & Food Quality",
            "🕒 Hostel Timings & Rules",
            "💰 Hostel Fee Structure",
            "📋 How to Apply",
        ]
    if "placement" in cat_lower or "career" in cat_lower:
        return [
            "📊 Placement Statistics",
            "🏢 Top Recruiters",
            "💼 Internship Opportunities",
            "📋 B.Tech Admissions",
        ]
    return [
        "🎯 B.Tech Admissions",
        "💰 Fee Structure & Scholarships",
        "🏠 Hostel & Mess Facilities",
        "📊 Placement Records",
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
