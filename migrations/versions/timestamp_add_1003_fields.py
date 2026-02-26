"""add 1003 fields to BorrowerProfile

Revision ID: add_1003_fields
Revises: a49f234b0769
Create Date: 2025-02-10 01:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'add_1003_fields'
down_revision = 'a49f234b0769'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('borrower_profile', sa.Column('dob', sa.Date(), nullable=True))
    op.add_column('borrower_profile', sa.Column('ssn', sa.String(length=20), nullable=True))
    op.add_column('borrower_profile', sa.Column('citizenship', sa.String(length=50), nullable=True))
    op.add_column('borrower_profile', sa.Column('marital_status', sa.String(length=50), nullable=True))
    op.add_column('borrower_profile', sa.Column('dependents', sa.Integer(), nullable=True))

    op.add_column('borrower_profile', sa.Column('years_at_job', sa.Integer(), nullable=True))
    op.add_column('borrower_profile', sa.Column('employer_phone', sa.String(length=50), nullable=True))
    op.add_column('borrower_profile', sa.Column('job_title', sa.String(length=150), nullable=True))
    op.add_column('borrower_profile', sa.Column('monthly_income_secondary', sa.Float(), nullable=True))

    op.add_column('borrower_profile', sa.Column('housing_status', sa.String(length=50), nullable=True))
    op.add_column('borrower_profile', sa.Column('monthly_housing_payment', sa.Float(), nullable=True))

    op.add_column('borrower_profile', sa.Column('bank_balance', sa.Float(), nullable=True))
    op.add_column('borrower_profile', sa.Column('assets_description', sa.Text(), nullable=True))
    op.add_column('borrower_profile', sa.Column('liabilities_description', sa.Text(), nullable=True))

    op.add_column(
        'borrower_profile',
        sa.Column('reo_properties', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    
    op.add_column(
        'borrower_profile',
        sa.Column('declarations_flags', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )


def downgrade():
    op.drop_column('borrower_profile', 'dob')
    op.drop_column('borrower_profile', 'ssn')
    op.drop_column('borrower_profile', 'citizenship')
    op.drop_column('borrower_profile', 'marital_status')
    op.drop_column('borrower_profile', 'dependents')

    op.drop_column('borrower_profile', 'years_at_job')
    op.drop_column('borrower_profile', 'employer_phone')
    op.drop_column('borrower_profile', 'job_title')
    op.drop_column('borrower_profile', 'monthly_income_secondary')

    op.drop_column('borrower_profile', 'housing_status')
    op.drop_column('borrower_profile', 'monthly_housing_payment')

    op.drop_column('borrower_profile', 'bank_balance')
    op.drop_column('borrower_profile', 'assets_description')
    op.drop_column('borrower_profile', 'liabilities_description')

    op.drop_column('borrower_profile', 'reo_properties')
    op.drop_column('borrower_profile', 'declarations_flags')
