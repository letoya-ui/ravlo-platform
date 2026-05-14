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
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not inspector.has_table("partner_proposals"):
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

    partners_cols = {c["name"] for c in inspector.get_columns("partners")}
    partner_bool_cols = {
        "crm_enabled": sa.true(),
        "deal_visibility_enabled": sa.false(),
        "proposal_builder_enabled": sa.false(),
        "instant_quote_enabled": sa.false(),
        "ai_assist_enabled": sa.false(),
        "priority_placement_enabled": sa.false(),
        "smart_notifications_enabled": sa.false(),
        "portfolio_showcase_enabled": sa.false(),
    }
    new_partner_cols = [c for c in partner_bool_cols if c not in partners_cols]
    if new_partner_cols:
        for col in new_partner_cols:
            op.add_column("partners", sa.Column(col, sa.Boolean(), nullable=True))
        for col in new_partner_cols:
            op.execute(f"UPDATE partners SET {col} = ({str(partner_bool_cols[col].compile(dialect=conn.dialect)).lower()}) WHERE {col} IS NULL")
        for col, default in partner_bool_cols.items():
            if col in new_partner_cols:
                op.alter_column("partners", col, nullable=False, server_default=default)

    pcr_cols = {c["name"] for c in inspector.get_columns("partner_connection_requests")}
    with op.batch_alter_table("partner_connection_requests", schema=None) as batch_op:
        if "title" not in pcr_cols:
            batch_op.add_column(sa.Column("title", sa.String(length=255), nullable=True))
        if "budget" not in pcr_cols:
            batch_op.add_column(sa.Column("budget", sa.Float(), nullable=True))
        if "timeline" not in pcr_cols:
            batch_op.add_column(sa.Column("timeline", sa.String(length=120), nullable=True))
        if "priority" not in pcr_cols:
            batch_op.add_column(sa.Column("priority", sa.String(length=30), nullable=True))
        if "request_type" not in pcr_cols:
            batch_op.add_column(sa.Column("request_type", sa.String(length=50), nullable=True))
        if "internal_notes" not in pcr_cols:
            batch_op.add_column(sa.Column("internal_notes", sa.Text(), nullable=True))


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