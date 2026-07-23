"""Add salon public booking page + availability

Revision ID: 20260723sp01
Revises: 20260722st01
Create Date: 2026-07-23 00:00:00.000000

Adds the columns/table needed for a stylist's public landing page and
booking calendar: branding/slug columns on stylist_profile, a
confirmation_token on salon_appointments (for the public booking
confirmation page), and a new salon_availability table (recurring weekly
booking windows, mirroring demo_availability in an earlier migration).
"""

from alembic import op
import sqlalchemy as sa


revision = "20260723sp01"
down_revision = "20260722st01"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_table(table):
    try:
        return _insp().has_table(table)
    except Exception:
        return False


def _has_column(table, column):
    try:
        return any(c["name"] == column for c in _insp().get_columns(table))
    except Exception:
        return False


def upgrade():
    if not _has_column("stylist_profile", "public_slug"):
        op.add_column("stylist_profile", sa.Column("public_slug", sa.String(255), nullable=True))
        op.create_index("ix_stylist_profile_public_slug", "stylist_profile", ["public_slug"], unique=True)
    if not _has_column("stylist_profile", "brand_color"):
        op.add_column("stylist_profile", sa.Column("brand_color", sa.String(20), nullable=True))
    if not _has_column("stylist_profile", "logo_url"):
        op.add_column("stylist_profile", sa.Column("logo_url", sa.String(255), nullable=True))
    if not _has_column("stylist_profile", "headline"):
        op.add_column("stylist_profile", sa.Column("headline", sa.String(255), nullable=True))
    if not _has_column("stylist_profile", "service_area"):
        op.add_column("stylist_profile", sa.Column("service_area", sa.String(255), nullable=True))

    if not _has_column("salon_appointments", "confirmation_token"):
        op.add_column("salon_appointments", sa.Column("confirmation_token", sa.String(32), nullable=True))
        op.create_index(
            "ix_salon_appointments_confirmation_token", "salon_appointments", ["confirmation_token"], unique=True
        )

    if not _has_table("salon_availability"):
        op.create_table(
            "salon_availability",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "stylist_id",
                sa.Integer(),
                sa.ForeignKey("stylist_profile.id", name="fk_availability_stylist_id"),
                nullable=False,
            ),
            sa.Column("day_of_week", sa.Integer(), nullable=False),
            sa.Column("start_time", sa.Time(), nullable=False),
            sa.Column("end_time", sa.Time(), nullable=False),
            sa.Column("slot_minutes", sa.Integer(), nullable=False, server_default="60"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_salon_availability_stylist_id", "salon_availability", ["stylist_id"])


def downgrade():
    if _has_table("salon_availability"):
        op.drop_table("salon_availability")

    if _has_column("salon_appointments", "confirmation_token"):
        op.drop_index("ix_salon_appointments_confirmation_token", table_name="salon_appointments")
        op.drop_column("salon_appointments", "confirmation_token")

    for column in ("service_area", "headline", "logo_url", "brand_color"):
        if _has_column("stylist_profile", column):
            op.drop_column("stylist_profile", column)
    if _has_column("stylist_profile", "public_slug"):
        op.drop_index("ix_stylist_profile_public_slug", table_name="stylist_profile")
        op.drop_column("stylist_profile", "public_slug")
