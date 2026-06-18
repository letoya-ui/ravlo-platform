"""Add beta_payment_sent to partners

Revision ID: a1b2c3d4e5f6
Revises: 8c889c33231d
Create Date: 2026-06-17 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = '8c889c33231d'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('partners')]
    if 'beta_payment_sent' not in columns:
        op.add_column(
            'partners',
            sa.Column('beta_payment_sent', sa.Boolean(), nullable=True, server_default=sa.false())
        )


def downgrade():
    op.drop_column('partners', 'beta_payment_sent')
