"""Add brand_logo_url to companies

Revision ID: 20260719wl02
Revises: 20260719wl01
Create Date: 2026-07-19 04:30:00.000000

Adds Company.brand_logo_url -- a static-relative path to a full logo
lockup image that the sidebar renders in place of the text name/mark
entirely, when a white_label company has one set (see
LoanMVP/utils/branding.py's effective_brand()).

This is a separate migration rather than an edit to 20260719wl01
because that revision was already applied in production before this
column was added -- editing an already-applied migration file is a
no-op on redeploy, since Alembic tracks progress by revision id in
alembic_version, not by re-diffing file contents.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260719wl02"
down_revision = "20260719wl01"
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
    if not _has_column("companies", "brand_logo_url"):
        op.add_column("companies", sa.Column("brand_logo_url", sa.String(255), nullable=True))


def downgrade():
    if _has_column("companies", "brand_logo_url"):
        op.drop_column("companies", "brand_logo_url")
