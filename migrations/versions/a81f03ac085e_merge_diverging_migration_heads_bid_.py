"""Merge diverging migration heads (bid-discovery, elena-lead-owner, ai-memory-logs)

Revision ID: a81f03ac085e
Revises: 20260707bd01, 20260707lo01, d3f8a1c9e5b2
Create Date: 2026-07-09 08:29:45.361693

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a81f03ac085e'
down_revision = ('20260707bd01', '20260707lo01', 'd3f8a1c9e5b2')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
