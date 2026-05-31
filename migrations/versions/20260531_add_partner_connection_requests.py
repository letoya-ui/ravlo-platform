"""create partner_connection_requests table if not exists

Revision ID: 20260531pcr01
Revises: 20260531epl01
Create Date: 2026-05-31

- partner_connection_requests table was never created via migration; this
  creates it idempotently so flask db upgrade makes production consistent.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision = '20260531pcr01'
down_revision = '20260531epl01'
branch_labels = None
depends_on = None


def upgrade():
    inspector = Inspector.from_engine(op.get_bind())
    if 'partner_connection_requests' in inspector.get_table_names():
        return

    op.create_table(
        'partner_connection_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('borrower_user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('investor_user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('borrower_profile_id', sa.Integer(), sa.ForeignKey('borrower_profile.id'), nullable=True),
        sa.Column('investor_profile_id', sa.Integer(), sa.ForeignKey('investor_profile.id'), nullable=True),
        sa.Column('property_id', sa.Integer(), sa.ForeignKey('property.id'), nullable=True),
        sa.Column('lead_id', sa.Integer(), sa.ForeignKey('lead.id'), nullable=True),
        sa.Column('deal_id', sa.Integer(), sa.ForeignKey('deals.id'), nullable=True),
        sa.Column('saved_property_id', sa.Integer(), sa.ForeignKey('saved_properties.id'), nullable=True),
        sa.Column('partner_id', sa.Integer(), sa.ForeignKey('partners.id'), nullable=True),
        sa.Column('external_partner_lead_id', sa.Integer(), nullable=True),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('source', sa.String(30), server_default='internal'),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('responded_at', sa.DateTime(), nullable=True),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('budget', sa.Float(), nullable=True),
        sa.Column('timeline', sa.String(120), nullable=True),
        sa.Column('priority', sa.String(30), nullable=True),
        sa.Column('request_type', sa.String(50), nullable=True),
        sa.Column('internal_notes', sa.Text(), nullable=True),
    )
    op.create_index('ix_pcr_investor_user_id', 'partner_connection_requests', ['investor_user_id'])
    op.create_index('ix_pcr_partner_id', 'partner_connection_requests', ['partner_id'])


def downgrade():
    op.drop_index('ix_pcr_partner_id', table_name='partner_connection_requests')
    op.drop_index('ix_pcr_investor_user_id', table_name='partner_connection_requests')
    op.drop_table('partner_connection_requests')
