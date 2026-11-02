"""Tests for student profile extraction and dynamic counsellor guidance."""

from app.services.profile_service import build_counsellor_guidance, extract_student_profile


def test_extract_degree_and_branch():
    messages = [
        {"role": "user", "content": "I am interested in B.Tech CSE"},
    ]
    profile = extract_student_profile(messages)
    assert profile["degree"] == "B.Tech"
    assert "Computer Science" in profile["branch"]
    assert profile["has_score"] is False

    guidance = build_counsellor_guidance(profile)
    assert "B.Tech" in guidance
    assert "DO NOT ask what degree" in guidance
    assert "DO NOT ask what branch" in guidance
    assert "NOT PROVIDED YET" in guidance


def test_extract_score_percentage():
    messages = [
        {"role": "user", "content": "im interested in B.Tech"},
        {"role": "assistant", "content": "What is your 12th percentage?"},
        {"role": "user", "content": "I got 78% in 12th PCM and like AI & ML"},
    ]
    profile = extract_student_profile(messages)
    assert profile["degree"] == "B.Tech"
    assert profile["branch"] == "AI & Machine Learning"
    assert profile["has_score"] is True
    assert profile["score_pct"] == 78.0

    guidance = build_counsellor_guidance(profile)
    assert "78.0%" in guidance or "78%" in guidance
    assert "THEY ARE ELIGIBLE" in guidance


def test_extract_score_fraction():
    messages = [
        {"role": "user", "content": "I have 599 out of 1000 marks in intermediate"},
    ]
    profile = extract_student_profile(messages)
    assert profile["has_score"] is True
    assert profile["score_pct"] == 59.9

    guidance = build_counsellor_guidance(profile)
    assert "below" in guidance.lower()


def test_empty_profile():
    messages = [
        {"role": "user", "content": "Hello, tell me about library timings"},
    ]
    profile = extract_student_profile(messages)
    assert profile["degree"] is None
    assert profile["branch"] is None
    assert profile["has_score"] is False
    assert build_counsellor_guidance(profile) == ""


def test_guidance_eligibility_vs_comparison():
    messages = [{"role": "user", "content": "I want to do B.Tech CSE"}]
    profile = extract_student_profile(messages)

    # 1. Comparison query: Should NOT demand marks
    guidance_comp = build_counsellor_guidance(
        profile, current_query="compare CSE vs CSE with AIML specialization"
    )
    assert "Do NOT proactively demand or ask for their board marks" in guidance_comp

    # 2. Eligibility query: Should ask for marks
    guidance_elig = build_counsellor_guidance(
        profile, current_query="Am I eligible for admission in CSE?"
    )
    assert "state the 60% requirement and ask for their 10+2 PCM percentage" in guidance_elig
