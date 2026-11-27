"""Hybrid knowledge retrieval service for the SRU agent (keyword + ChromaDB vector search)."""

import asyncio
import hashlib
import json as _json
import logging
import re as _re

logger = logging.getLogger(__name__)

_EMB_LOCAL_CACHE: dict[str, list[float]] = {}
_EMB_CACHE_TTL = 86400

_GENERIC_WORDS = set(
    "what which when where whom whose about does have there their with from that this then than "
    "into your mine sru university universities college please tell know give show more some "
    "much many like would could should will shall also only just very really".split()
)

# Cosine distance above which a vector match is not about the question (measured on the index: right answers
# 0.19-0.34, unrelated passages 0.45+).
_SEMANTIC_MAX_DISTANCE = 0.42


async def _cached_embed_query(query: str) -> list[float]:
    """Return query embedding from local/Redis cache when available, else compute and cache."""
    norm = _re.sub(r"\s+", " ", (query or "").strip().lower())
    key_hash = hashlib.sha256(norm.encode()).hexdigest()[:16]
    if norm in _EMB_LOCAL_CACHE:
        return _EMB_LOCAL_CACHE[norm]

    redis_key = f"sru:emb:{key_hash}"
    try:
        from app.sru_agent import memory as _agent_mem
        r = _agent_mem.get_redis()
        if r is not None:
            raw = await r.get(redis_key)
            if raw:
                vec = _json.loads(raw)
                if len(_EMB_LOCAL_CACHE) > 1000:
                    _EMB_LOCAL_CACHE.clear()
                _EMB_LOCAL_CACHE[norm] = vec
                return vec
    except Exception:
        pass

    from app.api.v1.deps import get_embedding_provider
    vec = await get_embedding_provider().embed_single(query)
    if len(_EMB_LOCAL_CACHE) > 1000:
        _EMB_LOCAL_CACHE.clear()
    _EMB_LOCAL_CACHE[norm] = vec
    try:
        from app.sru_agent import memory as _agent_mem
        r = _agent_mem.get_redis()
        if r is not None:
            await r.set(redis_key, _json.dumps(vec), ex=_EMB_CACHE_TTL)
    except Exception:
        pass
    return vec


def _rerank_by_question_words(query: str, hits: list) -> list:
    """Re-rank semantic hits using 4-letter stems from distinctive question words."""
    words = {w[:4] for w in _re.findall(r"[a-z]+", (query or "").lower()) if len(w) > 3 and w not in _GENERIC_WORDS}
    if not words:
        return hits

    def adjusted(h: dict) -> float:
        text = f"{h.get('title', '')} {h.get('question', '')} {h.get('text', '')}".lower()
        found = {t[:4] for t in _re.findall(r"[a-z]+", text) if len(t) > 3}
        return (h.get("distance") or 0.5) - 0.03 * len(words & found)

    for h in hits:
        h["rank"] = round(adjusted(h), 3)
    return sorted(hits, key=lambda h: h["rank"])


from app.utils.rrf import rrf_merge


def _merge_evidence(semantic: list, lexical: list, limit: int = 6, k: int = 60) -> list:
    """Merge semantic (ChromaDB) and lexical (BM25) results using Reciprocal Rank Fusion (RRF).

    Ensures admin-uploaded PDFs/DOCXs in ChromaDB are never shadowed by BM25 short-circuiting.
    """
    return rrf_merge(semantic, lexical, limit=limit, k=k)


def zip_longest_lists(a: list, b: list):
    """Yield paired non-None elements from two lists up to the longer list's length."""
    for i in range(max(len(a), len(b))):
        yield [x for x in ((a[i] if i < len(a) else None), (b[i] if i < len(b) else None)) if x is not None]


async def agent_knowledge_search(query: str) -> list:
    """Approved-knowledge search for the agent: handbook keyword search AND vector index, merged."""
    lexical, semantic = [], []
    try:
        from app.sru_agent import knowledge
        lexical = [
            {"title": f["title"], "text": f["text"][:1800], "source": f["source"], "retrieval": "keyword"}
            for f in knowledge.search(query, k=6, min_score=1.0)
        ]
    except Exception as err:
        logger.warning("keyword handbook search failed: %s", err)
    try:
        from app.db.chroma import get_chroma_client
        from app.services.rag_service import COLLECTION_NAME
        collection = get_chroma_client().get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        emb = await _cached_embed_query(query)
        results = await asyncio.to_thread(collection.query, query_embeddings=[emb], n_results=8)
        docs = (results.get("documents") or [[]])[0]
        metas = (results.get("metadatas") or [[]])[0]
        dists = (results.get("distances") or [[]])[0] or [None] * len(docs)
        keep = (
            "document_type", "page", "effective_date", "publication_date",
            "document_id", "section", "question", "page_url",
        )
        for d, m, dist in zip(docs, metas, dists):
            if dist is not None and dist > _SEMANTIC_MAX_DISTANCE:
                continue  # not about this question
            m = m or {}
            semantic.append({
                "title": m.get("title", ""),
                "text": d,
                "retrieval": "semantic",
                "distance": round(dist, 3) if dist is not None else None,
                **{k: m.get(k) for k in keep if m.get(k)},
            })
        semantic = _rerank_by_question_words(query, semantic)
    except Exception as err:
        logger.warning("vector knowledge search unavailable, keyword results only: %s", err)
    return _merge_evidence(semantic, lexical)
