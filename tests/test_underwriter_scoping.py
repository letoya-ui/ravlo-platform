"""Per-underwriter scoping regression tests.

Underwriter dashboard/queue/pipeline/risk-reports previously showed every
loan in the underwriter's company rather than just their own assigned
files -- there was also no way for an admin to ever assign a loan to an
underwriter in the first place, so LoanApplication.underwriter_id was
permanently NULL. This covers both halves: the new admin assignment path,
and the routes actually scoping to the assigned underwriter.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.loan_models import BorrowerProfile, LoanApplication
from LoanMVP.models.underwriter_model import UnderwriterProfile
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_company(db_session, name="Scoping Co"):
    company = Company(name=name, is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()
    return company


def _make_admin(db_session, company, email="admin@example.com"):
    user = User(email=email, role="admin", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user


def _make_underwriter(db_session, company, email="uw@example.com"):
    user = User(email=email, role="underwriter", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    profile = UnderwriterProfile(user_id=user.id, full_name="Uma Writer")
    db_session.add(profile)
    db_session.commit()
    return user, profile


def _make_borrower(db_session, company, email="borrower@example.com", full_name="Bo Rower"):
    user = User(email=email, role="borrower", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    borrower = BorrowerProfile(user_id=user.id, full_name=full_name, email=email, company_id=company.id, state="FL")
    db_session.add(borrower)
    db_session.commit()
    return user, borrower


def _make_loan(db_session, company, borrower, **extra):
    extra.setdefault("status", "Submitted")
    loan = LoanApplication(company_id=company.id, borrower_profile_id=borrower.id, amount=250000, **extra)
    db_session.add(loan)
    db_session.commit()
    return loan


def test_admin_can_assign_underwriter_to_loan(db_session, client):
    company = _make_company(db_session)
    admin = _make_admin(db_session, company)
    uw_user, uw_profile = _make_underwriter(db_session, company)
    _, borrower = _make_borrower(db_session, company)
    loan = _make_loan(db_session, company, borrower)
    login_as(client, admin)

    resp = client.post(
        f"/admin/company/{company.id}/applications/{loan.id}/assign",
        data={"underwriter_id": str(uw_profile.id)},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    db_session.refresh(loan)
    assert loan.underwriter_id == uw_profile.id


def test_admin_assignment_rejects_underwriter_from_other_company(db_session, client):
    company = _make_company(db_session, name="Scoping Co A")
    other_company = _make_company(db_session, name="Scoping Co B")
    admin = _make_admin(db_session, company, email="admin2@example.com")
    outside_uw_user, outside_uw_profile = _make_underwriter(db_session, other_company, email="outsider@example.com")
    _, borrower = _make_borrower(db_session, company, email="borrower2@example.com")
    loan = _make_loan(db_session, company, borrower)
    login_as(client, admin)

    resp = client.post(
        f"/admin/company/{company.id}/applications/{loan.id}/assign",
        data={"underwriter_id": str(outside_uw_profile.id)},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    db_session.refresh(loan)
    assert loan.underwriter_id is None


def test_dashboard_shows_only_assigned_underwriters_loans(db_session, client):
    company = _make_company(db_session, name="Dashboard Co")
    uw_user, uw_profile = _make_underwriter(db_session, company, email="uw-dash@example.com")
    other_uw_user, other_uw_profile = _make_underwriter(db_session, company, email="uw-other@example.com")
    _, borrower_mine = _make_borrower(db_session, company, email="mine@example.com", full_name="Mine Borrower")
    _, borrower_other = _make_borrower(db_session, company, email="other@example.com", full_name="Other Borrower")
    mine = _make_loan(db_session, company, borrower_mine, underwriter_id=uw_profile.id)
    _make_loan(db_session, company, borrower_other, underwriter_id=other_uw_profile.id)
    login_as(client, uw_user)

    resp = client.get("/underwriter/dashboard")

    assert resp.status_code == 200
    assert b"Mine Borrower" in resp.data
    assert b"Other Borrower" not in resp.data


def test_queue_scoped_to_assigned_underwriter(db_session, client):
    company = _make_company(db_session, name="Queue Co")
    uw_user, uw_profile = _make_underwriter(db_session, company, email="uw-queue@example.com")
    other_uw_user, other_uw_profile = _make_underwriter(db_session, company, email="uw-queue-other@example.com")
    _, borrower_mine = _make_borrower(db_session, company, email="queue-mine@example.com", full_name="Queue Mine Borrower")
    _, borrower_other = _make_borrower(db_session, company, email="queue-other@example.com", full_name="Queue Other Borrower")
    _make_loan(db_session, company, borrower_mine, underwriter_id=uw_profile.id, status="UW Review")
    _make_loan(db_session, company, borrower_other, underwriter_id=other_uw_profile.id, status="UW Review")
    login_as(client, uw_user)

    resp = client.get("/underwriter/queue")

    assert resp.status_code == 200
    assert b"Queue Mine Borrower" in resp.data
    assert b"Queue Other Borrower" not in resp.data


def test_pipeline_scoped_to_assigned_underwriter(db_session, client):
    company = _make_company(db_session, name="Pipeline Co")
    uw_user, uw_profile = _make_underwriter(db_session, company, email="uw-pipe@example.com")
    other_uw_user, other_uw_profile = _make_underwriter(db_session, company, email="uw-pipe-other@example.com")
    _, borrower_mine = _make_borrower(db_session, company, email="pipe-mine@example.com")
    _, borrower_other = _make_borrower(db_session, company, email="pipe-other@example.com")
    _make_loan(db_session, company, borrower_mine, underwriter_id=uw_profile.id, status="Submitted", property_address="Pipeline Mine Ln")
    _make_loan(db_session, company, borrower_other, underwriter_id=other_uw_profile.id, status="Submitted", property_address="Pipeline Other Ln")
    login_as(client, uw_user)

    resp = client.get("/underwriter/pipeline")

    assert resp.status_code == 200
    assert b"Pipeline Mine Ln" in resp.data
    assert b"Pipeline Other Ln" not in resp.data


def test_pipeline_counts_only_my_loans(db_session, client):
    company = _make_company(db_session, name="Pipeline Count Co")
    uw_user, uw_profile = _make_underwriter(db_session, company, email="uw-count@example.com")
    other_uw_user, other_uw_profile = _make_underwriter(db_session, company, email="uw-count-other@example.com")
    _, borrower_mine = _make_borrower(db_session, company, email="count-mine@example.com")
    _, borrower_other = _make_borrower(db_session, company, email="count-other@example.com")
    _make_loan(db_session, company, borrower_mine, underwriter_id=uw_profile.id, status="Submitted")
    _make_loan(db_session, company, borrower_other, underwriter_id=other_uw_profile.id, status="Submitted")

    from LoanMVP.routes.underwriter import _underwriter_loans_query
    from flask_login import login_user

    with client.application.test_request_context():
        login_user(uw_user)
        submitted = _underwriter_loans_query().filter_by(status="Submitted").all()
        assert len(submitted) == 1
        assert submitted[0].borrower_profile_id == borrower_mine.id


def test_risk_reports_scoped_to_assigned_underwriter(db_session, client):
    company = _make_company(db_session, name="Risk Co")
    uw_user, uw_profile = _make_underwriter(db_session, company, email="uw-risk@example.com")
    other_uw_user, other_uw_profile = _make_underwriter(db_session, company, email="uw-risk-other@example.com")
    _, borrower_mine = _make_borrower(db_session, company, email="risk-mine@example.com", full_name="Risk Mine Borrower")
    _, borrower_other = _make_borrower(db_session, company, email="risk-other@example.com", full_name="Risk Other Borrower")
    _make_loan(db_session, company, borrower_mine, underwriter_id=uw_profile.id)
    _make_loan(db_session, company, borrower_other, underwriter_id=other_uw_profile.id)
    login_as(client, uw_user)

    resp = client.get("/underwriter/risk-reports")

    assert resp.status_code == 200
    assert b"Risk Mine Borrower" in resp.data
    assert b"Risk Other Borrower" not in resp.data


def test_unonboarded_underwriter_falls_back_to_company_wide_view(db_session, client):
    # No UnderwriterProfile yet -- nothing could ever have been assigned to
    # this user, so the fallback shows the company's queue rather than an
    # empty screen.
    company = _make_company(db_session, name="Fallback Co")
    user = User(email="uw-fallback@example.com", role="underwriter", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    _, borrower = _make_borrower(db_session, company, email="fallback-borrower@example.com", full_name="Fallback Borrower")
    _make_loan(db_session, company, borrower)
    login_as(client, user)

    resp = client.get("/underwriter/dashboard")

    assert resp.status_code == 200
    assert b"Fallback Borrower" in resp.data
