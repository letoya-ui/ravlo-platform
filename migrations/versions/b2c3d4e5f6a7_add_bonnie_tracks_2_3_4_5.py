"""Merge heads + add ga_measurement_id, gsc_verification_code, custom_domain,
vip_testimonials, vip_blog_posts.

Merges the main chain (20260514cs01) with the markets_json branch (a1b2c3d4e5f6)
and applies all columns/tables added for Bonnie's white-label site Tracks 2-5.

Uses ALTER TABLE ... ADD COLUMN IF NOT EXISTS (PostgreSQL 9.6+) so the upgrade
is safe to re-run even if the columns were added manually.

Revision ID: b2c3d4e5f6a7
Revises: 20260514cs01, a1b2c3d4e5f6
Create Date: 2026-05-29 00:02:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = ('20260514cs01', 'a1b2c3d4e5f6')
branch_labels = None
depends_on = None


def upgrade():
    # Use raw SQL with IF NOT EXISTS so this is idempotent on PostgreSQL.
    # batch_alter_table is silently a no-op for conditional adds on Postgres.
    op.execute("ALTER TABLE vip_profiles ADD COLUMN IF NOT EXISTS ga_measurement_id VARCHAR(50)")
    op.execute("ALTER TABLE vip_profiles ADD COLUMN IF NOT EXISTS gsc_verification_code VARCHAR(100)")
    op.execute("ALTER TABLE vip_profiles ADD COLUMN IF NOT EXISTS custom_domain VARCHAR(255)")

    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not inspector.has_table("vip_testimonials"):
        op.create_table(
            'vip_testimonials',
            sa.Column('id',             sa.Integer(),    nullable=False, autoincrement=True),
            sa.Column('created_at',     sa.DateTime(),   nullable=True),
            sa.Column('updated_at',     sa.DateTime(),   nullable=True),
            sa.Column('vip_profile_id', sa.Integer(),    nullable=False),
            sa.Column('reviewer_name',  sa.String(255),  nullable=False),
            sa.Column('reviewer_title', sa.String(255),  nullable=True),
            sa.Column('body',           sa.Text(),       nullable=False),
            sa.Column('rating',         sa.Integer(),    nullable=True),
            sa.Column('display_order',  sa.Integer(),    nullable=False, server_default='0'),
            sa.Column('approved',       sa.Boolean(),    nullable=False, server_default='true'),
            sa.ForeignKeyConstraint(['vip_profile_id'], ['vip_profiles.id']),
            sa.PrimaryKeyConstraint('id'),
        )

    if not inspector.has_table("vip_blog_posts"):
        op.create_table(
            'vip_blog_posts',
            sa.Column('id',             sa.Integer(),    nullable=False, autoincrement=True),
            sa.Column('created_at',     sa.DateTime(),   nullable=True),
            sa.Column('updated_at',     sa.DateTime(),   nullable=True),
            sa.Column('vip_profile_id', sa.Integer(),    nullable=False),
            sa.Column('title',          sa.String(255),  nullable=False),
            sa.Column('slug',           sa.String(255),  nullable=False),
            sa.Column('summary',        sa.String(500),  nullable=True),
            sa.Column('body',           sa.Text(),       nullable=True),
            sa.Column('cover_image_url', sa.String(500), nullable=True),
            sa.Column('is_published',   sa.Boolean(),    nullable=False, server_default='false'),
            sa.Column('published_at',   sa.DateTime(),   nullable=True),
            sa.ForeignKeyConstraint(['vip_profile_id'], ['vip_profiles.id']),
            sa.PrimaryKeyConstraint('id'),
        )


def downgrade():
    op.drop_table('vip_blog_posts')
    op.drop_table('vip_testimonials')
    op.execute("ALTER TABLE vip_profiles DROP COLUMN IF EXISTS custom_domain")
    op.execute("ALTER TABLE vip_profiles DROP COLUMN IF EXISTS gsc_verification_code")
    op.execute("ALTER TABLE vip_profiles DROP COLUMN IF EXISTS ga_measurement_id")
