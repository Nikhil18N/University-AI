"""add structured_facts table

Revision ID: d4e5f6789012
Revises: c3a1f8901234
Create Date: 2026-11-09 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6789012'
down_revision: Union[str, Sequence[str], None] = 'c3a1f8901234'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema safely."""
    op.execute("""
    CREATE TABLE IF NOT EXISTS structured_facts (
        id UUID PRIMARY KEY,
        category VARCHAR(50) NOT NULL,
        program VARCHAR(100) NOT NULL,
        key_attribute VARCHAR(100) NOT NULL,
        numeric_value DOUBLE PRECISION,
        currency VARCHAR(10),
        formatted_value VARCHAR(255) NOT NULL,
        frequency VARCHAR(50),
        academic_year VARCHAR(20) DEFAULT '2026-27' NOT NULL,
        source_doc VARCHAR(255) NOT NULL,
        notes TEXT,
        metadata JSONB,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_structured_facts_category ON structured_facts (category)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_structured_facts_program ON structured_facts (program)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_structured_facts_key_attr ON structured_facts (key_attribute)")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_structured_facts_key_attr', table_name='structured_facts')
    op.drop_index('ix_structured_facts_program', table_name='structured_facts')
    op.drop_index('ix_structured_facts_category', table_name='structured_facts')
    op.drop_table('structured_facts')
