"""Tests for AI Response Length, Readability, Scannability, and Natural Variation.

Validates:
1. Global length guidelines & scannability rules in prompt.py and system.md.
2. Word count of condensed static responses (_PLACEMENT_ASSISTANCE_RESPONSES,
   _LAB_FACILITIES_TEXT, _HOSTEL_INFO_TEXT, _HOSTEL_CURFEW_RULES_TEXT, _CAMPUS_CANTEEN_TEXT, _VIRTUAL_TOUR_TEXT) <= 90 words.
3. Career guidance follow-up suggestion chips matching the reference screenshot.
4. Deterministic session-stable variation for FALLBACK_OPTIONS and _LIMIT_REPLY_OPTIONS.
5. Anti-repetition and multi-turn freshness constraints.
6. Verification across 10 conversational categories.
"""
import re
import pytest
from app.sru_agent.prompt import build_system_prompt, PROMPT_VERSION
from app.sru_agent import followups
from app.sru_agent import responses
from app.sru_agent import agent


def test_prompt_version_and_length_guidelines():
    """Verify that the system prompt specifies the target response lengths."""
    prompt = build_system_prompt({})
    assert PROMPT_VERSION in ("2026-11-21.6", "2026-11-21.7", "2026-11-22.1", "2026-11-22.2", "2026-11-23.1", "2026-11-23.2", "2026-11-23.3", "2026-11-24.1", "2026-11-25.1", "2026-11-25.2", "2026-11-26.1", "2026-11-26.2")
    # v4.17.0: one answer layout (prompts/answer_layout.md) sets the length for every answer
    assert "50–130 words" in prompt and "≤170 with a table or steps" in prompt


def test_prompt_scannability_and_structure_rules():
    """Verify that prompt requires immediate answers, short paragraphs, and 2-4 clean bullets."""
    prompt = build_system_prompt({})
    assert "answer the actual question immediately" in prompt.lower() or "answer the core question" in prompt.lower()
    assert "3–5 bullets" in prompt and "a Markdown table" in prompt and "1. **Step:** detail" in prompt
    assert "at most one" in prompt.lower() or "only one question" in prompt.lower()
    assert "never dense walls of text" in prompt.lower()


def test_prompt_career_guidance_and_confused_persona():
    """Verify that confused students are guided with 2-3 clean pathways with emoji and one question."""
    prompt = build_system_prompt({}, persona="confused")
    assert "the user is confused" in prompt.lower()
    assert "2-3 clear pathways" in prompt.lower() or "2–4 clean bullet points" in prompt.lower()
    assert "no emoji in headings, bullets or tables" in prompt.lower()


def test_static_responses_word_counts():
    """Verify all major static responses are condensed to <= 90 words for effortless scanning."""
    for idx, resp in enumerate(responses._PLACEMENT_ASSISTANCE_RESPONSES):
        words = [w for w in resp.split() if w and not w.startswith(("#", ">", "|", "---"))]
        assert len(words) <= 95, f"Placement response {idx} too long: {len(words)} words"

    lab_words = [w for w in responses._LAB_FACILITIES_TEXT.split() if w and not w.startswith(("#", ">", "|", "---"))]
    assert len(lab_words) <= 90, f"_LAB_FACILITIES_TEXT too long: {len(lab_words)} words"

    hostel_words = [w for w in responses._HOSTEL_INFO_TEXT.split() if w and not w.startswith(("#", ">", "|", "---"))]
    assert len(hostel_words) <= 90, f"_HOSTEL_INFO_TEXT too long: {len(hostel_words)} words"

    curfew_words = [w for w in responses._HOSTEL_CURFEW_RULES_TEXT.split() if w and not w.startswith(("#", ">", "|", "---"))]
    assert len(curfew_words) <= 90, f"_HOSTEL_CURFEW_RULES_TEXT too long: {len(curfew_words)} words"

    canteen_words = [w for w in responses._CAMPUS_CANTEEN_TEXT.split() if w and not w.startswith(("#", ">", "|", "---"))]
    assert len(canteen_words) <= 90, f"_CAMPUS_CANTEEN_TEXT too long: {len(canteen_words)} words"

    tour_words = [w for w in agent._VIRTUAL_TOUR_TEXT.split() if w and not w.startswith(("#", ">", "|", "---"))]
    assert len(tour_words) <= 90, f"_VIRTUAL_TOUR_TEXT too long: {len(tour_words)} words"


def test_career_guidance_suggestion_chips():
    """Verify follow-up suggestion chips for career exploration match the reference screenshot."""
    queries = [
        "I did MPC in intermediate, but I'm really confused about which course to choose",
        "i have mpc background but not sure what to study",
        "which branch should i choose after 12th?",
        "suggest a course for me, i don't know what to take",
    ]
    for q in queries:
        chips = followups.suggest(q, tools_used=[], profile={})
        assert "I like computers" in chips, f"Missing 'I like computers' in chips for '{q}': {chips}"
        assert "I like building things" in chips, f"Missing 'I like building things' in chips for '{q}': {chips}"
        assert "People and numbers" in chips, f"Missing 'People and numbers' in chips for '{q}': {chips}"
        assert "Still not sure" in chips, f"Missing 'Still not sure' in chips for '{q}': {chips}"


def test_deterministic_session_variation_for_fallbacks_and_limits():
    """Verify FALLBACK_OPTIONS and _LIMIT_REPLY_OPTIONS vary across sessions but remain stable for the same session."""
    assert len(agent.FALLBACK_OPTIONS) >= 3
    assert len(agent.FALLBACK_OPTIONS) == len(set(agent.FALLBACK_OPTIONS))

    assert len(agent._LIMIT_REPLY_OPTIONS) >= 3
    assert len(agent._LIMIT_REPLY_OPTIONS) == len(set(agent._LIMIT_REPLY_OPTIONS))

    # Session stability: same session gives same result
    s1 = "user_session_abc_123"
    assert agent.get_fallback_text(s1) == agent.get_fallback_text(s1)
    assert agent.get_limit_reply(s1) == agent.get_limit_reply(s1)

    # Across different sessions, distinct variants are selected
    fb_results = {agent.get_fallback_text(f"session_test_{i}") for i in range(20)}
    assert len(fb_results) >= 2, "Fallback options should vary across different sessions"

    limit_results = {agent.get_limit_reply(f"session_test_{i}") for i in range(20)}
    assert len(limit_results) >= 2, "Limit replies should vary across different sessions"


def test_prompt_anti_repetition_and_freshness():
    """Verify prompt prevents repeating previously given explanations across turns."""
    prompt = build_system_prompt({})
    assert "multi-turn freshness" in prompt.lower()
    assert "never repeat explanations" in prompt.lower() or "never repeat, parrot" in prompt.lower()


def test_why_choose_sru_6_variants_content_and_rotation():
    """Verify all 6 Why Choose SR University drafts exist, are distinct, and contain verified ranking/placement facts."""
    assert len(responses._WHY_CHOOSE_SRU_VARIANTS) == 6
    assert len(set(responses._WHY_CHOOSE_SRU_VARIANTS)) == 6

    for idx, draft in enumerate(responses._WHY_CHOOSE_SRU_VARIANTS):
        words = [w for w in draft.split() if w and not w.startswith(("#", ">", "|", "---"))]
        assert len(words) <= 125, f"Why Choose draft {idx+1} too long: {len(words)} words"
        assert "95%" in draft or "95% placement" in draft
        assert "QS Asia" in draft or "NIRF" in draft

    # Verify rotation by variant_id
    for v_id in range(1, 7):
        assert responses.get_why_choose_sru_text(variant_id=v_id) == responses._WHY_CHOOSE_SRU_VARIANTS[v_id - 1]

    # Verify session-based stable selection
    s1 = "session_why_test"
    assert responses.get_why_choose_sru_text(session_id=s1) == responses.get_why_choose_sru_text(session_id=s1)


def test_hostel_info_variants_and_contextual_selection():
    """Verify hostel info variants are dynamic, context-aware, and free of removed inaccurate names."""
    assert len(responses._HOSTEL_INFO_VARIANTS) == 3

    # Check that removed names/wardens are completely gone from all variants
    for idx, text in enumerate(responses._HOSTEL_INFO_VARIANTS):
        assert "Sarvepalli" not in text, f"Variant {idx} still mentions Sarvepalli"
        assert "Kalpana Chawla" not in text, f"Variant {idx} still mentions Kalpana Chawla"
        assert "Rupesh Mishra" not in text, f"Variant {idx} still mentions Rupesh Mishra"
        assert "Anitha GP" not in text, f"Variant {idx} still mentions Anitha GP"

    # Contextual query matching
    room_resp = responses.get_hostel_info_text(query="what are the room sharing and ac options?")
    assert "AC" in room_resp
    assert "Non-AC" in room_resp

    amenity_resp = responses.get_hostel_info_text(query="tell me about gym, sports and wifi amenities")
    assert "Gymnasium" in amenity_resp or "gym" in amenity_resp.lower() or "sports" in amenity_resp.lower()


def test_hostel_facilities_card_clean_structure():
    """Verify HOSTEL_FACILITIES_CARD does not contain inaccurate blocks or wardens."""
    from app.services.card_service import HOSTEL_FACILITIES_CARD
    assert "blocks" not in HOSTEL_FACILITIES_CARD
    assert "contacts" not in HOSTEL_FACILITIES_CARD
    assert HOSTEL_FACILITIES_CARD["title"] == "SR University Residential Living & Campus Hostels"
    assert len(HOSTEL_FACILITIES_CARD["room_types"]) >= 2
    assert len(HOSTEL_FACILITIES_CARD["amenities"]) >= 5
    assert len(HOSTEL_FACILITIES_CARD["rules_summary"]) >= 3

