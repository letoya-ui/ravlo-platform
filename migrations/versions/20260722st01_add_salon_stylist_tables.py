"""Add salon/stylist vertical tables

Revision ID: 20260722st01
Revises: 20260719wl02
Create Date: 2026-07-22 00:00:00.000000

Adds the Stylist role's core dashboard tables: stylist_profile,
salon_clients, salon_appointments, salon_client_formulas,
salon_client_photos, salon_product_sales, salon_reviews, and
salon_loyalty_transactions.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260722st01"
down_revision = "20260719wl02"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_table(table):
    try:
        return _insp().has_table(table)
    except Exception:
        return False


def upgrade():
    if not _has_table("stylist_profile"):
        op.create_table(
            "stylist_profile",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", name="fk_stylist_user_id"), nullable=False, unique=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", name="fk_stylist_company_id"), nullable=True),
            sa.Column("full_name", sa.String(120), nullable=False),
            sa.Column("email", sa.String(120), nullable=True),
            sa.Column("phone", sa.String(50), nullable=True),
            sa.Column("specialty", sa.String(255), nullable=True),
            sa.Column("bio", sa.Text(), nullable=True),
            sa.Column("avatar_url", sa.String(255), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_stylist_profile_company_id", "stylist_profile", ["company_id"])

    if not _has_table("salon_clients"):
        op.create_table(
            "salon_clients",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", name="fk_salonclient_company_id"), nullable=False),
            sa.Column("stylist_id", sa.Integer(), sa.ForeignKey("stylist_profile.id", name="fk_salonclient_stylist_id"), nullable=False),
            sa.Column("full_name", sa.String(120), nullable=False),
            sa.Column("email", sa.String(120), nullable=True),
            sa.Column("phone", sa.String(50), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("loyalty_points", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_visit_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_salon_clients_company_id", "salon_clients", ["company_id"])
        op.create_index("ix_salon_clients_stylist_id", "salon_clients", ["stylist_id"])

    if not _has_table("salon_appointments"):
        op.create_table(
            "salon_appointments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", name="fk_appt_company_id"), nullable=False),
            sa.Column("stylist_id", sa.Integer(), sa.ForeignKey("stylist_profile.id", name="fk_appt_stylist_id"), nullable=False),
            sa.Column("client_id", sa.Integer(), sa.ForeignKey("salon_clients.id", name="fk_appt_client_id"), nullable=False),
            sa.Column("service_type", sa.String(150), nullable=False),
            sa.Column("scheduled_at", sa.DateTime(), nullable=False),
            sa.Column("duration_minutes", sa.Integer(), nullable=True, server_default="60"),
            sa.Column("price", sa.Numeric(10, 2), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_salon_appointments_company_id", "salon_appointments", ["company_id"])
        op.create_index("ix_salon_appointments_stylist_id", "salon_appointments", ["stylist_id"])
        op.create_index("ix_salon_appointments_client_id", "salon_appointments", ["client_id"])
        op.create_index("ix_salon_appointments_scheduled_at", "salon_appointments", ["scheduled_at"])

    if not _has_table("salon_client_formulas"):
        op.create_table(
            "salon_client_formulas",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("client_id", sa.Integer(), sa.ForeignKey("salon_clients.id", name="fk_formula_client_id"), nullable=False),
            sa.Column("stylist_id", sa.Integer(), sa.ForeignKey("stylist_profile.id", name="fk_formula_stylist_id"), nullable=False),
            sa.Column("title", sa.String(150), nullable=False),
            sa.Column("notes", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_salon_client_formulas_client_id", "salon_client_formulas", ["client_id"])
        op.create_index("ix_salon_client_formulas_stylist_id", "salon_client_formulas", ["stylist_id"])

    if not _has_table("salon_client_photos"):
        op.create_table(
            "salon_client_photos",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("client_id", sa.Integer(), sa.ForeignKey("salon_clients.id", name="fk_photo_client_id"), nullable=False),
            sa.Column("appointment_id", sa.Integer(), sa.ForeignKey("salon_appointments.id", name="fk_photo_appointment_id"), nullable=True),
            sa.Column("photo_type", sa.String(10), nullable=False, server_default="after"),
            sa.Column("image_url", sa.String(255), nullable=False),
            sa.Column("caption", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_salon_client_photos_client_id", "salon_client_photos", ["client_id"])
        op.create_index("ix_salon_client_photos_appointment_id", "salon_client_photos", ["appointment_id"])

    if not _has_table("salon_product_sales"):
        op.create_table(
            "salon_product_sales",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", name="fk_productsale_company_id"), nullable=False),
            sa.Column("stylist_id", sa.Integer(), sa.ForeignKey("stylist_profile.id", name="fk_productsale_stylist_id"), nullable=False),
            sa.Column("client_id", sa.Integer(), sa.ForeignKey("salon_clients.id", name="fk_productsale_client_id"), nullable=True),
            sa.Column("product_name", sa.String(150), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
            sa.Column("total", sa.Numeric(10, 2), nullable=False),
            sa.Column("sold_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_salon_product_sales_company_id", "salon_product_sales", ["company_id"])
        op.create_index("ix_salon_product_sales_stylist_id", "salon_product_sales", ["stylist_id"])
        op.create_index("ix_salon_product_sales_client_id", "salon_product_sales", ["client_id"])

    if not _has_table("salon_reviews"):
        op.create_table(
            "salon_reviews",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", name="fk_review_company_id"), nullable=False),
            sa.Column("stylist_id", sa.Integer(), sa.ForeignKey("stylist_profile.id", name="fk_review_stylist_id"), nullable=True),
            sa.Column("client_name", sa.String(120), nullable=False),
            sa.Column("rating", sa.Integer(), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("source", sa.String(50), nullable=True, server_default="direct"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_salon_reviews_company_id", "salon_reviews", ["company_id"])
        op.create_index("ix_salon_reviews_stylist_id", "salon_reviews", ["stylist_id"])

    if not _has_table("salon_loyalty_transactions"):
        op.create_table(
            "salon_loyalty_transactions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("client_id", sa.Integer(), sa.ForeignKey("salon_clients.id", name="fk_loyalty_client_id"), nullable=False),
            sa.Column("points", sa.Integer(), nullable=False),
            sa.Column("reason", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_salon_loyalty_transactions_client_id", "salon_loyalty_transactions", ["client_id"])


def downgrade():
    for table in (
        "salon_loyalty_transactions",
        "salon_reviews",
        "salon_product_sales",
        "salon_client_photos",
        "salon_client_formulas",
        "salon_appointments",
        "salon_clients",
        "stylist_profile",
    ):
        if _has_table(table):
            op.drop_table(table)
