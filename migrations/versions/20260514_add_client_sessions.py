"""add vip_client_sessions table

Revision ID: 20260514cs01
Revises: 20260514stripe01
Create Date: 2026-05-14

Adds:
- vip_client_sessions table  (Property Brothers client-meeting sessions)
  Stores property address, room-by-room renovation scope (JSON), commission
  tier selection, and estimated sale price for each client session John runs.
"""
from alembic import op
import sqlalchemy as sa

revision = '20260514cs01'
down_revision = '20260514stripe01'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not inspector.has_table('vip_client_sessions'):
        op.create_table(
            'vip_client_sessions',
            sa.Column('id',               sa.Integer(),     primary_key=True),
            sa.Column('vip_profile_id',   sa.Integer(),     sa.ForeignKey('vip_profiles.id'), nullable=False),

            # Client / property
            sa.Column('client_name',      sa.String(255),   nullable=True),
            sa.Column('client_email',     sa.String(255),   nullable=True),
            sa.Column('client_phone',     sa.String(50),    nullable=True),
            sa.Column('property_address', sa.String(500),   nullable=False),
            sa.Column('property_zip',     sa.String(20),    nullable=True),
            sa.Column('property_state',   sa.String(10),    nullable=True),
            sa.Column('bedrooms',         sa.Integer(),     nullable=True),
            sa.Column('bathrooms',        sa.String(10),    nullable=True),
            sa.Column('sqft',             sa.Integer(),     nullable=True),

            # Scope JSON
            sa.Column('scope_json',       sa.Text(),        nullable=True),

            # Commission
            sa.Column('commission_tier',  sa.String(20),    nullable=True, server_default='1.5'),
            sa.Column('commission_label', sa.String(80),    nullable=True),
            sa.Column('commission_pct',   sa.String(20),    nullable=True, server_default='1.5'),
            sa.Column('sale_price',       sa.Integer(),     nullable=True),

            sa.Column('notes',            sa.Text(),        nullable=True),
            sa.Column('status',           sa.String(30),    nullable=False, server_default='draft'),

            sa.Column('created_at',       sa.DateTime(),    nullable=True),
            sa.Column('updated_at',       sa.DateTime(),    nullable=True),
        )

    # Indexes
    cs_idxs = set()
    if inspector.has_table('vip_client_sessions'):
        cs_idxs = {i['name'] for i in inspector.get_indexes('vip_client_sessions')}

    if 'ix_vip_client_sessions_vip_profile_id' not in cs_idxs:
        op.create_index(
            'ix_vip_client_sessions_vip_profile_id',
            'vip_client_sessions', ['vip_profile_id'],
        )
    if 'ix_vip_client_sessions_status' not in cs_idxs:
        op.create_index(
            'ix_vip_client_sessions_status',
            'vip_client_sessions', ['status'],
        )


def downgrade():
    op.drop_index('ix_vip_client_sessions_status',          table_name='vip_client_sessions')
    op.drop_index('ix_vip_client_sessions_vip_profile_id',  table_name='vip_client_sessions')
    op.drop_table('vip_client_sessions')
