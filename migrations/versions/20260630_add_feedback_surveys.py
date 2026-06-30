"""Add feedback_surveys table

Revision ID: 20260630surv01
Revises: 20260630fin01
Create Date: 2026-06-30 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '20260630surv01'
down_revision = '20260630fin01'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = inspector.get_table_names()

    if 'feedback_surveys' not in existing:
        op.create_table(
            'feedback_surveys',
            sa.Column('id',           sa.Integer(),    primary_key=True),
            sa.Column('name',         sa.String(150),  nullable=True),
            sa.Column('email',        sa.String(255),  nullable=True),
            sa.Column('nps_score',    sa.Integer(),    nullable=False),
            sa.Column('liked',        sa.Text(),       nullable=True),
            sa.Column('improve',      sa.Text(),       nullable=True),
            sa.Column('source',       sa.String(50),   nullable=True),
            sa.Column('submitted_at', sa.DateTime(),   nullable=True),
        )


def downgrade():
    op.drop_table('feedback_surveys')
