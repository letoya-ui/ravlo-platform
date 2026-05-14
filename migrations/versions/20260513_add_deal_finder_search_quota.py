"""add deal_finder search quota columns to investor_profile

Revision ID: 20260513df01
Revises: 20260513ppl01
Create Date: 2026-05-13 00:00:00.000000

Adds:
- investor_profile.deal_finder_search_count  (Integer, default 0)
- investor_profile.deal_finder_search_reset_at (DateTime, nullable)
"""
from alembic import op
import sqlalchemy as sa

revision = '20260513df01'
down_revision = '20260513ppl01'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('investor_profile', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'deal_finder_search_count', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column(
            'deal_finder_search_reset_at', sa.DateTime(), nullable=True))

    op.execute("UPDATE investor_profile SET deal_finder_search_count = 0 WHERE deal_finder_search_count IS NULL")

    with op.batch_alter_table('investor_profile', schema=None) as batch_op:
        batch_op.alter_column(
            'deal_finder_search_count',
            existing_type=sa.Integer(),
            nullable=False,
        )


def downgrade():
    with op.batch_alter_table('investor_profile', schema=None) as batch_op:
        batch_op.drop_column('deal_finder_search_reset_at')
        batch_op.drop_column('deal_finder_search_count')
