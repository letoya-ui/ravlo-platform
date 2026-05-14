"""add cost_observations table

Revision ID: c0fbeac05741
Revises: 20260420r01
Create Date: 2026-04-19 21:30:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c0fbeac05741"
down_revision = "20260420r01"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not inspector.has_table("cost_observations"):
        op.create_table(
            "cost_observations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source",      sa.String(length=32),  nullable=False),
            sa.Column("user_id",     sa.Integer(),          sa.ForeignKey("user.id"),     nullable=True),
            sa.Column("deal_id",     sa.Integer(),          sa.ForeignKey("deals.id"),    nullable=True),
            sa.Column("partner_id",  sa.Integer(),          sa.ForeignKey("partners.id"), nullable=True),
            sa.Column("zip_code",    sa.String(length=10),  nullable=True),
            sa.Column("zip3",        sa.String(length=3),   nullable=True),
            sa.Column("state",       sa.String(length=2),   nullable=True),
            sa.Column("city",        sa.String(length=120), nullable=True),
            sa.Column("category",    sa.String(length=16),  nullable=False),
            sa.Column("asset_type",  sa.String(length=32),  nullable=True),
            sa.Column("scope",       sa.String(length=16),  nullable=True),
            sa.Column("sqft",           sa.Float(), nullable=True),
            sa.Column("total_cost",     sa.Float(), nullable=True),
            sa.Column("cost_per_sqft",  sa.Float(), nullable=True),
            sa.Column("confidence",  sa.Float(),   nullable=False, server_default="0.5"),
            sa.Column("status",      sa.String(length=16), nullable=False, server_default="verified"),
            sa.Column("supersedes_id", sa.Integer(), sa.ForeignKey("cost_observations.id"), nullable=True),
            sa.Column("notes",       sa.Text(), nullable=True),
            sa.Column("created_at",  sa.DateTime(), nullable=False),
            sa.Column("updated_at",  sa.DateTime(), nullable=False),
        )
        co_idxs = set()
    else:
        co_idxs = {i["name"] for i in inspector.get_indexes("cost_observations")}

    for idx_name, columns in [
        ("ix_cost_observations_source",        ["source"]),
        ("ix_cost_observations_user_id",       ["user_id"]),
        ("ix_cost_observations_deal_id",       ["deal_id"]),
        ("ix_cost_observations_partner_id",    ["partner_id"]),
        ("ix_cost_observations_zip_code",      ["zip_code"]),
        ("ix_cost_observations_zip3",          ["zip3"]),
        ("ix_cost_observations_state",         ["state"]),
        ("ix_cost_observations_category",      ["category"]),
        ("ix_cost_observations_scope",         ["scope"]),
        ("ix_cost_observations_cost_per_sqft", ["cost_per_sqft"]),
        ("ix_cost_observations_status",        ["status"]),
        ("ix_cost_obs_zip3_category",          ["zip3", "category"]),
        ("ix_cost_obs_state_category",         ["state", "category"]),
        ("ix_cost_obs_zip3_category_scope",    ["zip3", "category", "scope"]),
    ]:
        if idx_name not in co_idxs:
            op.create_index(idx_name, "cost_observations", columns)

    deals_cols = {c["name"] for c in inspector.get_columns("deals")} if inspector.has_table("deals") else set()
    with op.batch_alter_table("deals", schema=None) as batch_op:
        if "local_cost_factor" not in deals_cols:
            batch_op.add_column(sa.Column("local_cost_factor", sa.Float(), nullable=True))
        if "local_cost_label" not in deals_cols:
            batch_op.add_column(sa.Column("local_cost_label",  sa.String(length=120), nullable=True))


def downgrade():
    with op.batch_alter_table("deals", schema=None) as batch_op:
        batch_op.drop_column("local_cost_label")
        batch_op.drop_column("local_cost_factor")

    for name in [
        "ix_cost_obs_zip3_category_scope",
        "ix_cost_obs_state_category",
        "ix_cost_obs_zip3_category",
        "ix_cost_observations_status",
        "ix_cost_observations_cost_per_sqft",
        "ix_cost_observations_scope",
        "ix_cost_observations_category",
        "ix_cost_observations_state",
        "ix_cost_observations_zip3",
        "ix_cost_observations_zip_code",
        "ix_cost_observations_partner_id",
        "ix_cost_observations_deal_id",
        "ix_cost_observations_user_id",
        "ix_cost_observations_source",
    ]:
        op.drop_index(name, table_name="cost_observations")
    op.drop_table("cost_observations")
