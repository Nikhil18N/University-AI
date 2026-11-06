"""add prospective_leads table

Revision ID: c3a1f8901234
Revises: 2bfe9ad34558
Create Date: 2026-11-06 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c3a1f8901234'
down_revision: Union[str, Sequence[str], None] = '2bfe9ad34558'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema safely."""
    op.execute("""
    CREATE TABLE IF NOT EXISTS prospective_leads (
        id UUID PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        phone VARCHAR(20) NOT NULL,
        email VARCHAR(255),
        program_interest VARCHAR(255),
        score VARCHAR(100),
        exam_type VARCHAR(100),
        source VARCHAR(50) DEFAULT 'chat_inquiry' NOT NULL,
        conversation_id UUID REFERENCES conversations (id) ON DELETE SET NULL,
        status VARCHAR(50) DEFAULT 'interested' NOT NULL,
        metadata JSONB,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_prospective_leads_phone ON prospective_leads (phone)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_prospective_leads_created_at ON prospective_leads (created_at)")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_prospective_leads_created_at', table_name='prospective_leads')
    op.drop_index('ix_prospective_leads_phone', table_name='prospective_leads')
    op.drop_table('prospective_leads')
