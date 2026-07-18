"""Add Ravlo Pricing Playbook quote fields to business_inquiries

Revision ID: 20260718ae02
Revises: 20260718el01
Create Date: 2026-07-18 20:00:00.000000

Adds the AE quote-calculator columns: which rate-card plan was quoted,
list vs. discounted pricing, the special-deal flags that factor into the
discount-approval rules, and the resulting approval level/status. Mirrors
20260713ae01_add_account_executive_deal_fields.py's plain-columns-plus-FK
pattern for the same table.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260718ae02"
down_revision = "20260718el01"
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
    ("pricing_plan", sa.String(30)),
    ("enterprise_user_count", sa.Integer()),
    ("list_setup_fee", sa.Numeric(12, 2)),
    ("list_monthly_fee", sa.Numeric(12, 2)),
    ("discount_percent", sa.Numeric(5, 2)),
    ("setup_fee_waived", sa.Numeric(12, 2)),
    ("is_white_label", sa.Boolean()),
    ("is_custom_development", sa.Boolean()),
    ("is_multi_year", sa.Boolean()),
    ("is_strategic_partnership", sa.Boolean()),
    ("approval_level_required", sa.String(20)),
    ("approval_status", sa.String(20)),
    ("approved_at", sa.DateTime()),
]


def upgrade():
    for name, col_type in _PLAIN_COLUMNS:
        if not _has_column("business_inquiries", name):
            op.add_column("business_inquiries", sa.Column(name, col_type, nullable=True))

    if not _has_column("business_inquiries", "approved_by_id"):
        with op.batch_alter_table("business_inquiries", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "approved_by_id",
                    sa.Integer(),
                    sa.ForeignKey("user.id", name="fk_business_inquiries_approved_by"),
                    nullable=True,
                )
            )

    if _has_column("business_inquiries", "approval_status"):
        op.execute(
            "UPDATE business_inquiries SET approval_status = 'not_required' WHERE approval_status IS NULL"
        )


def downgrade():
    if _has_column("business_inquiries", "approved_by_id"):
        with op.batch_alter_table("business_inquiries", schema=None) as batch_op:
            batch_op.drop_column("approved_by_id")

    for name, _col_type in reversed(_PLAIN_COLUMNS):
        if _has_column("business_inquiries", name):
            op.drop_column("business_inquiries", name)
