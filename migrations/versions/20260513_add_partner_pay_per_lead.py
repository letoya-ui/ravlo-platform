"""add partner pay-per-lead columns and lead charges table

Revision ID: 20260513ppl01
Revises: f80fae86417f
Create Date: 2026-05-13 00:00:00.000000

Adds:
- partners.pay_per_lead_enabled  (Boolean, default False)
- partners.lead_price            (Float, default 25.00)
- partners.stripe_customer_id    (String, nullable)
- partners.stripe_payment_method_id (String, nullable)
- partner_lead_charges table     (tracks per-lead billing events)
"""
from alembic import op
import sqlalchemy as sa

revision = '20260513ppl01'
down_revision = 'f80fae86417f'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    p_cols = {c["name"] for c in inspector.get_columns("partners")} if inspector.has_table("partners") else set()
    with op.batch_alter_table('partners', schema=None) as batch_op:
        if 'pay_per_lead_enabled' not in p_cols:
            batch_op.add_column(sa.Column('pay_per_lead_enabled', sa.Boolean(), nullable=True))
        if 'lead_price' not in p_cols:
            batch_op.add_column(sa.Column('lead_price', sa.Float(), nullable=True))
        if 'stripe_customer_id' not in p_cols:
            batch_op.add_column(sa.Column('stripe_customer_id', sa.String(length=255), nullable=True))
        if 'stripe_payment_method_id' not in p_cols:
            batch_op.add_column(sa.Column('stripe_payment_method_id', sa.String(length=255), nullable=True))

    op.execute("UPDATE partners SET pay_per_lead_enabled = false WHERE pay_per_lead_enabled IS NULL")
    op.execute("UPDATE partners SET lead_price = 25.0 WHERE lead_price IS NULL")

    with op.batch_alter_table('partners', schema=None) as batch_op:
        batch_op.alter_column('pay_per_lead_enabled', existing_type=sa.Boolean(), nullable=False)

    if not inspector.has_table('partner_lead_charges'):
        op.create_table(
            'partner_lead_charges',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('partner_id', sa.Integer(), sa.ForeignKey('partners.id'), nullable=False),
            sa.Column('connection_request_id', sa.Integer(), sa.ForeignKey('partner_connection_requests.id'), nullable=True),
            sa.Column('amount', sa.Float(), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=True, server_default='pending'),
            sa.Column('stripe_payment_intent', sa.String(length=255), nullable=True),
            sa.Column('stripe_customer_id', sa.String(length=255), nullable=True),
            sa.Column('failure_reason', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('paid_at', sa.DateTime(), nullable=True),
        )


def downgrade():
    op.drop_table('partner_lead_charges')

    with op.batch_alter_table('partners', schema=None) as batch_op:
        batch_op.drop_column('stripe_payment_method_id')
        batch_op.drop_column('stripe_customer_id')
        batch_op.drop_column('lead_price')
        batch_op.drop_column('pay_per_lead_enabled')
