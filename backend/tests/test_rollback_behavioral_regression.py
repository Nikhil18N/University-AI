"""Behavioral regression test suite based on rollback_resp.pdf baseline and core conversational flows."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.schemas.chat import ChatRequest
from app.services.chat_service import (
    FAST_CONVERSATIONAL_RESPONSES,
    get_conversational_response,
    get_time_aware_greeting,
)
from app.services.intent_service import fast_classify
from app.services.suggestion_service import (
    CAMPUS_SUGGESTIONS,
    DEFAULT_GREETING_SUGGESTIONS,
    generate_suggestions,
)


# ==============================================================================
# Category 1: Casual Conversation
# ==============================================================================

def test_casual_greetings_accuracy():
    """Verify greetings are classified and answered with warm, non-robotic salutations."""
    for greeting in ["Hi", "Hello", "Hey there", "Good morning"]:
        intent = fast_classify(greeting)
        assert intent == "GREETING"
        resp = get_conversational_response(intent, has_context=False)
        assert any(term in resp for term in ["SRU Buddy", "Good morning", "Good afternoon", "Good evening", "Hello"])


def test_casual_how_are_you_warmth():
    """Verify 'how are you' returns the enthusiastic senior-mentor persona response."""
    intent = fast_classify("how are you")
    assert intent == "HOW_ARE_YOU"
    resp = get_conversational_response("HOW_ARE_YOU")
    assert any(term in resp for term in ["pumped to help", "Doing well", "All good here"])


def test_followup_greeting_context():
    """Verify subsequent greetings in an active session return conversational follow-ups."""
    from app.services.chat_service import GREETING_RESPONSES_FOLLOWUP
    resp = get_conversational_response("GREETING", has_context=True)
    assert resp in GREETING_RESPONSES_FOLLOWUP


def test_thank_you_and_help_queries():
    """Verify thanks and capabilities inquiries return supportive responses."""
    intent_thanks = fast_classify("Thank you")
    assert intent_thanks == "THANKS"
    resp = get_conversational_response("THANKS").lower()
    assert any(term in resp for term in ["welcome", "anytime", "happy", "pleasure"])

    intent_help = fast_classify("What can you help me with?")
    assert intent_help == "HELP"
    help_resp = get_conversational_response("HELP")
    assert "Admissions & Eligibility" in help_resp
    assert "Placements & Innovation" in help_resp


# ==============================================================================
# Category 2: Suggestion Chips & Video Isolation
# ==============================================================================

def test_campus_query_does_not_force_binary_video_chips_when_no_video_offered():
    """Verify queries mentioning campus do NOT inject binary Yes/No video chips if no video was offered."""
    suggestions = generate_suggestions(
        intent="UNIVERSITY",
        user_message="I came through an ad",
        answer="Welcome to SR University! Admissions are open across all programs.",
        sources=[{"title": "Admissions Guide"}],
    )
    # Binary video chips must NEVER appear unless video was actively offered
    assert "🎥 Yes, watch video" not in suggestions
    assert "❌ No, thanks" not in suggestions


def test_campus_query_offers_exploratory_campus_chips():
    """Verify campus inquiry returns natural exploratory suggestions."""
    suggestions = generate_suggestions(
        intent="UNIVERSITY",
        user_message="Tell me about the campus",
        answer="Our 150-acre green campus in Warangal features state-of-the-art facilities.",
        sources=[{"title": "Campus Life"}],
    )
    assert any("Campus" in s or "Lab" in s or "Hostel" in s for s in suggestions)
    assert "🎥 Yes, watch video" not in suggestions


# ==============================================================================
# Category 3: Admission & Eligibility Behavioral Alignment
# ==============================================================================

def test_btech_eligibility_classification():
    """Verify admissions and score inquiries are properly routed as UNIVERSITY inquiries."""
    assert fast_classify("I want to join B.Tech") == "UNIVERSITY"
    assert fast_classify("I secured 93% in 12th") == "UNIVERSITY"
    assert fast_classify("Am I eligible?") == "UNIVERSITY"
    assert fast_classify("What are the admission requirements?") == "UNIVERSITY"


# ==============================================================================
# Category 4: Context Handling & Short Follow-ups
# ==============================================================================

def test_affirmative_followup_preserves_university_context():
    """Verify bare affirmatives ('yes', 'sure', 'tell me more') maintain conversation context."""
    context = (
        "User: tell me about AI labs\n"
        "Assistant: We have modern AI labs. Would you like to know more about the curriculum?"
    )
    assert fast_classify("yes", conversation_context=context) == "UNIVERSITY"
    assert fast_classify("sure", conversation_context=context) == "UNIVERSITY"
    assert fast_classify("tell me more", conversation_context=context) == "UNIVERSITY"
    assert fast_classify("what about placements?", conversation_context=context) == "UNIVERSITY"


def test_refusal_followup_is_not_routed_to_rag():
    """Verify 'no' or 'not now' gracefully declines without re-invoking RAG."""
    context = (
        "User: tell me about AI labs\n"
        "Assistant: Would you like to watch a video tour?"
    )
    intent = fast_classify("no", conversation_context=context)
    assert intent in ("ACKNOWLEDGMENT", "REJECTION", None)
