"""Add product/service listing fields + image to network_posts

Revision ID: 20260813nw02
Revises: 20260813lp01
Create Date: 2026-08-13 00:00:00.000000

Ravlo Network v2: members can post structured product/service listings
(title, category, price, photo) instead of only free text. listing_type
defaults to "update" so every existing NetworkPost row keeps rendering
exactly as before. See network_routes.py's create_post()/feed().
"""

from alembic import op
import sqlalchemy as sa


revision = "20260813nw02"
down_revision = "20260813lp01"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_column(table, column):
    try:
        return column in {c["name"] for c in _insp().get_columns(table)}
    except Exception:
        return False


def upgrade():
    if not _has_column("network_posts", "listing_type"):
        op.add_column(
            "network_posts",
            sa.Column("listing_type", sa.String(20), nullable=False, server_default="update"),
        )
        op.alter_column("network_posts", "listing_type", server_default=None)
    if not _has_column("network_posts", "title"):
        op.add_column("network_posts", sa.Column("title", sa.String(150), nullable=True))
    if not _has_column("network_posts", "category"):
        op.add_column("network_posts", sa.Column("category", sa.String(50), nullable=True))
    if not _has_column("network_posts", "price_label"):
        op.add_column("network_posts", sa.Column("price_label", sa.String(50), nullable=True))
    if not _has_column("network_posts", "image_url"):
        op.add_column("network_posts", sa.Column("image_url", sa.String(500), nullable=True))


def downgrade():
    if _has_column("network_posts", "image_url"):
        op.drop_column("network_posts", "image_url")
    if _has_column("network_posts", "price_label"):
        op.drop_column("network_posts", "price_label")
    if _has_column("network_posts", "category"):
        op.drop_column("network_posts", "category")
    if _has_column("network_posts", "title"):
        op.drop_column("network_posts", "title")
    if _has_column("network_posts", "listing_type"):
        op.drop_column("network_posts", "listing_type")
