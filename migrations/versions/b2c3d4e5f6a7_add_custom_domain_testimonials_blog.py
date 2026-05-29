"""add custom_domain, vip_testimonials, vip_blog_posts

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-29 00:01:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # ── vip_profiles: custom_domain ──────────────────────────────────────────
    vp_cols = {c["name"] for c in inspector.get_columns("vip_profiles")} if inspector.has_table("vip_profiles") else set()
    with op.batch_alter_table('vip_profiles', schema=None) as batch_op:
        if "custom_domain" not in vp_cols:
            batch_op.add_column(sa.Column('custom_domain', sa.String(length=255), nullable=True))

    # ── vip_testimonials ─────────────────────────────────────────────────────
    if not inspector.has_table("vip_testimonials"):
        op.create_table(
            'vip_testimonials',
            sa.Column('id',            sa.Integer(),     nullable=False, autoincrement=True),
            sa.Column('created_at',    sa.DateTime(),    nullable=True),
            sa.Column('updated_at',    sa.DateTime(),    nullable=True),
            sa.Column('vip_profile_id', sa.Integer(),   nullable=False),
            sa.Column('reviewer_name', sa.String(255),  nullable=False),
            sa.Column('reviewer_title', sa.String(255), nullable=True),
            sa.Column('body',          sa.Text(),        nullable=False),
            sa.Column('rating',        sa.Integer(),     nullable=True),
            sa.Column('display_order', sa.Integer(),     nullable=False, server_default='0'),
            sa.Column('approved',      sa.Boolean(),     nullable=False, server_default='true'),
            sa.ForeignKeyConstraint(['vip_profile_id'], ['vip_profiles.id']),
            sa.PrimaryKeyConstraint('id'),
        )

    # ── vip_blog_posts ───────────────────────────────────────────────────────
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
    with op.batch_alter_table('vip_profiles', schema=None) as batch_op:
        batch_op.drop_column('custom_domain')
