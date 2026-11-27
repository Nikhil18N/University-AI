"""Lightweight Redis-backed (with in-memory fallback) async background job queue for heavy admin tasks."""

import asyncio
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_JOB_TTL_SECONDS = 86400
_MAX_LOCAL_JOBS = 200
_LOCAL_JOBS: dict[str, dict[str, Any]] = {}
_ACTIVE_TASKS: dict[str, asyncio.Task] = {}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redis_key(job_id: str) -> str:
    return f"sru:job:{job_id}"


async def _persist_job(record: dict[str, Any]) -> None:
    if len(_LOCAL_JOBS) >= _MAX_LOCAL_JOBS and record["job_id"] not in _LOCAL_JOBS:
        oldest_key = next(iter(_LOCAL_JOBS))
        _LOCAL_JOBS.pop(oldest_key, None)
    _LOCAL_JOBS[record["job_id"]] = dict(record)

    try:
        from app.sru_agent import memory as agent_memory
        r = agent_memory.get_redis()
        if r is not None:
            await r.set(_redis_key(record["job_id"]), json.dumps(record, default=str), ex=_JOB_TTL_SECONDS)
    except Exception as err:
        logger.debug("Redis job persist skipped (%s): %s", record["job_id"], err)


async def get_job(job_id: str) -> dict[str, Any] | None:
    """Return job status dict by ID from local memory or Redis."""
    if job_id in _LOCAL_JOBS:
        return dict(_LOCAL_JOBS[job_id])
    try:
        from app.sru_agent import memory as agent_memory
        r = agent_memory.get_redis()
        if r is not None:
            raw = await r.get(_redis_key(job_id))
            if raw:
                data = json.loads(raw)
                _LOCAL_JOBS[job_id] = data
                return dict(data)
    except Exception as err:
        logger.debug("Redis job read skipped (%s): %s", job_id, err)
    return None


async def list_jobs(limit: int = 20) -> list[dict[str, Any]]:
    """Return recent background jobs ordered newest-first (merging Redis across workers if available)."""
    merged: dict[str, dict[str, Any]] = {k: dict(v) for k, v in _LOCAL_JOBS.items()}
    try:
        from app.sru_agent import memory as agent_memory
        r = agent_memory.get_redis()
        if r is not None:
            keys = [k async for k in r.scan_iter(match="sru:job:*", count=100)]
            if keys:
                raw_values = await r.mget(keys[:200])
                for raw in raw_values:
                    if not raw:
                        continue
                    data = json.loads(raw)
                    jid = data.get("job_id")
                    if jid and jid not in merged:
                        merged[jid] = data
    except Exception as err:
        logger.debug("Redis job list skipped: %s", err)

    items = list(merged.values())
    items.sort(key=lambda j: j.get("created_at", ""), reverse=True)
    return [dict(item) for item in items[:limit]]


async def enqueue_job(job_type: str, runner: Callable[[], Awaitable[Any]]) -> dict[str, Any]:
    """Schedule an async background job and return its initial queued record."""
    job_id = str(uuid.uuid4())
    record: dict[str, Any] = {
        "job_id": job_id,
        "job_type": job_type,
        "status": "queued",
        "created_at": _utc_now_iso(),
        "started_at": None,
        "finished_at": None,
        "result": None,
        "error": None,
    }
    await _persist_job(record)

    async def _run() -> None:
        record["status"] = "running"
        record["started_at"] = _utc_now_iso()
        await _persist_job(record)
        try:
            result = await runner()
            record["status"] = "completed"
            record["result"] = result if isinstance(result, (dict, list, str, int, float, bool, type(None))) else str(result)
        except Exception as exc:
            logger.error("Background job %s (%s) failed: %s", job_id, job_type, exc, exc_info=True)
            record["status"] = "failed"
            record["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            record["finished_at"] = _utc_now_iso()
            await _persist_job(record)
            _ACTIVE_TASKS.pop(job_id, None)

    task = asyncio.create_task(_run(), name=f"job:{job_type}:{job_id}")
    _ACTIVE_TASKS[job_id] = task
    return dict(record)


async def wait_for_job(job_id: str, timeout: float = 5.0) -> dict[str, Any] | None:
    """Await an active background task (useful in tests) and return its final record."""
    task = _ACTIVE_TASKS.get(job_id)
    if task is not None:
        await asyncio.wait_for(task, timeout=timeout)
    return await get_job(job_id)
