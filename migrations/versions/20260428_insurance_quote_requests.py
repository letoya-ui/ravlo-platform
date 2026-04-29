"""Insurance quote requests

Revision ID: 20260428iq01
Revises: 20260420r02
Create Date: 2026-04-28 15:00:00.000000

Adds the ``insurance_quote_requests`` table for lead intake form
submissions. All changes are additive and guarded by existence checks
so the migration is safe to re-run.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260428iq01"
down_revision = "20260420r02"
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
    if _has_table("insurance_quote_requests"):
        return

    op.create_table(
        "insurance_quote_requests",
        sa.Column("id",                sa.Integer(), primary_key=True),
        sa.Column("created_at",        sa.DateTime(), nullable=True),
        sa.Column("updated_at",        sa.DateTime(), nullable=True),

        sa.Column("vip_profile_id",    sa.Integer(),
                  sa.ForeignKey("vip_profiles.id"), nullable=False),

        sa.Column("client_name",       sa.String(255), nullable=False),
        sa.Column("client_email",      sa.String(255), nullable=True),
        sa.Column("client_phone",      sa.String(50),  nullable=True),
        sa.Column("client_dob",        sa.String(20),  nullable=True),
        sa.Column("drivers_license",   sa.String(100), nullable=True),
        sa.Column("client_address",    sa.String(500), nullable=True),
        sa.Column("current_carrier",   sa.String(255), nullable=True),

        sa.Column("insurance_line",    sa.String(50),  nullable=False, server_default="auto"),
        sa.Column("details_json",      sa.Text(),      nullable=True),
        sa.Column("declarations_file", sa.String(500), nullable=True),

        sa.Column("status",            sa.String(30),  nullable=False, server_default="new"),
        sa.Column("followup_notes",    sa.Text(),      nullable=True),
        sa.Column("followup_date",     sa.DateTime(),  nullable=True),

        sa.Column("source",            sa.String(50),  nullable=True, server_default="dashboard"),
    )

    with op.batch_alter_table("insurance_quote_requests") as batch_op:
        batch_op.create_index(
            "ix_iqr_vip_profile_id",
            ["vip_profile_id"],
            unique=False,
        )
        batch_op.create_index(
            "ix_iqr_status",
            ["status"],
            unique=False,
        )


def downgrade():
    op.drop_table("insurance_quote_requests")
