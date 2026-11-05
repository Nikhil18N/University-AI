"""add evaluation_records table

Revision ID: 2bfe9ad34558
Revises: a1bee2861f77
Create Date: 2026-11-05 18:17:16.973772

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2bfe9ad34558'
down_revision: Union[str, Sequence[str], None] = 'a1bee2861f77'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    """Upgrade schema safely."""
    op.execute("""
    CREATE TABLE IF NOT EXISTS evaluation_records (
        id UUID PRIMARY KEY,
        test_id VARCHAR(64),
        conversation_id UUID REFERENCES conversations (id) ON DELETE SET NULL,
        message_id UUID REFERENCES messages (id) ON DELETE SET NULL,
        category VARCHAR(64),
        question TEXT NOT NULL,
        expected_answer TEXT,
        actual_answer TEXT NOT NULL,
        groundedness_score FLOAT DEFAULT 1.0 NOT NULL,
        retrieval_confidence FLOAT,
        latency_ms INTEGER,
        passed BOOLEAN DEFAULT true NOT NULL,
        sources JSONB,
        metadata JSONB,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_evaluation_records_test_id ON evaluation_records (test_id)")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_evaluation_records_test_id'), table_name='evaluation_records')
    op.drop_table('evaluation_records')
