"""Add Deal public reveal fields

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("deals", sa.Column("reveal_public_id", sa.String(length=32), nullable=True))
    op.add_column("deals", sa.Column("reveal_is_public", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("deals", sa.Column("reveal_published_at", sa.DateTime(), nullable=True))

    op.create_index("ix_deals_reveal_public_id", "deals", ["reveal_public_id"], unique=True)


def downgrade():
    op.drop_index("ix_deals_reveal_public_id", table_name="deals")

    op.drop_column("deals", "reveal_published_at")
    op.drop_column("deals", "reveal_is_public")
    op.drop_column("deals", "reveal_public_id")
