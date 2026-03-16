"""merge migration heads

Revision ID: 4f2b8ad8cda7
Revises: 020f690b0799, 20260315, add_partner_bio_specialty
Create Date: 2026-03-16 18:02:45.348715

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4f2b8ad8cda7'
down_revision = ('020f690b0799', '20260315', 'add_partner_bio_specialty')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
