"""add partner invite event

Revision ID: a42cef0d3266
Revises: f027518ead72
Create Date: 2026-03-21
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a42cef0d3266"
down_revision = "f027518ead72"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "partner_invite_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("partner_id", sa.Integer(), nullable=False),
        sa.Column("invite_token", sa.String(length=255), nullable=True),
        sa.Column("request_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.Column("ip_address", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(
            ["partner_id"],
            ["partners.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("partner_invite_event")
