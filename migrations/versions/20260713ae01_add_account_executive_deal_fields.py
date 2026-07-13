"""Add Account Executive deal-pipeline fields to business_inquiries

Revision ID: 20260713ae01
Revises: 20260712fb01
Create Date: 2026-07-13 19:00:00.000000

Adds account-executive-facing columns to the existing
``business_inquiries`` table (Ravlo's "prospective company wants to
license Lending OS" intake) rather than a new table: who the deal is
assigned to, the AE's own pipeline stage, contract terms, and commission
tracking. The existing ``status`` column (new/contacted/approved/declined)
is untouched -- it still drives the admin licensing_applications
Company/invite-creation workflow independently of this.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260713ae01"
down_revision = "20260712fb01"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_column(table, column):
    try:
        return any(c["name"] == column for c in _insp().get_columns(table))
    except Exception:
        return False


# Plain (non-FK) columns can be added directly; SQLite's ALTER TABLE
# doesn't support adding a column with an inline FK constraint outside of
# batch mode (see 20260513_add_company_id_scoping.py for the established
# pattern this mirrors), so the two FK columns are added separately below.
_PLAIN_COLUMNS = [
    ("ae_stage", sa.String(30)),
    ("contract_value", sa.Numeric(12, 2)),
    ("billing_cycle", sa.String(20)),
    ("commission_rate", sa.Numeric(5, 4)),
    ("commission_amount", sa.Numeric(12, 2)),
    ("commission_status", sa.String(20)),
    ("signed_at", sa.DateTime()),
    ("lost_reason", sa.Text()),
]


def upgrade():
    for name, col_type in _PLAIN_COLUMNS:
        if not _has_column("business_inquiries", name):
            op.add_column("business_inquiries", sa.Column(name, col_type, nullable=True))

    if not _has_column("business_inquiries", "assigned_ae_id"):
        with op.batch_alter_table("business_inquiries", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "assigned_ae_id",
                    sa.Integer(),
                    sa.ForeignKey("user.id", name="fk_business_inquiries_assigned_ae"),
                    nullable=True,
                )
            )
        op.create_index(
            "ix_business_inquiries_assigned_ae_id", "business_inquiries", ["assigned_ae_id"]
        )

    if not _has_column("business_inquiries", "linked_company_id"):
        with op.batch_alter_table("business_inquiries", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "linked_company_id",
                    sa.Integer(),
                    sa.ForeignKey("companies.id", name="fk_business_inquiries_linked_company"),
                    nullable=True,
                )
            )

    if _has_column("business_inquiries", "ae_stage"):
        op.execute("UPDATE business_inquiries SET ae_stage = 'prospect' WHERE ae_stage IS NULL")
    if _has_column("business_inquiries", "commission_status"):
        op.execute(
            "UPDATE business_inquiries SET commission_status = 'pending' WHERE commission_status IS NULL"
        )


def downgrade():
    if _has_column("business_inquiries", "linked_company_id"):
        with op.batch_alter_table("business_inquiries", schema=None) as batch_op:
            batch_op.drop_column("linked_company_id")

    if _has_column("business_inquiries", "assigned_ae_id"):
        try:
            op.drop_index("ix_business_inquiries_assigned_ae_id", table_name="business_inquiries")
        except Exception:
            pass
        with op.batch_alter_table("business_inquiries", schema=None) as batch_op:
            batch_op.drop_column("assigned_ae_id")

    for name, _col_type in reversed(_PLAIN_COLUMNS):
        if _has_column("business_inquiries", name):
            op.drop_column("business_inquiries", name)
