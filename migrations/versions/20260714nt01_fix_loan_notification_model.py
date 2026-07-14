"""Fix LoanNotification: add user_id, action_url, make loan_id nullable

Revision ID: 20260714nt01
Revises: 20260714ds01
Create Date: 2026-07-14 22:00:00.000000

LoanNotification previously required loan_id (NOT NULL) and had no
user_id column, even though notify_service.notify() already tried to
create rows keyed by user_id -- crashing immediately (TypeError: invalid
keyword argument) any time it ran, including live from
admin.approve_access_request(). Adds the missing user_id column so a
notification can target a specific user, an action_url so the
notification center can link somewhere useful, and relaxes loan_id to
nullable since most notifications (an AI summary, a demo booking, a
referral signup) aren't tied to any loan.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260714nt01"
down_revision = "20260714ds01"
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
    with op.batch_alter_table("loan_notification", schema=None) as batch_op:
        if not _has_column("loan_notification", "user_id"):
            batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_loan_notification_user_id", "user", ["user_id"], ["id"]
            )
            batch_op.create_index("ix_loan_notification_user_id", ["user_id"])

        if not _has_column("loan_notification", "action_url"):
            batch_op.add_column(sa.Column("action_url", sa.String(length=500), nullable=True))

        batch_op.alter_column("loan_id", existing_type=sa.Integer(), nullable=True)


def downgrade():
    with op.batch_alter_table("loan_notification", schema=None) as batch_op:
        batch_op.alter_column("loan_id", existing_type=sa.Integer(), nullable=False)

        if _has_column("loan_notification", "action_url"):
            batch_op.drop_column("action_url")

        if _has_column("loan_notification", "user_id"):
            batch_op.drop_index("ix_loan_notification_user_id")
            batch_op.drop_constraint("fk_loan_notification_user_id", type_="foreignkey")
            batch_op.drop_column("user_id")
