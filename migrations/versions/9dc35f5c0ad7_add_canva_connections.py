from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "9dc35f5c0ad7"
down_revision = "5fd82a8f3e41"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "canva_connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("scope", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "partner_note",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("partner_id", sa.Integer(), nullable=False),
        sa.Column("author", sa.String(length=120), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["partner_id"], ["partners.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    with op.batch_alter_table("elena_flyers", schema=None) as batch_op:
        batch_op.alter_column(
            "flyer_type",
            existing_type=postgresql.ENUM(
                "just_listed",
                "just_sold",
                "open_house",
                "coming_soon",
                "price_drop",
                "buyer_need",
                "market_update",
                name="flyertype",
            ),
            type_=sa.String(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "property_address",
            existing_type=sa.VARCHAR(),
            nullable=False,
        )
        batch_op.drop_column("export_url")
        batch_op.drop_column("created_by")

    with op.batch_alter_table("elena_listings", schema=None) as batch_op:
        batch_op.alter_column(
            "mls_number",
            existing_type=sa.VARCHAR(),
            nullable=True,
        )
        batch_op.alter_column(
            "address",
            existing_type=sa.VARCHAR(),
            nullable=False,
        )
        batch_op.alter_column(
            "city",
            existing_type=sa.VARCHAR(),
            nullable=False,
        )
        batch_op.alter_column(
            "state",
            existing_type=sa.VARCHAR(),
            nullable=False,
        )
        batch_op.alter_column(
            "zip_code",
            existing_type=sa.VARCHAR(),
            nullable=False,
        )
        batch_op.alter_column(
            "beds",
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            type_=sa.Integer(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "baths",
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            type_=sa.Integer(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "price",
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            type_=sa.Integer(),
            existing_nullable=True,
        )
        batch_op.drop_index(batch_op.f("ix_elena_listings_mls_number"))
        batch_op.drop_column("lot_size")
        batch_op.drop_column("property_type")
        batch_op.drop_column("year_built")

    with op.batch_alter_table("vip_assistant_actions", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("vip_assistant_actions_listing_id_fkey"),
            type_="foreignkey",
        )
        batch_op.drop_column("listing_id")

    with op.batch_alter_table("vip_assistant_suggestions", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("vip_assistant_suggestions_listing_id_fkey"),
            type_="foreignkey",
        )
        batch_op.drop_column("listing_id")

    with op.batch_alter_table("vip_budgets", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("vip_budgets_listing_id_fkey"),
            type_="foreignkey",
        )
        batch_op.drop_column("listing_id")

    with op.batch_alter_table("vip_expenses", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("vip_expenses_listing_id_fkey"),
            type_="foreignkey",
        )
        batch_op.drop_column("listing_id")

    with op.batch_alter_table("vip_income", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("vip_income_listing_id_fkey"),
            type_="foreignkey",
        )
        batch_op.drop_column("listing_id")

    with op.batch_alter_table("vip_interactions", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("vip_interactions_listing_id_fkey"),
            type_="foreignkey",
        )
        batch_op.drop_column("listing_id")

    with op.batch_alter_table("vip_profiles", schema=None) as batch_op:
        batch_op.add_column(sa.Column("dashboard_title", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("headline", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("bio", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("service_area", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("specialties", sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column("marketplace_enabled", sa.String(length=10), nullable=False, server_default="no")
        )
        batch_op.add_column(sa.Column("public_slug", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("enabled_modules", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("brand_color", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("logo_url", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("profile_image_url", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("cover_image_url", sa.String(length=500), nullable=True))

    with op.batch_alter_table("vip_profiles", schema=None) as batch_op:
        batch_op.alter_column("marketplace_enabled", server_default=None)


def downgrade():
    with op.batch_alter_table("vip_profiles", schema=None) as batch_op:
        batch_op.drop_column("cover_image_url")
        batch_op.drop_column("profile_image_url")
        batch_op.drop_column("logo_url")
        batch_op.drop_column("brand_color")
        batch_op.drop_column("enabled_modules")
        batch_op.drop_column("public_slug")
        batch_op.drop_column("marketplace_enabled")
        batch_op.drop_column("specialties")
        batch_op.drop_column("service_area")
        batch_op.drop_column("bio")
        batch_op.drop_column("headline")
        batch_op.drop_column("dashboard_title")

    with op.batch_alter_table("vip_interactions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("listing_id", sa.INTEGER(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("vip_interactions_listing_id_fkey"),
            "vip_listings",
            ["listing_id"],
            ["id"],
        )

    with op.batch_alter_table("vip_income", schema=None) as batch_op:
        batch_op.add_column(sa.Column("listing_id", sa.INTEGER(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("vip_income_listing_id_fkey"),
            "vip_listings",
            ["listing_id"],
            ["id"],
        )

    with op.batch_alter_table("vip_expenses", schema=None) as batch_op:
        batch_op.add_column(sa.Column("listing_id", sa.INTEGER(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("vip_expenses_listing_id_fkey"),
            "vip_listings",
            ["listing_id"],
            ["id"],
        )

    with op.batch_alter_table("vip_budgets", schema=None) as batch_op:
        batch_op.add_column(sa.Column("listing_id", sa.INTEGER(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("vip_budgets_listing_id_fkey"),
            "vip_listings",
            ["listing_id"],
            ["id"],
        )

    with op.batch_alter_table("vip_assistant_suggestions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("listing_id", sa.INTEGER(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("vip_assistant_suggestions_listing_id_fkey"),
            "vip_listings",
            ["listing_id"],
            ["id"],
        )

    with op.batch_alter_table("vip_assistant_actions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("listing_id", sa.INTEGER(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("vip_assistant_actions_listing_id_fkey"),
            "vip_listings",
            ["listing_id"],
            ["id"],
        )

    with op.batch_alter_table("elena_listings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("year_built", sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column("property_type", sa.VARCHAR(), nullable=True))
        batch_op.add_column(sa.Column("lot_size", sa.DOUBLE_PRECISION(precision=53), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_elena_listings_mls_number"),
            ["mls_number"],
            unique=False,
        )
        batch_op.alter_column(
            "price",
            existing_type=sa.Integer(),
            type_=sa.DOUBLE_PRECISION(precision=53),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "baths",
            existing_type=sa.Integer(),
            type_=sa.DOUBLE_PRECISION(precision=53),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "beds",
            existing_type=sa.Integer(),
            type_=sa.DOUBLE_PRECISION(precision=53),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "zip_code",
            existing_type=sa.VARCHAR(),
            nullable=True,
        )
        batch_op.alter_column(
            "state",
            existing_type=sa.VARCHAR(),
            nullable=True,
        )
        batch_op.alter_column(
            "city",
            existing_type=sa.VARCHAR(),
            nullable=True,
        )
        batch_op.alter_column(
            "address",
            existing_type=sa.VARCHAR(),
            nullable=True,
        )
        batch_op.alter_column(
            "mls_number",
            existing_type=sa.VARCHAR(),
            nullable=False,
        )

    with op.batch_alter_table("elena_flyers", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "created_by",
                sa.VARCHAR(),
                server_default=sa.text("'elena'::character varying"),
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column("export_url", sa.VARCHAR(), nullable=True))
        batch_op.alter_column(
            "property_address",
            existing_type=sa.VARCHAR(),
            nullable=True,
        )
        batch_op.alter_column(
            "flyer_type",
            existing_type=sa.String(),
            type_=postgresql.ENUM(
                "just_listed",
                "just_sold",
                "open_house",
                "coming_soon",
                "price_drop",
                "buyer_need",
                "market_update",
                name="flyertype",
            ),
            existing_nullable=False,
        )

    op.create_table(
        "vip_listings",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(), nullable=True),
        sa.Column("vip_profile_id", sa.INTEGER(), nullable=False),
        sa.Column("contact_id", sa.INTEGER(), nullable=True),
        sa.Column("mls_number", sa.VARCHAR(length=100), nullable=True),
        sa.Column("address", sa.VARCHAR(length=255), nullable=False),
        sa.Column("city", sa.VARCHAR(length=100), nullable=False),
        sa.Column("state", sa.VARCHAR(length=50), nullable=False),
        sa.Column("zip_code", sa.VARCHAR(length=20), nullable=False),
        sa.Column("status", sa.VARCHAR(length=50), nullable=False),
        sa.Column("price", sa.INTEGER(), nullable=True),
        sa.Column("beds", sa.INTEGER(), nullable=True),
        sa.Column("baths", sa.INTEGER(), nullable=True),
        sa.Column("sqft", sa.INTEGER(), nullable=True),
        sa.Column("description", sa.TEXT(), nullable=True),
        sa.ForeignKeyConstraint(["contact_id"], ["vip_contacts.id"], name=op.f("vip_listings_contact_id_fkey")),
        sa.ForeignKeyConstraint(["vip_profile_id"], ["vip_profiles.id"], name=op.f("vip_listings_vip_profile_id_fkey")),
        sa.PrimaryKeyConstraint("id", name=op.f("vip_listings_pkey")),
    )

    op.drop_table("partner_note")
    op.drop_table("canva_connections")