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
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    ef_cols = {c["name"] for c in inspector.get_columns("elena_flyers")} if inspector.has_table("elena_flyers") else set()
    ef_idxs = {i["name"] for i in inspector.get_indexes("elena_flyers")} if inspector.has_table("elena_flyers") else set()
    with op.batch_alter_table("elena_flyers", schema=None) as batch_op:
        if "canva_design_id" not in ef_cols:
            batch_op.add_column(sa.Column("canva_design_id", sa.String(length=128), nullable=True))
        if "canva_edit_url" not in ef_cols:
            batch_op.add_column(sa.Column("canva_edit_url", sa.Text(), nullable=True))
        if "canva_export_job_id" not in ef_cols:
            batch_op.add_column(sa.Column("canva_export_job_id", sa.String(length=128), nullable=True))
        if "canva_export_url" not in ef_cols:
            batch_op.add_column(sa.Column("canva_export_url", sa.Text(), nullable=True))
        if "canva_status" not in ef_cols:
            batch_op.add_column(sa.Column("canva_status", sa.String(length=50), nullable=True))
        if "canva_last_synced_at" not in ef_cols:
            batch_op.add_column(sa.Column("canva_last_synced_at", sa.DateTime(), nullable=True))
        if "ix_elena_flyers_canva_design_id" not in ef_idxs:
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