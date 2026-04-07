"""add blocking system to user and company

Revision ID: 05cd4a43d7c4
Revises: e9472fe8ccc1
Create Date: 2026-04-07 17:30:11.602885
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "05cd4a43d7c4"
down_revision = "e9472fe8ccc1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("blocked_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("blocked_reason", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("blocked_note", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("blocked_by", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_user_blocked_by_user", "user", ["blocked_by"], ["id"])

    with op.batch_alter_table("companies", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("blocked_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("blocked_reason", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("blocked_note", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("blocked_by", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("billing_status", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("grace_period_ends_at", sa.DateTime(), nullable=True))
        batch_op.create_foreign_key("fk_companies_blocked_by_user", "user", ["blocked_by"], ["id"])


def downgrade():
    with op.batch_alter_table("companies", schema=None) as batch_op:
        batch_op.drop_constraint("fk_companies_blocked_by_user", type_="foreignkey")
        batch_op.drop_column("grace_period_ends_at")
        batch_op.drop_column("billing_status")
        batch_op.drop_column("blocked_by")
        batch_op.drop_column("blocked_note")
        batch_op.drop_column("blocked_reason")
        batch_op.drop_column("blocked_at")
        batch_op.drop_column("is_blocked")

    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_constraint("fk_user_blocked_by_user", type_="foreignkey")
        batch_op.drop_column("blocked_by")
        batch_op.drop_column("blocked_note")
        batch_op.drop_column("blocked_reason")
        batch_op.drop_column("blocked_at")
        batch_op.drop_column("is_blocked")