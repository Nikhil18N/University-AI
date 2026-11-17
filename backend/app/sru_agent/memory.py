"""Remembers each student (profile + recent messages) between messages.

Uses Redis when REDIS_URL is set, otherwise the server's own memory
(fine for one server process; use Redis in production).
"""
import asyncio
import copy
import json
import logging
import time

from . import config

log = logging.getLogger("sru_agent")
TTL_SECONDS = 24 * 3600
MAX_HISTORY = 12  # messages kept per student

_local: dict = {}
_redis = None
_redis_loop = None

# ---- Speed: a copy in this server's own memory -------------------------------------------
# Every Redis or database trip from Render to a hosted Redis / PostgreSQL costs 50-150 ms, and a
# chat message used to make about 29 of them one after another (3-4 seconds before the first
# word, even for "hi"). The server runs ONE process (see backend/Dockerfile), so it keeps its own
# copy of each student's profile, chat context and conversation state: reads cost nothing, and
# Redis / the database are written in the background, in order, one write per key at a time.
# Set AGENT_LOCAL_CACHE=false if you ever run more than one server process (uvicorn --workers).
_hot: dict = {}            # key -> (expires_at, value)
_HOT_SECONDS = 1800
_HOT_MAX = 20000
_pending_writes: dict = {}  # key -> latest value still to be written to Redis
_flushing: dict = {}        # key -> the task writing it
_tasks: set = set()         # background tasks (kept so they are not garbage-collected)


def _client():
    global _redis, _redis_loop
    if config.REDIS_URL:
        try:
            import asyncio
            curr_loop = asyncio.get_running_loop()
        except RuntimeError:
            curr_loop = None
        if _redis is None or _redis_loop != curr_loop:
            import redis.asyncio as redis  # imported only when needed
            _redis = redis.from_url(config.REDIS_URL, decode_responses=True)
            _redis_loop = curr_loop
    return _redis


def _hot_get(key):
    if not config.AGENT_LOCAL_CACHE:
        return None
    item = _hot.get(key)
    if not item or item[0] < time.time():
        return None
    return copy.deepcopy(item[1])


def _hot_put(key, value):
    if not config.AGENT_LOCAL_CACHE:
        return
    if len(_hot) >= _HOT_MAX:  # forget the oldest quarter
        for k in sorted(_hot, key=lambda k: _hot[k][0])[: _HOT_MAX // 4]:
            _hot.pop(k, None)
    _hot[key] = (time.time() + _HOT_SECONDS, copy.deepcopy(value))


def in_background(coro, name: str = "write"):
    """Run a write after the student already has the answer. Errors are logged, never raised."""
    async def _guard():
        try:
            await coro
        except Exception as exc:  # the chat must never fail because a background write did
            log.warning("background %s failed: %s", name, exc)
    try:
        task = asyncio.get_running_loop().create_task(_guard())
    except RuntimeError:
        return None
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return task


async def flush():
    """Wait for every background write (tests, shutdown, and anything that reads the database
    straight after a write)."""
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)


async def _flush_key(key):
    r = _client()
    try:
        while key in _pending_writes:
            value = _pending_writes.pop(key)
            try:
                await r.set(key, json.dumps(value, ensure_ascii=False), ex=TTL_SECONDS)
            except Exception as exc:
                log.warning("redis write failed for %s: %s", key.split(":")[1], exc)
                _local[key] = (time.time() + TTL_SECONDS, value)
    finally:
        _flushing.pop(key, None)


async def _get(key, default):
    hot = _hot_get(key)
    if hot is not None:
        return hot
    r = _client()
    if r:
        try:
            raw = await r.get(key)
            value = json.loads(raw) if raw else None
            if value is not None:
                _hot_put(key, value)
                return value
            return default
        except Exception:
            pass
    item = _local.get(key)
    if not item or item[0] < time.time():
        return default
    return item[1]


async def _set(key, value):
    _hot_put(key, value)
    r = _client()
    if r:
        if config.AGENT_LOCAL_CACHE and config.AGENT_BACKGROUND_WRITES:
            _pending_writes[key] = copy.deepcopy(value)
            if key not in _flushing:
                task = in_background(_flush_key(key), "redis write")
                if task is not None:
                    _flushing[key] = task
                    return
                _pending_writes.pop(key, None)
            else:
                return
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


def seed_new_conversation(session_id: str, conversation_id: str):
    """A conversation that was created a moment ago has no earlier messages: remember that, so
    the first message does not wait for a database read that can only come back empty."""
    _hot_put(_history_key(session_id, conversation_id), [])
    _hot_put(_state_key(session_id, conversation_id), {})


# ---- Lasting storage (optional) ------------------------------------------------------------
# Redis / server memory forget a student after 24 hours or a restart. When these hooks are set
# (app/main.py wires them to PostgreSQL) the profile and the chat history survive that, so a
# student who comes back next week is still known and a reopened chat keeps its context.
_profile_loader = None   # async (session_id) -> dict
_profile_saver = None    # async (session_id, profile: dict) -> None
_history_loader = None   # async (session_id, conversation_id) -> [{"role": "user"|"model", "text": str}]

# What the student may see and edit about themselves (Settings > My details).
PUBLIC_PROFILE_KEYS = ("name", "phone", "program_interest", "percent", "board", "eapcet_rank",
                       "jee_percentile", "ib_score", "city", "is_parent", "language", "open_request")


def set_profile_store(loader, saver):
    global _profile_loader, _profile_saver
    _profile_loader, _profile_saver = loader, saver


def set_history_loader(loader):
    global _history_loader
    _history_loader = loader


def public_profile(profile: dict) -> dict:
    return {k: profile[k] for k in PUBLIC_PROFILE_KEYS if profile.get(k) not in (None, "")}


_profile_saving: dict = {}  # session_id -> latest profile still to be written to the database


async def _save_profile_now(session_id: str):
    while session_id in _profile_saving:
        profile = _profile_saving.pop(session_id)
        try:
            await _profile_saver(session_id, profile)
        except Exception:
            pass  # the chat must go on even if the database is briefly unavailable


async def _save_profile(session_id: str, profile: dict):
    await _set(f"sru:profile:{session_id}", profile)
    if not _profile_saver:
        return
    first = session_id not in _profile_saving
    _profile_saving[session_id] = copy.deepcopy(profile)
    if config.AGENT_LOCAL_CACHE and config.AGENT_BACKGROUND_WRITES:
        if first:
            in_background(_save_profile_now(session_id), "profile save")
        return
    await _save_profile_now(session_id)


async def get_profile(session_id: str) -> dict:
    profile = await _get(f"sru:profile:{session_id}", None)
    if profile is None:
        profile = {}
        if _profile_loader:
            try:
                profile = dict(await _profile_loader(session_id) or {})
            except Exception:
                profile = {}
        await _set(f"sru:profile:{session_id}", profile)
    return profile


async def update_profile(session_id: str, **fields) -> dict:
    profile = await get_profile(session_id)
    profile.update({k: v for k, v in fields.items() if v not in (None, "")})
    await _save_profile(session_id, profile)
    return profile


async def clear_profile(session_id: str) -> dict:
    """Forget everything about this student (Settings > Forget my details)."""
    await _save_profile(session_id, {})
    return {}


def _history_key(session_id: str, conversation_id: str | None = None) -> str:
    if conversation_id:
        return f"sru:history:{session_id}:{conversation_id}"
    return f"sru:history:{session_id}"


def _state_key(session_id: str, conversation_id: str | None = None) -> str:
    if conversation_id:
        return f"sru:state:{session_id}:{conversation_id}"
    return f"sru:state:{session_id}"


async def get_history(session_id: str, conversation_id: str | None = None) -> list:
    """Retrieve history for the specific active conversation.

    When nothing is cached (first message after a restart, or a chat reopened days later) the
    saved conversation is read back, so the agent still knows what was said."""
    key = _history_key(session_id, conversation_id)
    history = await _get(key, None)
    if history is None:
        history = []
        if _history_loader and conversation_id:
            try:
                history = list(await _history_loader(session_id, conversation_id) or [])[-MAX_HISTORY:]
            except Exception:
                history = []
        await _set(key, history)
    return history


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
    _hot.pop(key, None)
    _pending_writes.pop(key, None)
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
    r = None if config.AGENT_LOCAL_CACHE else _client()  # one server process: count here, no trip
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
    await _save_profile(session_id, profile)
    return profile


async def get_cached_answer(key: str, max_age_seconds: int):
    """A saved answer to a common first question, if it is still fresh."""
    item = await _get(key, None)
    if not item or time.time() - item.get("at", 0) > max_age_seconds:
        return None
    return item.get("value")


async def set_cached_answer(key: str, value: dict):
    await _set(key, {"at": time.time(), "value": value})
