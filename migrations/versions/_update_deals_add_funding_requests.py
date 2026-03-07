"""update deals and add funding requests

Revision ID: 9f3d2c7a4b10
Revises: YOUR_PREVIOUS_REVISION_ID
Create Date: 2026-03-07 08:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9f3d2c7a4b10"
down_revision = "YOUR_PREVIOUS_REVISION_ID"
branch_labels = None
depends_on = None


def upgrade():
    # =========================================================
    # DEALS TABLE UPDATES
    # =========================================================

    with op.batch_alter_table("deals", schema=None) as batch_op:
        # If user_id is currently missing a foreign key, this adds one.
        # Keep this only if your existing deals.user_id does NOT already have an FK.
        batch_op.create_foreign_key(
            "fk_deals_user_id_user",
            "user",
            ["user_id"],
            ["id"],
        )

        batch_op.add_column(sa.Column("address", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("city", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("state", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("zip_code", sa.String(length=20), nullable=True))

        batch_op.add_column(sa.Column("recommended_strategy", sa.String(length=50), nullable=True))

        batch_op.add_column(sa.Column("purchase_price", sa.Float(), nullable=True, server_default="0"))
        batch_op.add_column(sa.Column("arv", sa.Float(), nullable=True, server_default="0"))
        batch_op.add_column(sa.Column("estimated_rent", sa.Float(), nullable=True, server_default="0"))
        batch_op.add_column(sa.Column("rehab_cost", sa.Float(), nullable=True, server_default="0"))

        batch_op.add_column(sa.Column("deal_score", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("rehab_scope_json", sa.JSON(), nullable=True))

        batch_op.add_column(
            sa.Column("submitted_for_funding", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("funding_requested_at", sa.DateTime(), nullable=True))

    # Remove server defaults after backfilling existing rows safely
    with op.batch_alter_table("deals", schema=None) as batch_op:
        batch_op.alter_column("purchase_price", server_default=None)
        batch_op.alter_column("arv", server_default=None)
        batch_op.alter_column("estimated_rent", server_default=None)
        batch_op.alter_column("rehab_cost", server_default=None)
        batch_op.alter_column("submitted_for_funding", server_default=None)

    # =========================================================
    # FUNDING REQUESTS TABLE
    # =========================================================

    op.create_table(
        "funding_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("investor_id", sa.Integer(), nullable=False),
        sa.Column("deal_id", sa.Integer(), nullable=False),
        sa.Column("requested_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="submitted"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], name="fk_funding_requests_deal_id_deals"),
        sa.ForeignKeyConstraint(["investor_id"], ["user.id"], name="fk_funding_requests_investor_id_user"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_funding_requests_investor_id",
        "funding_requests",
        ["investor_id"],
        unique=False,
    )
    op.create_index(
        "ix_funding_requests_deal_id",
        "funding_requests",
        ["deal_id"],
        unique=False,
    )

    # Remove server defaults after creation if you want model-driven defaults only
    with op.batch_alter_table("funding_requests", schema=None) as batch_op:
        batch_op.alter_column("requested_amount", server_default=None)
        batch_op.alter_column("status", server_default=None)
        batch_op.alter_column("created_at", server_default=None)
        batch_op.alter_column("updated_at", server_default=None)


def downgrade():
    # =========================================================
    # DROP FUNDING REQUESTS
    # =========================================================

    op.drop_index("ix_funding_requests_deal_id", table_name="funding_requests")
    op.drop_index("ix_funding_requests_investor_id", table_name="funding_requests")
    op.drop_table("funding_requests")

    # =========================================================
    # REVERT DEALS TABLE
    # =========================================================

    with op.batch_alter_table("deals", schema=None) as batch_op:
        batch_op.drop_column("funding_requested_at")
        batch_op.drop_column("submitted_for_funding")
        batch_op.drop_column("rehab_scope_json")
        batch_op.drop_column("deal_score")
        batch_op.drop_column("rehab_cost")
        batch_op.drop_column("estimated_rent")
        batch_op.drop_column("arv")
        batch_op.drop_column("purchase_price")
        batch_op.drop_column("recommended_strategy")
        batch_op.drop_column("zip_code")
        batch_op.drop_column("state")
        batch_op.drop_column("city")
        batch_op.drop_column("address")

        # Only keep this if upgrade created the FK
        batch_op.drop_constraint("fk_deals_user_id_user", type_="foreignkey")