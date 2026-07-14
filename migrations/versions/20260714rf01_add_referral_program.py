"""Add referral program (personal referral links + attribution)

Revision ID: 20260714rf01
Revises: 20260714pm01
Create Date: 2026-07-14 18:00:00.000000

Adds User.referral_code (a user's personal share code, generated lazily
on first use rather than backfilled here) and the referrals table, which
records attribution when someone signs up through a user's /r/<code>
link. Independent of BusinessInquiry (the existing /refer page's manual
"email us your friend" form) -- that stays a sales-inbox lead, this is an
automated, code-based attribution record.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260714rf01"
down_revision = "20260714pm01"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_table(table):
    try:
        return _insp().has_table(table)
    except Exception:
        return False


def _has_column(table, column):
    try:
        return any(c["name"] == column for c in _insp().get_columns(table))
    except Exception:
        return False


def upgrade():
    if not _has_column("user", "referral_code"):
        with op.batch_alter_table("user", schema=None) as batch_op:
            batch_op.add_column(sa.Column("referral_code", sa.String(length=16), nullable=True))
            batch_op.create_index("ix_user_referral_code", ["referral_code"], unique=True)

    if not _has_table("referrals"):
        op.create_table(
            "referrals",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("referrer_user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
            sa.Column("referred_user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
            sa.Column("referral_code", sa.String(length=16), nullable=False),
            sa.Column("referred_email", sa.String(length=120), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="signed_up"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("converted_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_referrals_referrer_user_id", "referrals", ["referrer_user_id"])
        op.create_index("ix_referrals_referred_user_id", "referrals", ["referred_user_id"])
        op.create_index("ix_referrals_referral_code", "referrals", ["referral_code"])


def downgrade():
    if _has_table("referrals"):
        op.drop_index("ix_referrals_referral_code", table_name="referrals")
        op.drop_index("ix_referrals_referred_user_id", table_name="referrals")
        op.drop_index("ix_referrals_referrer_user_id", table_name="referrals")
        op.drop_table("referrals")

    if _has_column("user", "referral_code"):
        with op.batch_alter_table("user", schema=None) as batch_op:
            batch_op.drop_index("ix_user_referral_code")
            batch_op.drop_column("referral_code")
