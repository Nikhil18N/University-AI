"""Tests for agent video recommendations and university video tool."""

import pytest
from app.sru_agent import agent, tools
from tests.test_agent_loop import FakeClient, _text, _call


@pytest.mark.asyncio
async def test_agent_video_recommendations_contextual_card(monkeypatch):
    """Verify that asking about campus in run_agent produces video_recommendations card."""
    fake_embedding = [0.01] * 3072

    class FakeEmbeddingProvider:
        async def embed_single(self, text: str):
            return fake_embedding

    monkeypatch.setattr("app.api.v1.deps.get_embedding_provider", lambda: FakeEmbeddingProvider())

    # Mock video collection
    mock_results = {
        "metadatas": [[
            {
                "id": "campus-vid-1",
                "platform": "youtube",
                "title": "SR University Campus Tour 2026",
                "category": "Campus Tour & Infrastructure",
                "url": "https://www.youtube.com/watch?v=campus-vid-1",
                "thumbnail_url": "https://i.ytimg.com/vi/campus-vid-1/hqdefault.jpg",
                "type": "video",
                "channel_name": "SR University Official",
                "channel_url": "https://www.youtube.com/@SRUniversity/videos",
            }
        ]],
        "distances": [[0.15]],
    }

    class MockCollection:
        def count(self):
            return 10

        def query(self, **kwargs):
            return mock_results

    monkeypatch.setattr("app.services.video_service._get_video_collection", lambda: MockCollection())

    client = FakeClient([_text("Here is information about our lush green 150-acre campus.")])
    events = [e async for e in agent.run_agent("Tell me about the campus and facilities", "s-vid-test", client=client)]
    
    done = [e for e in events if e["type"] == "done"][0]
    cards = done.get("cards", [])
    card_types = [c.get("type") for c in cards]
    
    assert "video_recommendations" in card_types
    vid_card = next(c for c in cards if c.get("type") == "video_recommendations")
    assert len(vid_card["videos"]) >= 1
    # The agent now picks videos by their own category / keywords (no embedding call), from the
    # real catalogue: a campus question must get campus-tour videos.
    assert all("Campus Tour" in v["category"] for v in vid_card["videos"])
    assert len(done.get("suggestions", [])) > 0


@pytest.mark.asyncio
async def test_tool_get_university_videos(monkeypatch):
    """Verify tool_get_university_videos retrieves and formats video cards."""
    fake_embedding = [0.01] * 3072

    class FakeEmbeddingProvider:
        async def embed_single(self, text: str):
            return fake_embedding

    monkeypatch.setattr("app.api.v1.deps.get_embedding_provider", lambda: FakeEmbeddingProvider())

    mock_results = {
        "metadatas": [[
            {
                "id": "hostel-vid-1",
                "platform": "youtube",
                "title": "SR University Hostel Life",
                "category": "Hostels & Living",
                "url": "https://www.youtube.com/watch?v=hostel-vid-1",
                "thumbnail_url": "https://i.ytimg.com/vi/hostel-vid-1/hqdefault.jpg",
                "type": "video",
                "channel_name": "SR University Official",
                "channel_url": "https://www.youtube.com/@SRUniversity/videos",
            }
        ]],
        "distances": [[0.12]],
    }

    class MockCollection:
        def count(self):
            return 10

        def query(self, **kwargs):
            return mock_results

    monkeypatch.setattr("app.services.video_service._get_video_collection", lambda: MockCollection())

    result = await tools.tool_get_university_videos({"topic": "hostel life"}, {})
    assert result["status"] == "ok"
    assert result["type"] == "video_recommendations"
    # Videos are now matched on their own titles / keywords (no embedding call): every video
    # returned for "hostel life" must be a hostel video from the real catalogue.
    assert 1 <= len(result["videos"]) <= 2
    assert all("Hostel" in v["category"] for v in result["videos"])


def test_is_about_sru_or_campus_query_detection():
    """Verify is_about_sru_or_campus_query correctly discriminates generic SRU/campus queries from sub-topics."""
    from app.services.video_service import is_about_sru_or_campus_query

    assert is_about_sru_or_campus_query("tell me about sru") is True
    assert is_about_sru_or_campus_query("about sru") is True
    assert is_about_sru_or_campus_query("what is sru") is True
    assert is_about_sru_or_campus_query("about sr university") is True
    assert is_about_sru_or_campus_query("tell me about the campus") is True
    assert is_about_sru_or_campus_query("how is campus life") is True
    assert is_about_sru_or_campus_query("campus") is True

    # Hostels must NOT be treated as generic about-sru
    assert is_about_sru_or_campus_query("tell me about hostels") is False
    assert is_about_sru_or_campus_query("how is hostel life?") is False

    # Events/fests must NOT be treated as generic about-sru
    assert is_about_sru_or_campus_query("what fests happen at sru?") is False
    assert is_about_sru_or_campus_query("tell me about sparkrill") is False

    # Placements must NOT be treated as generic about-sru
    assert is_about_sru_or_campus_query("what are the placements like?") is False


def test_about_sru_video_filtering_prefers_campus_and_excludes_hostels_and_events(monkeypatch):
    """Verify get_relevant_videos on 'tell me about sru' filters out hostels and events and returns campus videos."""
    from app.services.video_service import get_relevant_videos

    mock_candidates = {
        "metadatas": [[
            {
                "id": "hostel-vid-1",
                "title": "Best Hostel Life in India? | SR University",
                "category": "Hostels & Living",
                "url": "https://www.youtube.com/watch?v=hostel-1",
            },
            {
                "id": "event-vid-1",
                "title": "SPARKILL 2026 Ramp Walk | SRU Fest",
                "category": "Campus Life & Fests",
                "url": "https://www.youtube.com/watch?v=event-1",
            },
            {
                "id": "campus-vid-1",
                "title": "SR University Campus Tour 2026",
                "category": "Campus Tour & Infrastructure",
                "url": "https://www.youtube.com/watch?v=campus-1",
            },
            {
                "id": "campus-vid-2",
                "title": "Beautiful Night View of SR University | Full Campus Tour",
                "category": "Campus Tour & Infrastructure",
                "url": "https://www.youtube.com/watch?v=campus-2",
            },
        ]],
        "distances": [[0.20, 0.21, 0.22, 0.23]],
    }

    class MockCollection:
        def count(self):
            return 4

        def query(self, **kwargs):
            return mock_candidates

    monkeypatch.setattr("app.services.video_service._get_video_collection", lambda: MockCollection())

    fake_embedding = [0.01] * 768
    vids = get_relevant_videos(
        user_message="Tell me about SRU",
        query_embedding=fake_embedding,
    )

    # Must return campus videos only, NO hostels and NO events
    assert len(vids) == 2
    for v in vids:
        assert v["category"] == "Campus Tour & Infrastructure"
        assert "hostel" not in v["title"].lower()
        assert "fest" not in v["title"].lower()
        assert "sparkill" not in v["title"].lower()


def test_international_categories_distinction():
    """Verify IEP is in International Programs while international student stories are in International Student Experience."""
    from app.services.video_service import load_videos

    videos = load_videos(force_reload=True)
    iep_video = next((v for v in videos if v["id"] == "QntEaaW5b34"), None)
    assert iep_video is not None
    assert iep_video["category"] == "International Programs"

    intl_students = [v for v in videos if v["id"] in ("xfQVXz_bBA4", "VF5FgBIuWKI", "JZpvKru8dFw")]
    assert len(intl_students) == 3
    for v in intl_students:
        assert v["category"] == "International Student Experience"

