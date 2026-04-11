"""add company dashboard settings

Revision ID: b8e1d7c4a912
Revises: 05cd4a43d7c4
Create Date: 2026-04-10 09:25:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b8e1d7c4a912"
down_revision = "05cd4a43d7c4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("companies", schema=None) as batch_op:
        batch_op.add_column(sa.Column("dashboard_settings", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("companies", schema=None) as batch_op:
        batch_op.drop_column("dashboard_settings")
