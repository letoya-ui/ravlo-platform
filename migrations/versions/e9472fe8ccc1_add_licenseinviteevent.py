"""add license invite event

Revision ID: e9472fe8ccc1
Revises: 8c889c33231d
Create Date: 2026-04-07
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e9472fe8ccc1"
down_revision = "8c889c33231d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "license_invite_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invite_token", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("ip_address", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("ix_license_invite_events_email", "license_invite_events", ["email"], unique=False)
    op.create_index("ix_license_invite_events_invite_token", "license_invite_events", ["invite_token"], unique=False)
    op.create_index("ix_license_invite_events_event_type", "license_invite_events", ["event_type"], unique=False)

def downgrade():
    op.drop_index("ix_license_invite_events_event_type", table_name="license_invite_events")
    op.drop_index("ix_license_invite_events_invite_token", table_name="license_invite_events")
    op.drop_index("ix_license_invite_events_email", table_name="license_invite_events")
    op.drop_table("license_invite_events")