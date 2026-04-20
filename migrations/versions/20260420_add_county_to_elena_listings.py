"""Add county column to elena_listings

Revision ID: 20260420r03
Revises: 20260420r02
Create Date: 2026-04-20 11:30:00.000000

Adds a ``county`` column to the ``elena_listings`` table so realtors can
record (and search by) county on the Properties page.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260420r03"
down_revision = "20260420r02"
branch_labels = None
depends_on = None


def _has_column(table, column):
    try:
        insp = sa.inspect(op.get_bind())
        return any(c["name"] == column for c in insp.get_columns(table))
    except Exception:
        return False


def upgrade():
    if not _has_column("elena_listings", "county"):
        op.add_column(
            "elena_listings",
            sa.Column("county", sa.String(length=120), nullable=True),
        )
        op.create_index(
            "ix_elena_listings_county",
            "elena_listings",
            ["county"],
        )


def downgrade():
    if _has_column("elena_listings", "county"):
        try:
            op.drop_index("ix_elena_listings_county", table_name="elena_listings")
        except Exception:
            pass
        op.drop_column("elena_listings", "county")
