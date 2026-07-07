"""Add origin + external_ref to bid_suggestions for auto-discovery

Revision ID: 20260707bd01
Revises: 20260707bkfl
Create Date: 2026-07-07 01:30:00.000000

Adds two columns to ``bid_suggestions`` so the construction bid feed can
auto-import opportunities from public procurement sources (e.g. SAM.gov):

* ``origin``       — "manual" for hand-entered rows, otherwise the adapter
                     name ("samgov", ...).
* ``external_ref`` — stable per-source id ("samgov:<noticeId>") used to
                     dedupe repeated imports.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260707bd01"
down_revision = "20260707bkfl"
branch_labels = None
depends_on = None


def _has_column(table, column):
    try:
        insp = sa.inspect(op.get_bind())
        return any(c["name"] == column for c in insp.get_columns(table))
    except Exception:
        return False


def _has_index(table, index):
    try:
        insp = sa.inspect(op.get_bind())
        return any(ix["name"] == index for ix in insp.get_indexes(table))
    except Exception:
        return False


def upgrade():
    if not _has_column("bid_suggestions", "origin"):
        op.add_column(
            "bid_suggestions",
            sa.Column(
                "origin", sa.String(length=30),
                nullable=False, server_default="manual",
            ),
        )
    if not _has_column("bid_suggestions", "external_ref"):
        op.add_column(
            "bid_suggestions",
            sa.Column("external_ref", sa.String(length=255), nullable=True),
        )
    if not _has_index("bid_suggestions", "ix_bid_suggestions_external_ref"):
        op.create_index(
            "ix_bid_suggestions_external_ref",
            "bid_suggestions",
            ["external_ref"],
        )


def downgrade():
    if _has_index("bid_suggestions", "ix_bid_suggestions_external_ref"):
        try:
            op.drop_index(
                "ix_bid_suggestions_external_ref", table_name="bid_suggestions"
            )
        except Exception:
            pass
    for col in ("external_ref", "origin"):
        if _has_column("bid_suggestions", col):
            op.drop_column("bid_suggestions", col)
