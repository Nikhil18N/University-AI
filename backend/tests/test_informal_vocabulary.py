"""Tests for expanded informal vocabulary handling, fuzzy spell correction, and Hinglish support."""

import pytest
from app.services.reformulation_service import (
    canonicalize_query,
    apply_fuzzy_corrections,
    needs_reformulation,
)
from app.services.profile_service import extract_student_profile, build_counsellor_guidance
from app.services.intent_service import fast_classify


# ---------------------------------------------------------------------------
# Exact typo + synonym corrections
# ---------------------------------------------------------------------------

class TestCanonicalizeQuery:
    def test_discount_to_scholarship(self):
        assert "scholarship" in canonicalize_query("can i get a discount on fees?")

    def test_dorm_to_hostel(self):
        assert "hostel" in canonicalize_query("tell me about dorm facilities")

    def test_salary_to_placement(self):
        result = canonicalize_query("what is the average salary?")
        assert "placement" in result.lower() or "CTC" in result

    def test_typo_elgblty(self):
        assert "eligibility" in canonicalize_query("what is elgblty criteria?")

    def test_typo_hostle(self):
        assert "hostel" in canonicalize_query("hostle rules and timings")

    def test_typo_schlrshp(self):
        assert "scholarship" in canonicalize_query("schlrshp for merit students")

    def test_typo_collge(self):
        assert "college" in canonicalize_query("what is the collge ranking?")

    def test_typo_semister(self):
        assert "semester" in canonicalize_query("when does semister start?")

    def test_typo_syllubus(self):
        assert "syllabus" in canonicalize_query("where can i find syllubus?")

    def test_typo_attendence(self):
        assert "attendance" in canonicalize_query("what is minimum attendence?")

    def test_synonym_cost_to_fee(self):
        result = canonicalize_query("what is the cost of B.Tech?")
        assert "fee" in result.lower()

    def test_synonym_company_to_recruiter(self):
        result = canonicalize_query("which companies come for placement?")
        assert "recruiter" in result.lower() or "placement" in result.lower()

    def test_synonym_last_date(self):
        result = canonicalize_query("what is the last date to apply?")
        assert "deadline" in result.lower() or "application" in result.lower()

    def test_synonym_join(self):
        result = canonicalize_query("how to join B.Tech CSE?")
        assert "admission" in result.lower()

    def test_synonym_free_seat(self):
        result = canonicalize_query("is there a free seat for merit students?")
        assert "scholarship" in result.lower()


# ---------------------------------------------------------------------------
# Fuzzy spell correction for unknown misspellings
# ---------------------------------------------------------------------------

class TestFuzzyCorrections:
    def test_fuzzy_eligiblity(self):
        result = apply_fuzzy_corrections("eligiblity criteria")
        assert "eligibility" in result

    def test_fuzzy_scholership(self):
        result = apply_fuzzy_corrections("scholership merit details")
        assert "scholarship" in result

    def test_fuzzy_placment(self):
        result = apply_fuzzy_corrections("placment statistics 2024")
        assert "placement" in result

    def test_fuzzy_accomodation(self):
        result = apply_fuzzy_corrections("accomodation in hostel")
        assert "accommodation" in result

    def test_fuzzy_libary(self):
        result = apply_fuzzy_corrections("libary timings")
        assert "library" in result

    def test_no_false_positive_short_word(self):
        # Short words should not be fuzzy-corrected
        result = apply_fuzzy_corrections("fee is ok")
        assert result == "fee is ok"


# ---------------------------------------------------------------------------
# Informal / Hinglish vocabulary through needs_reformulation
# ---------------------------------------------------------------------------

class TestInformalVocabulary:
    def test_hinglish_chatter_detected(self):
        # "yaar" and "bhai" are Hinglish markers; should need reformulation
        assert needs_reformulation("yaar what is the hostle timing bhai?", "") is True

    def test_informal_discount_detected(self):
        assert needs_reformulation("can I get discount on btech fees", "") is True

    def test_informal_dorm_detected(self):
        assert needs_reformulation("tell me dorm facilities", "") is True

    def test_slang_lol_detected(self):
        assert needs_reformulation("lol what are the fees?", "") is True

    def test_slang_btw_detected(self):
        assert needs_reformulation("btw what is the last date for admission?", "") is True


# ---------------------------------------------------------------------------
# Intent classification routes informal queries to UNIVERSITY
# ---------------------------------------------------------------------------

class TestIntentForInformalQueries:
    def test_discount_intent(self):
        assert fast_classify("can i get discount on fees?") == "UNIVERSITY"

    def test_dorm_intent(self):
        assert fast_classify("what are dorm facilities?") == "UNIVERSITY"

    def test_salary_intent(self):
        assert fast_classify("what is the average salary?") == "UNIVERSITY"

    def test_typo_admsn_intent(self):
        assert fast_classify("admsn process for btech?") == "UNIVERSITY"

    def test_join_intent(self):
        assert fast_classify("how to join cse btech?") == "UNIVERSITY"


# ---------------------------------------------------------------------------
# Profile extraction works with informal input
# ---------------------------------------------------------------------------

class TestProfileWithInformalInput:
    def test_score_in_12th_natural(self):
        msgs = [{"role": "user", "content": "i got 85 in 12th"}]
        prof = extract_student_profile(msgs)
        assert prof["has_score"] is True
        assert prof["score_pct"] == 85.0

    def test_score_percentage_symbol(self):
        msgs = [{"role": "user", "content": "scored 78% in inter"}]
        prof = extract_student_profile(msgs)
        assert prof["has_score"] is True
        assert prof["score_pct"] == 78.0

    def test_counsellor_guidance_no_repeat_ask(self):
        msgs = [{"role": "user", "content": "i got 85 in 12th, want btech cse"}]
        prof = extract_student_profile(msgs)
        guidance = build_counsellor_guidance(prof, current_query="am i eligible?")
        assert "DO NOT ask for their score" in guidance
        assert "ELIGIBLE" in guidance
