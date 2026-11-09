"""Unit tests for claim-level grounding and known-gaps memory (T15)."""

import pytest

from app.services.claims_service import (
    load_verified_highlights,
    get_relevant_highlights,
    format_highlights_for_prompt,
    verify_persuasive_output,
    verify_qualitative_claims,
    record_known_gap,
    get_known_gaps,
    detect_topic_gap_from_response,
    get_turn_fallback,
)


def test_load_verified_highlights():
    highlights = load_verified_highlights()
    assert len(highlights) >= 5
    ids = [h["id"] for h in highlights]
    assert "HL_CAMPUS_SPORTS" in ids
    assert "HL_PLACEMENTS_STATS" in ids
    for h in highlights:
        assert "short_text" in h
        assert "source_name" in h
        assert "tags" in h


def test_get_relevant_highlights():
    sports_hl = get_relevant_highlights("Tell me about sports and gym")
    assert any("SPORTS" in h["id"] for h in sports_hl)

    placement_hl = get_relevant_highlights("What are the placement packages?", limit=2)
    assert any("PLACEMENTS" in h["id"] for h in placement_hl)


def test_verify_persuasive_output_valid_json():
    valid_json = '{"reply_text": "SR University has a 150-acre sports ground and gym.", "used_highlight_ids": ["HL_CAMPUS_SPORTS"]}'
    is_valid, reply, used_ids = verify_persuasive_output(valid_json, ["HL_CAMPUS_SPORTS", "HL_PLACEMENTS_STATS"])
    assert is_valid is True
    assert "150-acre" in reply
    assert used_ids == ["HL_CAMPUS_SPORTS"]


def test_verify_persuasive_output_rejects_hallucinated_id():
    invalid_json = '{"reply_text": "We have an Olympic swimming pool.", "used_highlight_ids": ["HL_OLYMPIC_POOL_UNKNOWN"]}'
    is_valid, reply, used_ids = verify_persuasive_output(invalid_json, ["HL_CAMPUS_SPORTS"])
    assert is_valid is False
    assert "HL_OLYMPIC_POOL_UNKNOWN" in used_ids


def test_verify_qualitative_claims_supported():
    context = "Our 150-acre campus includes a modern gymnasium, cricket ground, and basketball court."
    reply = "SR University offers a modern gymnasium and cricket ground for students."
    is_valid, unsupported = verify_qualitative_claims(reply, context)
    assert is_valid is True
    assert len(unsupported) == 0


def test_verify_qualitative_claims_unsupported():
    context = "The syllabus covers Python and Java programming."
    # Reply claims cricket grounds and gym which are not in context
    reply = "You can enjoy cricket grounds and a gym during your study."
    is_valid, unsupported = verify_qualitative_claims(reply, context)
    assert is_valid is False
    assert "cricket" in unsupported
    assert "gym" in unsupported


@pytest.mark.asyncio
async def test_known_gaps_tracking():
    session_id = "test-session-gap-123"
    await record_known_gap(session_id, "sports_facilities")
    gaps = await get_known_gaps(session_id)
    assert "sports_facilities" in gaps


def test_detect_topic_gap_from_response():
    user_msg = "Do you have an international student hostel?"
    bot_resp = "Our notes do not list hostel fees for international students. Please check with the Admissions Office."
    detected = detect_topic_gap_from_response(user_msg, bot_resp)
    assert detected == "international_hostel"


def test_fallback_selection_by_reason_code():
    # Numeric failure must have "numbers I'm unsure about"
    num_fallback = get_turn_fallback("ungrounded_number")
    assert "numbers I'm unsure about" in num_fallback

    # Qualitative / unsupported failure must NOT say "numbers I'm unsure about"
    qual_fallback = get_turn_fallback("unsupported_claim")
    assert "numbers I'm unsure about" not in qual_fallback
    assert "verified notes" in qual_fallback or "official" in qual_fallback

    fac_fallback = get_turn_fallback("unverified_facility")
    assert "numbers I'm unsure about" not in fac_fallback
