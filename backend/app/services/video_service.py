"""Video service — Contrastive Bi-Encoder intent-based video recommendation via Ollama embeddings.

Uses Ollama's nomic-embed-text model (already running at localhost:11434) to embed user queries
against per-video positive and negative intent descriptions. A video is recommended only if:
  - S_pos  >= MIN_POS_SCORE   (strong positive alignment)
  - S_neg  <  MAX_NEG_SCORE   (negative intent veto ceiling)
  - S_pos - S_neg >= MIN_MARGIN (contrastive margin gate)

This eliminates false positives (e.g. "ragging on campus" → no video) while
correctly routing visual/exploratory queries (e.g. "tell me how campus looks" → tour video).
No sklearn, no sentence-transformers — only httpx + numpy which are already in the venv.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

import httpx
import numpy as np

logger = logging.getLogger(__name__)

_VIDEOS_FILE = Path(__file__).resolve().parent.parent / "data" / "university_videos.json"
_CACHED_VIDEOS: list[dict] | None = None

_MEDIA_TAG_PATTERN = re.compile(
    r"\[(?:MEDIA|RESOURCE|VIDEO):\s*([a-zA-Z0-9_\-]+(?:\s*,\s*[a-zA-Z0-9_\-]+)*)\]",
    re.IGNORECASE,
)

# Ollama embedding endpoint (same instance used by ChromaDB/RAG pipeline)
_OLLAMA_BASE_URL = "http://localhost:11434"
_EMBED_MODEL = "nomic-embed-text"


# ---------------------------------------------------------------------------
# JSON loader
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Helper utilities (used by rag_service and chat_service)
# ---------------------------------------------------------------------------

def get_media_catalog_for_prompt() -> str:
    """Generate a clean bulleted catalog of available university media for LLM system prompt."""
    videos = load_videos()
    lines = []
    for v in videos:
        media_id = v.get("id", "")
        title = v.get("title", "")
        cat = v.get("category", "")
        desc = v.get("description", "")
        platform = v.get("platform", "youtube")
        lines.append(f"- [MEDIA:{media_id}] \"{title}\" (Category: {cat} | Platform: {platform}) — {desc}")
    return "\n".join(lines)


def get_video_by_id(media_id: str) -> dict | None:
    """Retrieve video metadata by its unique ID."""
    videos = load_videos()
    norm_id = media_id.strip().lower()
    for v in videos:
        if v.get("id", "").strip().lower() == norm_id:
            return v
    return None


def get_media_by_ids(media_ids: list[str]) -> list[dict]:
    """Retrieve full video/media objects for a list of media IDs in order, deduplicated."""
    videos = load_videos()
    lookup = {v.get("id", "").strip().lower(): v for v in videos}
    result = []
    seen = set()
    for mid in media_ids:
        mid_norm = mid.strip().lower()
        if mid_norm in lookup and mid_norm not in seen:
            seen.add(mid_norm)
            result.append(lookup[mid_norm])
    return result


def extract_media_tags(text: str) -> tuple[str, list[str]]:
    """Parse and strip [MEDIA: <id>] tags from model response text.

    Returns:
        (cleaned_text, list_of_media_ids)
    """
    if not text:
        return text, []

    media_ids: list[str] = []
    matches = _MEDIA_TAG_PATTERN.findall(text)
    for match in matches:
        parts = [p.strip() for p in match.split(",") if p.strip()]
        media_ids.extend(parts)

    cleaned = _MEDIA_TAG_PATTERN.sub("", text).rstrip()
    return cleaned, media_ids


# ---------------------------------------------------------------------------
# Ollama embedding helper
# ---------------------------------------------------------------------------

def _embed_texts(texts: list[str]) -> np.ndarray:
    """Embed a list of texts using Ollama nomic-embed-text. Returns (N, dim) float32 array."""
    if not texts:
        return np.empty((0, 768), dtype=np.float32)

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{_OLLAMA_BASE_URL}/api/embed",
                json={"model": _EMBED_MODEL, "input": texts},
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings = data.get("embeddings") or data.get("embedding")
            arr = np.array(embeddings, dtype=np.float32)
            # L2-normalise each row for cosine similarity via dot product
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1.0, norms)
            return arr / norms
    except Exception as exc:
        logger.error("Ollama embed error: %s", exc)
        return np.empty((0, 768), dtype=np.float32)


def _embed_single(text: str) -> np.ndarray:
    """Embed a single text. Returns (dim,) float32 array."""
    arr = _embed_texts([text])
    if arr.shape[0] == 0:
        return np.zeros(768, dtype=np.float32)
    return arr[0]


# ---------------------------------------------------------------------------
# Contrastive Bi-Encoder recommender (Ollama-backed)
# ---------------------------------------------------------------------------

class IntentVideoRecommender:
    """Semantic video recommender using contrastive embedding scores via Ollama.

    Each video has positive_intents (what the user wants to SEE) and
    negative_intents (topics sharing keywords but wrong intent). A video
    passes recommendation only if it clears all three gates simultaneously:
      1. S_pos >= min_pos_score
      2. S_neg <  max_neg_score  (hard veto ceiling)
      3. S_pos - S_neg >= min_margin
    """

    def __init__(
        self,
        min_pos_score: float = 0.60,
        max_neg_score: float = 0.70,
        min_margin: float = 0.05,
    ):
        self.min_pos_score = min_pos_score
        self.max_neg_score = max_neg_score
        self.min_margin = min_margin
        self._indexed: list[dict] = []
        self._ready = False

    # ------------------------------------------------------------------
    # Lazy initialisation — catalog embeddings computed once on first use
    # ------------------------------------------------------------------

    def _ensure_ready(self) -> bool:
        """Pre-embed all video intent texts (idempotent)."""
        if self._ready:
            return True
        try:
            self._index_catalog()
            self._ready = True
            logger.info(
                "IntentVideoRecommender ready — %d videos indexed via Ollama",
                len(self._indexed),
            )
            return True
        except Exception as exc:
            logger.error("IntentVideoRecommender init failed: %s", exc)
            return False

    def _index_catalog(self) -> None:
        """Pre-compute Ollama embeddings for every video's positive and negative intents."""
        videos = load_videos()
        self._indexed = []
        for v in videos:
            pos_texts = v.get("positive_intents") or []
            neg_texts = v.get("negative_intents") or []
            if not pos_texts:
                # Skip videos without intent metadata
                logger.warning("Video %s has no positive_intents — skipped", v.get("id"))
                continue
            entry = dict(v)
            entry["pos_emb"] = _embed_texts(pos_texts)   # (N_pos, dim)
            entry["neg_emb"] = _embed_texts(neg_texts) if neg_texts else None
            self._indexed.append(entry)
            logger.debug("Indexed video %s (%d pos, %d neg)", v.get("id"), len(pos_texts), len(neg_texts))

    def _reset(self) -> None:
        """Force re-indexing on next recommend() call (e.g. after catalog update)."""
        self._ready = False
        self._indexed = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def recommend(self, user_query: str, limit: int = 2) -> list[dict]:
        """Return up to *limit* videos that semantically match the user's visual intent.

        Returns [] when no video passes the dual-threshold gates — including
        queries about ragging, policy, fees, timings, etc. that share campus
        keywords but have wrong intent.
        """
        if not user_query or not user_query.strip():
            return []

        if not self._ensure_ready():
            logger.warning("Recommender not ready — returning no videos")
            return []

        query_emb = _embed_single(user_query.strip())  # (dim,)

        if query_emb.sum() == 0:
            # Ollama unreachable
            logger.warning("Embed returned zero vector — Ollama may be down")
            return []

        scored: list[tuple[float, float, dict]] = []

        for entry in self._indexed:
            pos_emb = entry["pos_emb"]   # (N_pos, dim)
            neg_emb = entry.get("neg_emb")  # (N_neg, dim) or None

            if pos_emb.shape[0] == 0:
                continue

            # Cosine similarity = dot product (both L2-normalised)
            s_pos = float(np.max(pos_emb @ query_emb))

            if neg_emb is not None and neg_emb.shape[0] > 0:
                s_neg = float(np.max(neg_emb @ query_emb))
            else:
                s_neg = 0.0

            # Gate 1: veto if negative intent score is too high
            if s_neg >= self.max_neg_score:
                logger.debug(
                    "VETO  video=%-25s s_pos=%.3f s_neg=%.3f (neg threshold %.3f)",
                    entry.get("id"),
                    s_pos,
                    s_neg,
                    self.max_neg_score,
                )
                continue

            # Gate 2: positive confidence
            if s_pos < self.min_pos_score:
                logger.debug(
                    "SKIP  video=%-25s s_pos=%.3f < %.3f",
                    entry.get("id"),
                    s_pos,
                    self.min_pos_score,
                )
                continue

            # Gate 3: contrastive margin
            margin = s_pos - s_neg
            if margin < self.min_margin:
                logger.debug(
                    "MARGIN video=%-25s s_pos=%.3f s_neg=%.3f margin=%.3f < %.3f",
                    entry.get("id"),
                    s_pos,
                    s_neg,
                    margin,
                    self.min_margin,
                )
                continue

            scored.append((margin, s_pos, entry))
            logger.info(
                "PASS  video=%-25s s_pos=%.3f s_neg=%.3f margin=%.3f",
                entry.get("id"),
                s_pos,
                s_neg,
                margin,
            )

        # Sort by margin descending (most confident recommendations first)
        scored.sort(key=lambda x: x[0], reverse=True)

        # Return clean video dicts (strip embedding tensors)
        results = []
        for _, _, entry in scored[:limit]:
            clean = {k: v for k, v in entry.items() if k not in ("pos_emb", "neg_emb")}
            results.append(clean)
        return results


# ---------------------------------------------------------------------------
# Module-level singleton (lazy-initialised on first recommend() call)
# ---------------------------------------------------------------------------

_recommender: Optional[IntentVideoRecommender] = None


def get_recommender() -> IntentVideoRecommender:
    """Return the shared IntentVideoRecommender singleton."""
    global _recommender
    if _recommender is None:
        _recommender = IntentVideoRecommender()
    return _recommender


def get_relevant_videos(
    user_message: str,
    answer: str = "",
    sources: list[dict] | None = None,
    limit: int = 2,
) -> list[dict]:
    """Public API: return semantically relevant videos using the Bi-Encoder recommender.

    Signature kept compatible with the old keyword-based version so card_service
    and tests can call it without changes.
    """
    return get_recommender().recommend(user_message, limit=limit)


# ---------------------------------------------------------------------------
# Card builder
# ---------------------------------------------------------------------------

def create_video_card(
    videos: list[dict],
    is_explicit: bool = False,
    title: str | None = None,
) -> dict:
    """Format structured video/media recommendation card."""
    if not videos:
        return {}

    has_ig = any(v.get("platform") == "instagram" for v in videos)
    has_yt = any(v.get("platform", "youtube") == "youtube" for v in videos)

    default_title = "Official SR University Video Tours" if is_explicit else "Related Campus Videos"
    if has_ig and not has_yt:
        default_title = "Official SR University Instagram Reels"
        default_channel_name = "@sruniversity_official"
        default_channel_url = "https://www.instagram.com/sruniversity_official/"
    elif has_ig and has_yt:
        default_title = "Featured Campus Media (YouTube & Instagram)"
        default_channel_name = "SR University Official"
        default_channel_url = "https://www.youtube.com/@SRUniversity/videos"
    else:
        default_channel_name = "SR University Official"
        default_channel_url = "https://www.youtube.com/@SRUniversity/videos"

    channel_name = videos[0].get("channel_name") or default_channel_name
    channel_url = videos[0].get("channel_url") or default_channel_url

    return {
        "type": "video_recommendations",
        "title": title or default_title,
        "channel_name": channel_name,
        "channel_url": channel_url,
        "videos": videos,
    }
