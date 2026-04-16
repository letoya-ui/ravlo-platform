"""Add Elena clients and interactions

Revision ID: add_elena_clients_interactions
Revises: 49db4afbfb1
Create Date: 2026-04-16
"""

from alembic import op
import sqlalchemy as sa


revision = "add_elena_clients_interactions"
down_revision = "49db4afbfb1"
branch_labels = None
depends_on = None


def upgrade():
    # ---------------- elena_clients ----------------
    op.create_table(
        "elena_clients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),

        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),

        sa.Column("pipeline_stage", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),

        sa.Column("preferred_areas", sa.String(), nullable=True),
        sa.Column("budget", sa.String(), nullable=True),
    )

    # ---------------- elena_interactions ----------------
    op.create_table(
        "elena_interactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),

        sa.Column("client_id", sa.Integer(), sa.ForeignKey("elena_clients.id"), nullable=False),
        sa.Column("interaction_type", sa.String(), nullable=False),

        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("meta", sa.String(), nullable=True),
    )


def downgrade():
    op.drop_table("elena_interactions")
    op.drop_table("elena_clients")
