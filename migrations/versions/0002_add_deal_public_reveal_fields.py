"""Add Deal public reveal fields

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("deals", sa.Column("reveal_public_id", sa.String(length=32), nullable=True))
    op.add_column("deals", sa.Column("reveal_is_public", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("deals", sa.Column("reveal_published_at", sa.DateTime(), nullable=True))

    op.create_index("ix_deals_reveal_public_id", "deals", ["reveal_public_id"], unique=True)


def downgrade():
    op.drop_index("ix_deals_reveal_public_id", table_name="deals")

    op.drop_column("deals", "reveal_published_at")
    op.drop_column("deals", "reveal_is_public")
    op.drop_column("deals", "reveal_public_id")

def upgrade():
    op.create_table(
        'rehab_jobs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('deal_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('plan_url', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('result_plan', sa.Text(), nullable=True),
        sa.Column('result_cost_low', sa.Integer(), nullable=True),
        sa.Column('result_cost_high', sa.Integer(), nullable=True),
        sa.Column('result_arv', sa.Integer(), nullable=True),
        sa.Column('result_images', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade():
    op.drop_table('rehab_jobs')
