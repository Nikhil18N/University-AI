"""add resumable clarification tasks."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a7b8c9d0e123"
down_revision: Union[str, Sequence[str], None] = "f6a1b2c3d456"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pending_agent_tasks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("original_query", sa.Text(), nullable=False),
        sa.Column("missing_inputs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pending_agent_tasks_conversation_id", "pending_agent_tasks", ["conversation_id"])
    op.create_index("ix_pending_agent_tasks_session_id", "pending_agent_tasks", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_pending_agent_tasks_session_id", table_name="pending_agent_tasks")
    op.drop_index("ix_pending_agent_tasks_conversation_id", table_name="pending_agent_tasks")
    op.drop_table("pending_agent_tasks")
