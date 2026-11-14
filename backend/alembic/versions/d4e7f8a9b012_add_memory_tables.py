"""add consented memory and conversation summary tables."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e7f8a9b012"
down_revision: Union[str, Sequence[str], None] = "c3a1f8901234"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversation_summaries",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("conversation_id"),
    )
    op.create_table(
        "user_memories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("memory_key", sa.String(length=64), nullable=False),
        sa.Column("memory_value", sa.String(length=255), nullable=False),
        sa.Column("consented", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "memory_key", name="uq_user_memory_session_key"),
    )
    op.create_index("ix_user_memories_session_id", "user_memories", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_user_memories_session_id", table_name="user_memories")
    op.drop_table("user_memories")
    op.drop_table("conversation_summaries")
