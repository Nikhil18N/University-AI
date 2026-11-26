"""add response_meta json column to turn_telemetry

Revision ID: k1l2m3n4o567
Revises: j0k1l2m3n456
Create Date: 2026-11-26 17:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "k1l2m3n4o567"
down_revision = "j0k1l2m3n456"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE turn_telemetry ADD COLUMN IF NOT EXISTS response_meta JSON")


def downgrade() -> None:
    op.execute("ALTER TABLE turn_telemetry DROP COLUMN IF EXISTS response_meta")
