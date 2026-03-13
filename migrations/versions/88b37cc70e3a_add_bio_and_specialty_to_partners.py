from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "add_partner_bio_specialty"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('partners', sa.Column('specialty', sa.String(length=255), nullable=True))
    op.add_column('partners', sa.Column('bio', sa.Text(), nullable=True))

def downgrade():
    op.drop_column('partners', 'bio')
    op.drop_column('partners', 'specialty')
