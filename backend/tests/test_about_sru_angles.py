"""Unit tests for the 20 About SRU angles, rotation, and session-scoped card suppression."""

import pytest
from unittest.mock import AsyncMock
from app.services.card_service import (
    generate_cards,
    record_session_card,
    get_session_shown_cards,
    clear_session_cards,
    CAMPUS_TOUR_CARD,
)
from app.services.rag_service import (
    is_about_sru_query,
    determine_about_sru_angle,
    ABOUT_SRU_ANGLES,
    RAGService,
)
from app.sru_agent.prompt import build_system_prompt


def test_is_about_sru_query_detection():
    """Verify is_about_sru_query accurately detects overview inquiries."""
    positive_queries = [
        "about sru",
        "tell me about sru",
        "what is sru?",
        "describe sru",
        "about sr university",
        "give me an overview of sru",
        "what is sr university?",
        "why choose sru",
        "sru overview",
        "tell me about sru campus",
    ]
    for q in positive_queries:
        assert is_about_sru_query(q) is True, f"Failed for query: {q}"

    negative_queries = [
        "What is the fee for B.Tech CSE?",
        "How much is the bus transport fee?",
        "What are the hostel room sharing options?",
        "Show me placement statistics for Microsoft",
        "Can I join with 65% in inter?",
    ]
    for q in negative_queries:
        assert is_about_sru_query(q) is False, f"False positive for query: {q}"


def test_about_sru_angles_pool_contains_minimum_20_distinct_angles():
    """Verify there are at least 20 distinct verified thematic angles."""
    assert len(ABOUT_SRU_ANGLES) >= 20
    # Ensure all angles are unique
    assert len(set(ABOUT_SRU_ANGLES)) == len(ABOUT_SRU_ANGLES)
    # Check key thematic angles are present
    assert any("Placements & Career Launchpad" in a for a in ABOUT_SRU_ANGLES)
    assert any("Innovation, Startups & Entrepreneurship" in a for a in ABOUT_SRU_ANGLES)
    assert any("Research Excellence" in a for a in ABOUT_SRU_ANGLES)
    assert any("170-Acre Master-Planned Campus" in a for a in ABOUT_SRU_ANGLES)
    assert any("50-Year Sri Rajeshwara Educational Legacy" in a for a in ABOUT_SRU_ANGLES)
    assert any("Fully Flexible Credit System" in a for a in ABOUT_SRU_ANGLES)


def test_determine_about_sru_angle_rotation():
    """Verify angle rotates sequentially across turns and cycles cleanly."""
    # Explicit angle override
    assert determine_about_sru_angle("", "about sru", explicit_angle=7) == 7

    # Empty context defaults to angle 1
    assert determine_about_sru_angle("", "about sru") == 1

    # Simulated turns in conversation_context
    context_turn_1 = "User: tell me about sru\nAssistant: SR University is a top university..."
    assert determine_about_sru_angle(context_turn_1, "what is sru") == 2

    context_turn_2 = (
        "User: tell me about sru\nAssistant: Facts...\n"
        "User: describe sru\nAssistant: More facts..."
    )
    assert determine_about_sru_angle(context_turn_2, "why choose sru") == 3


def test_session_scoped_campus_tour_card_suppression():
    """Verify CAMPUS_TOUR_CARD is shown only on the 1st turn of a session, and suppressed on repeat."""
    session_id = "test_user_session_101"
    clear_session_cards(session_id)

    query = "Tell me about SRU"
    answer = "SR University is a premiere institution in Warangal."

    # Turn 1: First time asking in this session -> CAMPUS_TOUR_CARD must be present
    cards_turn_1 = generate_cards(query, answer, session_id=session_id)
    card_types_1 = [c.get("type") for c in cards_turn_1]
    assert "campus_tour" in card_types_1
    assert "campus_tour" in get_session_shown_cards(session_id)

    # Turn 2: Second time asking in the same session -> CAMPUS_TOUR_CARD must NOT be present
    cards_turn_2 = generate_cards(query, answer, session_id=session_id)
    card_types_2 = [c.get("type") for c in cards_turn_2]
    assert "campus_tour" not in card_types_2

    # Turn 3: Asking in a DIFFERENT session -> CAMPUS_TOUR_CARD must appear for the new session
    other_session_id = "test_user_session_202"
    clear_session_cards(other_session_id)
    cards_other = generate_cards(query, answer, session_id=other_session_id)
    card_types_other = [c.get("type") for c in cards_other]
    assert "campus_tour" in card_types_other

    # Suppressed via seen_card_types set parameter
    fresh_session = "test_fresh_session_303"
    clear_session_cards(fresh_session)
    cards_seen = generate_cards(
        query, answer, session_id=fresh_session, seen_card_types={"campus_tour"}
    )
    assert "campus_tour" not in [c.get("type") for c in cards_seen]

    # Clean up test sessions
    clear_session_cards(session_id)
    clear_session_cards(other_session_id)
    clear_session_cards(fresh_session)


@pytest.mark.asyncio
async def test_prepare_rag_request_renders_about_sru_angle():
    """Verify prepare_rag_request renders the chosen angle string into the prompt."""
    mock_llm = AsyncMock()
    mock_embedding = AsyncMock()
    rag = RAGService(mock_llm, mock_embedding)

    chunks = [
        {
            "content": "SR University 170-acre campus in Warangal.",
            "metadata": {"title": "Campus Overview", "document_id": "overview.md"},
        }
    ]

    # Angle 2: Innovation, Startups & Entrepreneurship
    messages, sources, evidence = await rag.prepare_rag_request(
        question="Tell me about SRU",
        conversation_context="",
        retrieved_chunks=chunks,
        about_sru_angle=2,
    )
    system_content = messages[0]["content"]
    assert "ABOUT_SRU_ANGLE" in system_content
    assert "Innovation, Startups & Entrepreneurship" in system_content

    # Angle 5: 170-Acre Master-Planned Campus Ecosystem
    messages_5, _, _ = await rag.prepare_rag_request(
        question="Tell me about SRU",
        conversation_context="",
        retrieved_chunks=chunks,
        about_sru_angle=5,
    )
    assert "170-Acre Master-Planned Campus Ecosystem" in messages_5[0]["content"]


def test_agent_build_system_prompt_includes_angle():
    """Verify agent prompt builder accepts and embeds about_sru_angle."""
    prompt_angle_4 = build_system_prompt(variant_id=2, about_sru_angle=4)
    assert "- ABOUT_SRU_ANGLE: 4" in prompt_angle_4
    assert "Accreditations, NIRF Rankings & UGC Recognition" in prompt_angle_4
