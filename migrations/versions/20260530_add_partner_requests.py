"""add partner_requests table

Revision ID: 20260530apr01
Revises: b2c3d4e5f6a7
Create Date: 2026-05-30

- partner_requests table for marketplace-originated service requests
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision = '20260530apr01'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    inspector = Inspector.from_engine(op.get_bind())
    if 'partner_requests' not in inspector.get_table_names():
        op.create_table(
            'partner_requests',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('investor_user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=True),
            sa.Column('investor_profile_id', sa.Integer(), sa.ForeignKey('investor_profile.id'), nullable=True),
            sa.Column('partner_id', sa.Integer(), sa.ForeignKey('partners.id'), nullable=True),
            sa.Column('deal_id', sa.Integer(), sa.ForeignKey('deals.id'), nullable=True),
            sa.Column('saved_property_id', sa.Integer(), sa.ForeignKey('saved_properties.id'), nullable=True),
            sa.Column('service_type', sa.String(100), nullable=False),
            sa.Column('city', sa.String(100), nullable=True),
            sa.Column('state', sa.String(10), nullable=True),
            sa.Column('zip_code', sa.String(20), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('request_status', sa.String(30), server_default='requested'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('ix_partner_requests_investor_user_id', 'partner_requests', ['investor_user_id'])


def downgrade():
    op.drop_index('ix_partner_requests_investor_user_id', table_name='partner_requests')
    op.drop_table('partner_requests')
