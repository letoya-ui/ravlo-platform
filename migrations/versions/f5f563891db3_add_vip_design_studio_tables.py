"""add vip design studio tables

Revision ID: add_vip_design_studio_tables
Revises: <your_previous_revision_id>
Create Date: 2026-04-18
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_vip_design_studio_tables"
down_revision = "<your_previous_revision_id>"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "vip_design_projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),

        sa.Column("vip_profile_id", sa.Integer(), nullable=False),
        sa.Column("contact_id", sa.Integer(), nullable=True),

        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="draft"),

        sa.Column("source_file", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),

        sa.ForeignKeyConstraint(["vip_profile_id"], ["vip_profiles.id"]),
        sa.ForeignKeyConstraint(["contact_id"], ["vip_contacts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "vip_design_annotations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),

        sa.Column("project_id", sa.Integer(), nullable=False),

        sa.Column("annotation_type", sa.String(length=50), nullable=True),
        sa.Column("action_type", sa.String(length=50), nullable=True),

        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),

        sa.Column("x", sa.Integer(), nullable=True),
        sa.Column("y", sa.Integer(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),

        sa.ForeignKeyConstraint(["project_id"], ["vip_design_projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("vip_design_annotations")
    op.drop_table("vip_design_projects")