"""Rename license_applications to business_inquiries, add inquiry_type

Revision ID: 20260707binq01
Revises: 20260630surv01
Create Date: 2026-07-07 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '20260707binq01'
down_revision = '20260630surv01'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = inspector.get_table_names()

    if 'license_applications' in existing and 'business_inquiries' not in existing:
        op.rename_table('license_applications', 'business_inquiries')
        existing = sa.inspect(conn).get_table_names()

    if 'business_inquiries' not in existing:
        # Fresh database that never had license_applications -- create it directly.
        op.create_table(
            'business_inquiries',
            sa.Column('id',                  sa.Integer(),     primary_key=True),
            sa.Column('inquiry_type',        sa.String(50),    nullable=False, server_default='license_application'),
            sa.Column('company_name',        sa.String(255),   nullable=False, server_default='—'),
            sa.Column('contact_name',        sa.String(255),   nullable=False),
            sa.Column('email',               sa.String(255),   nullable=False),
            sa.Column('phone',                sa.String(50)),
            sa.Column('website',             sa.String(255)),
            sa.Column('business_type',       sa.String(100)),
            sa.Column('team_size',           sa.String(50)),
            sa.Column('plan_interest',       sa.String(100)),
            sa.Column('monthly_loan_volume', sa.String(100)),
            sa.Column('current_tools',       sa.Text()),
            sa.Column('goals',               sa.Text()),
            sa.Column('notes',               sa.Text()),
            sa.Column('status',              sa.String(50),    nullable=False, server_default='new'),
            sa.Column('created_at',          sa.DateTime(),    nullable=False),
        )
        op.create_index('ix_business_inquiries_email', 'business_inquiries', ['email'])
        return

    columns = {c['name'] for c in inspector.get_columns('business_inquiries')}
    if 'inquiry_type' not in columns:
        op.add_column(
            'business_inquiries',
            sa.Column('inquiry_type', sa.String(50), nullable=True),
        )
        conn.execute(sa.text(
            "UPDATE business_inquiries SET inquiry_type = "
            "CASE "
            "  WHEN business_type = 'contact' THEN 'contact' "
            "  WHEN business_type = 'lending_os_lead' THEN 'lending_os_lead' "
            "  ELSE 'license_application' "
            "END "
            "WHERE inquiry_type IS NULL"
        ))
        op.alter_column(
            'business_inquiries', 'inquiry_type',
            nullable=False, server_default='license_application',
        )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = inspector.get_table_names()

    if 'business_inquiries' in existing:
        columns = {c['name'] for c in inspector.get_columns('business_inquiries')}
        if 'inquiry_type' in columns:
            op.drop_column('business_inquiries', 'inquiry_type')
        if 'license_applications' not in existing:
            op.rename_table('business_inquiries', 'license_applications')
