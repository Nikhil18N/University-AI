import pytest
from app.services.reformulation_service import canonicalize_query
from app.services.profile_service import extract_student_profile, build_counsellor_guidance
from app.services.intent_service import fast_classify


def test_canonicalize_query_synonyms_and_typos():
    assert "scholarship" in canonicalize_query("can i get discount on btech fees?")
    assert "hostel" in canonicalize_query("what about dorm accommodation?")
    assert "placement package CTC" in canonicalize_query("what is the average salary and package?")
    assert "eligibility" in canonicalize_query("tell me elgblty criteria")
    assert "college" in canonicalize_query("at clg")


def test_extract_student_profile_natural_marks():
    cases = [
        ("i got 85 in 12th", 85.0),
        ("my 12th marks is 85", 85.0),
        ("i scored 85% in inter", 85.0),
        ("78 in pcm for b.tech cse", 78.0),
        ("450/600 in intermediate", 75.0),
        ("85 percent in 12th", 85.0),
        ("my marks are 92", 92.0),
    ]
    for prompt, expected_score in cases:
        prof = extract_student_profile([{"role": "user", "content": prompt}])
        assert prof["has_score"] is True, f"Failed for prompt: {prompt}"
        assert prof["score_pct"] == expected_score, f"Expected {expected_score} for {prompt}"


def test_counsellor_guidance_for_known_marks():
    prof = extract_student_profile([{"role": "user", "content": "i got 85 in 12th want btech cse"}])
    guidance = build_counsellor_guidance(prof, current_query="am i eligible?")
    assert "ELIGIBLE" in guidance
    assert "DO NOT ask for their score or percentage again" in guidance


def test_intent_classification_for_marks_and_synonyms():
    assert fast_classify("i got 85 in 12th") == "UNIVERSITY"
    assert fast_classify("my 12th marks is 85") == "UNIVERSITY"
    assert fast_classify("can i get discount on fees?") == "UNIVERSITY"
    assert fast_classify("dorm facilities details") == "UNIVERSITY"
    assert fast_classify("what is the average salary?") == "UNIVERSITY"
