"""Elena dashboard — add missing fields on clients / listings / flyers / interactions

Revision ID: 20260417elena01
Revises: 1382fd92af8d
Create Date: 2026-04-17 14:00:00.000000

Adds the fields required by the Elena CRM dashboard spec:

- ``elena_clients.role`` (contact role: realtor, investor, contractor, etc.)
- ``elena_clients.tags`` (comma-separated tags)
- ``elena_listings.status`` (active, pending, sold, withdrawn)
- ``elena_flyers.title`` (optional flyer title)
- ``elena_flyers.cta`` (optional call-to-action)
- ``elena_interactions.due_at`` (optional follow-up / meeting time)

All columns are nullable or have defaults, so the migration is safe to run on
existing data and is fully reversible.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260417elena01"
down_revision = "1382fd92af8d"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("elena_clients") as batch:
        batch.add_column(sa.Column("role", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("tags", sa.String(length=255), nullable=True))

    with op.batch_alter_table("elena_listings") as batch:
        batch.add_column(
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default="active",
            )
        )

    with op.batch_alter_table("elena_flyers") as batch:
        batch.add_column(sa.Column("title", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("cta", sa.String(length=255), nullable=True))

    with op.batch_alter_table("elena_interactions") as batch:
        batch.add_column(sa.Column("due_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("elena_interactions") as batch:
        batch.drop_column("due_at")

    with op.batch_alter_table("elena_flyers") as batch:
        batch.drop_column("cta")
        batch.drop_column("title")

    with op.batch_alter_table("elena_listings") as batch:
        batch.drop_column("status")

    with op.batch_alter_table("elena_clients") as batch:
        batch.drop_column("tags")
        batch.drop_column("role")
