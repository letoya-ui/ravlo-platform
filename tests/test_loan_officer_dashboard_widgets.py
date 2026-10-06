"""Regression tests for the Loan Officer Dashboard redesign
(LoanMVP/routes/loan_officer.py's build_loan_officer_dashboard_context(),
templates/loan_officer/dashboard.html): the hero banner, stat-tile
trend badges, loan-status donut, monthly volume chart, lead-source
breakdown, recent-activity feed, and upcoming-tasks list -- all built
from this officer's real loans/leads/tasks/status-events, not
hardcoded sample numbers.

Also covers a real bug found while building this: Lead.source is a
relationship to LeadSource, not a plain string -- grouping leads by
source crashed with AttributeError before the fix.
"""
from datetime import date, datetime, timedelta

from LoanMVP.extensions import db
from LoanMVP.models.admin import Company
from LoanMVP.models.crm_models import Lead, LeadSource, Task
from LoanMVP.models.loan_models import LoanApplication, LoanStatusEvent
from LoanMVP.models.loan_officer_model import LoanOfficerProfile
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_loan_officer(db_session, email="lo-widgets@example.com"):
    company = Company(name="Widgets Lending Co", is_active=True)
    db_session.add(company)
    db_session.commit()

    user = User(
        email=email, role="loan_officer", is_active=True, company_id=company.id,
        first_name="Chris", onboarding_complete=True,
        ica_accepted=True, nda_accepted=True,
    )
    db_session.add(user)
    db_session.commit()

    officer = LoanOfficerProfile(user_id=user.id, name="Chris Nakamura", email=email)
    db_session.add(officer)
    db_session.commit()
    return user, officer


def test_dashboard_renders_with_no_data(db_session, client):
    user, officer = _make_loan_officer(db_session)
    login_as(client, user)

    resp = client.get("/loan_officer/dashboard")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Welcome back, Chris." in body
    assert "No loans yet." in body
    assert "No leads yet." in body
    assert "Nothing on your plate right now." in body


def test_stat_trend_reflects_this_month_vs_last_month(db_session, client):
    user, officer = _make_loan_officer(db_session, email="lo-trend@example.com")
    now = datetime.utcnow()
    this_month_start = now.replace(day=1, hour=12)
    last_month_start = (this_month_start - timedelta(days=1)).replace(day=1, hour=12)

    # 2 leads last month, 4 this month -> up 100%
    for i in range(2):
        db_session.add(Lead(name=f"Last Month Lead {i}", assigned_to=user.id, created_at=last_month_start))
    for i in range(4):
        db_session.add(Lead(name=f"This Month Lead {i}", assigned_to=user.id, created_at=this_month_start))
    db_session.commit()

    login_as(client, user)
    body = client.get("/loan_officer/dashboard").get_data(as_text=True)

    assert "4" in body
    assert "100%" in body


def test_lead_source_breakdown_uses_source_relationship_not_crashing(db_session, client):
    user, officer = _make_loan_officer(db_session, email="lo-source@example.com")
    source = LeadSource(source_name="Instagram Ads", source_type="Social")
    db_session.add(source)
    db_session.commit()

    db_session.add(Lead(name="Jordan Blake", assigned_to=user.id, source_id=source.id))
    db_session.add(Lead(name="No Source Lead", assigned_to=user.id))
    db_session.commit()

    login_as(client, user)
    resp = client.get("/loan_officer/dashboard")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Instagram Ads" in body
    assert "Unknown" in body


def test_loan_status_breakdown_shows_real_statuses_not_a_fixed_list(db_session, client):
    user, officer = _make_loan_officer(db_session, email="lo-status@example.com")
    db_session.add(LoanApplication(loan_officer_id=officer.id, status="In Review", amount=100000))
    db_session.add(LoanApplication(loan_officer_id=officer.id, status="Approved", amount=200000))
    db_session.commit()

    login_as(client, user)
    body = client.get("/loan_officer/dashboard").get_data(as_text=True)

    assert "In Review" in body
    assert "Approved" in body
    # No fabricated "Funded" bucket when nothing actually has that status
    # ("Conditions" isn't checked here -- the unrelated onboarding tour
    # partial mentions a "Conditions Tracker" feature on every page).
    assert "Funded" not in body


def test_monthly_loan_volume_sums_real_amounts(db_session, client):
    user, officer = _make_loan_officer(db_session, email="lo-volume@example.com")
    this_month = datetime.utcnow().replace(day=1, hour=12)
    db_session.add(LoanApplication(loan_officer_id=officer.id, status="Submitted", amount=300000, created_at=this_month))
    db_session.add(LoanApplication(loan_officer_id=officer.id, status="Submitted", amount=150000, created_at=this_month))
    db_session.commit()

    login_as(client, user)
    body = client.get("/loan_officer/dashboard").get_data(as_text=True)

    assert "$450,000" in body


def test_recent_activity_shows_status_events_for_this_officers_loans(db_session, client):
    user, officer = _make_loan_officer(db_session, email="lo-activity@example.com")
    loan = LoanApplication(loan_officer_id=officer.id, status="Submitted", amount=100000)
    db_session.add(loan)
    db_session.commit()

    db_session.add(LoanStatusEvent(loan_id=loan.id, event_name="Application Received", description="Initial docs in."))
    db_session.commit()

    login_as(client, user)
    body = client.get("/loan_officer/dashboard").get_data(as_text=True)

    assert "Application Received" in body
    assert "Initial docs in." in body


def test_upcoming_tasks_shows_tasks_assigned_to_this_user(db_session, client):
    user, officer = _make_loan_officer(db_session, email="lo-tasks@example.com")
    db_session.add(Task(title="Call Danielle re: inspection date", assigned_to=user.id, due_date=date.today(), completed=False))
    db_session.add(Task(title="Already done task", assigned_to=user.id, due_date=date.today(), completed=True))
    db_session.commit()

    login_as(client, user)
    body = client.get("/loan_officer/dashboard").get_data(as_text=True)

    assert "Call Danielle re: inspection date" in body
    assert "Already done task" not in body
