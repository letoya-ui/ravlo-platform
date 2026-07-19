"""Replace flat AE commission fields with a commission ledger

Revision ID: 20260718ae04
Revises: 20260718ae03
Create Date: 2026-07-18 23:30:00.000000

Setup-fee commission and first-year monthly commission are paid at
different rates and on different schedules (setup pays once at signing,
monthly commission accrues for 12 months, optional renewal commission
accrues indefinitely thereafter) -- a single flat commission_rate/
commission_amount/commission_status on business_inquiries can't represent
that, so this replaces those three columns with a new
ae_commission_entries ledger table (one row per payout) plus the rate/
fee columns locked in at signing. BusinessInquiry.commission_amount and
.commission_status become computed Python properties over the ledger
instead of stored columns.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260718ae04"
down_revision = "20260718ae03"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_column(table, column):
    try:
        return any(c["name"] == column for c in _insp().get_columns(table))
    except Exception:
        return False


def _has_table(table):
    try:
        return table in _insp().get_table_names()
    except Exception:
        return False


_NEW_COLUMNS = [
    ("signed_setup_fee", sa.Numeric(12, 2)),
    ("signed_monthly_fee", sa.Numeric(12, 2)),
    ("setup_commission_rate", sa.Numeric(5, 4)),
    ("monthly_commission_rate", sa.Numeric(5, 4)),
    ("renewal_commission_rate", sa.Numeric(5, 4)),
]

_OLD_COLUMNS = ["commission_rate", "commission_amount", "commission_status"]


def upgrade():
    for name, col_type in _NEW_COLUMNS:
        if not _has_column("business_inquiries", name):
            op.add_column("business_inquiries", sa.Column(name, col_type, nullable=True))

    for name in _OLD_COLUMNS:
        if _has_column("business_inquiries", name):
            with op.batch_alter_table("business_inquiries", schema=None) as batch_op:
                batch_op.drop_column(name)

    if not _has_table("ae_commission_entries"):
        op.create_table(
            "ae_commission_entries",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("deal_id", sa.Integer(), sa.ForeignKey("business_inquiries.id"), nullable=False),
            sa.Column("entry_type", sa.String(20), nullable=False),
            sa.Column("period_number", sa.Integer(), nullable=True),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("paid_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index(
            "ix_ae_commission_entries_deal_id", "ae_commission_entries", ["deal_id"]
        )


def downgrade():
    if _has_table("ae_commission_entries"):
        try:
            op.drop_index("ix_ae_commission_entries_deal_id", table_name="ae_commission_entries")
        except Exception:
            pass
        op.drop_table("ae_commission_entries")

    for name in _OLD_COLUMNS:
        if not _has_column("business_inquiries", name):
            col_type = {
                "commission_rate": sa.Numeric(5, 4),
                "commission_amount": sa.Numeric(12, 2),
                "commission_status": sa.String(20),
            }[name]
            op.add_column("business_inquiries", sa.Column(name, col_type, nullable=True))

    for name, _col_type in reversed(_NEW_COLUMNS):
        if _has_column("business_inquiries", name):
            op.drop_column("business_inquiries", name)
