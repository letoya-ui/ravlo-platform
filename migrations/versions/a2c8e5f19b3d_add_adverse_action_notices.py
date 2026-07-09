"""add adverse_action_notices table

Revision ID: a2c8e5f19b3d
Revises: f3a7c9e21b4d
Create Date: 2026-07-09 15:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'a2c8e5f19b3d'
down_revision = 'f3a7c9e21b4d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'adverse_action_notices',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('loan_id', sa.Integer(), sa.ForeignKey('loan_application.id'), nullable=False),
        sa.Column('borrower_profile_id', sa.Integer(), sa.ForeignKey('borrower_profile.id'), nullable=False),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=True),
        sa.Column('reasons', sa.Text(), nullable=True),
        sa.Column('notice_html', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('email_sent', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index('ix_adverse_action_notices_loan_id', 'adverse_action_notices', ['loan_id'])
    op.create_index('ix_adverse_action_notices_borrower_profile_id', 'adverse_action_notices', ['borrower_profile_id'])
    op.create_index('ix_adverse_action_notices_company_id', 'adverse_action_notices', ['company_id'])


def downgrade():
    op.drop_index('ix_adverse_action_notices_company_id', table_name='adverse_action_notices')
    op.drop_index('ix_adverse_action_notices_borrower_profile_id', table_name='adverse_action_notices')
    op.drop_index('ix_adverse_action_notices_loan_id', table_name='adverse_action_notices')
    op.drop_table('adverse_action_notices')
