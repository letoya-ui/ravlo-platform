"""add discovery_events table

Revision ID: a1b2c3d4e5f6
Revises: f80fae86417f
Create Date: 2026-06-29 00:00:00.000000
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
    if not inspector.has_table("discovery_events"):
        op.create_table(
            "discovery_events",
            sa.Column("id",         sa.Integer(),     nullable=False),
            sa.Column("source",     sa.String(80),    nullable=False),
            sa.Column("user_agent", sa.Text(),        nullable=True),
            sa.Column("ip",         sa.String(50),    nullable=True),
            sa.Column("path",       sa.String(500),   nullable=True),
            sa.Column("created_at", sa.DateTime(),    nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_discovery_events_source",     "discovery_events", ["source"])
        op.create_index("ix_discovery_events_created_at", "discovery_events", ["created_at"])


def downgrade():
    op.drop_index("ix_discovery_events_created_at", table_name="discovery_events")
    op.drop_index("ix_discovery_events_source",     table_name="discovery_events")
    op.drop_table("discovery_events")
