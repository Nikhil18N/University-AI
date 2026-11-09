"""Tests for deterministic numeric and date validator service."""

from app.services.validator_service import (
    validate_response_grounding,
    extract_numeric_tokens,
    FALLBACK_VALIDATOR_BLOCK,
)


def test_extract_numeric_tokens():
    text = "Tuition is ₹1,47,500 per semester with 50% cutoff and 51 LPA package, ranking 91st."
    tokens = extract_numeric_tokens(text)
    assert "₹1,47,500" in tokens
    assert "147500" in tokens
    assert "50%" in tokens
    assert "51 LPA" in tokens
    assert "91st" in tokens


def test_validate_response_grounded_in_evidence():
    evidence = "The B.Tech tuition fee is ₹1,47,500 per semester. Eligibility requires 50% in MPC."
    answer = "The tuition fee is ₹1,47,500 per semester, and you need at least 50% in MPC."
    is_valid, ungrounded = validate_response_grounding(answer, evidence_text=evidence)
    assert is_valid is True
    assert len(ungrounded) == 0


def test_validate_response_blocks_hallucinated_number():
    evidence = "The fee is ₹1,47,500 per semester."
    answer = "The fee is ₹1,95,000 per semester with a 99% guarantee."
    is_valid, ungrounded = validate_response_grounding(answer, evidence_text=evidence)
    assert is_valid is False
    assert any("195000" in u or "₹1,95,000" in u or "99%" in u for u in ungrounded)


def test_validate_allows_user_supplied_numbers():
    user_msg = "I scored 72% in my 12th board exams."
    answer = "With your 72%, you meet our eligibility criteria."
    is_valid, ungrounded = validate_response_grounding(answer, user_message=user_msg)
    assert is_valid is True
    assert len(ungrounded) == 0


def test_validate_whitelisted_standard_numbers():
    answer = "SR University operates a 150-acre campus with 24/7 security and 4-year degree programs."
    is_valid, ungrounded = validate_response_grounding(answer)
    assert is_valid is True
    assert len(ungrounded) == 0
