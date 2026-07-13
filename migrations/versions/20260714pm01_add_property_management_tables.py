"""Add property management tables (units, tenants, rent, maintenance)

Revision ID: 20260714pm01
Revises: 20260713ae01
Create Date: 2026-07-14 12:00:00.000000

Adds the data model for turning /property into a real property
management tool: property_units, property_tenants,
property_rent_payments, property_maintenance_requests, plus an
owner_investor_id column on the existing ``property`` table so an
investor can claim a property into their managed rental portfolio.
Independent of PropertyAnalysis/Deal (one-time underwriting records for
a prospective purchase) -- these tables track ongoing rental operations.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260714pm01"
down_revision = "20260713ae01"
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
    if not _has_column("property", "owner_investor_id"):
        with op.batch_alter_table("property", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "owner_investor_id",
                    sa.Integer(),
                    sa.ForeignKey("investor_profile.id", name="fk_property_owner_investor"),
                    nullable=True,
                )
            )
        op.create_index("ix_property_owner_investor_id", "property", ["owner_investor_id"])

    if not _has_table("property_units"):
        op.create_table(
            "property_units",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("property_id", sa.Integer(), sa.ForeignKey("property.id"), nullable=False),
            sa.Column("unit_label", sa.String(100), nullable=False, server_default="Main Unit"),
            sa.Column("bedrooms", sa.Integer(), nullable=True),
            sa.Column("bathrooms", sa.Float(), nullable=True),
            sa.Column("sqft", sa.Integer(), nullable=True),
            sa.Column("market_rent", sa.Numeric(10, 2), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_property_units_property_id", "property_units", ["property_id"])

    if not _has_table("property_tenants"):
        op.create_table(
            "property_tenants",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("unit_id", sa.Integer(), sa.ForeignKey("property_units.id"), nullable=False),
            sa.Column("full_name", sa.String(255), nullable=False),
            sa.Column("email", sa.String(255), nullable=True),
            sa.Column("phone", sa.String(50), nullable=True),
            sa.Column("lease_start", sa.Date(), nullable=True),
            sa.Column("lease_end", sa.Date(), nullable=True),
            sa.Column("monthly_rent", sa.Numeric(10, 2), nullable=True),
            sa.Column("security_deposit", sa.Numeric(10, 2), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_property_tenants_unit_id", "property_tenants", ["unit_id"])

    if not _has_table("property_rent_payments"):
        op.create_table(
            "property_rent_payments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("unit_id", sa.Integer(), sa.ForeignKey("property_units.id"), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("property_tenants.id"), nullable=True),
            sa.Column("period_month", sa.Date(), nullable=False),
            sa.Column("amount_due", sa.Numeric(10, 2), nullable=False),
            sa.Column("amount_paid", sa.Numeric(10, 2), nullable=True, server_default="0"),
            sa.Column("paid_date", sa.Date(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="unpaid"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_property_rent_payments_unit_id", "property_rent_payments", ["unit_id"])
        op.create_index("ix_property_rent_payments_tenant_id", "property_rent_payments", ["tenant_id"])

    if not _has_table("property_maintenance_requests"):
        op.create_table(
            "property_maintenance_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("unit_id", sa.Integer(), sa.ForeignKey("property_units.id"), nullable=False),
            sa.Column("reported_by_user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
            sa.Column("status", sa.String(20), nullable=False, server_default="open"),
            sa.Column("actual_cost", sa.Numeric(10, 2), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
        )
        op.create_index(
            "ix_property_maintenance_requests_unit_id", "property_maintenance_requests", ["unit_id"]
        )


def downgrade():
    if _has_table("property_maintenance_requests"):
        op.drop_table("property_maintenance_requests")
    if _has_table("property_rent_payments"):
        op.drop_table("property_rent_payments")
    if _has_table("property_tenants"):
        op.drop_table("property_tenants")
    if _has_table("property_units"):
        op.drop_table("property_units")

    if _has_column("property", "owner_investor_id"):
        try:
            op.drop_index("ix_property_owner_investor_id", table_name="property")
        except Exception:
            pass
        with op.batch_alter_table("property", schema=None) as batch_op:
            batch_op.drop_column("owner_investor_id")
