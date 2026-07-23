"""Add address to stylist_profile

Revision ID: 20260723sp02
Revises: 20260723sp01
Create Date: 2026-07-23 01:00:00.000000

Adds a physical street address to stylist_profile, shown on the public
landing/booking pages for salons with a walk-in location (clients travel
to the shop, unlike Ravlo's own demo-scheduling which is remote).
"""

from alembic import op
import sqlalchemy as sa


revision = "20260723sp02"
down_revision = "20260723sp01"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_column(table, column):
    try:
        return any(c["name"] == column for c in _insp().get_columns(table))
    except Exception:
        return False


def upgrade():
    if not _has_column("stylist_profile", "address"):
        op.add_column("stylist_profile", sa.Column("address", sa.String(255), nullable=True))


def downgrade():
    if _has_column("stylist_profile", "address"):
        op.drop_column("stylist_profile", "address")
