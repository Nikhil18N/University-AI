"""add turn_telemetry table for token and latency observability."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h8i9j0k1l234"
down_revision: Union[str, Sequence[str], None] = "g7h8i9j0k123"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The API creates this table at startup when Alembic cannot run (v4.18.0): skip it if it is already there.
    if sa.inspect(op.get_bind()).has_table("turn_telemetry"):
        return
    op.create_table(
        "turn_telemetry",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("conversation_id", sa.String(length=64), nullable=True),
        sa.Column("detected_intent", sa.String(length=64), nullable=False),
        sa.Column("response_mode", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("llm_rounds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("candidates_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("thoughts_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cached_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("routing_latency_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("generation_latency_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_latency_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("first_token_ms", sa.Float(), nullable=True),
        sa.Column("fallback_decision", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("fallback_reason", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_turn_telemetry_session_id", "turn_telemetry", ["session_id"])
    op.create_index("ix_turn_telemetry_conversation_id", "turn_telemetry", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_turn_telemetry_conversation_id", table_name="turn_telemetry")
    op.drop_index("ix_turn_telemetry_session_id", table_name="turn_telemetry")
    op.drop_table("turn_telemetry")
