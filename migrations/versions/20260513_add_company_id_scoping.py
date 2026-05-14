"""add company_id to borrower_profile, loan_application, loan_document

Revision ID: 20260513cid01
Revises: 20260513merge01
Create Date: 2026-05-13 00:00:00.000000

Adds company_id FK columns so licensed companies cannot see each other's data.
Backfills existing rows via the assigned loan officer's user.company_id.
Upgrade is idempotent — safe to run even if columns already exist.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260513cid01"
down_revision = "20260513merge01"
branch_labels = None
depends_on = None


def _col_exists(inspector, table, col):
    return col in {c["name"] for c in inspector.get_columns(table)}


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # ── borrower_profile ────────────────────────────────────────────
    if not _col_exists(inspector, "borrower_profile", "company_id"):
        with op.batch_alter_table("borrower_profile", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "company_id",
                    sa.Integer(),
                    sa.ForeignKey("companies.id", name="fk_borrower_company"),
                    nullable=True,
                )
            )
        op.create_index(
            "ix_borrower_profile_company_id", "borrower_profile", ["company_id"], unique=False
        )

    # ── loan_application ────────────────────────────────────────────
    if not _col_exists(inspector, "loan_application", "company_id"):
        with op.batch_alter_table("loan_application", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "company_id",
                    sa.Integer(),
                    sa.ForeignKey("companies.id", name="fk_loanapp_company"),
                    nullable=True,
                )
            )
        op.create_index(
            "ix_loan_application_company_id", "loan_application", ["company_id"], unique=False
        )

    # ── loan_document ───────────────────────────────────────────────
    if not _col_exists(inspector, "loan_document", "company_id"):
        with op.batch_alter_table("loan_document", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "company_id",
                    sa.Integer(),
                    sa.ForeignKey("companies.id", name="fk_loandoc_company"),
                    nullable=True,
                )
            )
        op.create_index(
            "ix_loan_document_company_id", "loan_document", ["company_id"], unique=False
        )

    # ── Backfill: set company_id from the assigned loan officer's user ──
    # loan_application: join through loan_officer_profile → user
    conn.execute(sa.text("""
        UPDATE loan_application la
        SET company_id = u.company_id
        FROM loan_officer_profile lop
        JOIN "user" u ON u.id = lop.user_id
        WHERE la.loan_officer_id = lop.id
          AND la.company_id IS NULL
          AND u.company_id IS NOT NULL
    """))

    # borrower_profile: inherit from their linked loan_application (most recent)
    conn.execute(sa.text("""
        UPDATE borrower_profile bp
        SET company_id = sub.company_id
        FROM (
            SELECT DISTINCT ON (borrower_profile_id)
                   borrower_profile_id,
                   company_id
            FROM loan_application
            WHERE company_id IS NOT NULL
            ORDER BY borrower_profile_id, created_at DESC
        ) sub
        WHERE bp.id = sub.borrower_profile_id
          AND bp.company_id IS NULL
    """))

    # loan_document: inherit from linked loan_application
    conn.execute(sa.text("""
        UPDATE loan_document ld
        SET company_id = la.company_id
        FROM loan_application la
        WHERE ld.loan_id = la.id
          AND ld.company_id IS NULL
          AND la.company_id IS NOT NULL
    """))


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    for table, idx in [
        ("loan_document", "ix_loan_document_company_id"),
        ("loan_application", "ix_loan_application_company_id"),
        ("borrower_profile", "ix_borrower_profile_company_id"),
    ]:
        try:
            op.drop_index(idx, table_name=table)
        except Exception:
            pass

    for table in ("loan_document", "loan_application", "borrower_profile"):
        if _col_exists(inspector, table, "company_id"):
            with op.batch_alter_table(table, schema=None) as batch_op:
                batch_op.drop_column("company_id")
