"""add arv_tier to deals and project_budgets

Revision ID: c7e1a9b4d2f0
Revises: a4c9e2f87b31
Create Date: 2026-07-07 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'c7e1a9b4d2f0'
down_revision = 'a4c9e2f87b31'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE deals
        ADD COLUMN IF NOT EXISTS arv_tier VARCHAR(20) NOT NULL DEFAULT 'base'
    """)
    op.execute("""
        ALTER TABLE project_budgets
        ADD COLUMN IF NOT EXISTS arv_tier VARCHAR(20)
    """)


def downgrade():
    op.drop_column('deals', 'arv_tier')
    op.drop_column('project_budgets', 'arv_tier')
