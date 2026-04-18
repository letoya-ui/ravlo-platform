"""add vip base models

Revision ID: 5fd82a8f3e41
Revises: 20260417elena01
Create Date: 2026-04-18
"""

from alembic import op
import sqlalchemy as sa


revision = "5fd82a8f3e41"
down_revision = "20260417elena01"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "vip_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("role_type", sa.String(length=50), nullable=False),
        sa.Column("assistant_name", sa.String(length=100), nullable=True),
        sa.Column("business_name", sa.String(length=255), nullable=True),
    )

    op.create_table(
        "vip_contacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("vip_profile_id", sa.Integer(), sa.ForeignKey("vip_profiles.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("contact_type", sa.String(length=50), nullable=True),
        sa.Column("tags", sa.String(length=255), nullable=True),
        sa.Column("pipeline_stage", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "vip_listings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("vip_profile_id", sa.Integer(), sa.ForeignKey("vip_profiles.id"), nullable=False),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("vip_contacts.id"), nullable=True),
        sa.Column("mls_number", sa.String(length=100), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=50), nullable=False),
        sa.Column("zip_code", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("price", sa.Integer(), nullable=True),
        sa.Column("beds", sa.Integer(), nullable=True),
        sa.Column("baths", sa.Integer(), nullable=True),
        sa.Column("sqft", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
    )

    op.create_table(
        "vip_interactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("vip_profile_id", sa.Integer(), sa.ForeignKey("vip_profiles.id"), nullable=False),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("vip_contacts.id"), nullable=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("vip_listings.id"), nullable=True),
        sa.Column("interaction_type", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("meta", sa.String(length=255), nullable=True),
        sa.Column("due_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "vip_expenses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("vip_profile_id", sa.Integer(), sa.ForeignKey("vip_profiles.id"), nullable=False),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("vip_contacts.id"), nullable=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("vip_listings.id"), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=True),
        sa.Column("miles", sa.Integer(), nullable=True),
        sa.Column("expense_date", sa.DateTime(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "vip_income",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("vip_profile_id", sa.Integer(), sa.ForeignKey("vip_profiles.id"), nullable=False),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("vip_contacts.id"), nullable=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("vip_listings.id"), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("income_date", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "vip_budgets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("vip_profile_id", sa.Integer(), sa.ForeignKey("vip_profiles.id"), nullable=False),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("vip_listings.id"), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("budget_amount", sa.Integer(), nullable=False),
        sa.Column("period_type", sa.String(length=20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "vip_assistant_suggestions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("vip_profile_id", sa.Integer(), sa.ForeignKey("vip_profiles.id"), nullable=False),
        sa.Column("suggestion_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("vip_contacts.id"), nullable=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("vip_listings.id"), nullable=True),
        sa.Column("proposed_amount", sa.Integer(), nullable=True),
        sa.Column("proposed_miles", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("due_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "vip_assistant_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("vip_profile_id", sa.Integer(), sa.ForeignKey("vip_profiles.id"), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("vip_contacts.id"), nullable=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("vip_listings.id"), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=True),
        sa.Column("miles", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "vip_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("vip_profile_id", sa.Integer(), sa.ForeignKey("vip_profiles.id"), nullable=False),
        sa.Column("notification_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("is_read", sa.String(length=10), nullable=False),
        sa.Column("action_url", sa.String(length=255), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table("vip_notifications")
    op.drop_table("vip_assistant_actions")
    op.drop_table("vip_assistant_suggestions")
    op.drop_table("vip_budgets")
    op.drop_table("vip_income")
    op.drop_table("vip_expenses")
    op.drop_table("vip_interactions")
    op.drop_table("vip_listings")
    op.drop_table("vip_contacts")
    op.drop_table("vip_profiles")
