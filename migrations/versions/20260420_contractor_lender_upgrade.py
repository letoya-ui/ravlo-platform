"""Contractor & Lender VIP upgrade

Revision ID: 20260420r02
Revises: 20260420r01
Create Date: 2026-04-20 01:00:00.000000

Adds:
- ``contractor_jobs`` (contractor's day-to-day job board — status, schedule,
  agreed price, source).
- ``contractor_bids`` (bids the contractor sends out — scope, line items,
  timeline, status).
- ``contractor_change_orders`` (change-order requests raised against a job).
- ``contractor_job_photos`` (before / during / after photos, drives the job
  report).
- ``lender_rate_sheets`` (loan products the lender is actively quoting for
  the upgraded LO VIP dashboard).

All additive, idempotent, and reversible.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260420r02"
down_revision = "20260420r01"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_table(table):
    try:
        return _insp().has_table(table)
    except Exception:
        return False


def upgrade():
    if not _has_table("contractor_jobs"):
        op.create_table(
            "contractor_jobs",
            sa.Column("id",             sa.Integer(),      primary_key=True),
            sa.Column("vip_profile_id", sa.Integer(),
                      sa.ForeignKey("vip_profiles.id"), nullable=False),

            sa.Column("title",        sa.String(200), nullable=False),
            sa.Column("client_name",  sa.String(200), nullable=True),
            sa.Column("client_email", sa.String(255), nullable=True),
            sa.Column("client_phone", sa.String(50),  nullable=True),

            sa.Column("address",    sa.String(255), nullable=True),
            sa.Column("scope_text", sa.Text(),      nullable=True),

            sa.Column("status",       sa.String(30), nullable=False,
                      server_default="scheduled"),
            sa.Column("agreed_price", sa.Float(),    nullable=True),

            sa.Column("start_date",   sa.Date(),     nullable=True),
            sa.Column("end_date",     sa.Date(),     nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),

            sa.Column("source",     sa.String(30),  nullable=True),
            sa.Column("source_ref", sa.String(100), nullable=True),

            sa.Column("notes", sa.Text(), nullable=True),

            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index(
            "ix_contractor_jobs_vip_profile_id",
            "contractor_jobs",
            ["vip_profile_id"],
        )

    if not _has_table("contractor_bids"):
        op.create_table(
            "contractor_bids",
            sa.Column("id",             sa.Integer(), primary_key=True),
            sa.Column("vip_profile_id", sa.Integer(),
                      sa.ForeignKey("vip_profiles.id"), nullable=False),
            sa.Column("job_id",         sa.Integer(),
                      sa.ForeignKey("contractor_jobs.id"), nullable=True),

            sa.Column("prospect_name",  sa.String(200), nullable=False),
            sa.Column("prospect_email", sa.String(255), nullable=True),
            sa.Column("prospect_phone", sa.String(50),  nullable=True),

            sa.Column("address",    sa.String(255), nullable=True),
            sa.Column("scope_text", sa.Text(),      nullable=True),

            sa.Column("labor_cost",     sa.Float(), nullable=True, server_default="0"),
            sa.Column("materials_cost", sa.Float(), nullable=True, server_default="0"),
            sa.Column("other_cost",     sa.Float(), nullable=True, server_default="0"),
            sa.Column("total_cost",     sa.Float(), nullable=True, server_default="0"),

            sa.Column("timeline", sa.String(120), nullable=True),

            sa.Column("status", sa.String(30), nullable=False, server_default="draft"),

            sa.Column("sent_at",      sa.DateTime(), nullable=True),
            sa.Column("responded_at", sa.DateTime(), nullable=True),
            sa.Column("expires_at",   sa.DateTime(), nullable=True),

            sa.Column("notes",      sa.Text(),     nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index(
            "ix_contractor_bids_vip_profile_id",
            "contractor_bids",
            ["vip_profile_id"],
        )

    if not _has_table("contractor_change_orders"):
        op.create_table(
            "contractor_change_orders",
            sa.Column("id",             sa.Integer(), primary_key=True),
            sa.Column("vip_profile_id", sa.Integer(),
                      sa.ForeignKey("vip_profiles.id"), nullable=False),
            sa.Column("job_id",         sa.Integer(),
                      sa.ForeignKey("contractor_jobs.id"), nullable=False),

            sa.Column("title",       sa.String(200), nullable=False),
            sa.Column("description", sa.Text(),      nullable=True),

            sa.Column("added_cost", sa.Float(),   nullable=True, server_default="0"),
            sa.Column("added_days", sa.Integer(), nullable=True, server_default="0"),

            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),

            sa.Column("requested_at", sa.DateTime(), nullable=True),
            sa.Column("responded_at", sa.DateTime(), nullable=True),
            sa.Column("created_at",   sa.DateTime(), nullable=True),
            sa.Column("updated_at",   sa.DateTime(), nullable=True),
        )
        op.create_index(
            "ix_contractor_change_orders_job_id",
            "contractor_change_orders",
            ["job_id"],
        )

    if not _has_table("contractor_job_photos"):
        op.create_table(
            "contractor_job_photos",
            sa.Column("id",             sa.Integer(), primary_key=True),
            sa.Column("vip_profile_id", sa.Integer(),
                      sa.ForeignKey("vip_profiles.id"), nullable=False),
            sa.Column("job_id",         sa.Integer(),
                      sa.ForeignKey("contractor_jobs.id"), nullable=False),

            sa.Column("phase",     sa.String(20),  nullable=False,
                      server_default="before"),
            sa.Column("file_path", sa.String(500), nullable=False),
            sa.Column("caption",   sa.String(500), nullable=True),

            sa.Column("taken_at",   sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index(
            "ix_contractor_job_photos_job_id",
            "contractor_job_photos",
            ["job_id"],
        )

    if not _has_table("lender_rate_sheets"):
        op.create_table(
            "lender_rate_sheets",
            sa.Column("id",             sa.Integer(), primary_key=True),
            sa.Column("vip_profile_id", sa.Integer(),
                      sa.ForeignKey("vip_profiles.id"), nullable=False),

            sa.Column("product_name", sa.String(200), nullable=False),
            sa.Column("loan_type",    sa.String(100), nullable=True),

            sa.Column("base_rate",   sa.Float(),   nullable=True),
            sa.Column("max_ltv",     sa.Float(),   nullable=True),
            sa.Column("min_credit",  sa.Integer(), nullable=True),
            sa.Column("term_months", sa.Integer(), nullable=True),
            sa.Column("points",      sa.Float(),   nullable=True),
            sa.Column("fees_text",   sa.Text(),    nullable=True),

            sa.Column("notes", sa.Text(), nullable=True),

            sa.Column("is_active",      sa.Boolean(), nullable=False,
                      server_default=sa.true()),
            sa.Column("effective_date", sa.Date(),    nullable=True),

            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index(
            "ix_lender_rate_sheets_vip_profile_id",
            "lender_rate_sheets",
            ["vip_profile_id"],
        )


def downgrade():
    for idx, tbl in [
        ("ix_lender_rate_sheets_vip_profile_id",       "lender_rate_sheets"),
        ("ix_contractor_job_photos_job_id",            "contractor_job_photos"),
        ("ix_contractor_change_orders_job_id",         "contractor_change_orders"),
        ("ix_contractor_bids_vip_profile_id",          "contractor_bids"),
        ("ix_contractor_jobs_vip_profile_id",          "contractor_jobs"),
    ]:
        if _has_table(tbl):
            try:
                op.drop_index(idx, table_name=tbl)
            except Exception:
                pass

    for tbl in [
        "lender_rate_sheets",
        "contractor_job_photos",
        "contractor_change_orders",
        "contractor_bids",
        "contractor_jobs",
    ]:
        if _has_table(tbl):
            op.drop_table(tbl)
