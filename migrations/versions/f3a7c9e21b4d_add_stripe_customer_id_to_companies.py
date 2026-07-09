"""add stripe_customer_id to companies

Revision ID: f3a7c9e21b4d
Revises: de6cd90aa0dd
Create Date: 2026-07-09 14:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'f3a7c9e21b4d'
down_revision = 'de6cd90aa0dd'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE companies
        ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255)
    """)


def downgrade():
    op.drop_column('companies', 'stripe_customer_id')
