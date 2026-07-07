"""Backfill discovery_events and construction_projects tables

Revision ID: 20260707bkfl
Revises: 20260707binq01
Create Date: 2026-07-07 01:50:00.000000

Both tables were missing in production despite discovery_events having
its own earlier migration (e1f2a3b4c5d6). That migration's revision was
already below the alembic_version stamped during an earlier bootstrap
(db.create_all() + `flask db stamp head`), so alembic considers it
already applied and never re-runs its upgrade() -- but db.create_all()
ran before the DiscoveryEvent model existed, so the table was never
actually created either way. construction_projects never had a
migration at all. Both creates are guarded with has_table() so this is
safe to run regardless of what state either database is actually in.
"""
from alembic import op
import sqlalchemy as sa

revision = '20260707bkfl'
down_revision = '20260707binq01'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not inspector.has_table("discovery_events"):
        op.create_table(
            "discovery_events",
            sa.Column("id",         sa.Integer(),   nullable=False),
            sa.Column("source",     sa.String(80),  nullable=False),
            sa.Column("user_agent", sa.Text(),      nullable=True),
            sa.Column("ip",         sa.String(50),  nullable=True),
            sa.Column("path",       sa.String(500), nullable=True),
            sa.Column("created_at", sa.DateTime(),  nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_discovery_events_source",     "discovery_events", ["source"])
        op.create_index("ix_discovery_events_created_at", "discovery_events", ["created_at"])

    if not inspector.has_table("construction_projects"):
        op.create_table(
            "construction_projects",
            sa.Column("id",                   sa.Integer(),  nullable=False),
            sa.Column("bid_opportunity_id",    sa.Integer(),  nullable=True),
            sa.Column("partner_id",            sa.Integer(),  nullable=False),
            sa.Column("project_name",          sa.String(255), nullable=False),
            sa.Column("location",              sa.String(255), nullable=True),
            sa.Column("category",              sa.String(100), nullable=True),
            sa.Column("source",                sa.String(120), nullable=True),
            sa.Column("estimated_value",       sa.Float(),    nullable=True),
            sa.Column("contract_amount",       sa.Float(),    nullable=True),
            sa.Column("notes",                 sa.Text(),     nullable=True),
            sa.Column("bid_date",              sa.DateTime(), nullable=True),
            sa.Column("project_manager",       sa.String(120), nullable=True),
            sa.Column("office_coordinator",    sa.String(120), nullable=True),
            sa.Column("executive",             sa.String(120), nullable=True),
            sa.Column("status",                sa.String(50), nullable=False, server_default="pre_construction"),
            sa.Column("start_date",            sa.DateTime(), nullable=True),
            sa.Column("estimated_completion",  sa.DateTime(), nullable=True),
            sa.Column("actual_completion",     sa.DateTime(), nullable=True),
            sa.Column("created_at",            sa.DateTime(), nullable=True),
            sa.Column("updated_at",            sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["bid_opportunity_id"], ["contractor_bid_opportunities.id"]),
            sa.ForeignKeyConstraint(["partner_id"], ["partners.id"]),
            sa.UniqueConstraint("bid_opportunity_id"),
        )
        op.create_index("ix_construction_projects_partner_id", "construction_projects", ["partner_id"])


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if inspector.has_table("construction_projects"):
        op.drop_index("ix_construction_projects_partner_id", table_name="construction_projects")
        op.drop_table("construction_projects")

    if inspector.has_table("discovery_events"):
        op.drop_index("ix_discovery_events_created_at", table_name="discovery_events")
        op.drop_index("ix_discovery_events_source",     table_name="discovery_events")
        op.drop_table("discovery_events")
