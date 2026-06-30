"""Add support_status and support_notes to contractor_bid_opportunities

Revision ID: 20260630bidsup01
Revises: 20260630surv01
Create Date: 2026-06-30 14:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '20260630bidsup01'
down_revision = '20260630surv01'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'contractor_bid_opportunities' not in existing_tables:
        return  # table created by earlier migration; nothing to alter yet

    cols = {c['name'] for c in inspector.get_columns('contractor_bid_opportunities')}

    if 'support_status' not in cols:
        op.add_column('contractor_bid_opportunities',
                      sa.Column('support_status', sa.String(60), nullable=True))

    if 'support_notes' not in cols:
        op.add_column('contractor_bid_opportunities',
                      sa.Column('support_notes', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('contractor_bid_opportunities', 'support_notes')
    op.drop_column('contractor_bid_opportunities', 'support_status')
