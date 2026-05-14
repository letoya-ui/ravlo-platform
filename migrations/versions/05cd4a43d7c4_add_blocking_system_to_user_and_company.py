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
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    user_cols = {c["name"] for c in inspector.get_columns("user")}
    user_fks = {fk["name"] for fk in inspector.get_foreign_keys("user")}
    with op.batch_alter_table("user", schema=None) as batch_op:
        if "is_blocked" not in user_cols:
            batch_op.add_column(sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.false()))
        if "blocked_at" not in user_cols:
            batch_op.add_column(sa.Column("blocked_at", sa.DateTime(), nullable=True))
        if "blocked_reason" not in user_cols:
            batch_op.add_column(sa.Column("blocked_reason", sa.String(length=100), nullable=True))
        if "blocked_note" not in user_cols:
            batch_op.add_column(sa.Column("blocked_note", sa.Text(), nullable=True))
        if "blocked_by" not in user_cols:
            batch_op.add_column(sa.Column("blocked_by", sa.Integer(), nullable=True))
        if "fk_user_blocked_by_user" not in user_fks:
            try:
                batch_op.create_foreign_key("fk_user_blocked_by_user", "user", ["blocked_by"], ["id"])
            except Exception:
                pass

    co_cols = {c["name"] for c in inspector.get_columns("companies")}
    co_fks = {fk["name"] for fk in inspector.get_foreign_keys("companies")}
    with op.batch_alter_table("companies", schema=None) as batch_op:
        if "is_blocked" not in co_cols:
            batch_op.add_column(sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.false()))
        if "blocked_at" not in co_cols:
            batch_op.add_column(sa.Column("blocked_at", sa.DateTime(), nullable=True))
        if "blocked_reason" not in co_cols:
            batch_op.add_column(sa.Column("blocked_reason", sa.String(length=100), nullable=True))
        if "blocked_note" not in co_cols:
            batch_op.add_column(sa.Column("blocked_note", sa.Text(), nullable=True))
        if "blocked_by" not in co_cols:
            batch_op.add_column(sa.Column("blocked_by", sa.Integer(), nullable=True))
        if "billing_status" not in co_cols:
            batch_op.add_column(sa.Column("billing_status", sa.String(length=50), nullable=True))
        if "grace_period_ends_at" not in co_cols:
            batch_op.add_column(sa.Column("grace_period_ends_at", sa.DateTime(), nullable=True))
        if "fk_companies_blocked_by_user" not in co_fks:
            try:
                batch_op.create_foreign_key("fk_companies_blocked_by_user", "user", ["blocked_by"], ["id"])
            except Exception:
                pass


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