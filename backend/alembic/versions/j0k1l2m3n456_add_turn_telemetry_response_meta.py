"""add response_meta json column to turn_telemetry

Revision ID: j0k1l2m3n456
Revises: i9j0k1l2m345
Create Date: 2026-11-26 17:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "j0k1l2m3n456"
down_revision = "i9j0k1l2m345"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("turn_telemetry", sa.Column("response_meta", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("turn_telemetry", "response_meta")
