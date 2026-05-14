"""update deals and add funding requests

Revision ID: 0002b_deals_funding
Revises: 0002
Create Date: 2026-03-07 08:30:00.000000

Note: renamed from accidental duplicate of 9f3d2c7a4b10_company_access_invite.
Upgrade is idempotent — safe to run even if columns/table already exist.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002b_deals_funding"
down_revision = "0002"
branch_labels = None
depends_on = None


def _col_exists(inspector, table, col):
    return col in {c["name"] for c in inspector.get_columns(table)}


def _table_exists(inspector, table):
    return inspector.has_table(table)


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # ── Deals table columns ──────────────────────────────────────
    deals_cols = {c["name"] for c in inspector.get_columns("deals")}

    with op.batch_alter_table("deals", schema=None) as batch_op:
        if "address" not in deals_cols:
            batch_op.add_column(sa.Column("address", sa.String(length=255), nullable=True))
        if "city" not in deals_cols:
            batch_op.add_column(sa.Column("city", sa.String(length=120), nullable=True))
        if "state" not in deals_cols:
            batch_op.add_column(sa.Column("state", sa.String(length=50), nullable=True))
        if "zip_code" not in deals_cols:
            batch_op.add_column(sa.Column("zip_code", sa.String(length=20), nullable=True))
        if "recommended_strategy" not in deals_cols:
            batch_op.add_column(sa.Column("recommended_strategy", sa.String(length=50), nullable=True))
        if "purchase_price" not in deals_cols:
            batch_op.add_column(sa.Column("purchase_price", sa.Float(), nullable=True))
        if "arv" not in deals_cols:
            batch_op.add_column(sa.Column("arv", sa.Float(), nullable=True))
        if "estimated_rent" not in deals_cols:
            batch_op.add_column(sa.Column("estimated_rent", sa.Float(), nullable=True))
        if "rehab_cost" not in deals_cols:
            batch_op.add_column(sa.Column("rehab_cost", sa.Float(), nullable=True))
        if "deal_score" not in deals_cols:
            batch_op.add_column(sa.Column("deal_score", sa.Integer(), nullable=True))
        if "rehab_scope_json" not in deals_cols:
            batch_op.add_column(sa.Column("rehab_scope_json", sa.JSON(), nullable=True))
        if "submitted_for_funding" not in deals_cols:
            batch_op.add_column(sa.Column("submitted_for_funding", sa.Boolean(), nullable=True))
        if "funding_requested_at" not in deals_cols:
            batch_op.add_column(sa.Column("funding_requested_at", sa.DateTime(), nullable=True))

    # ── funding_requests table ───────────────────────────────────
    if not _table_exists(inspector, "funding_requests"):
        op.create_table(
            "funding_requests",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("investor_id", sa.Integer(), nullable=False),
            sa.Column("deal_id", sa.Integer(), nullable=False),
            sa.Column("requested_amount", sa.Float(), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], name="fk_funding_requests_deal_id_deals"),
            sa.ForeignKeyConstraint(["investor_id"], ["user.id"], name="fk_funding_requests_investor_id_user"),
            sa.PrimaryKeyConstraint("id"),
        )

        existing_indexes = {idx["name"] for idx in inspector.get_indexes("funding_requests")} if _table_exists(inspector, "funding_requests") else set()
        if "ix_funding_requests_investor_id" not in existing_indexes:
            op.create_index("ix_funding_requests_investor_id", "funding_requests", ["investor_id"], unique=False)
        if "ix_funding_requests_deal_id" not in existing_indexes:
            op.create_index("ix_funding_requests_deal_id", "funding_requests", ["deal_id"], unique=False)


def downgrade():
    try:
        op.drop_index("ix_funding_requests_deal_id", table_name="funding_requests")
    except Exception:
        pass
    try:
        op.drop_index("ix_funding_requests_investor_id", table_name="funding_requests")
    except Exception:
        pass
    try:
        op.drop_table("funding_requests")
    except Exception:
        pass

    with op.batch_alter_table("deals", schema=None) as batch_op:
        for col in ["funding_requested_at", "submitted_for_funding", "rehab_scope_json",
                    "deal_score", "rehab_cost", "estimated_rent", "arv", "purchase_price",
                    "recommended_strategy", "zip_code", "state", "city", "address"]:
            try:
                batch_op.drop_column(col)
            except Exception:
                pass
