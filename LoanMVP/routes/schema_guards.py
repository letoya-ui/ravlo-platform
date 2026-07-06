from flask import Blueprint, current_app

from LoanMVP.extensions import db

# Import models so their tables are present in SQLAlchemy metadata.
from LoanMVP.models.company_finance_models import (  # noqa: F401
    CMFinanceEntry,
    ChallengeEnrollment,
    FeedbackSurvey,
    UserEmailConnection,
)
from LoanMVP.models.contractor_models import ContractorBidOpportunity  # noqa: F401

schema_guards_bp = Blueprint("schema_guards", __name__)

_CHECKED_ONCE = False


@schema_guards_bp.before_app_request
def ensure_operational_tables():
    """Best-effort production safety net for operational tables.

    Alembic migrations remain the source of truth. This guard prevents a deploy
    from hard-crashing when the app code is ahead of a production database by
    creating only known additive tables that already have SQLAlchemy models.
    """
    global _CHECKED_ONCE
    if _CHECKED_ONCE:
        return None

    _CHECKED_ONCE = True

    table_names = [
        "cm_finance_entries",
        "contractor_bid_opportunities",
        "challenge_enrollments",
        "feedback_surveys",
        "user_email_connections",
    ]

    try:
        from sqlalchemy import inspect

        inspector = inspect(db.engine)
        for table_name in table_names:
            try:
                if inspector.has_table(table_name):
                    continue

                table = db.metadata.tables.get(table_name)
                if table is None:
                    current_app.logger.warning("schema guard missing metadata for %s", table_name)
                    continue

                table.create(db.engine, checkfirst=True)
                current_app.logger.warning("schema guard created missing table %s", table_name)
            except Exception as exc:
                current_app.logger.warning("schema guard could not create %s: %s", table_name, exc)
    except Exception as exc:
        current_app.logger.warning("schema guard skipped: %s", exc)

    return None
