"""add borrower consent and credit pull audit

Revision ID: add_borrower_consent_credit_pull_audit
Revises: add_partner_bio_specialty
Create Date: 2026-03-15
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_borrower_consent_credit_pull_audit"
down_revision = "add_partner_bio_specialty"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "borrower_consents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("borrower_id", sa.Integer(), nullable=False),
        sa.Column("consent_type", sa.String(length=50), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("ip_address", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrower_profile.id"]),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index(op.f("ix_borrower_consents_borrower_id"), "borrower_consents", ["borrower_id"], unique=False)

    op.create_table(
        "credit_pull_audits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("borrower_id", sa.Integer(), nullable=False),
        sa.Column("loan_officer_id", sa.Integer(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("permissible_purpose", sa.String(length=255), nullable=True),
        sa.Column("result_status", sa.String(length=50), nullable=True),
        sa.Column("raw_response", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrower_profile.id"]),
        sa.ForeignKeyConstraint(["loan_officer_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index(op.f("ix_credit_pull_audits_borrower_id"), "credit_pull_audits", ["borrower_id"], unique=False)
    op.create_index(op.f("ix_credit_pull_audits_loan_officer_id"), "credit_pull_audits", ["loan_officer_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_credit_pull_audits_loan_officer_id"), table_name="credit_pull_audits")
    op.drop_index(op.f("ix_credit_pull_audits_borrower_id"), table_name="credit_pull_audits")
    op.drop_table("credit_pull_audits")

    op.drop_index(op.f("ix_borrower_consents_borrower_id"), table_name="borrower_consents")
    op.drop_table("borrower_consents")