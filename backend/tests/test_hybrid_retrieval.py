"""Tests for BM25 + Reciprocal Rank Fusion (RRF) Hybrid Retrieval (Task T9)."""

import pytest
from unittest.mock import MagicMock

from app.config import settings
from app.services.bm25_service import (
    BM25Index,
    get_or_build_bm25_index,
    invalidate_bm25_index,
    reciprocal_rank_fusion,
    tokenize,
)


def test_tokenize():
    tokens = tokenize("SR University CSE-AIML 2026! Dr. Sumanth's lab?")
    assert "sr" in tokens
    assert "university" in tokens
    assert "cse" in tokens
    assert "aiml" in tokens
    assert "dr" in tokens
    assert "sumanth" in tokens


def test_bm25_exact_keyword_matching():
    """Exact keywords like proper names or course codes must rank highest in BM25."""
    docs = [
        {"content": "General overview of the university campus and student clubs.", "metadata": {"title": "Campus Life"}},
        {"content": "Admissions eligibility and fee payment dates for 2026.", "metadata": {"title": "Admissions"}},
        {"content": "CSE-AIML-401 Machine Learning curriculum authored by Dr. Sumanth.", "metadata": {"title": "CSE Syllabus"}},
        {"content": "Hostel room sharing options, mess food, and night curfew.", "metadata": {"title": "Hostel Rules"}},
    ]

    index = BM25Index(docs)

    # 1. Search for specific faculty / term
    results = index.search("Dr. Sumanth", top_k=3)
    assert len(results) > 0
    top_doc, top_score = results[0]
    assert "Dr. Sumanth" in top_doc["content"]
    assert top_score > 0.0

    # 2. Search for exact course code
    results_code = index.search("CSE-AIML-401", top_k=1)
    assert len(results_code) == 1
    assert "CSE-AIML-401" in results_code[0][0]["content"]


def test_reciprocal_rank_fusion_boosts_exact_matches():
    """RRF must boost documents that appear in sparse keyword ranking even if lower in dense vector search."""
    doc_a = {"content": "Vague overview of computing", "metadata": {"title": "Doc A"}}
    doc_b = {"content": "General faculty directory", "metadata": {"title": "Doc B"}}
    doc_exact = {"content": "Dr. Sumanth research papers in AI", "metadata": {"title": "Doc Exact"}}

    # Dense retrieval ranked doc_a #1, doc_b #2, doc_exact #3
    dense_results = [doc_a, doc_b, doc_exact]

    # Sparse BM25 retrieval ranked doc_exact #1 due to exact name match
    sparse_results = [doc_exact]

    fused = reciprocal_rank_fusion(dense_results, sparse_results, k=60, top_k=3)

    # doc_exact gets 1/(60+3) + 1/(60+1) = 0.0158 + 0.0163 = 0.0322
    # doc_a gets 1/(60+1) = 0.0163
    # doc_b gets 1/(60+2) = 0.0161
    assert fused[0]["metadata"]["title"] == "Doc Exact"
    assert "rrf_score" in fused[0]
    assert fused[0]["rrf_score"] > fused[1]["rrf_score"]


def test_bm25_index_invalidation():
    """Invalidating BM25 index must clear cached index so next retrieval rebuilds with updated chunks."""
    mock_collection = MagicMock()
    mock_collection.get.return_value = {
        "documents": ["Chunk 1 content", "Chunk 2 content"],
        "metadatas": [{"title": "Doc 1"}, {"title": "Doc 2"}],
    }

    # Initial build
    index1 = get_or_build_bm25_index(mock_collection, current_index_version=1)
    assert index1.corpus_size == 2

    # Second call returns cached instance
    index2 = get_or_build_bm25_index(mock_collection, current_index_version=1)
    assert index1 is index2

    # Invalidate cache
    invalidate_bm25_index()

    # Next call rebuilds
    mock_collection.get.return_value = {
        "documents": ["Chunk 1", "Chunk 2", "Chunk 3 updated"],
        "metadatas": [{"title": "Doc 1"}, {"title": "Doc 2"}, {"title": "Doc 3"}],
    }
    index3 = get_or_build_bm25_index(mock_collection, current_index_version=2)
    assert index3.corpus_size == 3
    assert index3 is not index1
