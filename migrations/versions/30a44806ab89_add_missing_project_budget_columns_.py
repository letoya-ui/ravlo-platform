from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "30a44806ab89"
down_revision = "4f2b8ad8cda7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("project_budgets", sa.Column("deal_id", sa.Integer(), nullable=True))
    op.add_column("project_budgets", sa.Column("build_project_id", sa.Integer(), nullable=True))
    op.add_column("project_budgets", sa.Column("budget_type", sa.String(length=50), nullable=False, server_default="rehab"))
    op.add_column("project_budgets", sa.Column("paid_amount", sa.Float(), nullable=True, server_default="0"))

    op.create_foreign_key(
        "fk_project_budgets_deal_id_manual",
        "project_budgets",
        "deals",
        ["deal_id"],
        ["id"],
    )

    op.create_foreign_key(
        "fk_project_budgets_build_project_id_manual",
        "project_budgets",
        "build_projects",
        ["build_project_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint("fk_project_budgets_build_project_id_manual", "project_budgets", type_="foreignkey")
    op.drop_constraint("fk_project_budgets_deal_id_manual", "project_budgets", type_="foreignkey")

    op.drop_column("project_budgets", "paid_amount")
    op.drop_column("project_budgets", "budget_type")
    op.drop_column("project_budgets", "build_project_id")
    op.drop_column("project_budgets", "deal_id")