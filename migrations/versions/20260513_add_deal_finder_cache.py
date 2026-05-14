"""add deal_finder_cache table

Revision ID: 20260513dfc01
Revises: 20260513df01
Create Date: 2026-05-13 00:00:00.000000

Adds:
- deal_finder_cache table  (shared zip-code level cache for Deal Finder results)
  TTL-based: expires_at column controls freshness (default 24h)
  Keyed by zip_code + strategy + asset_type
"""
from alembic import op
import sqlalchemy as sa

revision = '20260513dfc01'
down_revision = '20260513df01'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not inspector.has_table('deal_finder_cache'):
        op.create_table(
            'deal_finder_cache',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('zip_code', sa.String(length=20), nullable=False),
            sa.Column('city', sa.String(length=100), nullable=True),
            sa.Column('state', sa.String(length=10), nullable=True),
            sa.Column('strategy', sa.String(length=30), nullable=False, server_default='all'),
            sa.Column('asset_type', sa.String(length=30), nullable=False, server_default='any'),
            sa.Column('results_json', sa.Text(), nullable=False),
            sa.Column('meta_json', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
        )
        dfc_idxs = set()
    else:
        dfc_idxs = {i["name"] for i in inspector.get_indexes('deal_finder_cache')}

    if 'ix_deal_finder_cache_zip_code' not in dfc_idxs:
        op.create_index('ix_deal_finder_cache_zip_code', 'deal_finder_cache', ['zip_code'])
    if 'ix_deal_finder_cache_expires_at' not in dfc_idxs:
        op.create_index('ix_deal_finder_cache_expires_at', 'deal_finder_cache', ['expires_at'])


def downgrade():
    op.drop_index('ix_deal_finder_cache_expires_at', table_name='deal_finder_cache')
    op.drop_index('ix_deal_finder_cache_zip_code', table_name='deal_finder_cache')
    op.drop_table('deal_finder_cache')
