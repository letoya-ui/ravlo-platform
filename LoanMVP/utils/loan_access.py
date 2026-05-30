"""Loan and borrower access helpers that enforce company-level tenancy."""
from flask import abort
from flask_login import current_user
from LoanMVP.models.loan_models import LoanApplication, BorrowerProfile


def get_loan_or_404(loan_id: int) -> LoanApplication:
    """Return the LoanApplication if it belongs to the current user's company, else 404."""
    loan = LoanApplication.query.get_or_404(loan_id)
    _assert_loan_access(loan)
    return loan


def get_borrower_or_404(borrower_id: int) -> BorrowerProfile:
    """Return BorrowerProfile if it belongs to the current user's company, else 404."""
    borrower = BorrowerProfile.query.get_or_404(borrower_id)
    _assert_company_match(borrower.company_id, borrower_id, "borrower")
    return borrower


def _assert_loan_access(loan: LoanApplication):
    _assert_company_match(loan.company_id, loan.id, "loan")


def _assert_company_match(record_company_id, record_id, kind: str):
    user_company_id = getattr(current_user, "company_id", None)
    # If both are None (solo/no-company setup), allow.
    if user_company_id is None and record_company_id is None:
        return
    # If company IDs are set and match, allow.
    if user_company_id and record_company_id and user_company_id == record_company_id:
        return
    # Mismatch → 404 (don't leak record existence).
    abort(404)
