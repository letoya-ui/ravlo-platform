"""Realtor listing presentations

Revision ID: 20260420r02
Revises: 20260420r01
Create Date: 2026-04-20 01:00:00.000000

Adds the ``realtor_listing_presentations`` table that backs the pitch-deck
builder in the unified realtor workspace (Frank / Elena / VIP realtor).

All changes are additive and guarded by existence checks so the migration
is safe to re-run.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260420r02"
down_revision = "c0fbeac05741"
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
    if _has_table("realtor_listing_presentations"):
        return

    op.create_table(
        "realtor_listing_presentations",
        sa.Column("id",                   sa.Integer(), primary_key=True),
        sa.Column("created_at",           sa.DateTime(), nullable=True),
        sa.Column("updated_at",           sa.DateTime(), nullable=True),

        sa.Column("vip_profile_id",       sa.Integer(),
                  sa.ForeignKey("vip_profiles.id"), nullable=True),
        sa.Column("listing_id",           sa.Integer(),
                  sa.ForeignKey("elena_listings.id"), nullable=True),
        sa.Column("client_id",            sa.Integer(),
                  sa.ForeignKey("elena_clients.id"), nullable=True),

        sa.Column("title",                sa.String(length=255), nullable=False,
                  server_default="Listing Presentation"),
        sa.Column("prospect_name",        sa.String(length=255), nullable=True),
        sa.Column("prospect_email",       sa.String(length=255), nullable=True),
        sa.Column("prospect_phone",       sa.String(length=50),  nullable=True),
        sa.Column("property_address",     sa.String(length=255), nullable=True),
        sa.Column("property_city",        sa.String(length=120), nullable=True),
        sa.Column("property_state",       sa.String(length=50),  nullable=True),
        sa.Column("property_zip",         sa.String(length=20),  nullable=True),
        sa.Column("property_beds",        sa.Integer(), nullable=True),
        sa.Column("property_baths",       sa.Integer(), nullable=True),
        sa.Column("property_sqft",        sa.Integer(), nullable=True),

        sa.Column("cover_image_url",      sa.String(length=500), nullable=True),

        sa.Column("agent_tagline",        sa.String(length=255), nullable=True),
        sa.Column("agent_bio",            sa.Text(), nullable=True),
        sa.Column("agent_stats_json",     sa.Text(), nullable=True),

        sa.Column("market_snapshot",      sa.Text(), nullable=True),
        sa.Column("market_stats_json",    sa.Text(), nullable=True),

        sa.Column("cma_rows_json",        sa.Text(), nullable=True),
        sa.Column("cma_summary",          sa.Text(), nullable=True),

        sa.Column("suggested_list_price", sa.Integer(), nullable=True),
        sa.Column("pricing_range_low",    sa.Integer(), nullable=True),
        sa.Column("pricing_range_high",   sa.Integer(), nullable=True),
        sa.Column("pricing_rationale",    sa.Text(), nullable=True),

        sa.Column("marketing_plan_json",  sa.Text(), nullable=True),
        sa.Column("testimonials_json",    sa.Text(), nullable=True),

        sa.Column("commission_rate",      sa.String(length=20), nullable=True),
        sa.Column("listing_term_months",  sa.Integer(), nullable=True),
        sa.Column("listing_term_notes",   sa.Text(), nullable=True),

        sa.Column("next_steps",           sa.Text(), nullable=True),
        sa.Column("signature_line",       sa.String(length=255), nullable=True),

        sa.Column("status",               sa.String(length=20), nullable=False,
                  server_default="draft"),
        sa.Column("share_slug",           sa.String(length=64), nullable=True),
        sa.Column("share_enabled",        sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        sa.Column("sent_at",              sa.DateTime(), nullable=True),
        sa.Column("last_viewed_at",       sa.DateTime(), nullable=True),
        sa.Column("view_count",           sa.Integer(), nullable=False,
                  server_default="0"),
    )
    op.create_index(
        "ix_realtor_presentations_share_slug",
        "realtor_listing_presentations",
        ["share_slug"],
        unique=True,
    )
    op.create_index(
        "ix_realtor_presentations_vip_profile_id",
        "realtor_listing_presentations",
        ["vip_profile_id"],
    )
    op.create_index(
        "ix_realtor_presentations_listing_id",
        "realtor_listing_presentations",
        ["listing_id"],
    )


def downgrade():
    if not _has_table("realtor_listing_presentations"):
        return
    for idx in (
        "ix_realtor_presentations_share_slug",
        "ix_realtor_presentations_vip_profile_id",
        "ix_realtor_presentations_listing_id",
    ):
        try:
            op.drop_index(idx, table_name="realtor_listing_presentations")
        except Exception:
            pass
    op.drop_table("realtor_listing_presentations")
