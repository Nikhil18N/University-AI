"""Tests for the university video recommendation service (Contrastive Bi-Encoder via Ollama)."""

import pytest
from app.services.video_service import (
    load_videos,
    get_relevant_videos,
    create_video_card,
    get_media_catalog_for_prompt,
    get_video_by_id,
    get_media_by_ids,
    extract_media_tags,
    get_recommender,
)


def test_load_videos():
    """Verify videos load correctly from university_videos.json with YouTube & Instagram support."""
    videos = load_videos()
    assert isinstance(videos, list)
    assert len(videos) >= 4
    for v in videos:
        assert "id" in v
        assert "title" in v
        assert "url" in v
        assert "thumbnail_url" in v
        # Bi-Encoder schema: positive_intents replace keywords
        assert "positive_intents" in v
        assert isinstance(v["positive_intents"], list)
        assert len(v["positive_intents"]) >= 2
        assert "youtube.com" in v["url"] or "instagram.com" in v["url"]
        assert (
            "i.ytimg.com/vi/" in v["thumbnail_url"]
            or "img.youtube.com/vi/" in v["thumbnail_url"]
            or "unsplash.com" in v["thumbnail_url"]
        )


def test_media_catalog_and_lookup():
    """Verify dynamic prompt catalog generation and ID-based lookup."""
    catalog = get_media_catalog_for_prompt()
    assert "[MEDIA:" in catalog
    assert "9kYIkkadZkU" in catalog

    video = get_video_by_id("9kYIkkadZkU")
    assert video is not None
    assert video["id"] == "9kYIkkadZkU"

    media_list = get_media_by_ids(["9kYIkkadZkU", "sru_fest_reel_1"])
    assert len(media_list) == 2


def test_extract_media_tags():
    """Verify [MEDIA: ...] tag extraction and clean text stripping."""
    text_with_tag = "Here is our vibrant campus!\n\nWould you like a tour?\n[MEDIA: 9kYIkkadZkU]"
    cleaned, media_ids = extract_media_tags(text_with_tag)
    assert media_ids == ["9kYIkkadZkU"]
    assert "[MEDIA:" not in cleaned
    assert "Would you like a tour?" in cleaned

    # Multiple comma-separated IDs
    multi_text = "Check these out!\n[MEDIA: 9kYIkkadZkU, yYgB3h4wkug]"
    cleaned2, media_ids2 = extract_media_tags(multi_text)
    assert media_ids2 == ["9kYIkkadZkU", "yYgB3h4wkug"]
    assert "[MEDIA:" not in cleaned2

    # No tag
    plain_text = "Minimum attendance required is 75%."
    cleaned3, media_ids3 = extract_media_tags(plain_text)
    assert media_ids3 == []
    assert cleaned3 == plain_text


def test_recommender_singleton():
    """Verify get_recommender() returns the same singleton instance."""
    r1 = get_recommender()
    r2 = get_recommender()
    assert r1 is r2


def test_create_video_card():
    """Verify card formatting conforms to UI requirements."""
    videos = load_videos()[:2]
    card = create_video_card(videos, is_explicit=True)

    assert card["type"] == "video_recommendations"
    assert "channel_url" in card
    assert "channel_name" in card
    assert len(card["videos"]) == 2


def test_create_video_card_instagram():
    """Verify Instagram-only card uses correct defaults."""
    ig_video = next(
        (v for v in load_videos() if v.get("platform") == "instagram"), None
    )
    if ig_video is None:
        pytest.skip("No Instagram video in catalog")

    card = create_video_card([ig_video], is_explicit=True)
    assert card["type"] == "video_recommendations"
    assert "instagram" in card["channel_url"].lower() or "@" in card["channel_name"]


# ---------------------------------------------------------------------------
# Semantic recommender tests (require Ollama running at localhost:11434)
# These are marked with a custom marker so they can be skipped when Ollama
# is not available: pytest -m "not ollama"
# ---------------------------------------------------------------------------

def _ollama_available() -> bool:
    """Check if Ollama embed endpoint is reachable."""
    try:
        import httpx
        r = httpx.get("http://localhost:11434/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


requires_ollama = pytest.mark.skipif(
    not _ollama_available(),
    reason="Ollama not reachable at localhost:11434",
)


@requires_ollama
def test_blacklist_queries_return_no_videos():
    """Verify ragging, policy, and timings queries never return video cards."""
    # Ragging: negative intent should veto
    assert (
        get_relevant_videos("how is ragging in our college campus") == []
    ), "Ragging query must never produce a video card"

    # Mess timings: unrelated to any positive visual intent
    assert (
        get_relevant_videos("hostel mess timings") == []
    ), "Mess timings query must never produce a video card"

    # Attendance policy
    assert (
        get_relevant_videos("What is the minimum attendance percentage required?") == []
    ), "Attendance query must never produce a video card"

    # Condonation
    assert (
        get_relevant_videos("What is the condonation fee for attendance shortage?") == []
    ), "Condonation query must never produce a video card"


@requires_ollama
def test_visual_queries_return_campus_video():
    """Verify visual/exploratory campus queries return the campus tour video."""
    for query in [
        "tell me how campus looks",
        "give me how campus looks like",
        "show me the campus",
    ]:
        videos = get_relevant_videos(query)
        assert len(videos) > 0, f"Expected campus video for query: {query!r}"
        ids = [v["id"] for v in videos]
        assert "9kYIkkadZkU" in ids, f"Expected campus tour video for query: {query!r}"


@requires_ollama
def test_hostel_video_query_returns_hostel_video():
    """Verify hostel room visual queries return the hostel journey video."""
    videos = get_relevant_videos("show me hostel room video")
    assert len(videos) > 0, "Expected hostel video card"
    assert any("hostel" in v["category"].lower() for v in videos)


@requires_ollama
def test_empty_query_returns_no_videos():
    """Empty or whitespace queries must return []."""
    assert get_relevant_videos("") == []
    assert get_relevant_videos("   ") == []
