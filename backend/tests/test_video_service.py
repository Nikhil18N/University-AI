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
    has_recent_video_offer,
    is_explicit_video_query,
    is_video_topic_query,
    should_retrieve_video_matches,
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


def test_video_retrieval_is_not_enabled_for_ordinary_questions():
    assert is_explicit_video_query("What are the hostel fees?") is False
    assert is_explicit_video_query("How does attendance work?") is False
    assert is_video_topic_query("What are the hostel fees?") is False
    assert is_video_topic_query("Tell me about the sports clubs") is True
    assert is_video_topic_query("Show me a video of the library") is True
    assert should_retrieve_video_matches(
        "What are the hostel fees?",
        "UNIVERSITY",
        [],
        contextual_offer_allowed=False,
    ) is False


@pytest.mark.parametrize(
    "query",
    [
        "Show me a video of the university campus",
        "Show me a hostel tour video",
        "Show me placement videos",
        "Show me sports and clubs videos",
        "Show me startup and incubation videos",
        "Show me cultural event videos",
        "Show me a library video",
    ],
)
def test_video_topic_policy_allows_approved_topics(query):
    assert is_video_topic_query(query) is True
    assert should_retrieve_video_matches(
        query,
        "UNIVERSITY",
        [],
        contextual_offer_allowed=False,
    ) is True


@pytest.mark.parametrize(
    "query",
    [
        "Show me a video about fees",
        "Show me scholarship videos",
        "Show me admission videos",
        "Show me an attendance video",
        "Show me exam videos",
        "Show me syllabus videos",
        "Show me transport videos",
        "Show me the application video",
    ],
)
def test_video_topic_policy_blocks_excluded_topics(query):
    assert is_video_topic_query(query) is False
    assert should_retrieve_video_matches(
        query,
        "UNIVERSITY",
        [],
        contextual_offer_allowed=False,
    ) is False


def test_contextual_video_offer_has_a_cooldown():
    recent = [
        {
            "role": "assistant",
            "content": "Would you like to watch a short video tour of Campus Life? (Yes / No)",
            "metadata": {"video_offer": True, "cards": []},
        }
    ]
    assert has_recent_video_offer(recent) is True
    assert should_retrieve_video_matches(
        "Tell me about campus life",
        "UNIVERSITY",
        recent,
        contextual_offer_allowed=True,
    ) is False


def test_contextual_video_offer_cooldown_covers_longer_conversations():
    recent = [
        {"role": "assistant", "content": "Earlier answer", "metadata": {}}
        for _ in range(19)
    ]
    recent.insert(
        0,
        {
            "role": "assistant",
            "content": "Would you like to watch a video?",
            "metadata": {"video_offer": True},
        },
    )
    assert has_recent_video_offer(recent) is True


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


def test_cards_displayed_directly_for_visual_queries(monkeypatch):
    """Verify video cards are displayed directly for visual/facility queries without requiring explicit confirmation."""
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

    # 1. Visual/facilities question about hostels -> Video card is directly attached!
    cards_hostel = generate_cards(
        user_message="Tell me about the hostel facilities and rooms",
        answer="SR University provides separate hostels with study spaces and Wi-Fi.",
        query_embedding=fake_embedding,
    )
    assert any(c.get("type") == "video_recommendations" for c in cards_hostel)

    # 2. Purely transactional/numerical fee question -> NO video card attached!
    cards_fee = generate_cards(
        user_message="What is the tuition fee for B.Tech CSE?",
        answer="The tuition fee is ₹3,40,000 per year.",
        query_embedding=fake_embedding,
    )
    assert not any(c.get("type") == "video_recommendations" for c in cards_fee)

    # 3. Explicit video ask -> Video card is attached directly!
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


def test_format_video_offer_prompt_replaces_mismatched_category():
    """Verify format_video_offer_prompt replaces a stale or mismatched category with the correct one."""
    ans = (
        "SR University maintains an impressive placement record with an average package of 6 LPA, "
        "while the highest package reached 51 LPA through an offer from Microsoft.\n\n"
        "Would you like to watch a short video tour of Hostel Life & Amenities? (Yes / No)\n\n"
        "> ⚠️ *May contain inaccuracies. Verify with official university sources.*"
    )
    formatted = format_video_offer_prompt(ans, "Placements & Careers")
    assert "Would you like to watch a short video tour of Placements & Careers? (Yes / No)" in formatted
    assert "Hostel Life & Amenities" not in formatted
    assert formatted.endswith("> ⚠️ *May contain inaccuracies. Verify with official university sources.*")


def test_sanitize_answer_video_prompts():
    """Verify sanitize_answer_video_prompts removes hallucinated video prompts when no video is matched."""
    from app.services.video_service import sanitize_answer_video_prompts

    ans = (
        "Here are the transport details.\n\n"
        "Would you like to watch a short video tour of Transport? (Yes / No)\n\n"
        "> ⚠️ *May contain inaccuracies. Verify with official university sources.*"
    )
    sanitized = sanitize_answer_video_prompts(ans)
    assert "Would you like to watch a short video tour" not in sanitized
    assert "Here are the transport details." in sanitized
    assert "> ⚠️ *May contain inaccuracies. Verify with official university sources.*" in sanitized


def test_extended_affirmative_and_negative_detection():
    """Verify natural-language affirmative and negative responses are correctly recognized."""
    recent_offered = [
        {"role": "user", "content": "Tell me about the hostel rooms."},
        {
            "role": "assistant",
            "content": "Our hostels offer AC and non-AC rooms.\n\nWould you like to watch a short video tour of Hostels & Living? (Yes / No)",
            "metadata": {"suggestions": ["🎥 Yes, watch video", "❌ No, thanks"]},
        },
    ]

    affirmative_samples = [
        "go ahead",
        "sounds good",
        "show me the video",
        "i want to watch",
        "why not",
        "definitely",
        "absolutely",
        "let's watch",
        "show it",
    ]
    for sample in affirmative_samples:
        is_yes, is_no = check_video_affirmative_or_negative(sample, recent_offered)
        assert is_yes is True, f"Expected affirmative for '{sample}'"
        assert is_no is False

    negative_samples = [
        "not interested",
        "i'm good",
        "no need",
        "pass",
        "that's fine",
        "not now",
        "skip",
    ]
    for sample in negative_samples:
        is_yes, is_no = check_video_affirmative_or_negative(sample, recent_offered)
        assert is_yes is False
        assert is_no is True, f"Expected negative for '{sample}'"


def test_is_explicit_video_query():
    """Verify explicit video intent detection across diverse user formulations."""
    from app.services.video_service import is_explicit_video_query

    assert is_explicit_video_query("show me a campus video") is True
    assert is_explicit_video_query("can I see the hostel rooms?") is True
    assert is_explicit_video_query("what does the campus look like?") is True
    assert is_explicit_video_query("drone view of the university") is True
    assert is_explicit_video_query("any youtube walkthrough?") is True
    assert is_explicit_video_query("what is the fee structure for B.Tech CSE?") is False
    assert is_explicit_video_query("how to apply for admission?") is False


def test_video_content_hash():
    """Verify video content hash detects modifications to video catalog metadata."""
    from app.services.video_service import _compute_videos_hash

    sample = [{"id": "vid1", "title": "Tour 1", "category": "Campus"}]
    hash1 = _compute_videos_hash(sample)
    assert isinstance(hash1, str) and len(hash1) == 64

    # Identical content -> identical hash
    assert _compute_videos_hash(sample) == hash1

    # Modified content -> different hash
    modified = [{"id": "vid1", "title": "Tour 1 Updated", "category": "Campus"}]
    hash2 = _compute_videos_hash(modified)
    assert hash1 != hash2


def test_category_diversity_in_semantic_retrieval(monkeypatch):
    """Verify semantic retrieval prioritizes diverse categories among top candidates."""
    mock_results = {
        "metadatas": [[
            {"id": "v1", "title": "Hostel Tour 1", "category": "Hostels & Living", "url": "https://yt/v1"},
            {"id": "v2", "title": "Hostel Tour 2", "category": "Hostels & Living", "url": "https://yt/v2"},
            {"id": "v3", "title": "Campus Greenery", "category": "Campus Tour & Infrastructure", "url": "https://yt/v3"},
        ]],
        "distances": [[0.15, 0.16, 0.17]],
    }

    class MockCollection:
        def count(self):
            return 3

        def query(self, **kwargs):
            return mock_results

    monkeypatch.setattr("app.services.video_service._get_video_collection", lambda: MockCollection())
    results = get_semantic_videos(query_embedding=[0.01] * 768, limit=2, max_distance=0.25)

    assert len(results) == 2
    # Verify diverse categories are returned (one Hostel, one Campus)
    categories = [r["category"] for r in results]
    assert "Hostels & Living" in categories
    assert "Campus Tour & Infrastructure" in categories


def test_should_offer_video_tour():
    """Verify should_offer_video_tour allows campus/facility queries and blocks purely transactional queries."""
    from app.services.chat_service import should_offer_video_tour

    assert should_offer_video_tour("tell me about the hostel rooms") is True
    assert should_offer_video_tour("how is campus life at SRU?") is True
    assert should_offer_video_tour("show me the sports grounds") is True
    assert should_offer_video_tour("what does the campus look like?") is True

    # Blocked transactional/numerical queries
    assert should_offer_video_tour("what is the B.Tech CSE tuition fee?") is False
    assert should_offer_video_tour("what is the cutoff percentage for scholarships?") is False
    assert should_offer_video_tour("what are the exam attendance rules?") is False

