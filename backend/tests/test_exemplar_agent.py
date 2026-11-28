"""Tests for wiring verified exemplars into sru_agent."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.sru_agent.agent import _lookup_exemplar_block
from app.sru_agent.prompt import build_dynamic_suffix


def test_build_dynamic_suffix_includes_exemplar_block():
    suffix = build_dynamic_suffix(
        exemplar_block="APPROVED EXEMPLAR ANSWER:\nQ: Why SRU?\nA: SRU is top-ranked."
    )
    assert "APPROVED EXEMPLAR ANSWER" in suffix
    assert "SRU is top-ranked." in suffix


@pytest.mark.asyncio
async def test_lookup_exemplar_block_returns_match():
    fake_svc = MagicMock()
    fake_svc._exemplar_count = 1
    fake_svc.find_matching_exemplar = AsyncMock(
        return_value={"question": "Why SRU?", "answer": "Approved VC response."}
    )
    with patch("app.api.v1.deps.get_embedding_provider", return_value=MagicMock()), \
         patch("app.services.exemplar_service.ExemplarService", return_value=fake_svc):
        block = await _lookup_exemplar_block("Why should I choose SRU?")
    assert "APPROVED EXEMPLAR ANSWER" in block
    assert "Approved VC response." in block


@pytest.mark.asyncio
async def test_lookup_exemplar_block_skips_when_empty():
    fake_svc = MagicMock()
    fake_svc._exemplar_count = 0
    fake_svc.find_matching_exemplar = AsyncMock()
    with patch("app.api.v1.deps.get_embedding_provider", return_value=MagicMock()), \
         patch("app.services.exemplar_service.ExemplarService", return_value=fake_svc):
        block = await _lookup_exemplar_block("Why should I choose SRU?")
    assert block == ""
    fake_svc.find_matching_exemplar.assert_not_awaited()
