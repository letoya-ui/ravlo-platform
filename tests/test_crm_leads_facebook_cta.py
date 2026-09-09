"""Regression test: the CRM Leads page (crm.leads) gave loan officers
no indication that Facebook/Instagram Lead Ads even exist as a lead
source, let alone how to connect one -- reported as "looking at loan
officer's leads, it doesn't say connect to facebook."
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.crm_models import FacebookPageConnection
from LoanMVP.models.loan_officer_model import LoanOfficerProfile
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_company(db_session, name="Lead Co"):
    company = Company(name=name, is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()
    return company


def _make_loan_officer(db_session, company, email="lo@example.com"):
    user = User(email=email, role="loan_officer", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    profile = LoanOfficerProfile(user_id=user.id, name="Lonnie Officer", email=email)
    db_session.add(profile)
    db_session.commit()
    return user


def _make_admin(db_session, company, email="admin@example.com"):
    user = User(email=email, role="admin", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user


def test_loan_officer_sees_connect_facebook_prompt_when_not_connected(db_session, client):
    company = _make_company(db_session)
    officer = _make_loan_officer(db_session, company)
    login_as(client, officer)

    resp = client.get("/crm/leads")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "No Facebook or Instagram Lead Ads connected" in body
    assert "Ask your admin to connect it" in body
    assert "/admin/company/" not in body


def test_admin_sees_a_connect_link_when_not_connected(db_session, client):
    company = _make_company(db_session, "Admin Lead Co")
    admin = _make_admin(db_session, company, email="admin2@example.com")
    login_as(client, admin)

    resp = client.get("/crm/leads")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "No Facebook or Instagram Lead Ads connected" in body
    assert f"/admin/company/{company.id}/settings" in body


def test_prompt_disappears_once_a_page_is_connected(db_session, client):
    company = _make_company(db_session, "Connected Co")
    officer = _make_loan_officer(db_session, company, email="lo2@example.com")
    connection = FacebookPageConnection(
        company_id=company.id, page_id="123", page_name="Connected Page",
        platform="facebook", page_access_token="tok", is_active=True,
    )
    db_session.add(connection)
    db_session.commit()

    login_as(client, officer)
    resp = client.get("/crm/leads")

    assert resp.status_code == 200
    assert "No Facebook or Instagram Lead Ads connected" not in resp.get_data(as_text=True)


def test_prompt_still_shows_if_connection_is_inactive(db_session, client):
    company = _make_company(db_session, "Disconnected Co")
    officer = _make_loan_officer(db_session, company, email="lo3@example.com")
    connection = FacebookPageConnection(
        company_id=company.id, page_id="456", page_name="Old Page",
        platform="facebook", page_access_token="tok", is_active=False,
    )
    db_session.add(connection)
    db_session.commit()

    login_as(client, officer)
    resp = client.get("/crm/leads")

    assert resp.status_code == 200
    assert "No Facebook or Instagram Lead Ads connected" in resp.get_data(as_text=True)
