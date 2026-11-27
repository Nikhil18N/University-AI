"""Shared Reciprocal Rank Fusion (RRF) helpers for hybrid semantic + lexical retrieval."""

import re


def rrf_key(item: dict) -> str:
    """Return a normalized 160-char deduplication key for a retrieved passage."""
    return re.sub(r"\W+", " ", (item.get("text") or "").lower()).strip()[:160]


def rrf_fuse(
    *ranked_lists: list[dict],
    k: int = 60,
) -> tuple[dict[str, dict], dict[str, float]]:
    """Fuse multiple ranked hit lists into `(fused_by_key, scores_by_key)` using RRF."""
    fused: dict[str, dict] = {}
    scores: dict[str, float] = {}
    for hits in ranked_lists:
        for rank, item in enumerate(hits, start=1):
            key = rrf_key(item)
            if not key:
                continue
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            if key not in fused:
                fused[key] = dict(item)
    return fused, scores


def rrf_merge(
    primary: list[dict],
    secondary: list[dict],
    *,
    limit: int = 6,
    k: int = 60,
) -> list[dict]:
    """Merge two ranked hit lists using RRF and return top `limit` entries with `rrf_score`."""
    fused, scores = rrf_fuse(primary, secondary, k=k)
    ranked_keys = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    out: list[dict] = []
    for key in ranked_keys[:limit]:
        entry = fused[key]
        entry["rrf_score"] = round(scores[key], 6)
        out.append(entry)
    return out
