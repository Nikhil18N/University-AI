"""Pure-Python Okapi BM25 sparse keyword index and Reciprocal Rank Fusion (RRF) for hybrid retrieval (T9)."""

from collections import Counter
import logging
import math
import re
from typing import Any

logger = logging.getLogger(__name__)

# Tokenization helper
TOKEN_REGEX = re.compile(r"\b\w+\b", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Tokenize and lower-case text into words."""
    if not text:
        return []
    return [t.lower() for t in TOKEN_REGEX.findall(text)]


class BM25Index:
    """Okapi BM25 sparse search index designed for in-memory fast keyword retrieval."""

    def __init__(self, documents: list[dict], k1: float = 1.5, b: float = 0.75):
        self.documents = documents
        self.k1 = k1
        self.b = b
        self.corpus_size = len(documents)
        self.doc_lengths: list[int] = []
        self.doc_term_freqs: list[Counter] = []
        self.df: dict[str, int] = {}
        self.idf: dict[str, float] = {}

        total_length = 0
        for doc in documents:
            text = doc.get("content", "")
            title = doc.get("metadata", {}).get("title", "")
            # Combine content and title (with title weighted 2x)
            tokens = tokenize(f"{title} {title} {text}")
            length = len(tokens)
            self.doc_lengths.append(length)
            total_length += length

            tf = Counter(tokens)
            self.doc_term_freqs.append(tf)

            for term in tf.keys():
                self.df[term] = self.df.get(term, 0) + 1

        self.avgdl = (total_length / self.corpus_size) if self.corpus_size > 0 else 1.0

        # Calculate standard Okapi BM25 IDF
        for term, freq in self.df.items():
            self.idf[term] = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0)

    def search(self, query: str, top_k: int = 10) -> list[tuple[dict, float]]:
        """Score query against corpus and return top_k (doc, score) tuples."""
        if self.corpus_size == 0:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        scores: list[float] = [0.0] * self.corpus_size

        for term in query_tokens:
            if term not in self.idf:
                continue
            idf_val = self.idf[term]

            for idx in range(self.corpus_size):
                tf = self.doc_term_freqs[idx].get(term, 0)
                if tf == 0:
                    continue
                doc_len = self.doc_lengths[idx]
                numerator = tf * (self.k1 + 1.0)
                denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avgdl))
                scores[idx] += idf_val * (numerator / denominator)

        # Pair with documents and sort descending
        scored_pairs = [
            (self.documents[idx], scores[idx])
            for idx in range(self.corpus_size)
            if scores[idx] > 0.0
        ]
        scored_pairs.sort(key=lambda x: x[1], reverse=True)
        return scored_pairs[:top_k]


def reciprocal_rank_fusion(
    dense_results: list[dict],
    sparse_results: list[dict],
    k: int = 60,
    top_k: int = 8,
) -> list[dict]:
    """Combine dense and sparse rankings using Reciprocal Rank Fusion (RRF).

    Score = sum(1 / (k + rank_i)) for each ranker.
    """
    fused_scores: dict[str, float] = {}
    doc_map: dict[str, dict] = {}

    def _get_key(doc: dict) -> str:
        # Use content hash or snippet + title as unique chunk key
        meta = doc.get("metadata", {})
        title = meta.get("title", "")
        content = doc.get("content", "")
        return f"{title}::{content[:120]}"

    # Process dense ranks
    for rank, doc in enumerate(dense_results, start=1):
        key = _get_key(doc)
        fused_scores[key] = fused_scores.get(key, 0.0) + (1.0 / (k + rank))
        doc_map[key] = doc

    # Process sparse ranks
    for rank, doc in enumerate(sparse_results, start=1):
        key = _get_key(doc)
        fused_scores[key] = fused_scores.get(key, 0.0) + (1.0 / (k + rank))
        if key not in doc_map:
            doc_map[key] = doc

    # Sort keys by descending RRF score
    sorted_keys = sorted(fused_scores.keys(), key=lambda k: fused_scores[k], reverse=True)

    fused_docs = []
    for key in sorted_keys[:top_k]:
        chunk = doc_map[key].copy()
        chunk["rrf_score"] = fused_scores[key]
        fused_docs.append(chunk)

    return fused_docs


# Global cached BM25 instance and version tracker
_cached_bm25_index: BM25Index | None = None
_cached_index_version: int = -1


def invalidate_bm25_index() -> None:
    """Invalidate cached in-memory BM25 index on re-index or document change."""
    global _cached_bm25_index, _cached_index_version
    _cached_bm25_index = None
    _cached_index_version = -1
    logger.info("BM25 in-memory index invalidated.")


def get_or_build_bm25_index(collection: Any, current_index_version: int = 0) -> BM25Index:
    """Get or lazily construct the in-memory BM25 index from ChromaDB."""
    global _cached_bm25_index, _cached_index_version

    if _cached_bm25_index is not None and _cached_index_version == current_index_version:
        return _cached_bm25_index

    # Fetch all document chunks from ChromaDB
    try:
        all_docs = collection.get(include=["documents", "metadatas"])
        documents = []
        if all_docs and all_docs.get("documents"):
            raw_docs = all_docs["documents"]
            raw_metas = all_docs.get("metadatas", [])
            for i, content in enumerate(raw_docs):
                meta = raw_metas[i] if i < len(raw_metas) and isinstance(raw_metas[i], dict) else {}
                documents.append({"content": content, "metadata": meta, "distance": None})

        _cached_bm25_index = BM25Index(documents)
        _cached_index_version = current_index_version
        logger.info(
            "Built BM25 in-memory index over %d document chunks (version=%d)",
            len(documents),
            current_index_version,
        )
        return _cached_bm25_index
    except Exception as e:
        logger.warning("Could not build BM25 index from ChromaDB: %s", e)
        return BM25Index([])
