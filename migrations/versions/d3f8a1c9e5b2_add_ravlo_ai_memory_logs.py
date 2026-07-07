"""Add ravlo_ai_memory_logs table

Revision ID: d3f8a1c9e5b2
Revises: c7e1a9b4d2f0
Create Date: 2026-07-07 23:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'd3f8a1c9e5b2'
down_revision = 'c7e1a9b4d2f0'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = inspector.get_table_names()

    if 'ravlo_ai_memory_logs' not in existing:
        op.create_table(
            'ravlo_ai_memory_logs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('company_id', sa.Integer(), nullable=True),
            sa.Column('module', sa.String(length=80), nullable=False),
            sa.Column('feature', sa.String(length=100), nullable=True),
            sa.Column('event_type', sa.String(length=80), nullable=False),
            sa.Column('source', sa.String(length=80), nullable=True),
            sa.Column('role_view', sa.String(length=80), nullable=True),
            sa.Column('session_key', sa.String(length=120), nullable=True),
            sa.Column('prompt', sa.Text(), nullable=True),
            sa.Column('response', sa.Text(), nullable=True),
            sa.Column('summary', sa.Text(), nullable=True),
            sa.Column('metadata_json', sa.Text(), nullable=True),
            sa.Column('model', sa.String(length=100), nullable=True),
            sa.Column('provider', sa.String(length=50), nullable=True),
            sa.Column('object_type', sa.String(length=80), nullable=True),
            sa.Column('object_id', sa.String(length=80), nullable=True),
            sa.Column('quality_rating', sa.Integer(), nullable=True),
            sa.Column('approved_for_training', sa.Boolean(), nullable=False),
            sa.Column('contains_sensitive_data', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_ravlo_ai_memory_logs_user_id', 'ravlo_ai_memory_logs', ['user_id'])
        op.create_index('ix_ravlo_ai_memory_logs_company_id', 'ravlo_ai_memory_logs', ['company_id'])
        op.create_index('ix_ravlo_ai_memory_logs_module', 'ravlo_ai_memory_logs', ['module'])
        op.create_index('ix_ravlo_ai_memory_logs_feature', 'ravlo_ai_memory_logs', ['feature'])
        op.create_index('ix_ravlo_ai_memory_logs_event_type', 'ravlo_ai_memory_logs', ['event_type'])
        op.create_index('ix_ravlo_ai_memory_logs_session_key', 'ravlo_ai_memory_logs', ['session_key'])
        op.create_index('ix_ravlo_ai_memory_logs_object_type', 'ravlo_ai_memory_logs', ['object_type'])
        op.create_index('ix_ravlo_ai_memory_logs_object_id', 'ravlo_ai_memory_logs', ['object_id'])
        op.create_index('ix_ravlo_ai_memory_logs_approved_for_training', 'ravlo_ai_memory_logs', ['approved_for_training'])
        op.create_index('ix_ravlo_ai_memory_logs_created_at', 'ravlo_ai_memory_logs', ['created_at'])


def downgrade():
    op.drop_table('ravlo_ai_memory_logs')
