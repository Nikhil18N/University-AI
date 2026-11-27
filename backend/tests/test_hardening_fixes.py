"""Tests for faculty withdrawal guard, X-Session-Id header support, and production Redis warning."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app import security
from app.config import settings
from app.main import app
from app.sru_agent import answer_check


def test_guard_faculty_withdrawal_preserves_verified_directory_role():
    history = [
        {"role": "user", "text": "What role does Dr. Rupesh Mishra hold?"},
        {
            "role": "assistant",
            "text": "Dr. Rupesh Mishra is Associate Professor and Director of Centre for Experiential Learning in Computer Science & Artificial Intelligence.",
        },
    ]
    with patch(
        "app.sru_agent.faculty.search",
        return_value={
            "status": "ok",
            "matches": [
                {
                    "name": "Dr. Rupesh Mishra",
                    "designation": "Associate Professor and Director of Centre for Experiential Learning",
                    "department": "Computer Science & Artificial Intelligence",
                }
            ],
        },
    ):
        updated, problems = answer_check.guard_faculty_withdrawal(
            "My apologies, Dr. Rupesh Mishra is only listed as Boys Hostel Warden and not the Director.",
            history=history,
        )
    assert problems
    assert "Associate Professor and Director of Centre for Experiential Learning" in updated


def test_guard_faculty_withdrawal_ignores_normal_turns():
    updated, problems = answer_check.guard_faculty_withdrawal(
        "SR University offers B.Tech CSE with 4-year duration.",
        history=[{"role": "assistant", "text": "SR University is in Warangal."}],
    )
    assert problems == []
    assert updated == "SR University offers B.Tech CSE with 4-year duration."


@pytest.mark.asyncio
async def test_x_session_id_header_accepted_on_conversations_and_memory():
    sid = "test-session-header-0001"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        missing = await client.get("/api/v1/conversations")
        assert missing.status_code == 422

        with patch(
            "app.services.conversation_service.list_conversations",
            new=AsyncMock(return_value=[]),
        ) as mock_list:
            resp = await client.get(
                "/api/v1/conversations",
                headers={"X-Session-Id": sid},
            )
            assert resp.status_code == 200
            assert resp.json() == []
            mock_list.assert_awaited_once()


def test_production_startup_warns_when_redis_url_missing(monkeypatch):
    monkeypatch.setattr(security, "is_production", lambda: True)
    monkeypatch.setattr(settings, "REDIS_URL", "")
    warnings = security.startup_warnings()
    assert any("REDIS_URL" in w for w in warnings)


def test_agent_fail_fast_timeout_and_retry_defaults():
    from app.sru_agent import config as agent_config

    assert agent_config.AGENT_CALL_TIMEOUT <= 12
    assert agent_config.AGENT_TOTAL_TIMEOUT <= 25
    assert sum(agent_config.AGENT_RETRY_DELAYS) <= 2.5
