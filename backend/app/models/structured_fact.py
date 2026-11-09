"""StructuredFact model for verified fees, cutoffs, deadlines, and seat counts."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StructuredFact(Base):
    """Structured ground truth for university figures that must not be hallucinated."""

    __tablename__ = "structured_facts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    category: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    program: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    key_attribute: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    numeric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    formatted_value: Mapped[str] = mapped_column(String(255), nullable=False)
    frequency: Mapped[str | None] = mapped_column(String(50), nullable=True)
    academic_year: Mapped[str] = mapped_column(String(20), default="2026-27", nullable=False)
    source_doc: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<StructuredFact {self.id} category={self.category} program={self.program} key={self.key_attribute} value={self.formatted_value}>"
