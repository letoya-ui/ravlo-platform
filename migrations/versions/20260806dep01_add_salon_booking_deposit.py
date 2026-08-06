"""Add mandatory booking deposit to the Salon/Stylist vertical

Revision ID: 20260806dep01
Revises: 20260805bk01
Create Date: 2026-08-06 00:00:00.000000

Lets a stylist (e.g. GotStyles' Aisha) require clients to pay a deposit
through her own connected Stripe account before an online booking is
confirmed. Reuses the existing owner-agnostic PaymentAccount/PaymentRequest
tables from the Payments capability (payment_models.py) rather than adding
new Stripe columns here -- StylistProfile is already a supported owner_type
there. This migration only adds the stylist-side toggle/amount and the
Appointment<->PaymentRequest link.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260806dep01"
down_revision = "20260805bk01"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_column(table, column):
    try:
        return column in {c["name"] for c in _insp().get_columns(table)}
    except Exception:
        return False


def upgrade():
    if not _has_column("stylist_profile", "deposit_required"):
        op.add_column(
            "stylist_profile",
            sa.Column("deposit_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if not _has_column("stylist_profile", "deposit_amount_cents"):
        op.add_column(
            "stylist_profile", sa.Column("deposit_amount_cents", sa.Integer(), nullable=True)
        )

    if not _has_column("salon_appointments", "payment_request_id"):
        op.add_column(
            "salon_appointments",
            sa.Column("payment_request_id", sa.Integer(), nullable=True),
        )
        op.create_index(
            "ix_salon_appointments_payment_request_id",
            "salon_appointments",
            ["payment_request_id"],
        )
        op.create_foreign_key(
            "fk_appt_payment_request_id",
            "salon_appointments",
            "payment_requests",
            ["payment_request_id"],
            ["id"],
        )


def downgrade():
    if _has_column("salon_appointments", "payment_request_id"):
        op.drop_constraint("fk_appt_payment_request_id", "salon_appointments", type_="foreignkey")
        op.drop_index("ix_salon_appointments_payment_request_id", table_name="salon_appointments")
        op.drop_column("salon_appointments", "payment_request_id")

    if _has_column("stylist_profile", "deposit_amount_cents"):
        op.drop_column("stylist_profile", "deposit_amount_cents")
    if _has_column("stylist_profile", "deposit_required"):
        op.drop_column("stylist_profile", "deposit_required")
