"""Regression tests for processor.decision() -- the final lending decision
a processor can make when their company's Lending OS package has no
underwriter seat (Company.enabled_roles excludes "underwriter").

Built for a new partner that wants only loan_officer/admin/processor/
borrower roles, with processors doing what an underwriter would otherwise
do. Every existing company (enabled_roles unset) must keep going through
underwriter.decision() exactly as before -- processor.decision() should
refuse to act for them.
"""
from LoanMVP.extensions import db
from LoanMVP.models.admin import Company
from LoanMVP.models.loan_models import AdverseActionNotice, BorrowerProfile, LoanApplication
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_company(db_session, name="Decision Co", **kwargs):
    company = Company(name=name, is_active=True, subscription_tier="team", max_users=25, **kwargs)
    db_session.add(company)
    db_session.commit()
    return company


def _make_processor(db_session, company, email="proc@example.com"):
    user = User(email=email, role="processor", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user


def _make_borrower(db_session, company, email="borrower@example.com"):
    user = User(email=email, role="borrower", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    borrower = BorrowerProfile(user_id=user.id, full_name="Bo Rower", email=email, company_id=company.id, state="FL")
    db_session.add(borrower)
    db_session.commit()
    return borrower


def _make_loan(db_session, company, borrower, **extra):
    extra.setdefault("status", "Processing")
    loan = LoanApplication(company_id=company.id, borrower_profile_id=borrower.id, amount=250000, **extra)
    db_session.add(loan)
    db_session.commit()
    return loan


def test_decision_blocked_when_company_has_underwriter_seat(db_session, client):
    company = _make_company(db_session, name="Has-UW Co")  # enabled_roles unset -> full package
    processor = _make_processor(db_session, company, "proc1@example.com")
    borrower = _make_borrower(db_session, company, "borrower1@example.com")
    loan = _make_loan(db_session, company, borrower)
    login_as(client, processor)

    resp = client.post(
        f"/processor/decision/{loan.id}",
        data={"decision": "Approved", "notes": "looks good"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "has an underwriter seat" in resp.get_data(as_text=True)
    loan = LoanApplication.query.get(loan.id)
    assert loan.status == "Processing"
    assert loan.decision_date is None


def test_decision_allowed_when_company_has_no_underwriter_seat(db_session, client):
    company = _make_company(
        db_session, name="No-UW Co",
        enabled_roles=["admin", "loan_officer", "processor", "borrower"],
    )
    processor = _make_processor(db_session, company, "proc2@example.com")
    borrower = _make_borrower(db_session, company, "borrower2@example.com")
    loan = _make_loan(db_session, company, borrower)
    login_as(client, processor)

    resp = client.post(
        f"/processor/decision/{loan.id}",
        data={"decision": "Approved", "notes": "clean file"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    loan = LoanApplication.query.get(loan.id)
    assert loan.status == "Approved"
    assert loan.decision_notes == "clean file"
    assert loan.decision_date is not None


def test_decline_decision_generates_adverse_action_notice(db_session, client):
    company = _make_company(
        db_session, name="No-UW Decline Co",
        enabled_roles=["admin", "loan_officer", "processor", "borrower"],
    )
    processor = _make_processor(db_session, company, "proc3@example.com")
    borrower = _make_borrower(db_session, company, "borrower3@example.com")
    loan = _make_loan(db_session, company, borrower)
    login_as(client, processor)

    client.post(
        f"/processor/decision/{loan.id}",
        data={"decision": "Declined", "notes": "insufficient income"},
        follow_redirects=True,
    )

    loan = LoanApplication.query.get(loan.id)
    assert loan.status == "Declined"
    notice = AdverseActionNotice.query.filter_by(loan_id=loan.id).first()
    assert notice is not None
    assert notice.reasons == "insufficient income"


def test_submit_to_underwriter_blocked_when_no_underwriter_seat(db_session, client):
    company = _make_company(
        db_session, name="No-UW Submit Co",
        enabled_roles=["admin", "loan_officer", "processor", "borrower"],
    )
    processor = _make_processor(db_session, company, "proc4@example.com")
    borrower = _make_borrower(db_session, company, "borrower4@example.com")
    loan = _make_loan(db_session, company, borrower)
    login_as(client, processor)

    resp = client.get(f"/processor/submit-underwriter/{loan.id}", follow_redirects=True)

    assert resp.status_code == 200
    assert "no underwriter seat" in resp.get_data(as_text=True)
    loan = LoanApplication.query.get(loan.id)
    assert loan.status == "Processing"


def test_submit_to_underwriter_still_works_with_underwriter_seat(db_session, client):
    company = _make_company(db_session, name="Has-UW Submit Co")
    processor = _make_processor(db_session, company, "proc5@example.com")
    borrower = _make_borrower(db_session, company, "borrower5@example.com")
    loan = _make_loan(db_session, company, borrower)
    login_as(client, processor)

    resp = client.get(f"/processor/submit-underwriter/{loan.id}", follow_redirects=True)

    assert resp.status_code == 200
    loan = LoanApplication.query.get(loan.id)
    assert loan.status == "Submitted"


def test_file_review_shows_decision_form_only_without_underwriter_seat(db_session, client):
    company = _make_company(
        db_session, name="No-UW File Co",
        enabled_roles=["admin", "loan_officer", "processor", "borrower"],
    )
    processor = _make_processor(db_session, company, "proc6@example.com")
    borrower = _make_borrower(db_session, company, "borrower6@example.com")
    loan = _make_loan(db_session, company, borrower)
    login_as(client, processor)

    body = client.get(f"/processor/file/{loan.id}").get_data(as_text=True)

    assert "Final Lending Decision" in body
    assert "Submit to Underwriter" not in body


def test_file_review_hides_decision_form_with_underwriter_seat(db_session, client):
    company = _make_company(db_session, name="Has-UW File Co")
    processor = _make_processor(db_session, company, "proc7@example.com")
    borrower = _make_borrower(db_session, company, "borrower7@example.com")
    loan = _make_loan(db_session, company, borrower)
    login_as(client, processor)

    body = client.get(f"/processor/file/{loan.id}").get_data(as_text=True)

    assert "Final Lending Decision" not in body
    assert "Submit to Underwriter" in body
