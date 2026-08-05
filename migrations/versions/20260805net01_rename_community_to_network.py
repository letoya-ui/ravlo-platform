"""Rename Ravlo Community tables to Ravlo Network

Revision ID: 20260805net01
Revises: 20260805com01
Create Date: 2026-08-05 00:00:00.000000

Product rename: "Community" -> "Network". Renames the already-merged
community_groups/community_posts/community_comments tables (and their
indexes) to network_groups/network_posts/network_comments -- no column
changes, just names, to match the new model/route/template names.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260805net01"
down_revision = "20260805com01"
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
    if _has_table("community_comments") and not _has_table("network_comments"):
        op.drop_index("ix_community_comments_author_user_id", table_name="community_comments")
        op.drop_index("ix_community_comments_post_id", table_name="community_comments")
        op.rename_table("community_comments", "network_comments")
        op.create_index("ix_network_comments_post_id", "network_comments", ["post_id"])
        op.create_index("ix_network_comments_author_user_id", "network_comments", ["author_user_id"])

    if _has_table("community_posts") and not _has_table("network_posts"):
        op.drop_index("ix_community_posts_author_user_id", table_name="community_posts")
        op.drop_index("ix_community_posts_group_id", table_name="community_posts")
        op.rename_table("community_posts", "network_posts")
        op.create_index("ix_network_posts_group_id", "network_posts", ["group_id"])
        op.create_index("ix_network_posts_author_user_id", "network_posts", ["author_user_id"])

    if _has_table("community_groups") and not _has_table("network_groups"):
        op.drop_index("ix_community_groups_slug", table_name="community_groups")
        op.rename_table("community_groups", "network_groups")
        op.create_index("ix_network_groups_slug", "network_groups", ["slug"], unique=True)


def downgrade():
    if _has_table("network_groups") and not _has_table("community_groups"):
        op.drop_index("ix_network_groups_slug", table_name="network_groups")
        op.rename_table("network_groups", "community_groups")
        op.create_index("ix_community_groups_slug", "community_groups", ["slug"], unique=True)

    if _has_table("network_posts") and not _has_table("community_posts"):
        op.drop_index("ix_network_posts_author_user_id", table_name="network_posts")
        op.drop_index("ix_network_posts_group_id", table_name="network_posts")
        op.rename_table("network_posts", "community_posts")
        op.create_index("ix_community_posts_group_id", "community_posts", ["group_id"])
        op.create_index("ix_community_posts_author_user_id", "community_posts", ["author_user_id"])

    if _has_table("network_comments") and not _has_table("community_comments"):
        op.drop_index("ix_network_comments_author_user_id", table_name="network_comments")
        op.drop_index("ix_network_comments_post_id", table_name="network_comments")
        op.rename_table("network_comments", "community_comments")
        op.create_index("ix_community_comments_post_id", "community_comments", ["post_id"])
        op.create_index("ix_community_comments_author_user_id", "community_comments", ["author_user_id"])
