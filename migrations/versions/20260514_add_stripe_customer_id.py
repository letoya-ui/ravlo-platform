"""add stripe_customer_id to user table

Revision ID: 20260514stripe01
Revises: 20260513cid01
Create Date: 2026-05-14 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "20260514stripe01"
down_revision = "20260513cid01"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    user_cols = {c["name"] for c in inspector.get_columns("user")} if inspector.has_table("user") else set()
    with op.batch_alter_table("user", schema=None) as batch_op:
        if "stripe_customer_id" not in user_cols:
            batch_op.add_column(sa.Column("stripe_customer_id", sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_column("stripe_customer_id")
