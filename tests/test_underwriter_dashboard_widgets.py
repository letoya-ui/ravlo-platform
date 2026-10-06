"""Regression tests for the Underwriter Dashboard redesign
(LoanMVP/routes/underwriter.py's dashboard(), templates/underwriter/dashboard.html):
the hero photo banner, the approval/decline trend chart, the pipeline-mix
donut, the condition clear-rate gauge, recent activity, and upcoming tasks
-- all built from this underwriter's real loans/conditions/tasks, replacing
the previous hardcoded sample chart series ([10,14,20,...], 55/30/15, 78).
"""
from datetime import date, datetime, timedelta

from LoanMVP.extensions import db
from LoanMVP.models.admin import Company
from LoanMVP.models.loan_models import BorrowerProfile, LoanApplication, LoanStatusEvent
from LoanMVP.models.underwriter_model import UnderwriterProfile, UnderwritingCondition, UnderwriterTask
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_underwriter(db_session, email="underwriter-widgets@example.com"):
    company = Company(name="Widgets Lending Co", is_active=True)
    db_session.add(company)
    db_session.commit()

    user = User(
        email=email, role="underwriter", is_active=True, company_id=company.id,
        first_name="Devon", onboarding_complete=True,
        ica_accepted=True, nda_accepted=True,
    )
    db_session.add(user)
    db_session.commit()

    profile = UnderwriterProfile(user_id=user.id, full_name="Devon Marsh", email=email)
    db_session.add(profile)
    db_session.commit()
    return user, profile, company


def test_dashboard_renders_with_no_data(db_session, client):
    user, profile, company = _make_underwriter(db_session)
    login_as(client, user)

    resp = client.get("/underwriter/dashboard")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Welcome, Devon" in body
    assert "No reviews processed yet." in body
    assert "No open conditions right now." in body


def test_approval_trend_reflects_real_decisions(db_session, client):
    user, profile, company = _make_underwriter(db_session, email="underwriter-trend@example.com")
    this_month = datetime.utcnow().replace(day=1, hour=12)

    db_session.add(LoanApplication(
        underwriter_id=profile.id, company_id=company.id, status="Approved",
        amount=100000, decision_date=this_month,
    ))
    db_session.add(LoanApplication(
        underwriter_id=profile.id, company_id=company.id, status="Declined",
        amount=200000, decision_date=this_month,
    ))
    db_session.commit()

    login_as(client, user)
    body = client.get("/underwriter/dashboard").get_data(as_text=True)

    # Both counts (1 approved, 1 declined) should appear in the trend series
    assert "[0, 0, 0, 0, 0, 1]" in body
    # The pipeline-mix donut should also reflect the real approved/declined counts
    assert "[0, 1, 1, 0, 0]" in body


def test_condition_clear_rate_uses_real_conditions(db_session, client):
    user, profile, company = _make_underwriter(db_session, email="underwriter-conditions@example.com")
    borrower = BorrowerProfile(full_name="Test Borrower")
    db_session.add(borrower)
    db_session.commit()

    loan = LoanApplication(underwriter_id=profile.id, company_id=company.id, status="Approved with Conditions", amount=100000)
    db_session.add(loan)
    db_session.commit()

    db_session.add(UnderwritingCondition(borrower_profile_id=borrower.id, loan_id=loan.id, condition_type="Income Verification", status="Cleared"))
    db_session.add(UnderwritingCondition(borrower_profile_id=borrower.id, loan_id=loan.id, condition_type="Title Review", status="Open"))
    db_session.commit()

    login_as(client, user)
    body = client.get("/underwriter/dashboard").get_data(as_text=True)

    # 1 of 2 conditions cleared -> 50%
    assert "[50]" in body
    assert "Title Review" in body


def test_upcoming_tasks_shows_tasks_assigned_to_this_underwriter(db_session, client):
    user, profile, company = _make_underwriter(db_session, email="underwriter-tasks@example.com")
    db_session.add(UnderwriterTask(title="Review title commitment", assigned_to=profile.id, due_date=date.today(), status="Pending"))
    db_session.add(UnderwriterTask(title="Already done task", assigned_to=profile.id, due_date=date.today(), status="Completed"))
    db_session.commit()

    login_as(client, user)
    body = client.get("/underwriter/dashboard").get_data(as_text=True)

    assert "Review title commitment" in body
    assert "Already done task" not in body


def test_recent_activity_shows_status_events_for_this_underwriters_loans(db_session, client):
    user, profile, company = _make_underwriter(db_session, email="underwriter-activity@example.com")
    loan = LoanApplication(underwriter_id=profile.id, company_id=company.id, status="In Review", amount=100000)
    db_session.add(loan)
    db_session.commit()

    db_session.add(LoanStatusEvent(loan_id=loan.id, event_name="Sent to Underwriting", description="File complete, ready for decision."))
    db_session.commit()

    login_as(client, user)
    body = client.get("/underwriter/dashboard").get_data(as_text=True)

    assert "Sent to Underwriting" in body
    assert "File complete, ready for decision." in body
