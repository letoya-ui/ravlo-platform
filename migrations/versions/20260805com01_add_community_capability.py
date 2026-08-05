"""Add Ravlo Community: groups, posts, comments

Revision ID: 20260805com01
Revises: 20260805pay01
Create Date: 2026-08-05 00:00:00.000000

v1 of Ravlo Community -- professional networking across the ecosystem,
not a consumer social feed. Adds community_groups (one seeded "Real
Estate" group for v1), community_posts, and community_comments.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260805com01"
down_revision = "20260805pay01"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_table(table):
    try:
        return _insp().has_table(table)
    except Exception:
        return False


def upgrade():
    if not _has_table("community_groups"):
        op.create_table(
            "community_groups",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("slug", sa.String(100), nullable=False),
            sa.Column("name", sa.String(150), nullable=False),
            sa.Column("description", sa.String(500), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_community_groups_slug", "community_groups", ["slug"], unique=True)

    if not _has_table("community_posts"):
        op.create_table(
            "community_posts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "group_id", sa.Integer(),
                sa.ForeignKey("community_groups.id", name="fk_post_group_id"), nullable=False,
            ),
            sa.Column(
                "author_user_id", sa.Integer(),
                sa.ForeignKey("user.id", name="fk_post_author_id"), nullable=False,
            ),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_community_posts_group_id", "community_posts", ["group_id"])
        op.create_index("ix_community_posts_author_user_id", "community_posts", ["author_user_id"])

    if not _has_table("community_comments"):
        op.create_table(
            "community_comments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "post_id", sa.Integer(),
                sa.ForeignKey("community_posts.id", name="fk_comment_post_id"), nullable=False,
            ),
            sa.Column(
                "author_user_id", sa.Integer(),
                sa.ForeignKey("user.id", name="fk_comment_author_id"), nullable=False,
            ),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_community_comments_post_id", "community_comments", ["post_id"])
        op.create_index("ix_community_comments_author_user_id", "community_comments", ["author_user_id"])


def downgrade():
    if _has_table("community_comments"):
        op.drop_index("ix_community_comments_author_user_id", table_name="community_comments")
        op.drop_index("ix_community_comments_post_id", table_name="community_comments")
        op.drop_table("community_comments")

    if _has_table("community_posts"):
        op.drop_index("ix_community_posts_author_user_id", table_name="community_posts")
        op.drop_index("ix_community_posts_group_id", table_name="community_posts")
        op.drop_table("community_posts")

    if _has_table("community_groups"):
        op.drop_index("ix_community_groups_slug", table_name="community_groups")
        op.drop_table("community_groups")
