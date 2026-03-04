"""Add full investor profile schema

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-03 19:10:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0002'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Identity + contact
    op.add_column('investor_profile', sa.Column('address', sa.String(length=255)))
    op.add_column('investor_profile', sa.Column('city', sa.String(length=100)))
    op.add_column('investor_profile', sa.Column('state', sa.String(length=50)))
    op.add_column('investor_profile', sa.Column('zip_code', sa.String(length=20)))

    # Employment + financials
    op.add_column('investor_profile', sa.Column('employment_status', sa.String(length=100)))
    op.add_column('investor_profile', sa.Column('annual_income', sa.Integer()))
    op.add_column('investor_profile', sa.Column('credit_score', sa.Integer()))

    # Preferences
    op.add_column('investor_profile', sa.Column('strategy', sa.String(length=50)))
    op.add_column('investor_profile', sa.Column('experience_level', sa.String(length=30)))

    # Buy box
    op.add_column('investor_profile', sa.Column('target_markets', sa.Text()))
    op.add_column('investor_profile', sa.Column('property_types', sa.Text()))
    op.add_column('investor_profile', sa.Column('min_price', sa.Integer()))
    op.add_column('investor_profile', sa.Column('max_price', sa.Integer()))
    op.add_column('investor_profile', sa.Column('min_sqft', sa.Integer()))
    op.add_column('investor_profile', sa.Column('max_sqft', sa.Integer()))

    # Capital + returns
    op.add_column('investor_profile', sa.Column('capital_available', sa.Integer()))
    op.add_column('investor_profile', sa.Column('min_cash_on_cash', sa.Float()))
    op.add_column('investor_profile', sa.Column('min_roi', sa.Float()))

    # Risk + timeline
    op.add_column('investor_profile', sa.Column('timeline_days', sa.Integer()))
    op.add_column('investor_profile', sa.Column('risk_tolerance', sa.String(length=30)))

    # Verification
    op.add_column('investor_profile', sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'))


def downgrade():
    op.drop_column('investor_profile', 'is_verified')
    op.drop_column('investor_profile', 'risk_tolerance')
    op.drop_column('investor_profile', 'timeline_days')
    op.drop_column('investor_profile', 'min_roi')
    op.drop_column('investor_profile', 'min_cash_on_cash')
    op.drop_column('investor_profile', 'capital_available')
    op.drop_column('investor_profile', 'max_sqft')
    op.drop_column('investor_profile', 'min_sqft')
    op.drop_column('investor_profile', 'max_price')
    op.drop_column('investor_profile', 'min_price')
    op.drop_column('investor_profile', 'property_types')
    op.drop_column('investor_profile', 'target_markets')
    op.drop_column('investor_profile', 'experience_level')
    op.drop_column('investor_profile', 'strategy')
    op.drop_column('investor_profile', 'credit_score')
    op.drop_column('investor_profile', 'annual_income')
    op.drop_column('investor_profile', 'employment_status')
    op.drop_column('investor_profile', 'zip_code')
    op.drop_column('investor_profile', 'state')
    op.drop_column('investor_profile', 'city')
    op.drop_column('investor_profile', 'address')
