"""Add Quote Worksheet discovery fields to business_inquiries

Revision ID: 20260718ae03
Revises: 20260718ae02
Create Date: 2026-07-18 21:00:00.000000

Adds the discovery-call fields from the Ravlo Pricing Playbook's Quote
Worksheet (industry, users, workspaces, branding, implementation
complexity, training required) to the existing business_inquiries table.
Mirrors 20260718ae02_add_ae_pricing_quote_fields.py's plain-columns
pattern for the same table.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260718ae03"
down_revision = "20260718ae02"
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
    ("worksheet_industry", sa.String(120)),
    ("worksheet_user_count", sa.Integer()),
    ("worksheet_workspace_count", sa.Integer()),
    ("worksheet_branding", sa.String(20)),
    ("worksheet_implementation_complexity", sa.String(20)),
    ("worksheet_training_required", sa.Boolean()),
]


def upgrade():
    for name, col_type in _PLAIN_COLUMNS:
        if not _has_column("business_inquiries", name):
            op.add_column("business_inquiries", sa.Column(name, col_type, nullable=True))


def downgrade():
    for name, _col_type in reversed(_PLAIN_COLUMNS):
        if _has_column("business_inquiries", name):
            op.drop_column("business_inquiries", name)
