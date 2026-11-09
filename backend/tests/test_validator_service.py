"""Tests for deterministic numeric and date validator service (P1 Hardening T5)."""

from app.services.validator_service import (
    FALLBACK_VALIDATOR_BLOCK,
    WHITELISTED_CONSTANTS_WITH_REASONS,
    extract_dates,
    extract_numeric_tokens,
    mask_sensitive_token,
    normalize_currency_amount,
    validate_response_grounding,
)


def test_whitelist_constants_have_mandatory_comments():
    """Fail the test suite if any entry in the whitelist has an empty comment rationale."""
    assert len(WHITELISTED_CONSTANTS_WITH_REASONS) > 20
    for constant, reason in WHITELISTED_CONSTANTS_WITH_REASONS.items():
        assert isinstance(reason, str) and len(reason.strip()) > 5, f"Missing rationale for whitelisted constant: {constant}"


def test_normalize_currency_comma_and_digits():
    forms = normalize_currency_amount("1,25,000")
    assert "125000" in forms
    assert "1,25,000" in forms
    assert "1.25 lakh" in forms


def test_normalize_currency_lakh_format():
    forms = normalize_currency_amount("1.25 lakh")
    assert "125000" in forms
    assert "1,25,000" in forms


def test_extract_currency_variants():
    """Unifies ₹, Rs., Rs, and INR."""
    tokens1 = extract_numeric_tokens("Fee is ₹1,00,000")
    tokens2 = extract_numeric_tokens("Fee is Rs. 1,00,000")
    tokens3 = extract_numeric_tokens("Fee is INR 1,00,000")
    assert "100000" in tokens1
    assert "100000" in tokens2
    assert "100000" in tokens3


def test_extract_date_dd_month_yyyy():
    dates = extract_dates("Admissions close on 15 March 2027.")
    assert dates == ["2027-03-15"]


def test_extract_date_month_dd_yyyy():
    dates = extract_dates("Classes commence on July 31, 2026.")
    assert dates == ["2026-07-31"]


def test_extract_date_slash_format():
    dates = extract_dates("Deadline: 15/03/2027.")
    assert dates == ["2027-03-15"]


def test_extract_date_iso_format():
    dates = extract_dates("Effective from 2026-08-01.")
    assert dates == ["2026-08-01"]


def test_validate_date_grounded_across_formats():
    """Dates written as '15 March 2027' and '15/03/2027' compare equal via normalized date."""
    evidence = "The last date to register is 15/03/2027."
    answer = "Please note that the last date to apply is 15 March 2027."
    is_valid, ungrounded = validate_response_grounding(answer, evidence_text=evidence)
    assert is_valid is True
    assert len(ungrounded) == 0


def test_validate_date_unverified_blocks():
    evidence = "Registration opens in May."
    answer = "The entrance exam is scheduled on 28 December 2029."
    is_valid, ungrounded = validate_response_grounding(answer, evidence_text=evidence)
    assert is_valid is False
    assert any("2029-12-28" in u or "2029" in u for u in ungrounded)


def test_extract_unit_numbers_seats():
    tokens = extract_numeric_tokens("The program has 60 seats available.")
    assert "60" in tokens
    assert "60 seats" in tokens


def test_extract_unit_numbers_credits():
    tokens = extract_numeric_tokens("You must complete 160 credits to graduate.")
    assert "160" in tokens
    assert "160 credits" in tokens


def test_extract_unit_numbers_duration():
    tokens = extract_numeric_tokens("It is a 4 years degree across 8 semesters.")
    assert "4" in tokens
    assert "8" in tokens


def test_false_positive_phone_landline_whitelisted():
    answer = "For queries, call the Admissions Office at 0870-2818333."
    is_valid, ungrounded = validate_response_grounding(answer)
    assert is_valid is True
    assert len(ungrounded) == 0


def test_false_positive_national_helpline_whitelisted():
    answer = "If you're feeling distressed, call Tele-MANAS at 14416 or AASRA at 9820466726."
    is_valid, ungrounded = validate_response_grounding(answer)
    assert is_valid is True
    assert len(ungrounded) == 0


def test_false_positive_toll_free_whitelisted():
    answer = "You can reach student support on toll-free 1800-599-0019."
    is_valid, ungrounded = validate_response_grounding(answer)
    assert is_valid is True
    assert len(ungrounded) == 0


def test_false_positive_academic_years_whitelisted():
    answer = "The admissions handbook for 2026-27 is applicable for the 2026 intake."
    is_valid, ungrounded = validate_response_grounding(answer)
    assert is_valid is True
    assert len(ungrounded) == 0


def test_false_positive_campus_facilities_whitelisted():
    answer = "Our 150-acre campus features 24x7 security and is located 14 km from Kazipet."
    is_valid, ungrounded = validate_response_grounding(answer)
    assert is_valid is True
    assert len(ungrounded) == 0


def test_false_positive_higher_secondary_pattern():
    answer = "Candidates must have passed 10+2 with Physics, Chemistry and Mathematics."
    is_valid, ungrounded = validate_response_grounding(answer)
    assert is_valid is True
    assert len(ungrounded) == 0


def test_validate_response_blocks_hallucinated_fee():
    evidence = "The fee is ₹1,47,500 per semester."
    answer = "The fee is ₹2,80,000 per semester."
    is_valid, ungrounded = validate_response_grounding(answer, evidence_text=evidence)
    assert is_valid is False
    assert any("280000" in u or "₹2,80,000" in u for u in ungrounded)


def test_validate_response_blocks_hallucinated_percentage():
    evidence = "Minimum eligibility is 50% in 12th."
    answer = "You need at least 78% marks to apply."
    is_valid, ungrounded = validate_response_grounding(answer, evidence_text=evidence)
    assert is_valid is False
    assert any("78%" in u or "78" in u for u in ungrounded)


def test_validate_response_blocks_hallucinated_package():
    evidence = "The highest package is 51 LPA from Microsoft."
    answer = "We recorded a package of 98 LPA this year."
    is_valid, ungrounded = validate_response_grounding(answer, evidence_text=evidence)
    assert is_valid is False
    assert any("98 LPA" in u or "98" in u for u in ungrounded)


def test_validate_allows_user_supplied_marks():
    user_msg = "I scored 84% in my intermediate exams."
    answer = "With your 84% marks, you are well above the 50% cutoff."
    is_valid, ungrounded = validate_response_grounding(answer, user_message=user_msg)
    assert is_valid is True
    assert len(ungrounded) == 0


def test_validate_allows_structured_data_text():
    struct_data = "- [B.Tech CSE] tuition_fee_sem: ₹1,47,500 per semester"
    answer = "The B.Tech CSE tuition is ₹1,47,500 per semester."
    is_valid, ungrounded = validate_response_grounding(answer, structured_data_text=struct_data)
    assert is_valid is True
    assert len(ungrounded) == 0


def test_mask_sensitive_token_phone_and_email():
    masked_phone = mask_sensitive_token("9820466726")
    masked_email = mask_sensitive_token("student@gmail.com")
    assert masked_phone == "982******26"
    assert masked_email == "st***@gmail.com"
    assert mask_sensitive_token("₹1,50,000") == "₹1,50,000"


def test_empty_answer_passes_safely():
    is_valid, ungrounded = validate_response_grounding("")
    assert is_valid is True
    assert len(ungrounded) == 0
