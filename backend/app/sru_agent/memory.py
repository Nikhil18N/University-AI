"""Remembers each student (profile + recent messages) between messages.

Uses Redis when REDIS_URL is set, otherwise the server's own memory
(fine for one server process; use Redis in production).
"""
import json
import time

from . import config

TTL_SECONDS = 24 * 3600
MAX_HISTORY = 12  # messages kept per student

_local: dict = {}
_redis = None


def _client():
    global _redis
    if _redis is None and config.REDIS_URL:
        import redis.asyncio as redis  # imported only when needed
        _redis = redis.from_url(config.REDIS_URL, decode_responses=True)
    return _redis


async def _get(key, default):
    r = _client()
    if r:
        try:
            raw = await r.get(key)
            return json.loads(raw) if raw else default
        except Exception:
            pass
    item = _local.get(key)
    if not item or item[0] < time.time():
        return default
    return item[1]


async def _set(key, value):
    r = _client()
    if r:
        try:
            await r.set(key, json.dumps(value, ensure_ascii=False), ex=TTL_SECONDS)
            return
        except Exception:
            pass
    _local[key] = (time.time() + TTL_SECONDS, value)


async def get_profile(session_id: str) -> dict:
    return await _get(f"sru:profile:{session_id}", {})


async def update_profile(session_id: str, **fields) -> dict:
    profile = await get_profile(session_id)
    profile.update({k: v for k, v in fields.items() if v not in (None, "")})
    await _set(f"sru:profile:{session_id}", profile)
    return profile


async def get_history(session_id: str) -> list:
    return await _get(f"sru:history:{session_id}", [])


async def append_history(session_id: str, user_text: str, agent_text: str):
    history = await get_history(session_id)
    history += [{"role": "user", "text": user_text}, {"role": "model", "text": agent_text}]
    await _set(f"sru:history:{session_id}", history[-MAX_HISTORY:])


async def allow_request(session_id: str) -> bool:
    """Simple rate limit: N messages per minute per student."""
    key = f"sru:rate:{session_id}:{int(time.time() // 60)}"
    r = _client()
    if r:
        try:
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, 90)
            return count <= config.AGENT_RATE_LIMIT_PER_MIN
        except Exception:
            pass
    item = _local.get(key)
    count = (item[1] if item else 0) + 1
    _local[key] = (time.time() + 90, count)
    return count <= config.AGENT_RATE_LIMIT_PER_MIN
