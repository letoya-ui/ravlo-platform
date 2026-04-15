"""add development_type and exterior_url to build_projects

Revision ID: 49db4fa0bfb1
Revises: d1a2b3c4e5f6
Create Date: 2026-04-15 22:05:42.359291
"""

from alembic import op
import sqlalchemy as sa

revision = "49db4fa0bfb1"
down_revision = "d1a2b3c4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("build_projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("development_type", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("exterior_url", sa.Text(), nullable=True))
        batch_op.alter_column(
            "property_type",
            existing_type=sa.VARCHAR(length=100),
            type_=sa.String(length=64),
            existing_nullable=True,
        )

    op.execute("""
        UPDATE build_projects
        SET development_type = CASE
            WHEN property_type = 'townhome' THEN 'townhomes'
            WHEN property_type = 'multifamily' THEN 'apartments'
            WHEN property_type = 'single_family' THEN 'single_family_subdivision'
            ELSE development_type
        END
        WHERE development_type IS NULL
    """)


def downgrade():
    with op.batch_alter_table("build_projects", schema=None) as batch_op:
        batch_op.alter_column(
            "property_type",
            existing_type=sa.String(length=64),
            type_=sa.VARCHAR(length=100),
            existing_nullable=True,
        )
        batch_op.drop_column("exterior_url")
        batch_op.drop_column("development_type")