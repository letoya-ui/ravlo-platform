"""Add public_token to elena_listings for self-serve listing landing pages

Revision ID: 20260813lp01
Revises: 20260806dep01
Create Date: 2026-08-13 00:00:00.000000

Realtors on a paid Ravlo Partner plan get unlimited landing pages for
their listings -- one public, unguessable-token URL per ElenaListing,
generated lazily from the listing detail dashboard. See
public_pages.py's listing_landing()/listing_landing_inquire().
"""

from alembic import op
import sqlalchemy as sa


revision = "20260813lp01"
down_revision = "20260806dep01"
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
    if not _has_column("elena_listings", "public_token"):
        op.add_column(
            "elena_listings", sa.Column("public_token", sa.String(32), nullable=True)
        )
        op.create_index(
            "ix_elena_listings_public_token", "elena_listings", ["public_token"], unique=True
        )


def downgrade():
    if _has_column("elena_listings", "public_token"):
        op.drop_index("ix_elena_listings_public_token", table_name="elena_listings")
        op.drop_column("elena_listings", "public_token")
