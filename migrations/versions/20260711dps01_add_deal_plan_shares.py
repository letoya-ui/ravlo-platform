"""Add deal_plan_shares table

Revision ID: 20260711dps01
Revises: 20260707lo01
Create Date: 2026-07-11 19:00:00.000000

Adds the ``deal_plan_shares`` table -- a lightweight send-history log for
the "Send Plans" feature (investor emails a development-report PDF to a
loan officer, another investor, or anyone else). Additive only.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260711dps01"
down_revision = "20260707lo01"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_table(table):
    try:
        return _insp().has_table(table)
    except Exception:
        return False


def upgrade():
    if _has_table("deal_plan_shares"):
        return

    op.create_table(
        "deal_plan_shares",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("deal_id", sa.Integer(), sa.ForeignKey("deals.id"), nullable=False),
        sa.Column("sent_by_user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("recipient_name", sa.String(120), nullable=True),
        sa.Column("recipient_email", sa.String(255), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    with op.batch_alter_table("deal_plan_shares") as batch_op:
        batch_op.create_index("ix_deal_plan_shares_deal_id", ["deal_id"], unique=False)


def downgrade():
    op.drop_table("deal_plan_shares")
