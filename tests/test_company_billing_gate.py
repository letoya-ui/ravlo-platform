"""Tier-based feature gating regression tests.

Company.is_active/is_blocked/billing_status/grace_period_ends_at were all
wired correctly by the Stripe webhook (see test_company_billing_webhook.py)
but nothing ever read them -- a company past its grace period, explicitly
blocked, or deactivated kept full web and mobile access forever. These tests
cover the fix: a before_request hook holds web access, the mobile JWT
require_auth decorator holds API access, and both exempt the billing pages
themselves (so a company admin can actually pay) and Ravlo staff roles
(who need cross-company access regardless of any one company's billing).
"""
from datetime import datetime, timedelta

from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_company(db_session, **kwargs):
    defaults = dict(name="Gate Test Co", is_active=True, subscription_tier="team", max_users=10)
    defaults.update(kwargs)
    company = Company(**defaults)
    db_session.add(company)
    db_session.commit()
    return company


def _make_user(db_session, company, role="loan_officer", email="loanofficer@example.com"):
    user = User(email=email, role=role, is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user


# ---------------------------------------------------------------------------
# Web (Flask-Login session) enforcement
# ---------------------------------------------------------------------------

def test_blocked_company_user_redirected_to_billing_hold(db_session, client):
    company = _make_company(db_session, is_blocked=True, blocked_reason="non_payment")
    user = _make_user(db_session, company)
    login_as(client, user)

    resp = client.get("/loan_officer/dashboard", follow_redirects=True)

    assert resp.status_code == 200
    assert b"Workspace Access Suspended" in resp.data


def test_healthy_company_user_not_redirected(db_session, client):
    company = _make_company(db_session, billing_status="active")
    user = _make_user(db_session, company)
    login_as(client, user)

    # follow_redirects: /loan_officer/dashboard redirects to onboarding for a
    # user with no LoanOfficerProfile yet (unrelated, pre-existing behavior)
    # -- what matters here is that it never lands on the billing-hold page.
    resp = client.get("/loan_officer/dashboard", follow_redirects=True)

    assert resp.status_code == 200
    assert b"Workspace Access Suspended" not in resp.data


def test_expired_grace_period_lazily_blocks_and_redirects(db_session, client):
    company = _make_company(
        db_session,
        billing_status="past_due",
        grace_period_ends_at=datetime.utcnow() - timedelta(days=1),
        is_blocked=False,
    )
    user = _make_user(db_session, company, email="lo2@example.com")
    login_as(client, user)

    resp = client.get("/loan_officer/dashboard", follow_redirects=True)

    assert resp.status_code == 200
    assert b"Workspace Access Suspended" in resp.data
    db_session.refresh(company)
    assert company.is_blocked is True
    assert company.billing_status == "blocked"


def test_past_due_within_grace_period_not_blocked(db_session, client):
    company = _make_company(
        db_session,
        billing_status="past_due",
        grace_period_ends_at=datetime.utcnow() + timedelta(days=3),
    )
    user = _make_user(db_session, company, email="lo3@example.com")
    login_as(client, user)

    resp = client.get("/loan_officer/dashboard", follow_redirects=True)

    assert resp.status_code == 200
    assert b"Workspace Access Suspended" not in resp.data


def test_blocked_company_admin_can_still_reach_billing_page(db_session, client):
    company = _make_company(db_session, is_blocked=True)
    admin = _make_user(db_session, company, role="admin", email="companyadmin2@example.com")
    login_as(client, admin)

    resp = client.get(f"/admin/company/{company.id}/billing")

    assert resp.status_code == 200


def test_full_ravlo_staff_bypass_billing_hold(db_session, client):
    company = _make_company(db_session, is_blocked=True)
    exec_user = User(email="exec@ravlohq.com", role="executive", is_active=True, company_id=company.id)
    db_session.add(exec_user)
    db_session.commit()
    login_as(client, exec_user)

    # Don't follow redirects -- /admin/dashboard -> /executive/dashboard for
    # execs is an unrelated existing bounce. What matters is that this
    # request is never redirected to the billing-hold page.
    resp = client.get("/admin/dashboard")

    assert resp.headers.get("Location") != "/admin/billing-hold"


# ---------------------------------------------------------------------------
# Mobile (JWT) enforcement
# ---------------------------------------------------------------------------

def test_mobile_blocked_company_gets_402(db_session, client, app):
    from LoanMVP.routes.mobile_api import _encode_token

    company = _make_company(db_session, is_blocked=True, email_domain=None)
    user = _make_user(db_session, company, email="mobile-blocked@example.com")

    with app.app_context():
        token = _encode_token(user.id)

    resp = client.get("/mobile/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 402
    assert resp.get_json()["code"] == "billing_hold"


def test_mobile_healthy_company_succeeds(db_session, client, app):
    from LoanMVP.routes.mobile_api import _encode_token

    company = _make_company(db_session, billing_status="active")
    user = _make_user(db_session, company, email="mobile-healthy@example.com")

    with app.app_context():
        token = _encode_token(user.id)

    resp = client.get("/mobile/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
