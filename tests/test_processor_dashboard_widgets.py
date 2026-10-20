"""Regression tests for the Processor Dashboard redesign
(LoanMVP/routes/processor.py's dashboard(), templates/processor/dashboard.html):
the hero banner, stat-tile trend badges, loan-status donut, monthly
file-volume chart, document-type breakdown, recent-activity feed, and
upcoming-tasks list -- all built from this processor's real
loans/documents/tasks/status-events, not hardcoded sample numbers.
"""
from datetime import date, datetime, timedelta

from LoanMVP.extensions import db
from LoanMVP.models.admin import Company
from LoanMVP.models.crm_models import Task
from LoanMVP.models.document_models import LoanDocument
from LoanMVP.models.loan_models import LoanApplication, LoanStatusEvent
from LoanMVP.models.processor_model import ProcessorProfile
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_processor(db_session, email="processor-widgets@example.com"):
    company = Company(name="Widgets Lending Co", is_active=True)
    db_session.add(company)
    db_session.commit()

    user = User(
        email=email, role="processor", is_active=True, company_id=company.id,
        first_name="Jamie", onboarding_complete=True,
        ica_accepted=True, nda_accepted=True,
    )
    db_session.add(user)
    db_session.commit()

    profile = ProcessorProfile(user_id=user.id, full_name="Jamie Ortiz", email=email)
    db_session.add(profile)
    db_session.commit()
    return user, profile, company


def test_dashboard_renders_with_no_data(db_session, client):
    user, profile, company = _make_processor(db_session)
    login_as(client, user)

    resp = client.get("/processor/dashboard")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Welcome back, Jamie." in body
    assert "No loans yet." in body
    assert "Nothing on your plate right now." in body


def test_stat_trend_reflects_this_month_vs_last_month(db_session, client):
    user, profile, company = _make_processor(db_session, email="processor-trend@example.com")
    now = datetime.utcnow()
    this_month_start = now.replace(day=1, hour=12)
    last_month_start = (this_month_start - timedelta(days=1)).replace(day=1, hour=12)

    # 1 loan last month, 2 this month -> up 100%
    db_session.add(LoanApplication(
        processor_id=profile.id, company_id=company.id, status="Submitted",
        amount=100000, created_at=last_month_start,
    ))
    for i in range(2):
        db_session.add(LoanApplication(
            processor_id=profile.id, company_id=company.id, status="Submitted",
            amount=100000, created_at=this_month_start,
        ))
    db_session.commit()

    login_as(client, user)
    body = client.get("/processor/dashboard").get_data(as_text=True)

    assert "100%" in body


def test_loan_status_breakdown_shows_real_statuses_not_a_fixed_list(db_session, client):
    user, profile, company = _make_processor(db_session, email="processor-status@example.com")
    db_session.add(LoanApplication(processor_id=profile.id, company_id=company.id, status="In Review", amount=100000))
    db_session.add(LoanApplication(processor_id=profile.id, company_id=company.id, status="Conditions Pending", amount=200000))
    db_session.commit()

    login_as(client, user)
    body = client.get("/processor/dashboard").get_data(as_text=True)

    assert "In Review" in body
    assert "Conditions Pending" in body
    assert "Cleared" not in body


def test_monthly_volume_sums_real_amounts(db_session, client):
    user, profile, company = _make_processor(db_session, email="processor-volume@example.com")
    this_month = datetime.utcnow().replace(day=1, hour=12)
    db_session.add(LoanApplication(processor_id=profile.id, company_id=company.id, status="Submitted", amount=300000, created_at=this_month))
    db_session.add(LoanApplication(processor_id=profile.id, company_id=company.id, status="Submitted", amount=150000, created_at=this_month))
    db_session.commit()

    login_as(client, user)
    body = client.get("/processor/dashboard").get_data(as_text=True)

    assert "$450,000" in body


def test_doc_type_breakdown_uses_real_documents(db_session, client):
    user, profile, company = _make_processor(db_session, email="processor-docs@example.com")
    db_session.add(LoanDocument(company_id=company.id, document_type="Bank Statement", status="pending"))
    db_session.add(LoanDocument(company_id=company.id, document_type="Bank Statement", status="pending"))
    db_session.add(LoanDocument(company_id=company.id, document_type="Pay Stub", status="verified"))
    db_session.commit()

    login_as(client, user)
    body = client.get("/processor/dashboard").get_data(as_text=True)

    assert "Bank Statement" in body
    assert "Pay Stub" in body


def test_recent_activity_shows_status_events_for_this_processors_loans(db_session, client):
    user, profile, company = _make_processor(db_session, email="processor-activity@example.com")
    loan = LoanApplication(processor_id=profile.id, company_id=company.id, status="Submitted", amount=100000)
    db_session.add(loan)
    db_session.commit()

    db_session.add(LoanStatusEvent(loan_id=loan.id, event_name="Docs Verified", description="All income docs cleared."))
    db_session.commit()

    login_as(client, user)
    body = client.get("/processor/dashboard").get_data(as_text=True)

    assert "Docs Verified" in body
    assert "All income docs cleared." in body


def test_upcoming_tasks_shows_tasks_assigned_to_this_user(db_session, client):
    user, profile, company = _make_processor(db_session, email="processor-tasks@example.com")
    db_session.add(Task(title="Chase missing bank statement", assigned_to=user.id, due_date=date.today(), completed=False))
    db_session.add(Task(title="Already done task", assigned_to=user.id, due_date=date.today(), completed=True))
    db_session.commit()

    login_as(client, user)
    body = client.get("/processor/dashboard").get_data(as_text=True)

    assert "Chase missing bank statement" in body
    assert "Already done task" not in body
