"""make investor_profile_id nullable

Revision ID: c6dea7f1b64d
Revises: 30a44806ab89
Create Date: 2026-03-19 18:43:11.632185

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c6dea7f1b64d'
down_revision = '30a44806ab89'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'underwriting_condition',
        'investor_profile_id',
        existing_type=sa.Integer(),
        nullable=True
    )


def downgrade():
    op.alter_column(
        'underwriting_condition',
        'investor_profile_id',
        existing_type=sa.Integer(),
        nullable=False
    )