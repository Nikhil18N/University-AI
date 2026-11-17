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
    _sweep()


_writes = 0


def _sweep(every: int = 500):
    """Without Redis the server keeps chats in its own memory; drop the expired ones now and then
    so a long-running server does not slowly fill up."""
    global _writes
    _writes += 1
    if _writes % every:
        return
    now = time.time()
    for key in [k for k, item in _local.items() if item[0] < now]:
        _local.pop(key, None)


async def get_profile(session_id: str) -> dict:
    return await _get(f"sru:profile:{session_id}", {})


async def update_profile(session_id: str, **fields) -> dict:
    profile = await get_profile(session_id)
    profile.update({k: v for k, v in fields.items() if v not in (None, "")})
    await _set(f"sru:profile:{session_id}", profile)
    return profile


def _history_key(session_id: str, conversation_id: str | None = None) -> str:
    if conversation_id:
        return f"sru:history:{session_id}:{conversation_id}"
    return f"sru:history:{session_id}"


def _state_key(session_id: str, conversation_id: str | None = None) -> str:
    if conversation_id:
        return f"sru:state:{session_id}:{conversation_id}"
    return f"sru:state:{session_id}"


async def get_history(session_id: str, conversation_id: str | None = None) -> list:
    """Retrieve history for the specific active conversation."""
    return await _get(_history_key(session_id, conversation_id), [])


async def append_history(session_id: str, user_text: str, agent_text: str, conversation_id: str | None = None):
    """Append history strictly scoped to the active conversation."""
    history = await get_history(session_id, conversation_id)
    history += [{"role": "user", "text": user_text}, {"role": "model", "text": agent_text}]
    await _set(_history_key(session_id, conversation_id), history[-MAX_HISTORY:])


async def get_conversation_state(session_id: str, conversation_id: str | None = None) -> dict:
    """Retrieve structured conversation state (e.g., pending_visit_date, awaiting_date_confirmation)."""
    return await _get(_state_key(session_id, conversation_id), {})


async def update_conversation_state(session_id: str, conversation_id: str | None = None, **fields) -> dict:
    """Update structured conversation state."""
    state = await get_conversation_state(session_id, conversation_id)
    state.update(fields)
    await _set(_state_key(session_id, conversation_id), state)
    return state


async def clear_conversation_state(session_id: str, conversation_id: str | None = None):
    """Clear structured conversation state."""
    key = _state_key(session_id, conversation_id)
    r = _client()
    if r:
        try:
            await r.delete(key)
        except Exception:
            pass
    _local.pop(key, None)


async def allow_request(session_id: str, limit: int | None = None) -> bool:
    """Simple rate limit: N messages per minute per student (or per `limit` when given)."""
    limit = limit or config.AGENT_RATE_LIMIT_PER_MIN
    key = f"sru:rate:{session_id}:{int(time.time() // 60)}"
    r = _client()
    if r:
        try:
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, 90)
            return count <= limit
        except Exception:
            pass
    item = _local.get(key)
    count = (item[1] if item else 0) + 1
    _local[key] = (time.time() + 90, count)
    _sweep()
    return count <= limit


async def remove_profile_keys(session_id: str, *keys) -> dict:
    """Forget specific facts about a student (update_profile only ever adds)."""
    profile = await get_profile(session_id)
    for key in keys:
        profile.pop(key, None)
    await _set(f"sru:profile:{session_id}", profile)
    return profile
