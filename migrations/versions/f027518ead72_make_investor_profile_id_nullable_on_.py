"""make investor_profile_id nullable on document_event

Revision ID: f027518ead72
Revises: c6dea7f1b64d
Create Date: 2026-03-20 11:22:10.388347
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f027518ead72"
down_revision = "c6dea7f1b64d"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "document_event",
        "investor_profile_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade():
    op.alter_column(
        "document_event",
        "investor_profile_id",
        existing_type=sa.Integer(),
        nullable=False,
    )