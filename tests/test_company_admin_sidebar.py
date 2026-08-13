"""Regression tests for what a company admin (a customer lending
company's own "admin" user, as opposed to Ravlo's own staff admin) sees
in their sidebar. Sales Resources, Requests, and the Bid Support Queue
are all Ravlo-internal tools -- a customer company's admin never had a
working path to them (Bid Support Queue redirected them away with
"Access restricted", and Sales Resources/Requests are Ravlo-staff-only
concepts), so the links were shown but effectively dead. They're now
hidden for company admins entirely. This only removes the sidebar
shortcut -- company_dashboard.html's own "Access Requests" section/tile
is untouched and still fully functional.
"""
import re

from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _sidebar_html(body: str) -> str:
    match = re.search(r'id="reSidebar".*?</aside>', body, re.DOTALL)
    assert match, "could not find the employee-base sidebar in the response"
    return match.group(0)


def _make_company_admin(db_session, email="company-admin@example.com", company_name="Acme Lending"):
    company = Company(name=company_name, is_active=True)
    db_session.add(company)
    db_session.commit()
    user = User(email=email, role="admin", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user, company


def _make_ravlo_staff_admin(db_session, email="staff-admin@ravlohq.com"):
    user = User(email=email, role="master_admin", is_active=True, company_id=None)
    db_session.add(user)
    db_session.commit()
    return user


def test_company_admin_sidebar_hides_sales_resources_requests_and_bid_support(db_session, client):
    user, company = _make_company_admin(db_session)
    login_as(client, user)

    resp = client.get(f"/admin/company/{company.id}/dashboard")

    assert resp.status_code == 200
    sidebar = _sidebar_html(resp.get_data(as_text=True))
    assert "Sales Resources" not in sidebar
    assert "Bid Support Queue" not in sidebar
    assert ">Requests<" not in sidebar
    # Their own onboarding link must still be present -- this isn't a
    # wholesale removal of the Onboarding section.
    assert ">Team<" in sidebar


def test_ravlo_staff_admin_sidebar_keeps_sales_resources_requests_and_bid_support(db_session, client):
    user = _make_ravlo_staff_admin(db_session)
    login_as(client, user)

    resp = client.get("/admin/dashboard")

    assert resp.status_code == 200
    sidebar = _sidebar_html(resp.get_data(as_text=True))
    assert "Sales Resources" in sidebar
    assert "Bid Support Queue" in sidebar
    assert ">Requests<" not in sidebar  # they see "Access Requests" (the other nav item), not "Requests"
