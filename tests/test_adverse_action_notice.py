"""ECOA/Regulation B adverse-action notice regression tests.

Declining a loan previously just set LoanApplication.status = "Declined"
with zero downstream effect -- the borrower saw a colored status badge and
nothing else. No notice, no reasons, no 30-day clock, nothing required by
ECOA. These tests cover the fix: a decline creates a permanent notice
record and surfaces it to the borrower.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.loan_models import AdverseActionNotice, BorrowerProfile, LoanApplication
from LoanMVP.models.user_model import User
from LoanMVP.services.compliance_service import generate_adverse_action_notice

from tests.conftest import login_as


def _make_company(db_session, name="Notice Test Co"):
    company = Company(name=name, is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()
    return company


def _make_underwriter(db_session, company, email="uw@example.com"):
    user = User(email=email, role="underwriter", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user


def _make_borrower(db_session, company, email="applicant@example.com"):
    user = User(email=email, role="borrower", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    borrower = BorrowerProfile(user_id=user.id, full_name="Jane Applicant", email=email, company_id=company.id)
    db_session.add(borrower)
    db_session.commit()
    return user, borrower


def _make_loan(db_session, company, borrower, **extra):
    extra.setdefault("status", "Under Review")
    loan = LoanApplication(company_id=company.id, borrower_profile_id=borrower.id, amount=250000, **extra)
    db_session.add(loan)
    db_session.commit()
    return loan


def test_decline_creates_adverse_action_notice(db_session, client):
    company = _make_company(db_session)
    uw = _make_underwriter(db_session, company)
    _, borrower = _make_borrower(db_session, company)
    loan = _make_loan(db_session, company, borrower)
    login_as(client, uw)

    resp = client.post(
        f"/underwriter/decision/{loan.id}",
        data={"decision": "Declined", "notes": "Insufficient DSCR ratio."},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    notice = AdverseActionNotice.query.filter_by(loan_id=loan.id).first()
    assert notice is not None
    assert notice.borrower_profile_id == borrower.id
    assert notice.company_id == company.id
    assert "Insufficient DSCR ratio." in notice.reasons
    assert "Equal Credit Opportunity Act" in notice.notice_html


def test_approval_does_not_create_notice(db_session, client):
    company = _make_company(db_session, name="Approve Co")
    uw = _make_underwriter(db_session, company, email="uw2@example.com")
    _, borrower = _make_borrower(db_session, company, email="applicant2@example.com")
    loan = _make_loan(db_session, company, borrower)
    login_as(client, uw)

    client.post(
        f"/underwriter/decision/{loan.id}",
        data={"decision": "Approved", "notes": "Looks good."},
        follow_redirects=True,
    )

    assert AdverseActionNotice.query.filter_by(loan_id=loan.id).first() is None


def test_suspended_does_not_create_notice(db_session, client):
    # Suspended = more info requested, not a final adverse credit decision.
    company = _make_company(db_session, name="Suspend Co")
    uw = _make_underwriter(db_session, company, email="uw3@example.com")
    _, borrower = _make_borrower(db_session, company, email="applicant3@example.com")
    loan = _make_loan(db_session, company, borrower)
    login_as(client, uw)

    client.post(
        f"/underwriter/decision/{loan.id}",
        data={"decision": "Suspended", "notes": "Need more docs."},
        follow_redirects=True,
    )

    assert AdverseActionNotice.query.filter_by(loan_id=loan.id).first() is None


def test_decline_does_not_duplicate_notice_on_repeat(db_session, client):
    company = _make_company(db_session, name="Dup Co")
    uw = _make_underwriter(db_session, company, email="uw4@example.com")
    _, borrower = _make_borrower(db_session, company, email="applicant4@example.com")
    loan = _make_loan(db_session, company, borrower)
    login_as(client, uw)

    client.post(f"/underwriter/decision/{loan.id}", data={"decision": "Declined", "notes": "First reason."})
    client.post(f"/underwriter/decision/{loan.id}", data={"decision": "Declined", "notes": "First reason."})

    assert AdverseActionNotice.query.filter_by(loan_id=loan.id).count() == 1


def test_borrower_sees_notice_on_declined_loan(db_session, client):
    # Sets up the declined state directly (via the same service function the
    # underwriter route calls) rather than chaining two logins in one test --
    # this test suite's session handling isn't set up to switch users mid-test;
    # the underwriter route itself is already covered by
    # test_decline_creates_adverse_action_notice above.
    company = _make_company(db_session, name="Borrower View Co")
    borrower_user, borrower = _make_borrower(db_session, company, email="applicant5@example.com")
    loan = _make_loan(db_session, company, borrower, status="Declined", decision_notes="Low reserves.")
    generate_adverse_action_notice(loan)

    login_as(client, borrower_user)
    resp = client.get(f"/borrower/loan/{loan.id}")

    assert resp.status_code == 200
    assert b"Low reserves." in resp.data
    assert b"Equal Credit Opportunity Act" in resp.data


def test_borrower_does_not_see_notice_on_approved_loan(db_session, client):
    company = _make_company(db_session, name="No Notice Co")
    borrower_user, borrower = _make_borrower(db_session, company, email="applicant6@example.com")
    loan = _make_loan(db_session, company, borrower, status="Approved")

    login_as(client, borrower_user)
    resp = client.get(f"/borrower/loan/{loan.id}")

    assert resp.status_code == 200
    assert b"Equal Credit Opportunity Act" not in resp.data
