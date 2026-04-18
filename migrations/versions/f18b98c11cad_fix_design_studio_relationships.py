"""fix design project relationships

Revision ID: f18b98c11cad
Revises: f5f563891db3

Create Date: 2026-04-18
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "f18b98c11cad"
down_revision = "f5f563891db3"
branch_labels = None
depends_on = None


def upgrade():
    # ✅ add contact_id to vip_design_projects
    op.add_column(
        "vip_design_projects",
        sa.Column("contact_id", sa.Integer(), nullable=True),
    )

    # ✅ add foreign key constraint
    op.create_foreign_key(
        "fk_vip_design_projects_contact",
        "vip_design_projects",
        "vip_contacts",
        ["contact_id"],
        ["id"],
    )


def downgrade():
    # remove foreign key
    op.drop_constraint(
        "fk_vip_design_projects_contact",
        "vip_design_projects",
        type_="foreignkey",
    )

    # remove column
    op.drop_column("vip_design_projects", "contact_id")