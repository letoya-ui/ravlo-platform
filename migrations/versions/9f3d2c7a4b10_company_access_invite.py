"""add company, access_requests, user_invites

Revision ID: a1b2c3d4e5f6
Revises: 9f3d2c7a4b10
Create Date: 2026-03-12

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "9f3d2c7a4b10"
branch_labels = None
depends_on = None


def upgrade():
    # -----------------------------
    # companies table
    # -----------------------------
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email_domain", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # -----------------------------
    # access_requests table
    # -----------------------------
    op.create_table(
        "access_requests",
        sa.Column("id", sa.Integer(), primary_key=True),

        sa.Column("company_name", sa.String(255), nullable=True),
        sa.Column("contact_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),

        sa.Column("request_type", sa.String(50), nullable=False, server_default="company_setup"),
        sa.Column("requested_role", sa.String(50), nullable=True),

        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("notes", sa.Text(), nullable=True),

        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=True),

        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),

        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_index("ix_access_requests_email", "access_requests", ["email"])

    # -----------------------------
    # user_invites table
    # -----------------------------
    op.create_table(
        "user_invites",
        sa.Column("id", sa.Integer(), primary_key=True),

        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),

        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("first_name", sa.String(120), nullable=True),
        sa.Column("last_name", sa.String(120), nullable=True),
        sa.Column("role", sa.String(50), nullable=False),

        sa.Column("token", sa.String(255), nullable=False, unique=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),

        sa.Column("invited_by", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),

        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_index("ix_user_invites_email", "user_invites", ["email"])
    op.create_index("ix_user_invites_token", "user_invites", ["token"])


def downgrade():
    op.drop_index("ix_user_invites_token", table_name="user_invites")
    op.drop_index("ix_user_invites_email", table_name="user_invites")
    op.drop_table("user_invites")

    op.drop_index("ix_access_requests_email", table_name="access_requests")
    op.drop_table("access_requests")

    op.drop_table("companies")
