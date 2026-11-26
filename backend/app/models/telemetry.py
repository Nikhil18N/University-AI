"""Turn-level token and latency telemetry model."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TurnTelemetry(Base):
    """Persisted token usage and latency metrics for one agent turn."""

    __tablename__ = "turn_telemetry"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    conversation_id: Mapped[str | None] = mapped_column(
        String(64), index=True, nullable=True
    )
    detected_intent: Mapped[str] = mapped_column(String(64), nullable=False)
    response_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    llm_rounds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    candidates_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    thoughts_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cached_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    routing_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    generation_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    first_token_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    fallback_decision: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fallback_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    response_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
