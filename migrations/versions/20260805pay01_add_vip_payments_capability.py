"""Add Payments capability: Stripe Connect accounts + payment requests

Revision ID: 20260805pay01
Revises: 20260723sp02
Create Date: 2026-08-05 00:00:00.000000

Adds payment_accounts and payment_requests -- a workspace-type-agnostic
Payments capability (Stripe Connect deposits/invoices) usable by any
vertical (realtor/insurance/contractor VIPProfile rows, salon
StylistProfile rows, etc.). The owner is referenced polymorphically via
(owner_type, owner_id) rather than a foreign key into any one vertical's
profile table, so this schema never needs to change to onboard a new
workspace type -- see LoanMVP/models/payment_models.py and
LoanMVP/services/payments_service.py.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260805pay01"
down_revision = "20260723sp02"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_table(table):
    try:
        return _insp().has_table(table)
    except Exception:
        return False


def upgrade():
    if not _has_table("payment_accounts"):
        op.create_table(
            "payment_accounts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner_type", sa.String(50), nullable=False),
            sa.Column("owner_id", sa.Integer(), nullable=False),
            sa.Column("stripe_connect_account_id", sa.String(255), nullable=True),
            sa.Column(
                "stripe_connect_charges_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
            sa.Column(
                "stripe_connect_payouts_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
            sa.Column("stripe_connect_onboarded_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index(
            "ux_payment_accounts_owner", "payment_accounts", ["owner_type", "owner_id"], unique=True
        )

    if not _has_table("payment_requests"):
        op.create_table(
            "payment_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "payment_account_id",
                sa.Integer(),
                sa.ForeignKey("payment_accounts.id", name="fk_payment_requests_account_id"),
                nullable=False,
            ),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("amount_cents", sa.Integer(), nullable=False),
            sa.Column("client_name", sa.String(255), nullable=True),
            sa.Column("client_email", sa.String(255), nullable=True),
            sa.Column("client_phone", sa.String(50), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("stripe_checkout_session_id", sa.String(255), nullable=True),
            sa.Column("stripe_payment_intent_id", sa.String(255), nullable=True),
            sa.Column("confirmation_token", sa.String(64), nullable=False),
            sa.Column("paid_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index(
            "ix_payment_requests_account_id", "payment_requests", ["payment_account_id"]
        )
        op.create_index(
            "ix_payment_requests_confirmation_token",
            "payment_requests",
            ["confirmation_token"],
            unique=True,
        )


def downgrade():
    if _has_table("payment_requests"):
        op.drop_index("ix_payment_requests_confirmation_token", table_name="payment_requests")
        op.drop_index("ix_payment_requests_account_id", table_name="payment_requests")
        op.drop_table("payment_requests")

    if _has_table("payment_accounts"):
        op.drop_index("ux_payment_accounts_owner", table_name="payment_accounts")
        op.drop_table("payment_accounts")
