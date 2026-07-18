"""Regression tests for Academy career-track routing for the generic
"partner" role.

_ROLE_TRACK previously hardcoded role "partner" -> track "investor", but
"partner" is a catch-all covering realtors, contractors, property
managers, insurance agents, and more (Partner.category/type is what
actually distinguishes them). Every partner without a more specific role
string (e.g. "realtor") was shown Real Estate Investor lessons instead
of content for their actual profession.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.crm_models import Partner
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_partner(db_session, email, category, type_):
    company = Company(name=f"Co {email}", is_active=True)
    db_session.add(company)
    db_session.commit()
    user = User(email=email, role="partner", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    db_session.add(Partner(user_id=user.id, name=email, category=category, type=type_))
    db_session.commit()
    return user


def test_partner_with_realtor_business_gets_realtor_track(db_session, client):
    user = _make_partner(db_session, "realtor-partner@example.com", "realtor", "Realtor")
    login_as(client, user)

    resp = client.get("/academy/portal")

    assert resp.status_code == 200
    assert 'allowedTrack: "realtor"' in resp.get_data(as_text=True)


def test_partner_with_contractor_business_gets_contractor_track(db_session, client):
    user = _make_partner(db_session, "contractor-partner@example.com", "contractor", "General Contractor")
    login_as(client, user)

    resp = client.get("/academy/portal")

    assert resp.status_code == 200
    assert 'allowedTrack: "contractor"' in resp.get_data(as_text=True)


def test_partner_with_property_management_business_gets_property_mgmt_track(db_session, client):
    user = _make_partner(db_session, "pm-partner@example.com", "property_manager", "Property Management")
    login_as(client, user)

    resp = client.get("/academy/portal")

    assert resp.status_code == 200
    assert 'allowedTrack: "property_mgmt"' in resp.get_data(as_text=True)


def test_partner_with_no_matching_track_is_unrestricted_not_forced_into_investor(db_session, client):
    """Reproduces the reported bug: an insurance partner (no dedicated
    Academy track exists yet) must NOT be routed into investor content --
    unrestricted access (they can browse any track) is the correct
    fallback until real insurance lessons exist."""
    user = _make_partner(db_session, "insurance-partner@example.com", "insurance", "Insurance Agent")
    login_as(client, user)

    resp = client.get("/academy/portal")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'allowedTrack: null' in body
    assert 'allowedTrack: "investor"' not in body
