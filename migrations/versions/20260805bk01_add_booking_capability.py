"""Add Booking capability: availability + bookings

Revision ID: 20260805bk01
Revises: 20260805net01
Create Date: 2026-08-05 00:00:00.000000

Adds a workspace-type-agnostic Booking capability (public scheduling)
for VIP workspaces that have no booking system today (realtor,
insurance, contractor) -- starting with Mason-Fultz's quote-visit
scheduling. Deliberately separate from the Salon/Stylist vertical's own
existing Appointment/SalonAvailability tables, which stay as-is.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260805bk01"
down_revision = "20260805net01"
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
    if not _has_table("booking_availabilities"):
        op.create_table(
            "booking_availabilities",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner_type", sa.String(50), nullable=False),
            sa.Column("owner_id", sa.Integer(), nullable=False),
            sa.Column("day_of_week", sa.Integer(), nullable=False),
            sa.Column("start_time", sa.Time(), nullable=False),
            sa.Column("end_time", sa.Time(), nullable=False),
            sa.Column("slot_minutes", sa.Integer(), nullable=False, server_default="60"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index(
            "ix_booking_availabilities_owner_id", "booking_availabilities", ["owner_id"]
        )

    if not _has_table("bookings"):
        op.create_table(
            "bookings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner_type", sa.String(50), nullable=False),
            sa.Column("owner_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(255), nullable=True),
            sa.Column("starts_at", sa.DateTime(), nullable=False),
            sa.Column("ends_at", sa.DateTime(), nullable=False),
            sa.Column("client_name", sa.String(255), nullable=False),
            sa.Column("client_email", sa.String(255), nullable=True),
            sa.Column("client_phone", sa.String(50), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
            sa.Column("confirmation_token", sa.String(32), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_bookings_owner_id", "bookings", ["owner_id"])
        op.create_index("ix_bookings_starts_at", "bookings", ["starts_at"])
        op.create_index(
            "ix_bookings_confirmation_token", "bookings", ["confirmation_token"], unique=True
        )


def downgrade():
    if _has_table("bookings"):
        op.drop_index("ix_bookings_confirmation_token", table_name="bookings")
        op.drop_index("ix_bookings_starts_at", table_name="bookings")
        op.drop_index("ix_bookings_owner_id", table_name="bookings")
        op.drop_table("bookings")

    if _has_table("booking_availabilities"):
        op.drop_index("ix_booking_availabilities_owner_id", table_name="booking_availabilities")
        op.drop_table("booking_availabilities")
