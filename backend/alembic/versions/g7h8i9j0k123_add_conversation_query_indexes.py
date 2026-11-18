"""add indexes for conversation and message query patterns."""

from typing import Sequence, Union

from alembic import op


revision: str = "g7h8i9j0k123"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e123"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_conversations_session_updated_at",
        "conversations",
        ["session_id", "updated_at"],
    )
    op.create_index(
        "ix_messages_conversation_created_role",
        "messages",
        ["conversation_id", "created_at", "role"],
    )
    op.create_index(
        "ix_messages_conversation_role_created",
        "messages",
        ["conversation_id", "role", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_messages_conversation_role_created",
        table_name="messages",
    )
    op.drop_index(
        "ix_messages_conversation_created_role",
        table_name="messages",
    )
    op.drop_index(
        "ix_conversations_session_updated_at",
        table_name="conversations",
    )
