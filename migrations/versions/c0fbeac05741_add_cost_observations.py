"""add cost_observations table

Revision ID: c0fbeac05741
Revises: 20260420r01
Create Date: 2026-04-19 21:30:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# NOTE: down_revision originally pointed at "a1b2c3d4e5f6" (from PR #50), but
# that revision ID now collides with an unrelated migration already on main
# (9f3d2c7a4b10_company_access_invite.py also uses it). Chain off the newest
# unambiguous head on main instead so flask db upgrade has a clean lineage.
revision = "c0fbeac05741"
down_revision = "20260420r01"
branch_labels = None
depends_on = None


def upgrade():
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
    op.create_index("ix_cost_observations_source",       "cost_observations", ["source"])
    op.create_index("ix_cost_observations_user_id",      "cost_observations", ["user_id"])
    op.create_index("ix_cost_observations_deal_id",      "cost_observations", ["deal_id"])
    op.create_index("ix_cost_observations_partner_id",   "cost_observations", ["partner_id"])
    op.create_index("ix_cost_observations_zip_code",     "cost_observations", ["zip_code"])
    op.create_index("ix_cost_observations_zip3",         "cost_observations", ["zip3"])
    op.create_index("ix_cost_observations_state",        "cost_observations", ["state"])
    op.create_index("ix_cost_observations_category",     "cost_observations", ["category"])
    op.create_index("ix_cost_observations_scope",        "cost_observations", ["scope"])
    op.create_index("ix_cost_observations_cost_per_sqft","cost_observations", ["cost_per_sqft"])
    op.create_index("ix_cost_observations_status",       "cost_observations", ["status"])
    op.create_index("ix_cost_obs_zip3_category",         "cost_observations", ["zip3", "category"])
    op.create_index("ix_cost_obs_state_category",        "cost_observations", ["state", "category"])
    op.create_index("ix_cost_obs_zip3_category_scope",   "cost_observations", ["zip3", "category", "scope"])

    with op.batch_alter_table("deals", schema=None) as batch_op:
        batch_op.add_column(sa.Column("local_cost_factor", sa.Float(), nullable=True))
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
