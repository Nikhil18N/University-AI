from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1 import memory as memory_api
from app.main import app


@pytest.mark.asyncio
async def test_pending_tasks_endpoint_returns_owned_tasks(monkeypatch):
    conversation_id = uuid4()
    task = type(
        "Task",
        (),
        {
            "conversation_id": conversation_id,
            "task_type": "finance_estimate",
            "original_query": "Calculate my fee",
            "missing_inputs": ["program"],
            "status": "pending",
            "updated_at": datetime.now(timezone.utc),
        },
    )()

    async def fake_list_pending_tasks(db, session_id):
        assert session_id == "browser-session"
        return [task]

    monkeypatch.setattr(memory_api, "list_pending_tasks", fake_list_pending_tasks)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/memory/pending-tasks",
            params={"session_id": "browser-session"},
        )

    assert response.status_code == 200
    assert response.json()[0]["conversation_id"] == str(conversation_id)
    assert response.json()[0]["missing_inputs"] == ["program"]


@pytest.mark.asyncio
async def test_pending_task_cancel_endpoint_enforces_not_found(monkeypatch):
    conversation_id = uuid4()

    async def fake_cancel_pending_task(db, requested_conversation_id, session_id):
        assert requested_conversation_id == conversation_id
        assert session_id == "browser-session"
        return False

    monkeypatch.setattr(memory_api, "cancel_pending_task", fake_cancel_pending_task)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete(
            f"/api/v1/memory/pending-tasks/{conversation_id}",
            params={"session_id": "browser-session"},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Pending task not found"
