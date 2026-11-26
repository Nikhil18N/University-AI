"""Observability & Telemetry Service for Semantic Routing and Approved Answer Policies."""

from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import logging
import time
from typing import Any, Dict, List, Optional

log = logging.getLogger("sru_agent.observability")


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
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_recent_telemetry: List[PolicyTurnTelemetry] = []
_MAX_TELEMETRY_LOG = 500
_TELEMETRY_REDIS_KEY = "sru:recent_telemetry"
_TELEMETRY_TTL = 86400


async def _persist_telemetry_to_db(telemetry: PolicyTurnTelemetry) -> None:
    """Persist turn-level token and latency metrics to PostgreSQL; never fail the chat."""
    try:
        from app.db.session import async_session_factory
        from app.models.telemetry import TurnTelemetry
        if async_session_factory is None:
            return
        async with async_session_factory() as session:
            row = TurnTelemetry(
                session_id=(telemetry.session_id or "")[:64],
                conversation_id=str(telemetry.conversation_id)[:64] if telemetry.conversation_id else None,
                detected_intent=(telemetry.detected_intent or "GENERAL")[:64],
                response_mode=(telemetry.response_mode or "rag")[:32],
                model=telemetry.model[:64] if telemetry.model else None,
                llm_rounds=telemetry.llm_rounds,
                prompt_tokens=telemetry.prompt_tokens,
                candidates_tokens=telemetry.candidates_tokens,
                thoughts_tokens=telemetry.thoughts_tokens,
                cached_tokens=telemetry.cached_tokens,
                routing_latency_ms=telemetry.routing_latency_ms,
                generation_latency_ms=telemetry.generation_latency_ms,
                total_latency_ms=telemetry.total_latency_ms,
                first_token_ms=telemetry.first_token_ms,
                fallback_decision=telemetry.fallback_decision,
                fallback_reason=telemetry.fallback_reason[:128] if telemetry.fallback_reason else None,
            )
            session.add(row)
            await session.commit()
    except Exception as exc:
        log.debug("turn_telemetry DB write skipped: %s", exc)


def record_policy_telemetry(telemetry: PolicyTurnTelemetry, *, persist: bool = True) -> None:
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
    """Retrieve recent telemetry from Redis (multi-worker safe) with in-process fallback."""
    try:
        from . import memory
        r = memory.get_redis()
        if r is not None:
            raw_items = await r.lrange(_TELEMETRY_REDIS_KEY, 0, max(0, limit - 1))
            if raw_items:
                return [json.loads(item) for item in reversed(raw_items)]
    except Exception:
        pass
    return get_recent_telemetry(limit=limit)


def clear_telemetry() -> None:
    global _recent_telemetry
    _recent_telemetry.clear()
