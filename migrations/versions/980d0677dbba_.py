"""Add Elena clients and interactions

Revision ID: 980d0677dbba
Revises: 1382fd92af8d
Create Date: 2026-04-16 21:50:27.248588
"""

from alembic import op
import sqlalchemy as sa


revision = '980d0677dbba'
down_revision = '1382fd92af8d'
branch_labels = None
depends_on = None


def upgrade():
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
