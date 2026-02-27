"""Recreate LoanAIConversation clean schema

Revision ID: 265e3611df8e
Revises: fb74286cf72c
Create Date: 2025-11-07 23:14:48.411447
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '265e3611df8e'
down_revision = 'fb74286cf72c'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    conv_exists = bind.execute(
        text("SELECT to_regclass('public.loan_ai_conversation')")
    ).scalar()

    if conv_exists:
        # table already exists — skip creation (prevents DuplicateTable)
        return

    op.create_table(
        'loan_ai_conversation',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('loan_id', sa.Integer(), nullable=True),
        sa.Column('sender', sa.String(length=50), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('borrower_id', sa.Integer(), nullable=True),
        sa.Column('user_role', sa.String(length=50), nullable=True),
        sa.Column('topic', sa.String(length=120), nullable=True),
        sa.Column('user_message', sa.Text(), nullable=False),
        sa.Column('ai_response', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['borrower_id'], ['borrower_profile.id']),
        sa.ForeignKeyConstraint(['loan_id'], ['loan_application.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('loan_ai_conversation')
