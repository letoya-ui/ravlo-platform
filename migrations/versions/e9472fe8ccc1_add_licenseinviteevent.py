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
        "license_invite_event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),

        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("invite_email", sa.String(length=255), nullable=True),
        sa.Column("invite_token", sa.String(length=255), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),

        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"], ),
    )

    op.create_index(
        "ix_license_invite_event_invite_email",
        "license_invite_event",
        ["invite_email"],
        unique=False,
    )

    op.create_index(
        "ix_license_invite_event_invite_token",
        "license_invite_event",
        ["invite_token"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_license_invite_event_invite_token", table_name="license_invite_event")
    op.drop_index("ix_license_invite_event_invite_email", table_name="license_invite_event")
    op.drop_table("license_invite_event")