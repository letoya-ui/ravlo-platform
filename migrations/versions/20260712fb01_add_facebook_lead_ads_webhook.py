"""Add Facebook/Instagram Lead Ads webhook support

Revision ID: 20260712fb01
Revises: 20260711dps01
Create Date: 2026-07-12 15:00:00.000000

Adds the ``facebook_page_connections`` table (one connected Page per
company: page_id, page_name, platform, page_access_token) and an
``external_lead_id`` column on ``lead`` used to dedupe webhook redeliveries
of the same Meta leadgen event.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260712fb01"
down_revision = "20260711dps01"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_table(table):
    try:
        return _insp().has_table(table)
    except Exception:
        return False


def _has_column(table, column):
    try:
        return any(c["name"] == column for c in _insp().get_columns(table))
    except Exception:
        return False


def upgrade():
    if not _has_table("facebook_page_connections"):
        op.create_table(
            "facebook_page_connections",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("page_id", sa.String(64), nullable=False),
            sa.Column("page_name", sa.String(255), nullable=True),
            sa.Column("platform", sa.String(20), nullable=True, server_default="facebook"),
            sa.Column("page_access_token", sa.Text(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true()),
            sa.Column("connected_by_user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
            sa.Column("connected_at", sa.DateTime(), nullable=True),
        )
        with op.batch_alter_table("facebook_page_connections") as batch_op:
            batch_op.create_index(
                "ix_facebook_page_connections_page_id",
                ["page_id"],
                unique=False,
            )

    if not _has_column("lead", "external_lead_id"):
        op.add_column(
            "lead",
            sa.Column("external_lead_id", sa.String(64), nullable=True),
        )
        op.create_index(
            "ix_lead_external_lead_id",
            "lead",
            ["external_lead_id"],
        )


def downgrade():
    if _has_column("lead", "external_lead_id"):
        try:
            op.drop_index("ix_lead_external_lead_id", table_name="lead")
        except Exception:
            pass
        op.drop_column("lead", "external_lead_id")

    if _has_table("facebook_page_connections"):
        op.drop_table("facebook_page_connections")
