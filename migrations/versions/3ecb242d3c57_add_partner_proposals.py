"""add partner proposals

Revision ID: 3ecb242d3c57
Revises: a42cef0d3266
Create Date: 2026-03-23
"""

from alembic import op
import sqlalchemy as sa


revision = "3ecb242d3c57"
down_revision = "a42cef0d3266"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "partner_proposals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("partner_id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("proposal_text", sa.Text(), nullable=True),
        sa.Column("scope_of_work", sa.Text(), nullable=True),
        sa.Column("labor_cost", sa.Float(), nullable=True),
        sa.Column("materials_cost", sa.Float(), nullable=True),
        sa.Column("other_cost", sa.Float(), nullable=True),
        sa.Column("total_cost", sa.Float(), nullable=True),
        sa.Column("estimated_timeline", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["partner_id"], ["partners.id"]),
        sa.ForeignKeyConstraint(["request_id"], ["partner_connection_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.add_column("partners", sa.Column("crm_enabled", sa.Boolean(), nullable=True))
    op.add_column("partners", sa.Column("deal_visibility_enabled", sa.Boolean(), nullable=True))
    op.add_column("partners", sa.Column("proposal_builder_enabled", sa.Boolean(), nullable=True))
    op.add_column("partners", sa.Column("instant_quote_enabled", sa.Boolean(), nullable=True))
    op.add_column("partners", sa.Column("ai_assist_enabled", sa.Boolean(), nullable=True))
    op.add_column("partners", sa.Column("priority_placement_enabled", sa.Boolean(), nullable=True))
    op.add_column("partners", sa.Column("smart_notifications_enabled", sa.Boolean(), nullable=True))
    op.add_column("partners", sa.Column("portfolio_showcase_enabled", sa.Boolean(), nullable=True))

    op.execute("UPDATE partners SET crm_enabled = true WHERE crm_enabled IS NULL")
    op.execute("UPDATE partners SET deal_visibility_enabled = false WHERE deal_visibility_enabled IS NULL")
    op.execute("UPDATE partners SET proposal_builder_enabled = false WHERE proposal_builder_enabled IS NULL")
    op.execute("UPDATE partners SET instant_quote_enabled = false WHERE instant_quote_enabled IS NULL")
    op.execute("UPDATE partners SET ai_assist_enabled = false WHERE ai_assist_enabled IS NULL")
    op.execute("UPDATE partners SET priority_placement_enabled = false WHERE priority_placement_enabled IS NULL")
    op.execute("UPDATE partners SET smart_notifications_enabled = false WHERE smart_notifications_enabled IS NULL")
    op.execute("UPDATE partners SET portfolio_showcase_enabled = false WHERE portfolio_showcase_enabled IS NULL")

    op.alter_column("partners", "crm_enabled", nullable=False)
    op.alter_column("partners", "deal_visibility_enabled", nullable=False)
    op.alter_column("partners", "proposal_builder_enabled", nullable=False)
    op.alter_column("partners", "instant_quote_enabled", nullable=False)
    op.alter_column("partners", "ai_assist_enabled", nullable=False)
    op.alter_column("partners", "priority_placement_enabled", nullable=False)
    op.alter_column("partners", "smart_notifications_enabled", nullable=False)
    op.alter_column("partners", "portfolio_showcase_enabled", nullable=False)

    op.add_column("partner_connection_requests", sa.Column("title", sa.String(length=255), nullable=True))
    op.add_column("partner_connection_requests", sa.Column("budget", sa.Float(), nullable=True))
    op.add_column("partner_connection_requests", sa.Column("timeline", sa.String(length=120), nullable=True))
    op.add_column("partner_connection_requests", sa.Column("priority", sa.String(length=30), nullable=True))
    op.add_column("partner_connection_requests", sa.Column("request_type", sa.String(length=50), nullable=True))
    op.add_column("partner_connection_requests", sa.Column("internal_notes", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("partner_connection_requests", "internal_notes")
    op.drop_column("partner_connection_requests", "request_type")
    op.drop_column("partner_connection_requests", "priority")
    op.drop_column("partner_connection_requests", "timeline")
    op.drop_column("partner_connection_requests", "budget")
    op.drop_column("partner_connection_requests", "title")

    op.drop_column("partners", "portfolio_showcase_enabled")
    op.drop_column("partners", "smart_notifications_enabled")
    op.drop_column("partners", "priority_placement_enabled")
    op.drop_column("partners", "ai_assist_enabled")
    op.drop_column("partners", "instant_quote_enabled")
    op.drop_column("partners", "proposal_builder_enabled")
    op.drop_column("partners", "deal_visibility_enabled")
    op.drop_column("partners", "crm_enabled")

    op.drop_table("partner_proposals")