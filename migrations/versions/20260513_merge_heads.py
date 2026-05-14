"""merge all outstanding migration heads into a single chain

Revision ID: 20260513merge01
Revises: 20260513dfc01, 20260428iq01, 20260420r03, 0002b_deals_funding
Create Date: 2026-05-13 00:00:00.000000

Merges four open heads:
- 20260513dfc01     (deal_finder_cache)
- 20260428iq01      (insurance_quote_requests)
- 20260420r03       (add_county_to_elena_listings)
- 0002b_deals_funding (update_deals — renamed from duplicate 9f3d2c7a4b10)
"""
from alembic import op

revision = '20260513merge01'
down_revision = ('20260513dfc01', '20260428iq01', '20260420r03', '0002b_deals_funding')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
