import json
from pathlib import Path
import pytest

from app.services.suggestion_service import (
    filter_available_suggestions,
    generate_suggestions,
    CAMPUS_VIDEO_OFFER_SUGGESTIONS,
    BRANCH_COMPARISON_SUGGESTIONS,
)
from app.services.profile_service import (
    extract_student_profile,
    build_counsellor_guidance,
    add_profile_interest,
)


def test_chip_filtering_and_unavailable_topics():
    # Unavailable chips should be cleanly filtered out
    candidates = [
        "🔬 Specialized AI Labs",
        "⚽ Sports Arena",
        "🏠 Hostel Room & Mess Details",
        "International Hostel Options",
        "💰 Complete Tuition Fee Schedule",
    ]
    filtered = filter_available_suggestions(candidates)
    assert "🔬 Specialized AI Labs" not in filtered
    assert "⚽ Sports Arena" not in filtered
    assert "International Hostel Options" not in filtered
    assert "🏠 Hostel Room & Mess Details" in filtered
    assert "💰 Complete Tuition Fee Schedule" in filtered

    # Verify that default banks do not contain ungrounded chips
    for chip in CAMPUS_VIDEO_OFFER_SUGGESTIONS + BRANCH_COMPARISON_SUGGESTIONS:
        assert "specialized ai labs" not in chip.lower()
        assert "sports arena" not in chip.lower()


def test_generate_suggestions_never_returns_unavailable_chips():
    suggestions = generate_suggestions(
        intent="UNIVERSITY",
        user_message="Tell me about campus facilities and infrastructure",
        answer="Here are our campus facilities including hostels and libraries.",
    )
    for chip in suggestions:
        assert "sports arena" not in chip.lower()
        assert "specialized ai" not in chip.lower()


def test_profile_stage_prospective_by_default():
    # Student asking about B.Tech must remain 'prospective'
    messages = [
        {"role": "user", "content": "I want to apply for B.Tech CSE. What are the cutoffs?"},
    ]
    profile = extract_student_profile(messages)
    assert profile["stage"] == "prospective"
    assert profile["degree"] == "B.Tech"
    assert "Computer Science" in profile["branch"]

    guidance = build_counsellor_guidance(profile)
    assert "PROSPECTIVE APPLICANT" in guidance
    assert "Never address the student as already enrolled" in guidance


def test_profile_stage_current_student_explicit():
    # Student explicitly stating they study here
    messages = [
        {"role": "user", "content": "I am a current student studying at SRU in 2nd year. When do semester exams begin?"},
    ]
    profile = extract_student_profile(messages)
    assert profile["stage"] == "current"

    # Minimal degree slot to check guidance
    profile["degree"] = "B.Tech"
    guidance = build_counsellor_guidance(profile)
    assert "CURRENT STUDENT" in guidance


def test_interest_sources_distinction():
    profile = {
        "degree": "B.Tech",
        "branch": "CSE",
        "stage": "prospective",
        "interests": [],
        "interest_sources": {},
    }
    # User stated interest
    add_profile_interest(profile, "Robotics", source="stated")
    # User clicked a suggestion chip
    add_profile_interest(profile, "Hostel Life", source="chip")

    assert profile["interest_sources"]["Robotics"] == "stated"
    assert profile["interest_sources"]["Hostel Life"] == "chip"

    guidance = build_counsellor_guidance(profile)
    assert "Stated Student Interests: Robotics" in guidance
    assert "Explored Topics via Chips: Hostel Life" in guidance
    assert "DO NOT say 'you mentioned'" in guidance


def test_video_tags_accuracy_audit():
    videos_file = Path(__file__).resolve().parent.parent / "app" / "data" / "university_videos.json"
    with open(videos_file) as f:
        videos = json.load(f)

    for v in videos:
        title = v.get("title", "").lower()
        category = v.get("category", "").lower()
        keywords = [k.lower() for k in v.get("keywords", [])]

        # Verify hostel videos do not have sports tags
        if "hostel" in title or "hostels" in category:
            assert "sports" not in keywords, f"Hostel video {v['id']} should not contain sports tag"

        # Verify sports video contains relevant tags
        if "sports day" in title:
            assert "sports" in keywords
            assert "athletics" in keywords
