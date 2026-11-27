"""Unit and API tests for the async admin background job queue."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.services import job_queue


@pytest.mark.asyncio
async def test_job_queue_completes_and_records_result():
    async def _work():
        return {"passed": 10, "failed": 0}

    queued = await job_queue.enqueue_job("evaluation_suite", _work)
    assert queued["status"] == "queued"

    done = await job_queue.wait_for_job(queued["job_id"])
    assert done is not None
    assert done["status"] == "completed"
    assert done["result"] == {"passed": 10, "failed": 0}
    assert done["error"] is None
    assert done["started_at"] is not None
    assert done["finished_at"] is not None


@pytest.mark.asyncio
async def test_job_queue_records_failure_without_crashing():
    async def _boom():
        raise RuntimeError("index unavailable")

    queued = await job_queue.enqueue_job("document_ingestion", _boom)
    done = await job_queue.wait_for_job(queued["job_id"])
    assert done is not None
    assert done["status"] == "failed"
    assert "RuntimeError: index unavailable" in (done["error"] or "")


@pytest.mark.asyncio
async def test_admin_jobs_endpoints_require_key_and_enqueue_eval():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        missing = await client.post("/api/v1/admin/jobs/evaluations")
        assert missing.status_code == 422
        unauth = await client.post(
            "/api/v1/admin/jobs/evaluations",
            headers={"X-Admin-Key": "wrong-key"},
        )
        assert unauth.status_code == 403

        fake_session_ctx = MagicMock()
        fake_session_ctx.__aenter__ = AsyncMock(return_value=MagicMock())
        fake_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.db.session.async_session_factory", return_value=fake_session_ctx),
            patch(
                "app.services.evaluation_service.run_benchmark_suite",
                new=AsyncMock(return_value={"total": 5, "passed": 5}),
            ),
        ):
            resp = await client.post(
                "/api/v1/admin/jobs/evaluations",
                headers={"X-Admin-Key": settings.ADMIN_API_KEY},
            )
            assert resp.status_code == 202
            body = resp.json()
            assert body["job_type"] == "evaluation_suite"
            assert body["status"] == "queued"

            done = await job_queue.wait_for_job(body["job_id"])
            assert done is not None and done["status"] == "completed"

            status_resp = await client.get(
                f"/api/v1/admin/jobs/{body['job_id']}",
                headers={"X-Admin-Key": settings.ADMIN_API_KEY},
            )
            assert status_resp.status_code == 200
            assert status_resp.json()["result"] == {"total": 5, "passed": 5}

            list_resp = await client.get(
                "/api/v1/admin/jobs",
                headers={"X-Admin-Key": settings.ADMIN_API_KEY},
            )
            assert list_resp.status_code == 200
            assert any(item["job_id"] == body["job_id"] for item in list_resp.json()["items"])


@pytest.mark.asyncio
async def test_admin_job_not_found_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/admin/jobs/nonexistent-job-id",
            headers={"X-Admin-Key": settings.ADMIN_API_KEY},
        )
        assert resp.status_code == 404
