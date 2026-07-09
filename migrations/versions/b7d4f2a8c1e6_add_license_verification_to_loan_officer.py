"""add license verification fields to loan_officer_profile

Revision ID: b7d4f2a8c1e6
Revises: a2c8e5f19b3d
Create Date: 2026-07-09 15:30:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'b7d4f2a8c1e6'
down_revision = 'a2c8e5f19b3d'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE loan_officer_profile
        ADD COLUMN IF NOT EXISTS licensed_states VARCHAR(255)
    """)
    op.execute("""
        ALTER TABLE loan_officer_profile
        ADD COLUMN IF NOT EXISTS license_verified BOOLEAN NOT NULL DEFAULT FALSE
    """)
    op.execute("""
        ALTER TABLE loan_officer_profile
        ADD COLUMN IF NOT EXISTS license_verified_by INTEGER REFERENCES "user"(id)
    """)
    op.execute("""
        ALTER TABLE loan_officer_profile
        ADD COLUMN IF NOT EXISTS license_verified_at TIMESTAMP
    """)


def downgrade():
    op.drop_column('loan_officer_profile', 'license_verified_at')
    op.drop_column('loan_officer_profile', 'license_verified_by')
    op.drop_column('loan_officer_profile', 'license_verified')
    op.drop_column('loan_officer_profile', 'licensed_states')
