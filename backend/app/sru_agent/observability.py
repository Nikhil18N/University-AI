"""Observability & Telemetry Service for Semantic Routing and Approved Answer Policies."""

from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

log = logging.getLogger("sru_agent.observability")
_VIDEO_CARD_TYPES = {"video_recommendations", "get_university_videos", "event_highlights"}
_HAS_MD_TABLE_RE = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)


@dataclass
class PolicyTurnTelemetry:
    session_id: str
    conversation_id: Optional[str]
    message: str
    detected_intent: str
    selected_policy_id: Optional[str] = None
    policy_version: Optional[str] = None
    response_mode: str = "rag"
    retrieved_evidence_ids: List[str] = field(default_factory=list)
    routing_confidence: float = 0.0
    fallback_decision: bool = False
    fallback_reason: Optional[str] = None
    routing_latency_ms: float = 0.0
    generation_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    first_token_ms: Optional[float] = None
    model: Optional[str] = None
    llm_rounds: int = 0
    prompt_tokens: int = 0
    candidates_tokens: int = 0
    thoughts_tokens: int = 0
    cached_tokens: int = 0
    round_latencies_ms: List[float] = field(default_factory=list)
    evaluation_score: float = 1.0
    answer_chars: int = 0
    has_table: bool = False
    card_types: List[str] = field(default_factory=list)
    video_count: int = 0
    video_topics: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    sources_count: int = 0
    tools_used: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def attach_response_metadata(
    telemetry: PolicyTurnTelemetry,
    *,
    answer: str = "",
    cards: list | None = None,
    suggestions: list | None = None,
    sources: list | None = None,
    used: list | None = None,
) -> None:
    """Populate whole-response observability fields (cards, videos, tables, chips, sources, tools)."""
    telemetry.answer_chars = len(answer or "")
    telemetry.has_table = bool(_HAS_MD_TABLE_RE.search(answer or ""))
    card_list = [c for c in (cards or []) if isinstance(c, dict)]
    telemetry.card_types = [str(c.get("type")) for c in card_list if c.get("type")]
    v_count = 0
    v_topics: list[str] = []
    for c in card_list:
        if c.get("type") in _VIDEO_CARD_TYPES:
            vids = ((c.get("data") or c).get("videos") or [])
            v_count += len(vids) if isinstance(vids, list) else 0
            title = c.get("title") or (c.get("data") or {}).get("title")
            if title and str(title) not in v_topics:
                v_topics.append(str(title))
    telemetry.video_count = v_count
    telemetry.video_topics = v_topics
    telemetry.suggestions = [str(s) for s in (suggestions or [])][:6]
    telemetry.sources_count = len(sources or [])
    telemetry.tools_used = [
        str(t.get("name")) for t in (used or []) if isinstance(t, dict) and t.get("name")
    ]


_recent_telemetry: List[PolicyTurnTelemetry] = []
_MAX_TELEMETRY_LOG = 500
_TELEMETRY_REDIS_KEY = "sru:recent_telemetry"
_TELEMETRY_TTL = 86400


def build_turn_telemetry_row(telemetry: PolicyTurnTelemetry | Dict[str, Any]):
    """Construct a TurnTelemetry ORM row from a PolicyTurnTelemetry or dict."""
    from app.models.telemetry import TurnTelemetry

    d = telemetry.to_dict() if isinstance(telemetry, PolicyTurnTelemetry) else dict(telemetry or {})
    conv_id = d.get("conversation_id")
    model = d.get("model")
    fb_reason = d.get("fallback_reason")
    return TurnTelemetry(
        session_id=str(d.get("session_id") or "")[:64],
        conversation_id=str(conv_id)[:64] if conv_id else None,
        detected_intent=str(d.get("detected_intent") or "GENERAL")[:64],
        response_mode=str(d.get("response_mode") or "rag")[:32],
        model=str(model)[:64] if model else None,
        llm_rounds=int(d.get("llm_rounds") or 0),
        prompt_tokens=int(d.get("prompt_tokens") or 0),
        candidates_tokens=int(d.get("candidates_tokens") or 0),
        thoughts_tokens=int(d.get("thoughts_tokens") or 0),
        cached_tokens=int(d.get("cached_tokens") or 0),
        routing_latency_ms=float(d.get("routing_latency_ms") or 0.0),
        generation_latency_ms=float(d.get("generation_latency_ms") or 0.0),
        total_latency_ms=float(d.get("total_latency_ms") or 0.0),
        first_token_ms=float(d["first_token_ms"]) if d.get("first_token_ms") is not None else None,
        fallback_decision=bool(d.get("fallback_decision") or False),
        fallback_reason=str(fb_reason)[:128] if fb_reason else None,
        response_meta={
            "answer_chars": int(d.get("answer_chars") or 0),
            "has_table": bool(d.get("has_table") or False),
            "card_types": list(d.get("card_types") or []),
            "video_count": int(d.get("video_count") or 0),
            "video_topics": list(d.get("video_topics") or []),
            "suggestions": list(d.get("suggestions") or []),
            "sources_count": int(d.get("sources_count") or 0),
            "tools_used": list(d.get("tools_used") or []),
        },
    )


async def _persist_telemetry_to_db(telemetry: PolicyTurnTelemetry) -> None:
    """Persist turn-level token and latency metrics to PostgreSQL; never fail the chat."""
    try:
        from app.db.session import async_session_factory
        if async_session_factory is None:
            return
        async with async_session_factory() as session:
            session.add(build_turn_telemetry_row(telemetry))
            await session.commit()
    except Exception as exc:
        log.debug("turn_telemetry DB write skipped: %s", exc)


def record_policy_telemetry(
    telemetry: PolicyTurnTelemetry,
    *,
    persist: bool = True,
    persist_db: bool = True,
) -> None:
    """Record a policy routing and execution telemetry event."""
    global _recent_telemetry
    _recent_telemetry.append(telemetry)
    if len(_recent_telemetry) > _MAX_TELEMETRY_LOG:
        _recent_telemetry = _recent_telemetry[-_MAX_TELEMETRY_LOG:]

    log.info(
        "POLICY_TELEMETRY: intent=%s policy=%s conf=%.2f mode=%s fallback=%s "
        "rounds=%d prompt_tok=%d cand_tok=%d thoughts_tok=%d cached_tok=%d gen_ms=%.1f total_ms=%.1f ev_ids=%s",
        telemetry.detected_intent,
        telemetry.selected_policy_id,
        telemetry.routing_confidence,
        telemetry.response_mode,
        telemetry.fallback_decision,
        telemetry.llm_rounds,
        telemetry.prompt_tokens,
        telemetry.candidates_tokens,
        telemetry.thoughts_tokens,
        telemetry.cached_tokens,
        telemetry.generation_latency_ms,
        telemetry.total_latency_ms,
        telemetry.retrieved_evidence_ids,
    )
    if persist:
        try:
            from . import memory
            if persist_db:
                memory.in_background(_persist_telemetry_to_db(telemetry), "telemetry save")
            r = memory.get_redis()
            if r is not None:
                payload = json.dumps(telemetry.to_dict(), ensure_ascii=False)
                async def _push_redis():
                    await r.lpush(_TELEMETRY_REDIS_KEY, payload)
                    await r.ltrim(_TELEMETRY_REDIS_KEY, 0, _MAX_TELEMETRY_LOG - 1)
                    await r.expire(_TELEMETRY_REDIS_KEY, _TELEMETRY_TTL)
                memory.in_background(_push_redis(), "telemetry redis")
        except Exception:
            pass


def get_recent_telemetry(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieve recent policy execution telemetry records."""
    return [t.to_dict() for t in _recent_telemetry[-limit:]]


async def get_recent_telemetry_async(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieve recent telemetry from Redis (multi-worker safe), PostgreSQL, or in-process fallback."""
    try:
        from . import memory
        r = memory.get_redis()
        if r is not None:
            raw_items = await r.lrange(_TELEMETRY_REDIS_KEY, 0, max(0, limit - 1))
            if raw_items:
                return [json.loads(item) for item in reversed(raw_items)]
    except Exception:
        pass
    mem_records = get_recent_telemetry(limit=limit)
    if mem_records:
        return mem_records
    try:
        from sqlalchemy import select
        from app.db.session import async_session_factory
        from app.models.telemetry import TurnTelemetry
        if async_session_factory is not None:
            async with async_session_factory() as session:
                rows = (
                    await session.execute(
                        select(TurnTelemetry).order_by(TurnTelemetry.created_at.desc()).limit(limit)
                    )
                ).scalars().all()
                return [
                    {
                        "session_id": row.session_id,
                        "conversation_id": row.conversation_id,
                        "detected_intent": row.detected_intent,
                        "response_mode": row.response_mode,
                        "model": row.model,
                        "llm_rounds": row.llm_rounds,
                        "prompt_tokens": row.prompt_tokens,
                        "candidates_tokens": row.candidates_tokens,
                        "thoughts_tokens": row.thoughts_tokens,
                        "cached_tokens": row.cached_tokens,
                        "routing_latency_ms": row.routing_latency_ms,
                        "generation_latency_ms": row.generation_latency_ms,
                        "total_latency_ms": row.total_latency_ms,
                        "first_token_ms": row.first_token_ms,
                        "fallback_decision": row.fallback_decision,
                        "fallback_reason": row.fallback_reason,
                        **(row.response_meta or {}),
                        "timestamp": row.created_at.isoformat() if row.created_at else None,
                    }
                    for row in reversed(rows)
                ]
    except Exception:
        pass
    return []


def compute_telemetry_summary(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute latency percentiles, token totals, cache hit rate, and whole-response breakdowns."""
    total = len(records)
    if not total:
        return {
            "total_turns": 0,
            "avg_total_latency_ms": 0.0,
            "p50_total_latency_ms": 0.0,
            "p95_total_latency_ms": 0.0,
            "avg_generation_latency_ms": 0.0,
            "avg_first_token_ms": 0.0,
            "total_prompt_tokens": 0,
            "total_candidates_tokens": 0,
            "total_thoughts_tokens": 0,
            "total_cached_tokens": 0,
            "cache_hit_rate": 0.0,
            "fallback_rate": 0.0,
            "cards_shown_rate": 0.0,
            "videos_shown_rate": 0.0,
            "table_rate": 0.0,
            "by_intent": {},
            "by_model": {},
            "by_mode": {},
            "by_card_type": {},
        }

    latencies = sorted(float(r.get("total_latency_ms") or 0.0) for r in records)
    gen_lats = [float(r.get("generation_latency_ms") or 0.0) for r in records if r.get("llm_rounds")]
    ft_lats = [float(r["first_token_ms"]) for r in records if r.get("first_token_ms") is not None]
    p50 = latencies[int(0.50 * (total - 1))]
    p95 = latencies[min(total - 1, max(0, int((total * 95 + 99) // 100) - 1))]
    prompt_tok = sum(int(r.get("prompt_tokens") or 0) for r in records)
    cand_tok = sum(int(r.get("candidates_tokens") or 0) for r in records)
    thoughts_tok = sum(int(r.get("thoughts_tokens") or 0) for r in records)
    cached_tok = sum(int(r.get("cached_tokens") or 0) for r in records)
    cache_hits = sum(1 for r in records if r.get("response_mode") == "cache" or int(r.get("cached_tokens") or 0) > 0)
    fallbacks = sum(1 for r in records if r.get("fallback_decision"))
    cards_shown = sum(1 for r in records if r.get("card_types"))
    videos_shown = sum(1 for r in records if int(r.get("video_count") or 0) > 0)
    tables_shown = sum(1 for r in records if r.get("has_table"))

    by_intent: Dict[str, int] = {}
    by_model: Dict[str, int] = {}
    by_mode: Dict[str, int] = {}
    by_card_type: Dict[str, int] = {}
    for r in records:
        intent = str(r.get("detected_intent") or "UNKNOWN")
        model = str(r.get("model") or "deterministic")
        mode = str(r.get("response_mode") or "unknown")
        by_intent[intent] = by_intent.get(intent, 0) + 1
        by_model[model] = by_model.get(model, 0) + 1
        by_mode[mode] = by_mode.get(mode, 0) + 1
        for ct in (r.get("card_types") or []):
            by_card_type[str(ct)] = by_card_type.get(str(ct), 0) + 1

    return {
        "total_turns": total,
        "avg_total_latency_ms": round(sum(latencies) / total, 2),
        "p50_total_latency_ms": round(p50, 2),
        "p95_total_latency_ms": round(p95, 2),
        "avg_generation_latency_ms": round(sum(gen_lats) / len(gen_lats), 2) if gen_lats else 0.0,
        "avg_first_token_ms": round(sum(ft_lats) / len(ft_lats), 2) if ft_lats else 0.0,
        "total_prompt_tokens": prompt_tok,
        "total_candidates_tokens": cand_tok,
        "total_thoughts_tokens": thoughts_tok,
        "total_cached_tokens": cached_tok,
        "cache_hit_rate": round(cache_hits / total, 4),
        "fallback_rate": round(fallbacks / total, 4),
        "cards_shown_rate": round(cards_shown / total, 4),
        "videos_shown_rate": round(videos_shown / total, 4),
        "table_rate": round(tables_shown / total, 4),
        "by_intent": by_intent,
        "by_model": by_model,
        "by_mode": by_mode,
        "by_card_type": by_card_type,
    }


def clear_telemetry() -> None:
    global _recent_telemetry
    _recent_telemetry.clear()
