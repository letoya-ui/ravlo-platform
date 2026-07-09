"""add context to subscription_requests

Revision ID: de6cd90aa0dd
Revises: a81f03ac085e
Create Date: 2026-07-09 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'de6cd90aa0dd'
down_revision = 'a81f03ac085e'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE subscription_requests
        ADD COLUMN IF NOT EXISTS context VARCHAR(50) DEFAULT 'investor_preview'
    """)


def downgrade():
    op.drop_column('subscription_requests', 'context')
