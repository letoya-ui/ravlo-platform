"""add markets_json to vip_profiles

Revision ID: a1b2c3d4e5f6
Revises: f80fae86417f
Create Date: 2026-04-19 21:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f80fae86417f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('vip_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('markets_json', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('vip_profiles', schema=None) as batch_op:
        batch_op.drop_column('markets_json')
