"""add projects table

Revision ID: d1a2b3c4e5f6
Revises: b8e1d7c4a912
Create Date: 2026-04-15 09:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d1a2b3c4e5f6"
down_revision = "b8e1d7c4a912"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("deal_id", sa.Integer(), sa.ForeignKey("deals.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="draft"),
        sa.Column("arv_estimate", sa.Float(), nullable=True),
        sa.Column("rehab_budget", sa.Float(), nullable=True),
        sa.Column("rehab_level", sa.String(length=50), nullable=True),
        sa.Column("style_preset", sa.String(length=100), nullable=True),
        sa.Column("ai_plan", sa.Text(), nullable=True),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table("projects")
