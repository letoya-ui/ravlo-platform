"""Add white-label branding fields to companies

Revision ID: 20260719wl01
Revises: 20260718ae04
Create Date: 2026-07-19 00:30:00.000000

Adds brand_name/brand_logo_initials/brand_primary_color/
brand_secondary_color/brand_accent_color/brand_tagline to companies --
only rendered in place of Ravlo's own branding when a company is on the
"white_label" subscription tier AND has actually set these (see
LoanMVP/utils/branding.py's effective_brand()).
"""

from alembic import op
import sqlalchemy as sa


revision = "20260719wl01"
down_revision = "20260718ae04"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_column(table, column):
    try:
        return any(c["name"] == column for c in _insp().get_columns(table))
    except Exception:
        return False


_PLAIN_COLUMNS = [
    ("brand_name", sa.String(120)),
    ("brand_logo_initials", sa.String(4)),
    ("brand_primary_color", sa.String(9)),
    ("brand_secondary_color", sa.String(9)),
    ("brand_accent_color", sa.String(9)),
    ("brand_tagline", sa.String(160)),
]


def upgrade():
    for name, col_type in _PLAIN_COLUMNS:
        if not _has_column("companies", name):
            op.add_column("companies", sa.Column(name, col_type, nullable=True))


def downgrade():
    for name, _col_type in reversed(_PLAIN_COLUMNS):
        if _has_column("companies", name):
            op.drop_column("companies", name)
