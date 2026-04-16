"""Add Elena CRM, listing and flyers relation

Revision ID: 1382fd92af8d
Revises: 49dbf4a0bf81
Create Date: 2026-04-16 19:36:09.585444
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1382fd92af8d'
down_revision = '49dbf4a0bf81'
branch_labels = None
depends_on = None


def upgrade():
    # Create elena_listings table
    op.create_table(
        'elena_listings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('mls_number', sa.String(), nullable=False, index=True),

        sa.Column('address', sa.String(), nullable=True),
        sa.Column('city', sa.String(), nullable=True),
        sa.Column('state', sa.String(), nullable=True),
        sa.Column('zip_code', sa.String(), nullable=True),

        sa.Column('price', sa.Float(), nullable=True),
        sa.Column('beds', sa.Float(), nullable=True),
        sa.Column('baths', sa.Float(), nullable=True),
        sa.Column('sqft', sa.Integer(), nullable=True),
        sa.Column('lot_size', sa.Float(), nullable=True),
        sa.Column('property_type', sa.String(), nullable=True),
        sa.Column('year_built', sa.Integer(), nullable=True),

        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('photos_json', sa.Text(), nullable=True),

        sa.Column('client_id', sa.Integer(), sa.ForeignKey('elena_clients.id'), nullable=True),

        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # Create elena_flyers table
    op.create_table(
        'elena_flyers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('flyer_type', sa.Enum(
            'just_listed', 'just_sold', 'open_house', 'coming_soon',
            'price_drop', 'buyer_need', 'market_update',
            name='flyertype'
        ), nullable=False),

        sa.Column('property_address', sa.String(), nullable=True),
        sa.Column('property_id', sa.String(), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('export_url', sa.String(), nullable=True),

        sa.Column('listing_id', sa.Integer(), sa.ForeignKey('elena_listings.id'), nullable=True),

        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('created_by', sa.String(), server_default='elena'),
    )


def downgrade():
    op.drop_table('elena_flyers')
    op.drop_table('elena_listings')
