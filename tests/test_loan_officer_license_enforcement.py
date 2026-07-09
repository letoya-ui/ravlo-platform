"""State MLO licensing enforcement regression tests.

MR !34 added the ability for an admin to verify a loan officer's NMLS #
and licensed states, but nothing actually stopped an unverified or
wrong-state loan officer from being assigned a loan or self-creating one.
Since Ravlo is new software with no existing loan data to break, these
tests cover the strict version: assignment/self-creation is blocked
outright when the target state isn't covered by a verified license.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.loan_models import BorrowerProfile, LoanApplication
from LoanMVP.models.loan_officer_model import LoanOfficerProfile
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_company(db_session, name="Enforcement Co"):
    company = Company(name=name, is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()
    return company


def _make_company_admin(db_session, company, email="admin@example.com"):
    user = User(email=email, role="admin", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user


def _make_loan_officer(db_session, company, email="lo@example.com", verified=False, licensed_states=None):
    user = User(email=email, role="loan_officer", is_active=True, company_id=company.id, first_name="Jamie")
    db_session.add(user)
    db_session.commit()
    profile = LoanOfficerProfile(
        user_id=user.id,
        name="Jamie Officer",
        license_verified=verified,
        licensed_states=licensed_states,
    )
    if verified:
        profile.license_verified_by = user.id
    db_session.add(profile)
    db_session.commit()
    return user, profile


def _make_borrower(db_session, company, state="FL", email="borrower@example.com"):
    user = User(email=email, role="borrower", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    borrower = BorrowerProfile(user_id=user.id, full_name="Bo Rower", email=email, company_id=company.id, state=state)
    db_session.add(borrower)
    db_session.commit()
    return user, borrower


def _make_loan(db_session, company, borrower, **extra):
    extra.setdefault("status", "Application Submitted")
    loan = LoanApplication(company_id=company.id, borrower_profile_id=borrower.id, amount=250000, **extra)
    db_session.add(loan)
    db_session.commit()
    return loan


def test_assignment_blocked_when_officer_not_licensed_in_state(db_session, client):
    company = _make_company(db_session)
    admin = _make_company_admin(db_session, company)
    lo_user, lo_profile = _make_loan_officer(db_session, company, verified=True, licensed_states="GA,TX")
    _, borrower = _make_borrower(db_session, company, state="FL")
    loan = _make_loan(db_session, company, borrower)
    login_as(client, admin)

    resp = client.post(
        f"/admin/company/{company.id}/applications/{loan.id}/assign",
        data={"loan_officer_id": str(lo_profile.id)},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert b"isn" in resp.data.lower()  # "isn't verified/licensed" flash
    db_session.refresh(loan)
    assert loan.loan_officer_id is None


def test_assignment_blocked_when_officer_not_verified(db_session, client):
    company = _make_company(db_session, name="Unverified Co")
    admin = _make_company_admin(db_session, company, email="admin2@example.com")
    lo_user, lo_profile = _make_loan_officer(
        db_session, company, email="lo2@example.com", verified=False, licensed_states="FL"
    )
    _, borrower = _make_borrower(db_session, company, state="FL", email="borrower2@example.com")
    loan = _make_loan(db_session, company, borrower)
    login_as(client, admin)

    resp = client.post(
        f"/admin/company/{company.id}/applications/{loan.id}/assign",
        data={"loan_officer_id": str(lo_profile.id)},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    db_session.refresh(loan)
    assert loan.loan_officer_id is None


def test_assignment_succeeds_when_officer_verified_and_licensed(db_session, client):
    company = _make_company(db_session, name="Success Co")
    admin = _make_company_admin(db_session, company, email="admin3@example.com")
    lo_user, lo_profile = _make_loan_officer(
        db_session, company, email="lo3@example.com", verified=True, licensed_states="FL,GA"
    )
    _, borrower = _make_borrower(db_session, company, state="FL", email="borrower3@example.com")
    loan = _make_loan(db_session, company, borrower)
    login_as(client, admin)

    resp = client.post(
        f"/admin/company/{company.id}/applications/{loan.id}/assign",
        data={"loan_officer_id": str(lo_profile.id)},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    db_session.refresh(loan)
    assert loan.loan_officer_id == lo_profile.id


def test_assignment_not_blocked_when_state_unknown(db_session, client):
    # Neither the loan's property state nor the borrower's state is set --
    # nothing to enforce against, so assignment should proceed.
    company = _make_company(db_session, name="Unknown State Co")
    admin = _make_company_admin(db_session, company, email="admin4@example.com")
    lo_user, lo_profile = _make_loan_officer(
        db_session, company, email="lo4@example.com", verified=False, licensed_states=None
    )
    _, borrower = _make_borrower(db_session, company, state=None, email="borrower4@example.com")
    loan = _make_loan(db_session, company, borrower)
    login_as(client, admin)

    resp = client.post(
        f"/admin/company/{company.id}/applications/{loan.id}/assign",
        data={"loan_officer_id": str(lo_profile.id)},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    db_session.refresh(loan)
    assert loan.loan_officer_id == lo_profile.id


def test_auto_create_loan_rejects_unlicensed_officer(db_session, client):
    company = _make_company(db_session, name="Auto Create Co")
    lo_user, lo_profile = _make_loan_officer(
        db_session, company, email="lo5@example.com", verified=True, licensed_states="GA"
    )
    _, borrower = _make_borrower(db_session, company, state="FL", email="borrower5@example.com")
    login_as(client, lo_user)

    resp = client.post(
        f"/loan_officer/auto-create-loan/{borrower.id}",
        json={"loan_amount": 100000, "loan_type": "DSCR", "property_value": 200000},
    )

    assert resp.status_code == 403
    assert LoanApplication.query.filter_by(borrower_profile_id=borrower.id).first() is None


def test_auto_create_loan_succeeds_when_licensed(db_session, client):
    company = _make_company(db_session, name="Auto Create Success Co")
    lo_user, lo_profile = _make_loan_officer(
        db_session, company, email="lo6@example.com", verified=True, licensed_states="FL"
    )
    _, borrower = _make_borrower(db_session, company, state="FL", email="borrower6@example.com")
    login_as(client, lo_user)

    resp = client.post(
        f"/loan_officer/auto-create-loan/{borrower.id}",
        json={"loan_amount": 100000, "loan_type": "DSCR", "property_value": 200000},
    )

    assert resp.status_code == 200
    loan = LoanApplication.query.filter_by(borrower_profile_id=borrower.id).first()
    assert loan is not None
    assert loan.loan_officer_id == lo_profile.id
