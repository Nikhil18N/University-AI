"""alter user_memories.memory_value from varchar(255) to text."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i9j0k1l2m345"
down_revision: Union[str, Sequence[str], None] = "h8i9j0k1l234"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "user_memories",
        "memory_value",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "user_memories",
        "memory_value",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
