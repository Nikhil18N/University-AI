"""Unit tests for conversation state: pending offers, slot filling, post-distress cooldown (T13)."""

import pytest

from app.services.guardrail_service import verify_outcome_language
from app.services.profile_service import build_counsellor_guidance
from app.services.session_state_service import (
    get_session_state,
    is_in_distress_cooldown,
    resolve_pending_offer_if_affirmative,
    set_pending_offer,
    step_distress_cooldown,
    trigger_distress_cooldown,
)


@pytest.mark.asyncio
async def test_pending_offer_resolution_on_affirmative():
    session_id = "test-session-offer-1"
    # Bot sets pending offer to walk through application steps
    await set_pending_offer(
        session_id,
        offer_type="application_steps",
        topic="application",
        program="B.Tech CSE",
    )

    # Student says "yes"
    is_resolved, resolved_text, offer = await resolve_pending_offer_if_affirmative(
        session_id, "yes"
    )
    assert is_resolved is True
    assert "application process" in resolved_text
    assert "B.Tech CSE" in resolved_text

    # After acceptance, pending offer is cleared
    state = await get_session_state(session_id)
    assert state.get("pending_offer") is None
    assert "application" in state.get("completed_topics", [])


@pytest.mark.asyncio
async def test_pending_offer_ignores_unrelated_messages():
    session_id = "test-session-offer-2"
    await set_pending_offer(
        session_id,
        offer_type="application_steps",
        topic="application",
        program="B.Tech",
    )

    # Student asks an unrelated question instead of saying yes
    is_resolved, _, _ = await resolve_pending_offer_if_affirmative(
        session_id, "What about hostel fees?"
    )
    assert is_resolved is False

    state = await get_session_state(session_id)
    assert state.get("pending_offer") is not None
    assert state["pending_offer"]["age"] == 1


@pytest.mark.asyncio
async def test_distress_cooldown_lifecycle():
    session_id = "test-session-distress-1"
    assert await is_in_distress_cooldown(session_id) is False

    # Distress detected -> trigger 3-turn cooldown
    await trigger_distress_cooldown(session_id, turns=3)
    assert await is_in_distress_cooldown(session_id) is True

    # Turn 1
    rem1 = await step_distress_cooldown(session_id)
    assert rem1 == 3
    assert await is_in_distress_cooldown(session_id) is True

    # Turn 2
    rem2 = await step_distress_cooldown(session_id)
    assert rem2 == 2
    assert await is_in_distress_cooldown(session_id) is True

    # Turn 3
    rem3 = await step_distress_cooldown(session_id)
    assert rem3 == 1
    assert await is_in_distress_cooldown(session_id) is False


def test_verify_outcome_language_blocks_forbidden_phrases():
    # Blocks "you're in a great spot"
    bad_text_1 = "You're in a great spot with your 93% marks!"
    is_clean, detected = verify_outcome_language(bad_text_1)
    assert is_clean is False
    assert any("great spot" in d for d in detected)

    # Blocks "you've got this"
    bad_text_2 = "Don't worry, you've got this!"
    is_clean, detected = verify_outcome_language(bad_text_2)
    assert is_clean is False

    # Blocks "guaranteed admission"
    bad_text_3 = "You have guaranteed admission in B.Tech CSE."
    is_clean, detected = verify_outcome_language(bad_text_3)
    assert is_clean is False

    # Passes neutral factual eligibility statement
    good_text = "With 93%, you meet the minimum academic eligibility requirement of 60% for B.Tech CSE."
    is_clean, detected = verify_outcome_language(good_text)
    assert is_clean is True
    assert len(detected) == 0


def test_slot_filling_guidance_for_scholarship_board():
    profile = {
        "degree": "B.Tech",
        "branch": "Computer Science & Engineering (CSE)",
        "has_score": True,
        "score_pct": 93.0,
        "score_raw": "93%",
    }
    guidance = build_counsellor_guidance(profile, current_query="What scholarship will I get?")
    # Guidance must prompt to check board instead of assuming CBSE
    assert "Slot Filling for Scholarships" in guidance
    assert "CBSE vs State Board" in guidance

