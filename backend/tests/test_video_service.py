"""Tests for the pure dense semantic vector video recommendation service.

Zero keyword matching:
Relevance is governed entirely by ChromaDB cosine distance thresholds.
"""

import pytest
from app.services.video_service import (
    load_videos,
    get_relevant_videos,
    get_semantic_videos,
    create_video_card,
    check_video_affirmative_or_negative,
    format_video_offer_prompt,
)


def test_load_videos():
    """Verify official YouTube videos load correctly from university_videos.json."""
    videos = load_videos(force_reload=True)
    assert isinstance(videos, list)
    assert len(videos) >= 20
    for v in videos:
        assert "id" in v
        assert "title" in v
        assert "url" in v
        assert "thumbnail_url" in v
        assert "keywords" in v
        assert v.get("platform") == "youtube"
        assert "youtube.com/watch?v=" in v["url"] or "youtube.com/shorts/" in v["url"]


def test_semantic_vector_search_matching(monkeypatch):
    """Verify semantic vector search returns matching videos when query_embedding is within threshold."""
    mock_results = {
        "metadatas": [[
            {
                "id": "vf6DnDS83nw",
                "platform": "youtube",
                "title": "Best Hostel Life in India? | SR University Campus Experience",
                "category": "Hostels & Living",
                "url": "https://www.youtube.com/watch?v=vf6DnDS83nw",
                "thumbnail_url": "https://i.ytimg.com/vi/vf6DnDS83nw/hqdefault.jpg",
                "type": "video",
            }
        ]],
        "distances": [[0.185]],
    }

    class MockCollection:
        def count(self):
            return 53

        def query(self, **kwargs):
            return mock_results

    monkeypatch.setattr("app.services.video_service._get_video_collection", lambda: MockCollection())

    fake_embedding = [0.01] * 768
    results = get_relevant_videos(
        user_message="where do students sleep and eat?",
        answer="SR University provides comfortable residential hostel accommodations.",
        query_embedding=fake_embedding,
    )

    assert len(results) == 1
    assert results[0]["id"] == "vf6DnDS83nw"
    assert results[0]["category"] == "Hostels & Living"


def test_unrelated_queries_filtered_by_distance_threshold(monkeypatch):
    """Verify queries with distance > 0.25 (bus, attendance, exam fees) return NO videos without any keyword rules."""
    # Mock collection returning distance 0.284 (typical distance for bus/attendance queries)
    mock_unrelated = {
        "metadatas": [[
            {
                "id": "vf6DnDS83nw",
                "platform": "youtube",
                "title": "Best Hostel Life in India? | SR University Campus Experience",
                "category": "Hostels & Living",
                "url": "https://www.youtube.com/watch?v=vf6DnDS83nw",
                "thumbnail_url": "https://i.ytimg.com/vi/vf6DnDS83nw/hqdefault.jpg",
                "type": "video",
            }
        ]],
        "distances": [[0.284]],
    }

    class MockCollection:
        def count(self):
            return 53

        def query(self, **kwargs):
            return mock_unrelated

    monkeypatch.setattr("app.services.video_service._get_video_collection", lambda: MockCollection())

    fake_embedding = [0.01] * 768
    # Bus facilities query -> distance 0.284 > 0.25 threshold -> returns []
    results = get_relevant_videos(
        user_message="What are the bus facilities and transport routes?",
        answer="SR University provides transport routes across Warangal.",
        query_embedding=fake_embedding,
    )
    assert results == []


def test_create_video_card():
    """Verify card formatting conforms to UI requirements."""
    videos = load_videos()[:2]
    card = create_video_card(videos, is_explicit=True)

    assert card["type"] == "video_recommendations"
    assert "Official SR University" in card["title"]
    assert "channel_url" in card
    assert "channel_name" in card
    assert len(card["videos"]) == 2


def test_check_video_affirmative_or_negative():
    """Verify Yes/No detection when video tour was previously offered."""
    recent_offered = [
        {"role": "user", "content": "Tell me about the hostel rooms."},
        {
            "role": "assistant",
            "content": "Our hostels offer comfortable AC and non-AC rooms.\n\nWould you like to watch a short video tour of Hostels & Living? (Yes / No)",
            "metadata": {"suggestions": ["🎥 Yes, watch video", "❌ No, thanks", "🍽️ Mess & Food Quality"]},
        },
    ]

    # Affirmative responses
    for aff in ("yes", "Yes, please", "sure", "yeah", "yep", "show me", "🎥 Yes, watch video"):
        is_yes, is_no = check_video_affirmative_or_negative(aff, recent_offered)
        assert is_yes is True, f"Failed for {aff}"
        assert is_no is False

    # Negative responses
    for neg in ("no", "No thanks", "nope", "not now", "❌ No, thanks"):
        is_yes, is_no = check_video_affirmative_or_negative(neg, recent_offered)
        assert is_yes is False
        assert is_no is True, f"Failed for {neg}"

    # Unrelated follow-up query
    is_yes, is_no = check_video_affirmative_or_negative("What is the tuition fee?", recent_offered)
    assert is_yes is False
    assert is_no is False

    # History where assistant did NOT offer video
    recent_no_video = [
        {"role": "user", "content": "How much is the fee?"},
        {
            "role": "assistant",
            "content": "The tuition fee is 1,40,000 per year.\n\nWould you like to know about scholarships?",
            "metadata": {"suggestions": ["🎓 Merit Scholarships", "💳 Payment Schedule"]},
        },
    ]
    is_yes, is_no = check_video_affirmative_or_negative("yes", recent_no_video)
    assert is_yes is False
    assert is_no is False


def test_cards_not_shown_for_implicit_queries_until_confirmed(monkeypatch):
    """Verify video cards are NOT shown automatically on standard queries, but only upon confirmation."""
    from app.services.card_service import generate_cards

    mock_results = {
        "metadatas": [[
            {
                "id": "vf6DnDS83nw",
                "platform": "youtube",
                "title": "Best Hostel Life in India? | SR University Campus Experience",
                "category": "Hostels & Living",
                "url": "https://www.youtube.com/watch?v=vf6DnDS83nw",
                "thumbnail_url": "https://i.ytimg.com/vi/vf6DnDS83nw/hqdefault.jpg",
                "type": "video",
            }
        ]],
        "distances": [[0.185]],
    }

    class MockCollection:
        def count(self):
            return 53

        def query(self, **kwargs):
            return mock_results

    monkeypatch.setattr("app.services.video_service._get_video_collection", lambda: MockCollection())
    fake_embedding = [0.01] * 768

    # 1. Standard question about hostels -> NO video card in response!
    cards_initial = generate_cards(
        user_message="Tell me about the hostel facilities and rooms",
        answer="SR University provides separate hostels with study spaces and Wi-Fi.",
        query_embedding=fake_embedding,
    )
    assert not any(c.get("type") == "video_recommendations" for c in cards_initial)

    # 2. Confirmed affirmative response -> Video card is attached in separate response!
    cards_confirmed = generate_cards(
        user_message="yes",
        answer="Here is the official video tour of our Hostels & Living:",
        query_embedding=fake_embedding,
        is_video_confirmed=True,
    )
    assert any(c.get("type") == "video_recommendations" for c in cards_confirmed)

    # 3. Explicit video ask from the start -> Video card is attached directly!
    cards_explicit = generate_cards(
        user_message="Show me a video tour of the campus",
        answer="Here is our official campus tour walkthrough.",
        query_embedding=fake_embedding,
    )
    assert any(c.get("type") == "video_recommendations" for c in cards_explicit)


def test_format_video_offer_prompt():
    """Verify clean video offer formatting using matched category name."""
    ans = "SR University offers hostel facilities.\n\nWould you like more info?"
    formatted = format_video_offer_prompt(ans, "Hostels & Living")
    assert "Would you like to watch a short video tour of Hostels & Living? (Yes / No)" in formatted
    assert "Would you like more info?" not in formatted
