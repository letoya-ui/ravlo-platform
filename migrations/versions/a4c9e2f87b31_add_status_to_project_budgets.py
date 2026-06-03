"""add status to project_budgets

Revision ID: a4c9e2f87b31
Revises: f80fae86417f
Create Date: 2026-06-01 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'a4c9e2f87b31'
down_revision = 'f80fae86417f'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE project_budgets
        ADD COLUMN IF NOT EXISTS status VARCHAR(32) NOT NULL DEFAULT 'active'
    """)


def downgrade():
    op.drop_column('project_budgets', 'status')
