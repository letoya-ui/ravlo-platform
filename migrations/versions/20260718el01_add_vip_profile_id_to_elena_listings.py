"""Add vip_profile_id to elena_listings

Revision ID: 20260718el01
Revises: 20260714nt01
Create Date: 2026-07-18 00:00:00.000000

ElenaListing had no ownership column at all -- only a loose "market"
text field. Any realtor whose VIPProfile had no configured market saw
EVERY listing on the platform (and its auto-generated ElenaFlyer),
including other partners' demo/test data, since the dashboard's listing
queries had nothing to scope on besides market. Adds vip_profile_id so
each listing belongs to a specific partner; existing rows (and MLS-feed
imports, which aren't any one partner's own listing) stay NULL and are
now excluded from every "my listings" view.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260718el01"
down_revision = "20260714nt01"
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
    with op.batch_alter_table("elena_listings", schema=None) as batch_op:
        if not _has_column("elena_listings", "vip_profile_id"):
            batch_op.add_column(sa.Column("vip_profile_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_elena_listings_vip_profile_id", "vip_profiles", ["vip_profile_id"], ["id"]
            )
            batch_op.create_index("ix_elena_listings_vip_profile_id", ["vip_profile_id"])


def downgrade():
    with op.batch_alter_table("elena_listings", schema=None) as batch_op:
        if _has_column("elena_listings", "vip_profile_id"):
            batch_op.drop_index("ix_elena_listings_vip_profile_id")
            batch_op.drop_constraint("fk_elena_listings_vip_profile_id", type_="foreignkey")
            batch_op.drop_column("vip_profile_id")
