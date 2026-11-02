"""Tests for the university video recommendation service."""

import pytest
from app.services.video_service import (
    load_videos,
    get_relevant_videos,
    create_video_card,
)


def test_load_videos():
    """Verify videos load correctly from university_videos.json."""
    videos = load_videos()
    assert isinstance(videos, list)
    assert len(videos) >= 4
    for v in videos:
        assert "id" in v
        assert "title" in v
        assert "url" in v
        assert "thumbnail_url" in v
        assert "keywords" in v
        assert "https://www.youtube.com/watch?v=" in v["url"]
        assert "i.ytimg.com/vi/" in v["thumbnail_url"] or "img.youtube.com/vi/" in v["thumbnail_url"]


def test_blacklist_queries_return_no_videos():
    """Verify greetings, attendance rules, and low-confidence responses never return videos."""
    # Greeting
    assert get_relevant_videos("hi", "Hello! How can I help you?") == []
    assert get_relevant_videos("good morning", "Good morning! Welcome to SRU.") == []

    # Strict rule questions
    assert (
        get_relevant_videos(
            "What is the minimum attendance percentage required?",
            "You need minimum 75% attendance to write the semester exams.",
        )
        == []
    )
    assert (
        get_relevant_videos(
            "What is the condonation fee for attendance shortage?",
            "Condonation fee is applicable for attendance between 65% and 75%.",
        )
        == []
    )

    # Low-confidence fallback
    assert (
        get_relevant_videos(
            "Tell me about something unknown",
            "This information could not be verified in the student handbook.",
        )
        == []
    )


def test_explicit_video_queries_return_videos():
    """Verify explicit asks for videos or walkthroughs return matched videos."""
    videos = get_relevant_videos("Show me a video of the campus", "Here is our campus overview.")
    assert len(videos) > 0
    assert any("campus" in v["category"].lower() for v in videos)

    hostel_videos = get_relevant_videos(
        "Do you have a video of the hostel rooms and mess?",
        "Our hostels have AC and non-AC rooms.",
    )
    assert len(hostel_videos) > 0
    assert any("hostel" in v["category"].lower() for v in hostel_videos)


def test_contextual_visual_queries_return_videos():
    """Verify questions about campus life, hostels, and SRiX return relevant video recommendations."""
    campus_vids = get_relevant_videos(
        "Tell me about the campus facilities and buildings",
        "SR University campus spans 170+ acres with lush green open spaces, modern classrooms, and libraries.",
        sources=[{"title": "SRU Student Handbook — Campus Life, Facilities & Contacts"}],
    )
    assert len(campus_vids) > 0

    srix_vids = get_relevant_videos(
        "What is SRiX technology business incubator and what do startups do there?",
        "SRiX is the startup incubator supporting student entrepreneurship and robotics innovation.",
    )
    assert len(srix_vids) > 0
    assert any("srix" in v["title"].lower() or "innovation" in v["category"].lower() for v in srix_vids)


def test_create_video_card():
    """Verify card formatting conforms to UI requirements."""
    videos = load_videos()[:2]
    card = create_video_card(videos, is_explicit=True)

    assert card["type"] == "video_recommendations"
    assert "Official SR University" in card["title"]
    assert "channel_url" in card
    assert "channel_name" in card
    assert len(card["videos"]) == 2

