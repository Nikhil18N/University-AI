"""Conversation model — anonymous session-based."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Conversation(Base):
    """A conversation belongs to an anonymous browser session."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[str] = mapped_column(
        String(64), index=True, nullable=False,
        comment="Browser-generated UUID stored in localStorage",
    )
    title: Mapped[str] = mapped_column(
        String(255), default="New conversation"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan",
        # A question and its answer can carry the same timestamp (saved in one transaction), so the
        # role breaks the tie: "user" sorts before "assistant". Without it a reopened chat could
        # show the answer above its question.
        order_by="(Message.created_at, Message.role.desc())",
    )

    def __repr__(self) -> str:
        return f"<Conversation {self.id} session={self.session_id}>"
