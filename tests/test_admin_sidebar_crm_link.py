"""Regression test: company admins were missing the CRM nav link.

_sidebar_admin.html only rendered the CRM link inside the
"{% if not is_company_admin %}" branch (the Ravlo-staff view), even
though crm.dashboard's own @role_required already allows "admin" --
so a customer lending company's admin could reach /crm/dashboard
directly, but the sidebar gave them no way to find it (including the
Facebook/Instagram Lead Ads leads that flow into the CRM).
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_company_admin(db_session, company_name="Some Lending Co", email="admin@somelendingco.com"):
    company = Company(name=company_name, is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role="admin", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user, company


def test_company_admin_sees_crm_link_on_dashboard(db_session, client):
    user, company = _make_company_admin(db_session)
    login_as(client, user)

    resp = client.get(f"/admin/company/{company.id}/dashboard")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "/crm/dashboard" in body


def test_company_admin_can_load_crm_dashboard(db_session, client):
    user, company = _make_company_admin(db_session, email="admin2@somelendingco.com")
    login_as(client, user)

    resp = client.get("/crm/dashboard")

    assert resp.status_code == 200
