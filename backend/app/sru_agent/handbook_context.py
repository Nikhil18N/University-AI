"""Contextual query enrichment and hybrid handbook/vector retrieval for the SRU agent."""

import asyncio
import re

from . import ai_guard, knowledge, semantic_router, tools


def _has_word(text: str, *words: str) -> bool:
    for w in words:
        if re.search(r"\b" + re.escape(w) + r"\b", text):
            return True
    return False


def _contextual_query(
    message: str,
    history: list | None = None,
    active_topic: str | None = None,
    active_program: str | None = None,
) -> str:
    """Build a search query enriched with conversational context for follow-up questions."""
    low = (message or "").lower().strip()
    words = low.split()

    if len(words) > 7 and not re.search(r"\b(?:it|this|that|these|those)\b", low):
        return message

    additions = []
    topic = active_topic

    is_other_fee_inquiry = bool(
        re.search(
            r"\b(?:other\s+fees?|other\s+academic(?:\s*/\s*university|\s+university)?\s+charges?|other\s+charges?|annual\s+charges?|"
            r"university\s+charges?|additional\s+fees?|additional\s+charges?|enrolment\s+fee|enrollment\s+fee|application\s+form\s+fee|"
            r"specialisation\s+fee|specialization\s+fee|phd\s+fee|"
            r"fees?\s+(?:other\s+than|apart\s+from|besides|excluding|except)\s+(?:sem(?:ester)?\s+fee|tuition(?:\s+fee)?|course\s+fee)|"
            r"(?:other\s+than|apart\s+from|besides|excluding|except)\s+(?:sem(?:ester)?\s+fee|tuition(?:\s+fee)?|course\s+fee))\b",
            low,
        )
    )

    if is_other_fee_inquiry:
        additions.append(
            "Other fees and charges enrolment fee application fee other academic university charges examination fee specialisation fee phd fee"
        )
    elif topic == "hostel" or _has_word(low, "hostel", "mess", "curfew", "warden", "ac", "non-ac", "sharing", "double", "table", "bed", "in-time"):
        if not _has_word(low, "hostel", "hostels"):
            additions.append("hostel accommodation")
        if _has_word(low, "double", "table"):
            additions.append("rooms sharing 3-sharing 4-sharing categories")
        if _has_word(low, "mess", "food", "dining", "meal", "included"):
            additions.append("mess dining Mega Dining Hall food included fee")
        if _has_word(low, "ac", "non-ac", "air"):
            additions.append("AC Non-AC room amenities power backup")
        if _has_word(low, "fee", "cost", "annual", "charge", "rent"):
            additions.append("hostel fees per year electricity deposit")
    elif topic == "placements" or _has_word(low, "placement", "package", "guarantee", "guaranteed", "lpa", "jobs"):
        if not _has_word(low, "placement", "placements"):
            additions.append("placements assistance career")
        if _has_word(low, "guarantee", "guaranteed", "98%", "100%"):
            additions.append("100% placement assistance policy readiness CSSP")
    elif topic in ("btech", "programs") or _has_word(low, "btech", "b.tech", "branch", "branches", "stream", "engineering", "ai"):
        if not _has_word(low, "b.tech", "btech", "engineering"):
            additions.append("B.Tech engineering programs branches")
        if _has_word(low, "ai"):
            additions.append("Artificial Intelligence AI CSE AI Robotics")
    elif topic in ("fee", "scholarship") or _has_word(low, "fee", "fees", "scholarship", "scholarships", "waiver", "concession", "eligible", "eligibility", "60%", "85%", "90%"):
        if _has_word(low, "scholarship", "scholarships", "concession", "waiver", "discount"):
            additions.append("merit scholarships fee concessions slabs intermediate cbse jee eapcet")
        if active_program:
            additions.append(str(active_program))
        if _has_word(low, "eligible", "eligibility", "cutoff", "minimum"):
            additions.append("eligibility criteria minimum marks")

    if additions:
        return message + " " + " ".join(additions)
    return message


def _handbook_context(query: str) -> str:
    """Handbook passages for this query (and decomposed sub-questions), found by keyword search."""
    sub_questions = semantic_router.decompose_multi_questions(query)
    search_queries = [query]
    if len(sub_questions) > 1:
        search_queries.extend(sub_questions)

    found_by_id = {}
    per_sub_top: list[dict] = []
    for idx, q in enumerate(search_queries):
        try:
            results = knowledge.search(q, k=4, min_score=1.0)
            if idx > 0 and results:
                per_sub_top.extend(results[:2])
            for r in results:
                doc_key = r.get("title", "") + r.get("text", "")[:60]
                if doc_key not in found_by_id or r.get("score", 0) > found_by_id[doc_key].get("score", 0):
                    found_by_id[doc_key] = r
        except Exception:
            continue

    if not found_by_id:
        return ""

    max_passages = min(6, max(3, 2 * len(sub_questions))) if len(sub_questions) > 1 else 3
    picked: list[dict] = []
    seen_keys: set[str] = set()
    for item in per_sub_top + sorted(found_by_id.values(), key=lambda x: x.get("score", 0), reverse=True):
        doc_key = item.get("title", "") + item.get("text", "")[:60]
        if doc_key not in seen_keys:
            seen_keys.add(doc_key)
            picked.append(item)
            if len(picked) >= max_passages:
                break

    sorted_found = ai_guard.screen_passages(picked, "handbook")
    if not sorted_found:
        return ""
    top = max(f.get("score", 0) for f in sorted_found) or 1.0
    parts = [
        f"[{f['title'].split(' > ')[-1]} | source: {f.get('source') or 'SR University handbook'}]\n"
        f"{f['text'][:550]}"
        for f in sorted_found
        if f.get("score", 0) >= 0.40 * top or len(sub_questions) > 1
    ]
    return "\n\n".join(parts)


async def _hybrid_handbook_context(query: str) -> str:
    """Hybrid RRF retrieval combining BM25 handbook search and ChromaDB vector search."""
    if tools._knowledge_search is None:
        return _handbook_context(query)

    sub_questions = semantic_router.decompose_multi_questions(query)
    search_queries = [query] + (sub_questions if len(sub_questions) > 1 else [])

    bm25_per_q: list[list[dict]] = []
    for q in search_queries:
        try:
            bm25_per_q.append(knowledge.search(q, k=4, min_score=1.0))
        except Exception:
            bm25_per_q.append([])
    sem_batches = await asyncio.gather(
        *(tools._knowledge_search(q) for q in search_queries),
        return_exceptions=True,
    )

    bm25_hits = [item for batch in bm25_per_q for item in batch]
    sem_hits = [item for batch in sem_batches if isinstance(batch, list) for item in batch]

    if not sem_hits and not bm25_hits:
        return ""

    from app.utils.rrf import rrf_fuse, rrf_key

    fused, scores = rrf_fuse(sem_hits, bm25_hits, k=60)

    max_passages = min(6, max(3, 2 * len(sub_questions))) if len(sub_questions) > 1 else 3
    ranked: list[dict] = []
    seen_keys: set[str] = set()

    if len(sub_questions) > 1:
        for idx in range(1, len(search_queries)):
            sem_b = sem_batches[idx] if idx < len(sem_batches) and isinstance(sem_batches[idx], list) else []
            bm_b = bm25_per_q[idx] if idx < len(bm25_per_q) else []
            for item in (sem_b[:1] + bm_b[:1]):
                key = rrf_key(item)
                if key and key not in seen_keys:
                    seen_keys.add(key)
                    ranked.append(fused.get(key, dict(item)))

    for k in sorted(scores.keys(), key=lambda x: scores[x], reverse=True):
        if len(ranked) >= max_passages:
            break
        if k not in seen_keys:
            seen_keys.add(k)
            ranked.append(fused[k])

    ranked = ranked[:max_passages]
    ranked = ai_guard.screen_passages(ranked, "handbook")
    if not ranked:
        return ""
    return "\n\n".join(
        f"[{(f.get('title') or 'SRU Document').split(' > ')[-1]} | source: {f.get('source') or 'SR University knowledge base'}]\n"
        f"{(f.get('text') or '')[:550]}"
        for f in ranked
    )
