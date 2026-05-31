"""create external_partner_leads table if not exists

Revision ID: 20260531epl01
Revises: 20260530apr01
Create Date: 2026-05-31

- external_partner_leads stores Google/manual partner leads saved by investors
- required before partner_connection_requests due to FK dependency
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision = '20260531epl01'
down_revision = '20260530apr01'
branch_labels = None
depends_on = None


def upgrade():
    inspector = Inspector.from_engine(op.get_bind())
    if 'external_partner_leads' in inspector.get_table_names():
        return

    op.create_table(
        'external_partner_leads',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('investor_profile_id', sa.Integer(), sa.ForeignKey('investor_profile.id'), nullable=True),
        sa.Column('borrower_profile_id', sa.Integer(), sa.ForeignKey('borrower_profile.id'), nullable=True),
        sa.Column('partner_id', sa.Integer(), sa.ForeignKey('partners.id'), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('business_name', sa.String(255), nullable=True),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('source', sa.String(50), nullable=True),
        sa.Column('external_id', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('website', sa.String(255), nullable=True),
        sa.Column('address', sa.String(255), nullable=True),
        sa.Column('city', sa.String(120), nullable=True),
        sa.Column('state', sa.String(20), nullable=True),
        sa.Column('zip_code', sa.String(20), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('rating', sa.Float(), server_default='0'),
        sa.Column('review_count', sa.Integer(), server_default='0'),
        sa.Column('invite_status', sa.String(30), server_default='new'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('raw_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_epl_created_by_user_id', 'external_partner_leads', ['created_by_user_id'])


def downgrade():
    op.drop_index('ix_epl_created_by_user_id', table_name='external_partner_leads')
    op.drop_table('external_partner_leads')
