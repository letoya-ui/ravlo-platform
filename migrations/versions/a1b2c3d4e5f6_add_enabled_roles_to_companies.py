"""add enabled_roles to companies

Revision ID: a1b2c3d4e5f6
Revises: rp01add
Create Date: 2026-10-23 00:00:00.000000
"""
from alembic import op

revision = 'a1b2c3d4e5f6'
down_revision = 'rp01add'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE companies
        ADD COLUMN IF NOT EXISTS enabled_roles JSON
    """)


def downgrade():
    op.drop_column('companies', 'enabled_roles')
