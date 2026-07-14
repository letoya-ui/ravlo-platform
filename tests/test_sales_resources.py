"""Regression tests for the internal Sales Resources page (/resources):
the Lending OS one-pager and per-dashboard talking points, available to
account executives, Ravlo admins, and executives.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_user(db_session, email, role):
    company = Company.query.filter_by(name="Ravlo").first()
    if not company:
        company = Company(name="Ravlo", is_active=True)
        db_session.add(company)
        db_session.commit()
    user = User(email=email, role=role, is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user


def test_account_executive_can_view_resources(db_session, client):
    user = _make_user(db_session, "ae-resources@example.com", "account_executive")
    login_as(client, user)

    resp = client.get("/resources/")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Ravlo Lending OS" in body
    assert "LOAN OFFICER" in body
    assert "$149" in body
    assert "$799" in body


def test_admin_can_view_resources(db_session, client):
    user = _make_user(db_session, "admin-resources@example.com", "admin")
    login_as(client, user)

    resp = client.get("/resources/")

    assert resp.status_code == 200


def test_executive_can_view_resources(db_session, client):
    user = _make_user(db_session, "exec-resources@example.com", "executive")
    login_as(client, user)

    resp = client.get("/resources/")

    assert resp.status_code == 200


def test_unrelated_role_cannot_view_resources(db_session, client):
    user = _make_user(db_session, "lo-resources@example.com", "loan_officer")
    login_as(client, user)

    resp = client.get("/resources/", follow_redirects=False)

    assert resp.status_code == 302
    assert "/resources" not in resp.headers.get("Location", "")


def test_sales_resources_link_appears_on_ae_sidebar(db_session, client):
    user = _make_user(db_session, "ae-sidebar@example.com", "account_executive")
    login_as(client, user)

    resp = client.get("/account-executive/dashboard")

    assert resp.status_code == 200
    assert "/resources" in resp.get_data(as_text=True)
