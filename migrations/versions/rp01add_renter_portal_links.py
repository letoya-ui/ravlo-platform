"""Add renter portal link columns to property_tenants / property_rent_payments

Revision ID: rp01add
Revises: 20260813nw02
Create Date: 2026-08-20 00:00:00.000000

Renters Portal: tenants can now log in to make payments, view payment
history, and request maintenance. property_tenants.user_id links a Tenant
record to the User account created when they accept their portal invite
(nullable/unique -- most Tenant rows have no portal login).
property_rent_payments.payment_request_id links a rent period to the
generic Stripe Connect PaymentRequest created when a tenant pays online,
mirroring Appointment.payment_request_id for salon deposits.
"""

from alembic import op
import sqlalchemy as sa


revision = "rp01add"
down_revision = "20260813nw02"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_column(table, column):
    try:
        return column in {c["name"] for c in _insp().get_columns(table)}
    except Exception:
        return False


def _has_index(table, index_name):
    try:
        return index_name in {i["name"] for i in _insp().get_indexes(table)}
    except Exception:
        return False


def upgrade():
    if not _has_column("property_tenants", "user_id"):
        op.add_column(
            "property_tenants",
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        )
    if not _has_index("property_tenants", "ix_property_tenants_user_id"):
        op.create_index(
            "ix_property_tenants_user_id", "property_tenants", ["user_id"], unique=True
        )

    if not _has_column("property_rent_payments", "payment_request_id"):
        op.add_column(
            "property_rent_payments",
            sa.Column(
                "payment_request_id", sa.Integer(), sa.ForeignKey("payment_requests.id"), nullable=True
            ),
        )
    if not _has_index("property_rent_payments", "ix_property_rent_payments_payment_request_id"):
        op.create_index(
            "ix_property_rent_payments_payment_request_id",
            "property_rent_payments",
            ["payment_request_id"],
        )


def downgrade():
    if _has_index("property_rent_payments", "ix_property_rent_payments_payment_request_id"):
        op.drop_index("ix_property_rent_payments_payment_request_id", table_name="property_rent_payments")
    if _has_column("property_rent_payments", "payment_request_id"):
        op.drop_column("property_rent_payments", "payment_request_id")

    if _has_index("property_tenants", "ix_property_tenants_user_id"):
        op.drop_index("ix_property_tenants_user_id", table_name="property_tenants")
    if _has_column("property_tenants", "user_id"):
        op.drop_column("property_tenants", "user_id")
