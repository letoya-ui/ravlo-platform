"""Regression tests for the company admin dashboard's loan pipeline
breakdown and auto-flagged "needs follow-up" stale loans
(LoanMVP/routes/admin.py: _loan_pipeline_breakdown, _stale_loans_for_followup,
company_dashboard()).

The admin dashboard previously only showed a flat loan count -- no stage
breakdown and nothing to tell an admin which borrowers have gone quiet.
Stale loans are flagged automatically from each loan's own `updated_at`
(no new borrower-follow-up task needs to be created by hand).
"""
from datetime import datetime, timedelta

from LoanMVP.extensions import db
from LoanMVP.models.admin import Company
from LoanMVP.models.loan_models import BorrowerProfile, LoanApplication
from LoanMVP.models.user_model import User
from LoanMVP.routes.admin import STALE_LOAN_FOLLOWUP_DAYS, _loan_pipeline_breakdown, _stale_loans_for_followup

from tests.conftest import login_as


def _make_company(db_session, name="Pipeline Co"):
    company = Company(name=name, is_active=True, subscription_tier="team", max_users=25)
    db_session.add(company)
    db_session.commit()
    return company


def _make_admin(db_session, company, email="admin@example.com"):
    user = User(email=email, role="admin", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user


def _make_borrower(db_session, company, email, full_name):
    user = User(email=email, role="borrower", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    borrower = BorrowerProfile(user_id=user.id, full_name=full_name, email=email, company_id=company.id, state="FL")
    db_session.add(borrower)
    db_session.commit()
    return borrower


def _make_loan(db_session, company, borrower, status, updated_at=None, **extra):
    loan = LoanApplication(
        company_id=company.id, borrower_profile_id=borrower.id, amount=250000,
        status=status, **extra,
    )
    db_session.add(loan)
    db_session.commit()
    if updated_at is not None:
        # LoanApplication.updated_at has onupdate=utcnow -- force a specific
        # backdated value via a direct UPDATE so onupdate doesn't overwrite it.
        db.session.execute(
            LoanApplication.__table__.update()
            .where(LoanApplication.id == loan.id)
            .values(updated_at=updated_at)
        )
        db.session.commit()
    return LoanApplication.query.get(loan.id)


# ── _loan_pipeline_breakdown ──

def test_pipeline_breakdown_groups_by_status():
    class FakeLoan:
        def __init__(self, status):
            self.status = status

    loans = [FakeLoan("Processing"), FakeLoan("Processing"), FakeLoan("Approved")]
    breakdown = _loan_pipeline_breakdown(loans)

    assert ("Processing", 2) in breakdown
    assert ("Approved", 1) in breakdown
    assert breakdown[0] == ("Processing", 2)  # most common first


# ── _stale_loans_for_followup ──

def test_stale_loans_flags_loan_idle_past_threshold(db_session):
    company = _make_company(db_session, "Stale Co")
    borrower = _make_borrower(db_session, company, "stale1@example.com", "Stale Borrower")
    old = datetime.utcnow() - timedelta(days=STALE_LOAN_FOLLOWUP_DAYS + 2)
    loan = _make_loan(db_session, company, borrower, "Processing", updated_at=old)

    stale = _stale_loans_for_followup([loan])

    assert len(stale) == 1
    assert stale[0]["borrower_name"] == "Stale Borrower"
    assert stale[0]["days_idle"] >= STALE_LOAN_FOLLOWUP_DAYS


def test_stale_loans_excludes_recently_active_loans(db_session):
    company = _make_company(db_session, "Fresh Co")
    borrower = _make_borrower(db_session, company, "fresh1@example.com", "Fresh Borrower")
    loan = _make_loan(db_session, company, borrower, "Processing")  # updated_at = now

    stale = _stale_loans_for_followup([loan])

    assert stale == []


def test_stale_loans_excludes_terminal_statuses(db_session):
    company = _make_company(db_session, "Closed Co")
    borrower = _make_borrower(db_session, company, "closed1@example.com", "Closed Borrower")
    old = datetime.utcnow() - timedelta(days=STALE_LOAN_FOLLOWUP_DAYS + 10)
    loan = _make_loan(db_session, company, borrower, "Declined", updated_at=old)

    stale = _stale_loans_for_followup([loan])

    assert stale == []


def test_stale_loans_sorts_most_idle_first(db_session):
    company = _make_company(db_session, "Sort Co")
    b1 = _make_borrower(db_session, company, "sort1@example.com", "Less Idle")
    b2 = _make_borrower(db_session, company, "sort2@example.com", "More Idle")
    loan1 = _make_loan(db_session, company, b1, "Processing", updated_at=datetime.utcnow() - timedelta(days=6))
    loan2 = _make_loan(db_session, company, b2, "Processing", updated_at=datetime.utcnow() - timedelta(days=20))

    stale = _stale_loans_for_followup([loan1, loan2])

    assert [item["borrower_name"] for item in stale] == ["More Idle", "Less Idle"]


# ── company_dashboard() rendering ──

def test_dashboard_shows_needs_followup_for_stale_loan(db_session, client):
    company = _make_company(db_session, "Dash Stale Co")
    admin_user = _make_admin(db_session, company, "admindash1@example.com")
    borrower = _make_borrower(db_session, company, "dashstale@example.com", "Dashboard Stale Borrower")
    _make_loan(db_session, company, borrower, "Processing", updated_at=datetime.utcnow() - timedelta(days=10))
    login_as(client, admin_user)

    body = client.get(f"/admin/company/{company.id}/dashboard").get_data(as_text=True)

    assert "Dashboard Stale Borrower" in body
    assert "Needs Follow-Up" in body or "NEEDS FOLLOW-UP" in body


def test_dashboard_shows_nothing_stale_when_all_loans_fresh(db_session, client):
    company = _make_company(db_session, "Dash Fresh Co")
    admin_user = _make_admin(db_session, company, "admindash2@example.com")
    borrower = _make_borrower(db_session, company, "dashfresh@example.com", "Dashboard Fresh Borrower")
    _make_loan(db_session, company, borrower, "Processing")
    login_as(client, admin_user)

    body = client.get(f"/admin/company/{company.id}/dashboard").get_data(as_text=True)

    assert "Nothing stale" in body
