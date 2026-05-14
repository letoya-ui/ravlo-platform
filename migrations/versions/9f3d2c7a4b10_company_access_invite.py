"""add company, access_requests, user_invites

Revision ID: 9f3d2c7a4b10
Revises: 8c889c33231d
Create Date: 2026-03-12

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = "9f3d2c7a4b10"
down_revision = "8c889c33231d"
branch_labels = None
depends_on = None


def _table_exists(inspector, table):
    return inspector.has_table(table)


def _index_exists(inspector, table, index):
    if not _table_exists(inspector, table):
        return False
    return index in {idx["name"] for idx in inspector.get_indexes(table)}


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # -----------------------------
    # companies table
    # -----------------------------
    if not _table_exists(inspector, "companies"):
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
    if not _table_exists(inspector, "access_requests"):
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

    if not _index_exists(inspector, "access_requests", "ix_access_requests_email"):
        op.create_index("ix_access_requests_email", "access_requests", ["email"])

    # -----------------------------
    # user_invites table
    # -----------------------------
    if not _table_exists(inspector, "user_invites"):
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

    if not _index_exists(inspector, "user_invites", "ix_user_invites_email"):
        op.create_index("ix_user_invites_email", "user_invites", ["email"])
    if not _index_exists(inspector, "user_invites", "ix_user_invites_token"):
        op.create_index("ix_user_invites_token", "user_invites", ["token"])


def downgrade():
    op.drop_index("ix_user_invites_token", table_name="user_invites")
    op.drop_index("ix_user_invites_email", table_name="user_invites")
    op.drop_table("user_invites")

    op.drop_index("ix_access_requests_email", table_name="access_requests")
    op.drop_table("access_requests")

    op.drop_table("companies")
