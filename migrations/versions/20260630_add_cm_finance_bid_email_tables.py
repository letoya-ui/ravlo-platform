"""Add cm_finance_entries, contractor_bid_opportunities, user_email_connections, challenge_enrollments tables

Revision ID: 20260630fin01
Revises: e1f2a3b4c5d6
Create Date: 2026-06-30 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '20260630fin01'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = inspector.get_table_names()

    if 'cm_finance_entries' not in existing:
        op.create_table(
            'cm_finance_entries',
            sa.Column('id',            sa.Integer(),     primary_key=True),
            sa.Column('created_by_id', sa.Integer(),     sa.ForeignKey('user.id'), nullable=True),
            sa.Column('division',      sa.String(50),    nullable=False, server_default='construction'),
            sa.Column('entry_type',    sa.String(10),    nullable=False),
            sa.Column('category',      sa.String(100),   nullable=True),
            sa.Column('description',   sa.String(255),   nullable=True),
            sa.Column('amount',        sa.Float(),       nullable=False),
            sa.Column('entry_date',    sa.Date(),        nullable=False),
            sa.Column('project_name',  sa.String(255),   nullable=True),
            sa.Column('notes',         sa.Text(),        nullable=True),
            sa.Column('created_at',    sa.DateTime(),    nullable=True),
        )

    if 'contractor_bid_opportunities' not in existing:
        op.create_table(
            'contractor_bid_opportunities',
            sa.Column('id',              sa.Integer(),   primary_key=True),
            sa.Column('partner_id',      sa.Integer(),   sa.ForeignKey('partners.id'), nullable=False, index=True),
            sa.Column('project_name',    sa.String(255), nullable=False),
            sa.Column('source',          sa.String(120), nullable=True),
            sa.Column('category',        sa.String(100), nullable=True),
            sa.Column('location',        sa.String(255), nullable=True),
            sa.Column('estimated_value', sa.Float(),     nullable=True),
            sa.Column('bid_deadline',    sa.DateTime(),  nullable=True),
            sa.Column('notes',           sa.Text(),      nullable=True),
            sa.Column('status',          sa.String(50),  nullable=False, server_default='reviewing'),
            sa.Column('created_at',      sa.DateTime(),  nullable=True),
            sa.Column('updated_at',      sa.DateTime(),  nullable=True),
        )

    if 'user_email_connections' not in existing:
        op.create_table(
            'user_email_connections',
            sa.Column('id',             sa.Integer(),    primary_key=True),
            sa.Column('user_id',        sa.Integer(),    sa.ForeignKey('user.id'), nullable=False, unique=True),
            sa.Column('provider',       sa.String(20),   nullable=False, server_default='gmail'),
            sa.Column('email_address',  sa.String(255),  nullable=True),
            sa.Column('access_token',   sa.Text(),       nullable=True),
            sa.Column('refresh_token',  sa.Text(),       nullable=True),
            sa.Column('token_expiry',   sa.DateTime(),   nullable=True),
            sa.Column('connected_at',   sa.DateTime(),   nullable=True),
            sa.Column('last_synced_at', sa.DateTime(),   nullable=True),
        )


    if 'challenge_enrollments' not in existing:
        op.create_table(
            'challenge_enrollments',
            sa.Column('id',          sa.Integer(),    primary_key=True),
            sa.Column('user_id',     sa.Integer(),    sa.ForeignKey('user.id'), nullable=False),
            sa.Column('slug',        sa.String(50),   nullable=False),
            sa.Column('enrolled_at', sa.DateTime(),   nullable=True),
        )


def downgrade():
    op.drop_table('challenge_enrollments')
    op.drop_table('user_email_connections')
    op.drop_table('contractor_bid_opportunities')
    op.drop_table('cm_finance_entries')
