"""Regression tests for the Ravlo Pricing Playbook page (/resources/pricing-playbook).

The page is a read-only reference for AEs and Ravlo staff -- it reads the
standard/enterprise rate card and the approval-level thresholds straight
from LoanMVP/services/ae_pricing.py (the same module the Account
Executive deal tool's quote calculator uses) so the reference document
can never drift out of sync with what a real quote calculates.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User
from LoanMVP.services import ae_pricing

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


def test_account_executive_can_view_pricing_playbook(db_session, client):
    user = _make_user(db_session, "ae-playbook@example.com", "account_executive")
    login_as(client, user)

    resp = client.get("/resources/pricing-playbook")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Ravlo Pricing Playbook" in body
    assert "Approval Levels" in body or "APPROVAL LEVELS" in body


def test_playbook_shows_the_real_standard_plan_prices(db_session, client):
    user = _make_user(db_session, "ae-playbook2@example.com", "account_executive")
    login_as(client, user)

    resp = client.get("/resources/pricing-playbook")
    body = resp.get_data(as_text=True)

    solo = ae_pricing.STANDARD_PARTNER_PLANS["solo"]
    assert f"${solo['setup']:,.0f}" in body
    assert f"${solo['monthly']:,.0f}" in body

    regional = ae_pricing.STANDARD_LENDING_PLANS["regional"]
    assert f"${regional['setup']:,.0f}" in body
    assert f"${regional['monthly']:,.0f}" in body


def test_playbook_shows_the_real_enterprise_matrix(db_session, client):
    user = _make_user(db_session, "ae-playbook3@example.com", "account_executive")
    login_as(client, user)

    resp = client.get("/resources/pricing-playbook")
    body = resp.get_data(as_text=True)

    for _max_users, setup, monthly, label in ae_pricing.ENTERPRISE_TIERS:
        assert label in body
        if setup is not None:
            assert f"${setup:,.0f}" in body


def test_playbook_shows_the_real_approval_thresholds(db_session, client):
    user = _make_user(db_session, "ae-playbook4@example.com", "account_executive")
    login_as(client, user)

    resp = client.get("/resources/pricing-playbook")
    body = resp.get_data(as_text=True)

    assert f"{int(ae_pricing.AE_MAX_DISCOUNT_PERCENT)}%" in body
    assert f"${ae_pricing.AE_MAX_SETUP_WAIVER:,.0f}" in body
    assert f"{int(ae_pricing.SALES_MANAGER_MAX_DISCOUNT_PERCENT)}%" in body


def test_admin_can_view_pricing_playbook(db_session, client):
    user = _make_user(db_session, "admin-playbook@example.com", "admin")
    login_as(client, user)

    resp = client.get("/resources/pricing-playbook")

    assert resp.status_code == 200


def test_unrelated_role_cannot_view_pricing_playbook(db_session, client):
    user = _make_user(db_session, "lo-playbook@example.com", "loan_officer")
    login_as(client, user)

    resp = client.get("/resources/pricing-playbook", follow_redirects=False)

    assert resp.status_code == 302
    assert "/resources" not in resp.headers.get("Location", "")


def test_sales_resources_page_links_to_pricing_playbook(db_session, client):
    user = _make_user(db_session, "ae-playbook5@example.com", "account_executive")
    login_as(client, user)

    resp = client.get("/resources/")

    assert resp.status_code == 200
    assert "/resources/pricing-playbook" in resp.get_data(as_text=True)
