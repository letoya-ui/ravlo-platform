"""Realtor unify — market fields, income.status, team + lead routing

Revision ID: 20260420r01
Revises: 20260417elena01
Create Date: 2026-04-20 00:00:00.000000

Adds:
- ``elena_listings.market`` and ``elena_clients.market`` (multi-market realtor
  dashboard — the existing code queries these columns).
- ``elena_clients.assigned_member_id`` (which teammate the lead is routed to).
- ``vip_income.status`` (pending / received / voided — lets Finance track
  projected commission income from closings/appointments).
- ``vip_team_members`` table (Frank's team + lead distribution).

All changes are additive, nullable (or defaulted), and fully reversible.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260420r01"
down_revision = "20260417elena01"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_column(table, column):
    try:
        cols = {c["name"] for c in _insp().get_columns(table)}
    except Exception:
        return False
    return column in cols


def _has_table(table):
    try:
        return _insp().has_table(table)
    except Exception:
        return False


def upgrade():
    if not _has_column("elena_listings", "market"):
        with op.batch_alter_table("elena_listings") as batch:
            batch.add_column(sa.Column("market", sa.String(length=100), nullable=True))

    if _has_table("elena_clients"):
        if not _has_column("elena_clients", "market"):
            with op.batch_alter_table("elena_clients") as batch:
                batch.add_column(sa.Column("market", sa.String(length=100), nullable=True))
        if not _has_column("elena_clients", "assigned_member_id"):
            with op.batch_alter_table("elena_clients") as batch:
                batch.add_column(sa.Column("assigned_member_id", sa.Integer(), nullable=True))

    if not _has_column("vip_income", "status"):
        with op.batch_alter_table("vip_income") as batch:
            batch.add_column(
                sa.Column(
                    "status",
                    sa.String(length=50),
                    nullable=False,
                    server_default="received",
                )
            )

    if not _has_table("vip_team_members"):
        op.create_table(
            "vip_team_members",
            sa.Column("id",             sa.Integer(),      primary_key=True),
            sa.Column("vip_profile_id", sa.Integer(),      sa.ForeignKey("vip_profiles.id"), nullable=False),
            sa.Column("name",           sa.String(255),    nullable=False),
            sa.Column("email",          sa.String(255),    nullable=True),
            sa.Column("phone",          sa.String(50),     nullable=True),
            sa.Column("role",           sa.String(80),     nullable=True),
            sa.Column("market",         sa.String(100),    nullable=True),
            sa.Column("notes",          sa.Text(),         nullable=True),
            sa.Column("active",         sa.Boolean(),      nullable=False, server_default=sa.true()),
            sa.Column("created_at",     sa.DateTime(),     nullable=True),
            sa.Column("updated_at",     sa.DateTime(),     nullable=True),
        )
        op.create_index(
            "ix_vip_team_members_vip_profile_id",
            "vip_team_members",
            ["vip_profile_id"],
        )


def downgrade():
    if _has_table("vip_team_members"):
        try:
            op.drop_index("ix_vip_team_members_vip_profile_id", table_name="vip_team_members")
        except Exception:
            pass
        op.drop_table("vip_team_members")

    if _has_column("vip_income", "status"):
        with op.batch_alter_table("vip_income") as batch:
            batch.drop_column("status")

    if _has_table("elena_clients"):
        if _has_column("elena_clients", "assigned_member_id"):
            with op.batch_alter_table("elena_clients") as batch:
                batch.drop_column("assigned_member_id")
        if _has_column("elena_clients", "market"):
            with op.batch_alter_table("elena_clients") as batch:
                batch.drop_column("market")

    if _has_column("elena_listings", "market"):
        with op.batch_alter_table("elena_listings") as batch:
            batch.drop_column("market")
