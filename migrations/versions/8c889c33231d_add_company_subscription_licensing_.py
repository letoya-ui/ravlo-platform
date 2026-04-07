"""add company subscription + licensing models

Revision ID: 8c889c33231d
Revises: 08c332fe7527
Create Date: 2026-04-07 12:20:07.492310

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8c889c33231d'
down_revision = '08c332fe7527'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'license_applications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=255), nullable=False),
        sa.Column('contact_name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('website', sa.String(length=255), nullable=True),
        sa.Column('business_type', sa.String(length=100), nullable=True),
        sa.Column('team_size', sa.String(length=50), nullable=True),
        sa.Column('plan_interest', sa.String(length=100), nullable=True),
        sa.Column('monthly_loan_volume', sa.String(length=100), nullable=True),
        sa.Column('current_tools', sa.Text(), nullable=True),
        sa.Column('goals', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='new'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    with op.batch_alter_table('license_applications', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_license_applications_email'),
            ['email'],
            unique=False
        )

    with op.batch_alter_table('companies', schema=None) as batch_op:
        batch_op.add_column(sa.Column('subscription_tier', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('max_users', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('companies', schema=None) as batch_op:
        batch_op.drop_column('max_users')
        batch_op.drop_column('subscription_tier')

    with op.batch_alter_table('license_applications', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_license_applications_email'))

    op.drop_table('license_applications')