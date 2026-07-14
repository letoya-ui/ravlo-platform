"""Add demo scheduling tables (Ravlo's own booking tool)

Revision ID: 20260714ds01
Revises: 20260714rf01
Create Date: 2026-07-14 20:00:00.000000

Adds demo_availability (a staff member's recurring weekly open hours)
and demo_bookings (a prospect's actual booked demo slot with a
specific host). Available slots on the public booking page are
computed on the fly from demo_availability minus already-booked
demo_bookings rows -- no per-slot row is pre-generated.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260714ds01"
down_revision = "20260714rf01"
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
    if not _has_table("demo_availability"):
        op.create_table(
            "demo_availability",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("host_user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
            sa.Column("day_of_week", sa.Integer(), nullable=False),
            sa.Column("start_time", sa.Time(), nullable=False),
            sa.Column("end_time", sa.Time(), nullable=False),
            sa.Column("slot_minutes", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_demo_availability_host_user_id", "demo_availability", ["host_user_id"])

    if not _has_table("demo_bookings"):
        op.create_table(
            "demo_bookings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("host_user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
            sa.Column("confirmation_token", sa.String(length=32), nullable=False),
            sa.Column("starts_at", sa.DateTime(), nullable=False),
            sa.Column("ends_at", sa.DateTime(), nullable=False),
            sa.Column("prospect_name", sa.String(length=255), nullable=False),
            sa.Column("prospect_email", sa.String(length=255), nullable=False),
            sa.Column("prospect_company", sa.String(length=255), nullable=True),
            sa.Column("prospect_phone", sa.String(length=50), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="scheduled"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("canceled_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_demo_bookings_host_user_id", "demo_bookings", ["host_user_id"])
        op.create_index("ix_demo_bookings_starts_at", "demo_bookings", ["starts_at"])
        op.create_index("ix_demo_bookings_prospect_email", "demo_bookings", ["prospect_email"])
        op.create_index(
            "ix_demo_bookings_confirmation_token", "demo_bookings", ["confirmation_token"], unique=True
        )


def downgrade():
    if _has_table("demo_bookings"):
        op.drop_index("ix_demo_bookings_confirmation_token", table_name="demo_bookings")
        op.drop_index("ix_demo_bookings_prospect_email", table_name="demo_bookings")
        op.drop_index("ix_demo_bookings_starts_at", table_name="demo_bookings")
        op.drop_index("ix_demo_bookings_host_user_id", table_name="demo_bookings")
        op.drop_table("demo_bookings")

    if _has_table("demo_availability"):
        op.drop_index("ix_demo_availability_host_user_id", table_name="demo_availability")
        op.drop_table("demo_availability")
