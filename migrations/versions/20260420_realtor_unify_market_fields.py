"""Realtor unify — add market column to elena_listings and vip_income.status

Revision ID: 20260420r01
Revises: 20260417elena01
Create Date: 2026-04-20 00:00:00.000000

Adds:
- ``elena_listings.market`` (per-listing market label for the multi-market
  realtor dashboard; existing code already queries this column).
- ``vip_income.status`` (pending / received / voided — lets Finance track
  projected commission income from closings/appointments).

Both columns are additive and nullable (or have defaults), so this migration
is safe on existing data and fully reversible.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260420r01"
down_revision = "20260417elena01"
branch_labels = None
depends_on = None


def _has_column(table, column):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    try:
        cols = {c["name"] for c in insp.get_columns(table)}
    except Exception:
        return False
    return column in cols


def upgrade():
    if not _has_column("elena_listings", "market"):
        with op.batch_alter_table("elena_listings") as batch:
            batch.add_column(sa.Column("market", sa.String(length=100), nullable=True))

    if not _has_column("vip_income", "status"):
        with op.batch_alter_table("vip_income") as batch:
            batch.add_column(
                sa.Column(
                    "status",
                    sa.String(length=50),
                    nullable=False,
                    server_default="pending",
                )
            )


def downgrade():
    if _has_column("vip_income", "status"):
        with op.batch_alter_table("vip_income") as batch:
            batch.drop_column("status")

    if _has_column("elena_listings", "market"):
        with op.batch_alter_table("elena_listings") as batch:
            batch.drop_column("market")
