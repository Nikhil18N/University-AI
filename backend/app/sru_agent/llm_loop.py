"""Unified LLMProvider-backed model execution, key rotation, retry, and streaming loop for sru_agent."""
from __future__ import annotations

import asyncio
import logging
import time
import weakref
from collections.abc import AsyncIterator
from typing import Any

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

from app.providers.base import LLMProvider
from . import config, observability

log = logging.getLogger("sru_agent")
_MINIMAL_OK = (
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3-flash",
)


class ModelUnavailable(Exception):
    """Every key has used up its quota: answer without the model instead of making students wait."""


class _KeyRing:
    """One Gemini client per configured API key, handed out in turn."""

    def __init__(self):
        self._pool = None
        self._clients = {}

    def _get_pool(self):
        if self._pool is None:
            keys = list(config.GEMINI_API_KEYS) or ([config.GEMINI_API_KEY] if config.GEMINI_API_KEY else [])
            if not keys:
                return None
            from app.providers.key_pool import APIKeyPool
            self._pool = APIKeyPool(keys, default_cooldown=config.AGENT_KEY_COOLDOWN_SECONDS)
        return self._pool

    def next_key(self) -> str:
        pool = self._get_pool()
        return pool.get_next_key() if pool else ""

    def client(self, key: str):
        if key not in self._clients:
            self._clients[key] = genai.Client(api_key=key)
        return self._clients[key]

    def rate_limited(self, key: str, cooldown: float | None = None) -> str:
        """Rest this key for a while; returns the key to use next (may be the same one)."""
        pool = self._get_pool()
        return pool.mark_rate_limited(key, cooldown) if pool else key

    def all_resting(self) -> bool:
        """True when every key is waiting out a limit (no point calling the model right now)."""
        pool = self._get_pool()
        return bool(pool) and pool.active_keys_count == 0

    def worked(self, key: str):
        pool = self._get_pool()
        if pool:
            pool.mark_success(key)

    def size(self) -> int:
        pool = self._get_pool()
        return len(pool) if pool else 0


_ring = _KeyRing()
_gates: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def _gate() -> asyncio.Semaphore:
    """At most AGENT_MAX_CONCURRENCY model calls at a time; the rest queue instead of failing."""
    loop = asyncio.get_running_loop()
    gate = _gates.get(loop)
    if gate is None:
        gate = _gates[loop] = asyncio.Semaphore(max(1, config.AGENT_MAX_CONCURRENCY))
    return gate


def _extract_usage_metadata(resp) -> dict[str, int]:
    """Extract Gemini usage_metadata token counts safely from a GenerateContentResponse."""
    meta = getattr(resp, "usage_metadata", None)
    if meta is None:
        return {
            "prompt_token_count": 0,
            "candidates_token_count": 0,
            "thoughts_token_count": 0,
            "cached_content_token_count": 0,
        }
    return {
        "prompt_token_count": int(getattr(meta, "prompt_token_count", None) or 0),
        "candidates_token_count": int(getattr(meta, "candidates_token_count", None) or 0),
        "thoughts_token_count": int(getattr(meta, "thoughts_token_count", None) or 0),
        "cached_content_token_count": int(getattr(meta, "cached_content_token_count", None) or 0),
    }


def _record_round_usage(link: dict, model: str, resp, started_perf: float) -> None:
    round_ms = round((time.perf_counter() - started_perf) * 1000, 2)
    usage = _extract_usage_metadata(resp)
    link.setdefault("rounds", []).append({"model": model, "latency_ms": round_ms, **usage})


def _apply_rounds_telemetry(telemetry: observability.PolicyTurnTelemetry, link: dict | None) -> None:
    rounds = (link or {}).get("rounds") or []
    if not rounds:
        return
    telemetry.llm_rounds = len(rounds)
    telemetry.model = rounds[-1].get("model") or telemetry.model
    telemetry.prompt_tokens = sum(r.get("prompt_token_count", 0) for r in rounds)
    telemetry.candidates_tokens = sum(r.get("candidates_token_count", 0) for r in rounds)
    telemetry.thoughts_tokens = sum(r.get("thoughts_token_count", 0) for r in rounds)
    telemetry.cached_tokens = sum(r.get("cached_content_token_count", 0) for r in rounds)
    telemetry.round_latencies_ms = [r.get("latency_ms", 0.0) for r in rounds]
    telemetry.generation_latency_ms = round(sum(telemetry.round_latencies_ms), 2)


def _error_kind(exc: Exception) -> str:
    """'model' (try another model), 'rate' (try another key / wait), 'busy' (wait), 'config', or 'fatal'."""
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    text = str(exc).lower()
    if (code == 400 or "400" in text or "invalid_argument" in text) and "think" in text:
        return "config"
    if code == 404 or "not found" in text or "404" in text or "no longer available" in text:
        return "model"
    if code == 429 or "429" in text or "resource_exhausted" in text or "resource exhausted" in text \
            or "quota" in text or "rate limit" in text:
        return "rate"
    if isinstance(exc, (ConnectionError, OSError)) or "connecterror" in type(exc).__name__.lower() \
            or "connection" in text or "timed out" in text or "name resolution" in text:
        return "busy"
    if code in (500, 502, 503, 504) or isinstance(exc, (asyncio.TimeoutError, TimeoutError)) \
            or any(w in text for w in ("503", "unavailable", "overloaded", "deadline exceeded", "internal error")):
        return "busy"
    return "fatal"


def _remaining_budget(link: dict) -> float:
    deadline = link.get("deadline")
    if deadline is None:
        return config.AGENT_CALL_TIMEOUT
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ModelUnavailable("agent request time budget exhausted")
    return min(config.AGENT_CALL_TIMEOUT, remaining)


def _is_daily_limit(exc: Exception) -> bool:
    text = str(exc).lower().replace(" ", "").replace("_", "")
    return "perday" in text or "daily" in text or "requestsperday" in text


async def _handle_call_error(exc, link: dict, attempt: int, model: str, ring=None) -> float | None:
    ring = ring or _ring
    kind = link["error_kind"] = _error_kind(exc)
    err_str = str(exc).lower()
    if "name resolution" in err_str or "clientconnectordnserror" in type(exc).__name__.lower():
        raise exc
    if kind == "model" and link["model_idx"] + 1 < len(link["models"]):
        log.warning("Agent model %s unavailable (%s), trying the next model", model, exc)
        link["model_idx"] += 1
        return None
    if kind == "config" and link.get("thinking"):
        log.warning("Model %s refused the thinking setting (%s); retrying without it", model, str(exc)[:120])
        link["thinking"] = False
        return None
    if kind in ("fatal", "model", "config") or attempt >= len(config.AGENT_RETRY_DELAYS):
        raise exc
    wait = config.AGENT_RETRY_DELAYS[attempt]
    if kind == "rate" and not link["fixed"]:
        daily = _is_daily_limit(exc)
        new_key = ring.rate_limited(link["key"], config.AGENT_DAILY_LIMIT_COOLDOWN if daily else None)
        if ring.all_resting() and (daily or ring.size() > 1):
            raise ModelUnavailable(str(exc)[:200]) from exc
        if new_key != link["key"]:
            link["key"], wait = new_key, 0.2
    log.warning("Model call %s (%s); retry %d in %.1fs", kind, str(exc)[:120], attempt + 1, wait)
    return wait


def _with_thinking(cfg, link: dict, model: str):
    level = (link.get("thinking_level") or config.AGENT_THINKING_LEVEL or "").upper()
    if not link.get("thinking") or not level or level == "DEFAULT":
        return cfg
    if model.startswith("gemini-2"):
        thinking = types.ThinkingConfig(thinking_budget=0)
    else:
        if level == "MINIMAL" and not any(model.startswith(m) for m in _MINIMAL_OK):
            level = "LOW"
        thinking = types.ThinkingConfig(thinking_level=level)
    return cfg.model_copy(update={"thinking_config": thinking})


def select_model_tier(
    message: str,
    *,
    fallback_models: tuple[str, ...] = (),
    has_tools: bool = True,
    is_compound: bool = False,
    is_compare: bool = False,
    speculative_single_round: bool = False,
    has_pending_action: bool = False,
) -> tuple[list[str], str, str]:
    """Select (ordered_models, thinking_level, tier_name) based on query complexity.

    Simple synthesis turns (no tools needed, speculative single-round synthesis where
    tools already ran, or short single-question informational queries without comparisons
    or compound sub-questions) route to AGENT_LITE_MODEL with MINIMAL thinking.
    """
    base_models: list[str] = []
    for m in (config.AGENT_MODEL, *fallback_models):
        if m and m not in base_models:
            base_models.append(m)

    if not config.AGENT_MODEL_TIERING:
        return base_models, (config.AGENT_THINKING_LEVEL or "MINIMAL"), "standard"

    word_count = len((message or "").split())
    simple_synthesis = (
        not is_compound
        and not is_compare
        and not has_pending_action
        and (
            not has_tools
            or speculative_single_round
            or word_count <= 14
        )
    )
    if simple_synthesis and config.AGENT_LITE_MODEL:
        lite_models: list[str] = []
        for m in (config.AGENT_LITE_MODEL, *base_models):
            if m and m not in lite_models:
                lite_models.append(m)
        return lite_models, "MINIMAL", "lite"

    return base_models, (config.AGENT_THINKING_LEVEL or "MINIMAL"), "standard"


_EXPLICIT_CACHES: dict[tuple[str, str, str], tuple[float, str]] = {}
_CACHE_TTL_SECONDS = 3300


async def get_or_create_prompt_cache(
    client,
    model: str,
    static_prefix: str,
    tools_list: list | None = None,
    cache_key_tag: str = "default",
) -> str | None:
    """Create or reuse a Gemini explicit cachedContent for the static prompt prefix."""
    if not config.AGENT_EXPLICIT_CACHE or client is None:
        return None
    caches_api = getattr(getattr(client, "aio", None), "caches", None)
    if caches_api is None:
        return None
    key = (model, cache_key_tag, str(len(static_prefix)))
    entry = _EXPLICIT_CACHES.get(key)
    if entry and entry[0] > time.monotonic():
        return entry[1]
    try:
        cfg = types.CreateCachedContentConfig(
            system_instruction=static_prefix,
            tools=tools_list or None,
            ttl="3600s",
        )
        created = await asyncio.wait_for(
            caches_api.create(model=model, config=cfg),
            timeout=5.0,
        )
        name = getattr(created, "name", None)
        if name:
            _EXPLICIT_CACHES[key] = (time.monotonic() + _CACHE_TTL_SECONDS, name)
            return name
    except Exception as exc:
        log.debug("explicit prompt cache skipped for %s: %s", model, exc)
    return None


def invalidate_prompt_cache(model: str | None = None) -> None:
    if model is None:
        _EXPLICIT_CACHES.clear()
    else:
        for k in [k for k in _EXPLICIT_CACHES if k[0] == model]:
            _EXPLICIT_CACHES.pop(k, None)


class GeminiAgentProvider(LLMProvider):
    """LLMProvider implementation for sru_agent supporting tool calling, streaming, and usage_metadata."""

    def __init__(self, link: dict, ring=None):
        self.link = link
        self.ring = ring or _ring

    async def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        contents = [
            types.Content(
                role="model" if m.get("role") == "assistant" else "user",
                parts=[types.Part.from_text(text=m.get("content", ""))],
            )
            for m in messages
            if m.get("role") != "system" and m.get("content")
        ]
        sys_parts = [m.get("content", "") for m in messages if m.get("role") == "system" and m.get("content")]
        cfg = types.GenerateContentConfig(
            system_instruction="\n\n".join(sys_parts) if sys_parts else None,
            temperature=temperature,
            max_output_tokens=max_tokens or 900,
        )
        resp = await self.generate_with_tools(contents, cfg)
        return (getattr(resp, "text", None) or "").strip()

    async def stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        contents = [
            types.Content(
                role="model" if m.get("role") == "assistant" else "user",
                parts=[types.Part.from_text(text=m.get("content", ""))],
            )
            for m in messages
            if m.get("role") != "system" and m.get("content")
        ]
        sys_parts = [m.get("content", "") for m in messages if m.get("role") == "system" and m.get("content")]
        cfg = types.GenerateContentConfig(
            system_instruction="\n\n".join(sys_parts) if sys_parts else None,
            temperature=temperature,
            max_output_tokens=max_tokens or 900,
        )
        async for kind, val in self.stream_with_tools(contents, cfg):
            if kind == "text":
                yield val

    async def generate_with_tools(
        self,
        contents: Any,
        config_obj: Any,
        model: str | None = None,
    ) -> Any:
        return await _generate(contents, config_obj, self.link, ring=self.ring)

    async def stream_with_tools(
        self,
        contents: Any,
        config_obj: Any,
        model: str | None = None,
    ) -> AsyncIterator[tuple[str, Any]]:
        async for item in _generate_stream(contents, config_obj, self.link, ring=self.ring):
            yield item


def _apply_explicit_cache(cfg, link: dict, cached_name: str | None):
    if not cached_name or not link.get("dynamic_suffix"):
        return cfg
    return cfg.model_copy(
        update={
            "cached_content": cached_name,
            "system_instruction": link["dynamic_suffix"],
            "tools": None,
            "tool_config": None,
        }
    )


async def _generate(contents, cfg, link: dict, ring=None):
    """One model call that survives a retired model, a rate-limited key and a busy server."""
    ring = ring or _ring
    attempt = 0
    if not link["fixed"] and ring.all_resting():
        link["error_kind"] = "rate"
        raise ModelUnavailable("all Gemini keys are resting after a rate limit")
    while True:
        client = link["fixed"] or ring.client(link["key"])
        model = link["models"][link["model_idx"]]
        try:
            timeout = _remaining_budget(link)
            t0 = time.perf_counter()
            cached_name = None
            if link.get("static_prefix") and not link.get("skip_explicit_cache"):
                cached_name = await get_or_create_prompt_cache(
                    client,
                    model,
                    link["static_prefix"],
                    tools_list=getattr(cfg, "tools", None),
                    cache_key_tag=link.get("cache_tag", "default"),
                )
            effective_cfg = _with_thinking(_apply_explicit_cache(cfg, link, cached_name), link, model)
            async with _gate():
                resp = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=model,
                        contents=contents,
                        config=effective_cfg,
                    ),
                    timeout=timeout,
                )
            if not link["fixed"]:
                ring.worked(link["key"])
            _record_round_usage(link, model, resp, t0)
            return resp
        except Exception as exc:
            if "cachedcontent" in str(exc).lower() or "cached_content" in str(exc).lower():
                invalidate_prompt_cache(model)
                link["skip_explicit_cache"] = True
                continue
            wait = await _handle_call_error(exc, link, attempt, model, ring=ring)
            if wait is None:
                continue
            attempt += 1
            if link.get("deadline") is not None and time.monotonic() + wait >= link["deadline"]:
                raise ModelUnavailable("agent request time budget exhausted") from exc
            await asyncio.sleep(wait)


def _can_stream(link: dict, ring=None) -> bool:
    ring = ring or _ring
    client = link["fixed"] or (ring.client(link["key"]) if link["key"] else None)
    return bool(config.AGENT_STREAM) and client is not None and \
        hasattr(getattr(getattr(client, "aio", None), "models", None), "generate_content_stream")


async def _generate_stream(contents, cfg, link: dict, ring=None):
    """Like _generate, yielding ('text', delta) and ('done', merged_response) with usage_metadata."""
    ring = ring or _ring
    attempt = 0
    if not link["fixed"] and ring.all_resting():
        link["error_kind"] = "rate"
        raise ModelUnavailable("all Gemini keys are resting after a rate limit")
    while True:
        client = link["fixed"] or ring.client(link["key"])
        model = link["models"][link["model_idx"]]
        started = False
        try:
            timeout = _remaining_budget(link)
            t0 = time.perf_counter()
            cached_name = None
            if link.get("static_prefix") and not link.get("skip_explicit_cache"):
                cached_name = await get_or_create_prompt_cache(
                    client,
                    model,
                    link["static_prefix"],
                    tools_list=getattr(cfg, "tools", None),
                    cache_key_tag=link.get("cache_tag", "default"),
                )
            effective_cfg = _with_thinking(_apply_explicit_cache(cfg, link, cached_name), link, model)
            async with _gate():
                stream = await asyncio.wait_for(
                    client.aio.models.generate_content_stream(
                        model=model,
                        contents=contents,
                        config=effective_cfg,
                    ),
                    timeout=timeout,
                )
                parts, last = [], None
                iterator = stream.__aiter__()
                while True:
                    try:
                        chunk = await asyncio.wait_for(iterator.__anext__(), timeout=_remaining_budget(link))
                    except StopAsyncIteration:
                        break
                    last = chunk
                    cand = (chunk.candidates or [None])[0]
                    for part in ((cand.content.parts if cand and cand.content else None) or []):
                        parts.append(part)
                        if part.text and not getattr(part, "thought", False):
                            started = True
                            yield ("text", part.text)
            if not link["fixed"]:
                ring.worked(link["key"])
            merged = types.GenerateContentResponse(
                candidates=[types.Candidate(
                    content=types.Content(role="model", parts=parts),
                    finish_reason=getattr((last.candidates or [None])[0], "finish_reason", None) if last else None)],
                usage_metadata=getattr(last, "usage_metadata", None) if last else None,
            )
            _record_round_usage(link, model, merged, t0)
            yield ("done", merged)
            return
        except Exception as exc:
            if started:
                link["error_kind"] = _error_kind(exc)
                raise
            if "cachedcontent" in str(exc).lower() or "cached_content" in str(exc).lower():
                invalidate_prompt_cache(model)
                link["skip_explicit_cache"] = True
                continue
            wait = await _handle_call_error(exc, link, attempt, model, ring=ring)
            if wait is None:
                continue
            attempt += 1
            if link.get("deadline") is not None and time.monotonic() + wait >= link["deadline"]:
                raise ModelUnavailable("agent request time budget exhausted") from exc
            await asyncio.sleep(wait)
