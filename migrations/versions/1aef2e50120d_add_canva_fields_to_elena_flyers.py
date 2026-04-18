"""add canva fields to elena_flyers

Revision ID: 1aef2e50120d
Revises: 9dc35f5c0ad7
Create Date: 2026-04-18 16:10:56.792180
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1aef2e50120d"
down_revision = "9dc35f5c0ad7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("elena_flyers", schema=None) as batch_op:
        batch_op.add_column(sa.Column("canva_design_id", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("canva_edit_url", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("canva_export_job_id", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("canva_export_url", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("canva_status", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("canva_last_synced_at", sa.DateTime(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_elena_flyers_canva_design_id"),
            ["canva_design_id"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("elena_flyers", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_elena_flyers_canva_design_id"))
        batch_op.drop_column("canva_last_synced_at")
        batch_op.drop_column("canva_status")
        batch_op.drop_column("canva_export_url")
        batch_op.drop_column("canva_export_job_id")
        batch_op.drop_column("canva_edit_url")
        batch_op.drop_column("canva_design_id")