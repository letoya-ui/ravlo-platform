"""Loan officer state-MLO-license verification regression tests.

LoanOfficerProfile.nmls existed but was inert data -- never validated
against anything, no per-state license list, no record of anyone having
reviewed it. These tests cover the fix: a company (or full Ravlo) admin
can review and mark a loan officer's license verified, and that state is
scoped the same way every other company-admin action already is.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.loan_officer_model import LoanOfficerProfile
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_company(db_session, name="License Test Co"):
    company = Company(name=name, is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()
    return company


def _make_company_admin(db_session, company, email="companyadmin@example.com"):
    user = User(email=email, role="admin", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user


def _make_full_admin(db_session, email="ravlo-admin@ravlohq.com"):
    admin = User(email=email, role="executive", is_active=True)
    db_session.add(admin)
    db_session.commit()
    return admin


def _make_loan_officer(db_session, company, email="lo@example.com"):
    user = User(email=email, role="loan_officer", is_active=True, company_id=company.id, first_name="Jamie")
    db_session.add(user)
    db_session.commit()
    return user


def test_company_admin_can_verify_loan_officer_license(db_session, client):
    company = _make_company(db_session)
    admin = _make_company_admin(db_session, company)
    lo = _make_loan_officer(db_session, company)
    login_as(client, admin)

    resp = client.post(
        f"/admin/company/{company.id}/team/{lo.id}/license",
        data={"nmls": "1234567", "licensed_states": "fl, ga, tx", "verified": "on"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    profile = LoanOfficerProfile.query.filter_by(user_id=lo.id).first()
    assert profile is not None
    assert profile.nmls == "1234567"
    assert profile.licensed_states == "FL,GA,TX"
    assert profile.license_verified is True
    assert profile.license_verified_by == admin.id
    assert profile.license_verified_at is not None


def test_unchecking_verified_clears_verification(db_session, client):
    company = _make_company(db_session, name="Unverify Co")
    admin = _make_company_admin(db_session, company, email="admin2@example.com")
    lo = _make_loan_officer(db_session, company, email="lo2@example.com")
    login_as(client, admin)

    client.post(
        f"/admin/company/{company.id}/team/{lo.id}/license",
        data={"nmls": "999", "licensed_states": "FL", "verified": "on"},
    )
    client.post(
        f"/admin/company/{company.id}/team/{lo.id}/license",
        data={"nmls": "999", "licensed_states": "FL"},  # no "verified" field = unchecked
    )

    profile = LoanOfficerProfile.query.filter_by(user_id=lo.id).first()
    assert profile.license_verified is False
    assert profile.license_verified_by is None
    assert profile.license_verified_at is None


def test_outside_company_admin_cannot_verify(db_session, client):
    company_a = _make_company(db_session, name="Company A")
    company_b = _make_company(db_session, name="Company B")
    outsider_admin = _make_company_admin(db_session, company_b, email="outsider@example.com")
    lo = _make_loan_officer(db_session, company_a, email="lo3@example.com")
    login_as(client, outsider_admin)

    resp = client.post(
        f"/admin/company/{company_a.id}/team/{lo.id}/license",
        data={"nmls": "111", "licensed_states": "FL", "verified": "on"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert b"do not have access" in resp.data
    assert LoanOfficerProfile.query.filter_by(user_id=lo.id).first() is None


def test_full_admin_can_verify_any_companys_loan_officer(db_session, client):
    company = _make_company(db_session, name="Full Admin Co")
    full_admin = _make_full_admin(db_session)
    lo = _make_loan_officer(db_session, company, email="lo4@example.com")
    login_as(client, full_admin)

    resp = client.post(
        f"/admin/company/{company.id}/team/{lo.id}/license",
        data={"nmls": "222", "licensed_states": "GA", "verified": "on"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    profile = LoanOfficerProfile.query.filter_by(user_id=lo.id).first()
    assert profile.license_verified is True
    assert profile.license_verified_by == full_admin.id


def test_non_loan_officer_rejected(db_session, client):
    company = _make_company(db_session, name="Wrong Role Co")
    admin = _make_company_admin(db_session, company, email="admin3@example.com")
    processor = User(email="proc@example.com", role="processor", is_active=True, company_id=company.id)
    db_session.add(processor)
    db_session.commit()
    login_as(client, admin)

    resp = client.get(
        f"/admin/company/{company.id}/team/{processor.id}/license",
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert b"isn" in resp.data.lower()  # "isn't a loan officer" flash message


def test_team_page_shows_unverified_badge(db_session, client):
    company = _make_company(db_session, name="Badge Co")
    admin = _make_company_admin(db_session, company, email="admin4@example.com")
    _make_loan_officer(db_session, company, email="lo5@example.com")
    login_as(client, admin)

    resp = client.get(f"/admin/company/{company.id}/team")

    assert resp.status_code == 200
    assert b"Unverified" in resp.data


def test_team_page_shows_verified_badge_after_verification(db_session, client):
    company = _make_company(db_session, name="Verified Badge Co")
    admin = _make_company_admin(db_session, company, email="admin5@example.com")
    lo = _make_loan_officer(db_session, company, email="lo6@example.com")
    login_as(client, admin)

    client.post(
        f"/admin/company/{company.id}/team/{lo.id}/license",
        data={"nmls": "333", "licensed_states": "TX", "verified": "on"},
    )

    resp = client.get(f"/admin/company/{company.id}/team")

    assert resp.status_code == 200
    assert b"Verified" in resp.data
