"""Add academy lesson progress, scores, and chat log tables

Revision ID: a1b2c3d4e5f6
Revises: f80fae86417f
Create Date: 2026-06-27 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'f80fae86417f'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = inspector.get_table_names()

    if 'academy_lesson_progress' not in existing:
        op.create_table(
            'academy_lesson_progress',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('module_id', sa.String(length=50), nullable=False),
            sa.Column('lesson_index', sa.Integer(), nullable=False),
            sa.Column('completed_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'module_id', 'lesson_index', name='uq_user_module_lesson'),
        )
        op.create_index('ix_academy_lesson_progress_user_id', 'academy_lesson_progress', ['user_id'])

    if 'academy_lesson_scores' not in existing:
        op.create_table(
            'academy_lesson_scores',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('module_id', sa.String(length=50), nullable=False),
            sa.Column('lesson_index', sa.Integer(), nullable=False),
            sa.Column('score', sa.Integer(), nullable=False),
            sa.Column('attempts', sa.Integer(), nullable=False),
            sa.Column('passed', sa.Boolean(), nullable=False),
            sa.Column('completed_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'module_id', 'lesson_index', name='uq_user_lesson_score'),
        )
        op.create_index('ix_academy_lesson_scores_user_id', 'academy_lesson_scores', ['user_id'])

    if 'academy_chat_logs' not in existing:
        op.create_table(
            'academy_chat_logs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('session_key', sa.String(length=100), nullable=True),
            sa.Column('tier', sa.String(length=30), nullable=True),
            sa.Column('feature', sa.String(length=30), nullable=False),
            sa.Column('system_prompt', sa.Text(), nullable=True),
            sa.Column('messages_json', sa.Text(), nullable=True),
            sa.Column('ai_response', sa.Text(), nullable=True),
            sa.Column('model', sa.String(length=60), nullable=True),
            sa.Column('thumbs_up', sa.Boolean(), nullable=True),
            sa.Column('approved_for_training', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_academy_chat_logs_user_id', 'academy_chat_logs', ['user_id'])

    if 'studio_generation_logs' not in existing:
        op.create_table(
            'studio_generation_logs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('feature', sa.String(length=50), nullable=False),
            sa.Column('provider', sa.String(length=30), nullable=False),
            sa.Column('output_mode', sa.String(length=50), nullable=True),
            sa.Column('prompt', sa.Text(), nullable=True),
            sa.Column('payload_json', sa.Text(), nullable=True),
            sa.Column('image_url', sa.String(length=512), nullable=True),
            sa.Column('quality_rating', sa.Integer(), nullable=True),
            sa.Column('approved_for_training', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_studio_generation_logs_user_id', 'studio_generation_logs', ['user_id'])

    if 'training_jobs' not in existing:
        op.create_table(
            'training_jobs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('job_type', sa.String(length=50), nullable=False),
            sa.Column('provider', sa.String(length=30), nullable=True),
            sa.Column('external_job_id', sa.String(length=255), nullable=True),
            sa.Column('status', sa.String(length=30), nullable=True),
            sa.Column('config_json', sa.Text(), nullable=True),
            sa.Column('result_json', sa.Text(), nullable=True),
            sa.Column('model_url', sa.String(length=512), nullable=True),
            sa.Column('sample_count', sa.Integer(), nullable=True),
            sa.Column('triggered_by', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['triggered_by'], ['user.id']),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'user_avenue_unlocks' not in existing:
        op.create_table(
            'user_avenue_unlocks',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('avenue_id', sa.String(length=50), nullable=False),
            sa.Column('stripe_payment_id', sa.String(length=255), nullable=True),
            sa.Column('unlocked_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'avenue_id', name='uq_user_avenue'),
        )
        op.create_index('ix_user_avenue_unlocks_user_id', 'user_avenue_unlocks', ['user_id'])


def downgrade():
    op.drop_table('user_avenue_unlocks')
    op.drop_table('training_jobs')
    op.drop_table('studio_generation_logs')
    op.drop_table('academy_chat_logs')
    op.drop_table('academy_lesson_scores')
    op.drop_table('academy_lesson_progress')
