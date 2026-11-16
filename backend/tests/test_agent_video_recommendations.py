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
    assert vid_card["videos"][0]["id"] == "campus-vid-1"
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
    assert len(result["videos"]) == 1
    assert result["videos"][0]["id"] == "hostel-vid-1"
