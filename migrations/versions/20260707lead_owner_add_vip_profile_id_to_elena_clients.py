"""Add vip_profile_id owner column to elena_clients

Revision ID: 20260707lo01
Revises: 20260707bkfl
Create Date: 2026-07-07 00:30:00.000000

Adds an owning-realtor foreign key (``vip_profile_id``) to ``elena_clients``
so the realtor CRM can scope every lead/client to the VIPProfile that owns
it. Without this, clients were filtered only by ``market``, so a realtor on
"All Markets" (or sharing a market) saw other partners' leads.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260707lo01"
down_revision = "20260707bkfl"
branch_labels = None
depends_on = None


def _has_column(table, column):
    try:
        insp = sa.inspect(op.get_bind())
        return any(c["name"] == column for c in insp.get_columns(table))
    except Exception:
        return False


def _has_index(table, index):
    try:
        insp = sa.inspect(op.get_bind())
        return any(ix["name"] == index for ix in insp.get_indexes(table))
    except Exception:
        return False


def upgrade():
    if not _has_column("elena_clients", "vip_profile_id"):
        op.add_column(
            "elena_clients",
            sa.Column("vip_profile_id", sa.Integer(), nullable=True),
        )
    if not _has_index("elena_clients", "ix_elena_clients_vip_profile_id"):
        op.create_index(
            "ix_elena_clients_vip_profile_id",
            "elena_clients",
            ["vip_profile_id"],
        )


def downgrade():
    if _has_index("elena_clients", "ix_elena_clients_vip_profile_id"):
        try:
            op.drop_index(
                "ix_elena_clients_vip_profile_id", table_name="elena_clients"
            )
        except Exception:
            pass
    if _has_column("elena_clients", "vip_profile_id"):
        op.drop_column("elena_clients", "vip_profile_id")
