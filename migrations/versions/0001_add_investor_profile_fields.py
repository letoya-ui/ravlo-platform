"""Add investor profile fields

Revision ID: 0001
Revises: 
Create Date: 2026-03-03 19:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    pass
    # Example:
    # op.add_column('investor_profile', sa.Column('credit_score', sa.Integer()))
    # op.add_column('investor_profile', sa.Column('annual_income', sa.Numeric()))


def downgrade():
    pass
    # Example:
    # op.drop_column('investor_profile', 'credit_score')
    # op.drop_column('investor_profile', 'annual_income')
