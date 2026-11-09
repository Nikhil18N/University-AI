"""Tests for shadow re-embedding script (T11)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from scripts.shadow_reembed_text_embedding_004 import shadow_reembed


@pytest.mark.asyncio
async def test_shadow_reembed_dry_run():
    """Dry-run must count chunks and return without making external API calls."""
    res = await shadow_reembed(execute=False)
    assert res["facts"] == 95
    assert res["highlights"] == 67


@pytest.mark.asyncio
async def test_shadow_reembed_mock_execution():
    """Execution with mocked embedder must create target collections with 768 dims."""
    mock_embedder = MagicMock()
    mock_embedder.embed = AsyncMock(return_value=[[0.1] * 768, [0.2] * 768])
    mock_embedder.close = AsyncMock()

    with patch("scripts.shadow_reembed_text_embedding_004.GeminiEmbeddingProvider", return_value=mock_embedder):
        with patch("scripts.shadow_reembed_text_embedding_004.get_chroma_client") as mock_client_factory:
            mock_client = MagicMock()
            mock_source = MagicMock()
            mock_source.count.return_value = 2
            mock_source.get.return_value = {
                "ids": ["id1", "id2"],
                "documents": ["doc1", "doc2"],
                "metadatas": [{"title": "t1"}, {"title": "t2"}],
            }
            mock_target = MagicMock()
            mock_target.count.return_value = 2

            mock_client.get_collection.return_value = mock_source
            mock_client.get_or_create_collection.return_value = mock_target
            mock_client_factory.return_value = mock_client

            res = await shadow_reembed(execute=True, batch_size=2)
            assert res["facts"] == 2
            assert res["highlights"] == 2
            assert mock_target.add.called

