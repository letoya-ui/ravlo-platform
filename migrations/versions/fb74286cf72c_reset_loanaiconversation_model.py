"""Reset LoanAIConversation model

Revision ID: fb74286cf72c
Revises: 
Create Date: 2025-11-07 23:09:20.831034

"""
import sqlalchemy as sa
from sqlalchemy import text
from alembic import op


# revision identifiers, used by Alembic.
revision = 'fb74286cf72c'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    # ---------- ai_audit_log ----------
    ai_exists = bind.execute(
        text("SELECT to_regclass('public.ai_audit_log')")
    ).scalar()

    if not ai_exists:
        op.create_table(
            'ai_audit_log',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('actor_role', sa.String(length=50), nullable=True),
            sa.Column('action', sa.String(length=255), nullable=True),
            sa.Column('result', sa.Text(), nullable=True),
            sa.Column('timestamp', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )

    # ---------- loan_ai_conversation ----------
    conv_exists = bind.execute(
        text("SELECT to_regclass('public.loan_ai_conversation')")
    ).scalar()

    if not conv_exists:
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
    bind = op.get_bind()

    conv_exists = bind.execute(
        text("SELECT to_regclass('public.loan_ai_conversation')")
    ).scalar()
    if conv_exists:
        op.drop_table('loan_ai_conversation')

    ai_exists = bind.execute(
        text("SELECT to_regclass('public.ai_audit_log')")
    ).scalar()
    if ai_exists:
        op.drop_table('ai_audit_log')
