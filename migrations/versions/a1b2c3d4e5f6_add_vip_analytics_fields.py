"""add ga_measurement_id and gsc_verification_code to vip_profiles

Revision ID: a1b2c3d4e5f6
Revises: f80fae86417f
Create Date: 2026-05-29 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f80fae86417f'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    vp_cols = {c["name"] for c in inspector.get_columns("vip_profiles")} if inspector.has_table("vip_profiles") else set()
    with op.batch_alter_table('vip_profiles', schema=None) as batch_op:
        if "ga_measurement_id" not in vp_cols:
            batch_op.add_column(sa.Column('ga_measurement_id', sa.String(length=50), nullable=True))
        if "gsc_verification_code" not in vp_cols:
            batch_op.add_column(sa.Column('gsc_verification_code', sa.String(length=100), nullable=True))


def downgrade():
    with op.batch_alter_table('vip_profiles', schema=None) as batch_op:
        batch_op.drop_column('gsc_verification_code')
        batch_op.drop_column('ga_measurement_id')
