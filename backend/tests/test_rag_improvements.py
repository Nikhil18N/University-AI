"""Tests for Stage 5 RAG improvements, reranking, and mandatory disclaimers."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.rag_service import RAGService
from app.services.suggestion_service import (
    generate_suggestions,
    ACADEMIC_SUGGESTIONS,
    FEE_SUGGESTIONS,
    HOSTEL_SUGGESTIONS,
    PLACEMENT_SUGGESTIONS,
)


@pytest.mark.asyncio
async def test_rag_generates_clean_answer_without_disclaimer():
    """Verify that generate_answer returns a clean answer without appending disclaimer."""
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value="Tuition fee for B.Tech CSE is Rs. 1,47,500 per semester.")
    mock_embed = MagicMock()

    with patch("app.services.rag_service.chromadb.PersistentClient"):
        rag = RAGService(llm_provider=mock_llm, embedding_provider=mock_embed)
        # Mock prepare_rag_request
        rag.prepare_rag_request = AsyncMock(return_value=([], [], "Tuition fee is Rs. 1,47,500."))
        
        answer, sources = await rag.generate_answer(
            question="What is the fee for CSE?",
            conversation_context="",
            retrieved_chunks=[{"content": "Tuition fee is Rs. 1,47,500.", "metadata": {}}],
        )

        assert "May contain inaccuracies" not in answer
        assert "Verify with official university sources" not in answer


@pytest.mark.asyncio
async def test_rag_sanitizes_stray_disclaimer():
    """Verify that if disclaimer is in the raw LLM answer, it is sanitized out."""
    existing_answer = (
        "B.Tech CSE requires 60% PCM.\n\n"
        "> ⚠️ *May contain inaccuracies. Verify with official university sources.*"
    )
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=existing_answer)
    mock_embed = MagicMock()

    with patch("app.services.rag_service.chromadb.PersistentClient"):
        rag = RAGService(llm_provider=mock_llm, embedding_provider=mock_embed)
        rag.prepare_rag_request = AsyncMock(return_value=([], [], "Evidence text"))

        answer, _ = await rag.generate_answer(
            question="What is the cutoff?",
            conversation_context="",
            retrieved_chunks=[{"content": "Evidence", "metadata": {}}],
        )

        assert "May contain inaccuracies" not in answer



def test_specialist_suggestion_chips():
    """Verify contextual suggestions map to specialist domains."""
    # Hostel query
    chips = generate_suggestions(
        intent="UNIVERSITY",
        user_message="Tell me about campus hostel accommodation",
        answer="We offer triple sharing rooms with hot water and Wi-Fi.",
    )
    assert len(chips) >= 2
    assert any("curfew" in c.lower() or "mess" in c.lower() or "bus" in c.lower() for c in chips)

    # Attendance query
    chips_acad = generate_suggestions(
        intent="UNIVERSITY",
        user_message="What is the rule for attendance condonation?",
        answer="Attendance between 65% and 74.9% may be condoned on medical grounds.",
    )
    assert len(chips_acad) >= 2
    assert any("detention" in c.lower() or "credit" in c.lower() or "condonation" in c.lower() for c in chips_acad)


def test_suggestion_chips_anti_duplicate_filter():
    """Verify user's exact query does not appear as a suggested chip."""
    chips = generate_suggestions(
        intent="UNIVERSITY",
        user_message="What is the complete tuition fee schedule?",
        answer="Tuition is Rs. 2,10,000 for CSE.",
    )
    assert not any(c == "💰 Complete Tuition Fee Schedule" for c in chips)


def test_admission_eligibility_chips_exact_match():
    """Verify that when assistant asks for 10+2 PCM percentage, the 4 exact score chips are returned."""
    user_query = "What is the eligibility criteria and admission process for B.Tech 2026?"
    assistant_response = (
        "To join our B.Tech program, you need to have passed your 10+2 or equivalent examination with "
        "a minimum of 60% aggregate marks in Physics, Chemistry, and Mathematics. The admission process "
        "is straightforward as we offer direct admissions based on your board marks, meaning there is no "
        "requirement to appear for any entrance exams.\n\n"
        "To help me confirm your eligibility, could you please share your 10+2 PCM percentage? \n\n"
        "Would you like to know more about our available engineering branches?"
    )

    chips = generate_suggestions(
        intent="UNIVERSITY",
        user_message=user_query,
        answer=assistant_response,
    )

    expected = [
        "I scored 90%+",
        "I scored 75%",
        "I scored 60%",
        "What if I have < 60%?",
    ]
    assert chips == expected


def test_general_fee_disambiguation_suggestions():
    """Verify that broad fee queries return program options and calculator chip."""
    chips = generate_suggestions(
        intent="UNIVERSITY",
        user_message="What are the fee details?",
        answer="Please let me know which program's fee structure you would like to know.",
    )
    assert "🧮 Scholarship Calculator" in chips
    assert any("B.Tech" in c for c in chips)
    assert any("MBA" in c for c in chips)


def test_btech_fee_suggestions():
    """Verify that specific B.Tech fee queries return B.Tech branches and calculator."""
    chips = generate_suggestions(
        intent="UNIVERSITY",
        user_message="What is the tuition fee for B.Tech CSE?",
        answer="Tuition Fee for B.Tech CSE is ₹1,47,500 per semester.",
    )
    assert "🧮 Scholarship Calculator" in chips
    assert any("Scholarship" in c for c in chips)


@pytest.mark.asyncio
async def test_fast_lexical_rerank():
    """Verify that _fast_lexical_rerank boosts chunks with keyword matches without LLM network calls."""
    mock_llm = MagicMock()
    mock_embed = MagicMock()

    with patch("app.services.rag_service.chromadb.PersistentClient"):
        rag = RAGService(llm_provider=mock_llm, embedding_provider=mock_embed)
        chunks = [
            {"content": "General sports and playground facilities.", "metadata": {"title": "Sports"}, "distance": 0.2},
            {"content": "Hostel curfew timing is 9:00 PM for all residential students.", "metadata": {"title": "Hostel Regulations"}, "distance": 0.3},
            {"content": "Library timing is 8:00 AM to 8:00 PM on weekdays.", "metadata": {"title": "Library Rules"}, "distance": 0.25},
            {"content": "Hostel fee details: AC room is 1,25,000 per year.", "metadata": {"title": "Hostel Fees"}, "distance": 0.35},
            {"content": "Campus security guidelines.", "metadata": {"title": "Security"}, "distance": 0.4},
        ]

        # Query for hostel curfew
        reranked = rag._fast_lexical_rerank("what is hostel curfew timing?", chunks, keep_top=2)
        assert len(reranked) == 2
        assert "curfew timing is 9:00 PM" in reranked[0]["content"]

        # Test async wrapper
        async_reranked = await rag._rerank_chunks("hostel curfew", chunks, keep_top=3)
        assert len(async_reranked) == 3
        assert "curfew" in async_reranked[0]["content"].lower() or "hostel" in async_reranked[0]["content"].lower()

