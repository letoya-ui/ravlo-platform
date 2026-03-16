from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "020f690b0799"
down_revision = "e38e18913778"
branch_labels = None
depends_on = None


def upgrade():

    op.add_column("project_budgets", sa.Column("deal_id", sa.Integer(), nullable=True))
    op.add_column("project_budgets", sa.Column("build_project_id", sa.Integer(), nullable=True))
    op.add_column("project_budgets", sa.Column("budget_type", sa.String(length=50), nullable=False, server_default="rehab"))
    op.add_column("project_budgets", sa.Column("paid_amount", sa.Float(), nullable=True))

    op.create_foreign_key(
        None,
        "project_budgets",
        "deals",
        ["deal_id"],
        ["id"]
    )

    op.create_foreign_key(
        None,
        "project_budgets",
        "build_projects",
        ["build_project_id"],
        ["id"]
    )

    op.add_column("project_expenses", sa.Column("vendor", sa.String(length=255), nullable=True))
    op.add_column("project_expenses", sa.Column("status", sa.String(length=50), nullable=True))
    op.add_column("project_expenses", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("project_expenses", sa.Column("updated_at", sa.DateTime(), nullable=True))

def downgrade():

    op.drop_column("project_expenses", "updated_at")
    op.drop_column("project_expenses", "notes")
    op.drop_column("project_expenses", "status")
    op.drop_column("project_expenses", "vendor")

    op.drop_constraint(None, "project_budgets", type_="foreignkey")
    op.drop_constraint(None, "project_budgets", type_="foreignkey")

    op.drop_column("project_budgets", "paid_amount")
    op.drop_column("project_budgets", "budget_type")
    op.drop_column("project_budgets", "build_project_id")
    op.drop_column("project_budgets", "deal_id")
