"""Regression tests for the Demo Login "view as" feature.

Covers: the staff allowlist gate, idempotent demo-environment creation,
switching into a demo role and landing on that role's dashboard,
switching directly between demo roles without exiting first, exit
restoring the original staff account, and rejection of non-allowlisted
users.
"""
import pytest

from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User
from LoanMVP.services.demo_environment_service import (
    DEMO_COMPANY_NAME,
    DEMO_ROLE_EMAILS,
    ensure_demo_environment,
)

from tests.conftest import login_as


def _make_staff(db_session, email, role="executive"):
    company = Company.query.filter_by(name="Staff Co").first()
    if not company:
        company = Company(name="Staff Co", is_active=True)
        db_session.add(company)
        db_session.commit()
    user = User(email=email, role=role, company_id=company.id, is_active=True)
    db_session.add(user)
    db_session.commit()
    return user


# ---------------------------------------------------------------------------
# Allowlist gate
# ---------------------------------------------------------------------------

def test_non_allowlisted_user_cannot_demo_login(db_session, client):
    outsider = _make_staff(db_session, "some-admin@ravlohq.com")
    login_as(client, outsider)

    resp = client.post("/admin/demo-login/investor", follow_redirects=False)

    assert resp.status_code == 302
    assert "/admin/demo-center" in resp.headers["Location"]
    # Never switched identity.
    with client.session_transaction() as sess:
        assert sess.get("_user_id") == str(outsider.id)
        assert not sess.get("is_demo_mode")


@pytest.mark.parametrize("email", [
    "letoya@ravlohq.com",
    "jamaine.caughman@ravlohq.com",
    "sandra@ravlohq.com",
    "aishagelahun@gmail.com",
])
def test_allowlisted_staff_can_demo_login(db_session, client, email):
    staff = _make_staff(db_session, email)
    login_as(client, staff)

    resp = client.post("/admin/demo-login/investor", follow_redirects=False)

    assert resp.status_code == 302
    assert "/investor" in resp.headers["Location"] or "dashboard" in resp.headers["Location"]
    with client.session_transaction() as sess:
        assert sess.get("is_demo_mode") is True
        assert sess.get("demo_role") == "investor"
        assert sess.get("demo_admin_user_id") == staff.id


# ---------------------------------------------------------------------------
# Idempotent seeding
# ---------------------------------------------------------------------------

def test_ensure_demo_environment_is_idempotent(db_session):
    first = ensure_demo_environment()
    second = ensure_demo_environment()

    assert Company.query.filter_by(name=DEMO_COMPANY_NAME).count() == 1
    for role, user in first.items():
        assert second[role].id == user.id

    for role, email in DEMO_ROLE_EMAILS.items():
        assert User.query.filter_by(email=email).count() == 1


def test_ensure_demo_environment_returns_all_roles(db_session):
    demo_users = ensure_demo_environment()

    expected_roles = {
        "admin", "investor", "loan_officer", "processor",
        "underwriter", "borrower", "partner",
    }
    assert set(demo_users.keys()) == expected_roles
    for role, user in demo_users.items():
        assert user.role == role
        assert user.id is not None


# ---------------------------------------------------------------------------
# Role switching + landing dashboard
# ---------------------------------------------------------------------------

def test_demo_login_lands_on_role_dashboard(db_session, client):
    staff = _make_staff(db_session, "letoya@ravlohq.com")
    login_as(client, staff)

    resp = client.post("/admin/demo-login/loan_officer", follow_redirects=False)

    assert resp.status_code == 302
    assert "loan-officer" in resp.headers["Location"] or "loan_officer" in resp.headers["Location"]

    demo_lo = User.query.filter_by(email=DEMO_ROLE_EMAILS["loan_officer"]).first()
    with client.session_transaction() as sess:
        assert sess.get("_user_id") == str(demo_lo.id)


def test_demo_login_switches_role_without_exiting(db_session, client):
    staff = _make_staff(db_session, "sandra@ravlohq.com")
    login_as(client, staff)

    client.post("/admin/demo-login/investor", follow_redirects=False)
    with client.session_transaction() as sess:
        assert sess.get("demo_role") == "investor"
        original_return_id = sess.get("demo_admin_user_id")

    resp = client.post("/admin/demo-login/processor", follow_redirects=False)
    assert resp.status_code == 302

    with client.session_transaction() as sess:
        assert sess.get("demo_role") == "processor"
        # The stashed "return to me" account must still be the real staff
        # member, not the investor demo account we were just impersonating.
        assert sess.get("demo_admin_user_id") == original_return_id == staff.id

    demo_proc = User.query.filter_by(email=DEMO_ROLE_EMAILS["processor"]).first()
    with client.session_transaction() as sess:
        assert sess.get("_user_id") == str(demo_proc.id)


def test_demo_login_rejects_unknown_role(db_session, client):
    staff = _make_staff(db_session, "letoya@ravlohq.com")
    login_as(client, staff)

    resp = client.post("/admin/demo-login/not-a-real-role", follow_redirects=False)

    assert resp.status_code == 302
    assert "/admin/demo-center" in resp.headers["Location"]
    with client.session_transaction() as sess:
        assert not sess.get("is_demo_mode")


# ---------------------------------------------------------------------------
# Exit restores the original account
# ---------------------------------------------------------------------------

def test_demo_exit_restores_original_staff_account(db_session, client):
    staff = _make_staff(db_session, "jamaine.caughman@ravlohq.com")
    login_as(client, staff)

    client.post("/admin/demo-login/underwriter", follow_redirects=False)
    with client.session_transaction() as sess:
        assert sess.get("is_demo_mode") is True

    resp = client.post("/admin/demo-exit", follow_redirects=False)

    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert sess.get("_user_id") == str(staff.id)
        assert not sess.get("is_demo_mode")
        assert not sess.get("demo_role")
        assert not sess.get("demo_admin_user_id")


def test_demo_exit_when_not_in_demo_mode_is_a_noop(db_session, client):
    staff = _make_staff(db_session, "letoya@ravlohq.com")
    login_as(client, staff)

    resp = client.post("/admin/demo-exit", follow_redirects=False)

    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert sess.get("_user_id") == str(staff.id)


# ---------------------------------------------------------------------------
# Demo Center is Ravlo-staff only, not a customer company admin's page
# ---------------------------------------------------------------------------

def test_company_admin_cannot_view_demo_center(db_session, client):
    company_admin = _make_staff(db_session, "admin@customerco.com", role="admin")
    login_as(client, company_admin)

    resp = client.get("/admin/demo-center", follow_redirects=False)

    assert resp.status_code == 302
    assert "/admin/dashboard" in resp.headers["Location"]


@pytest.mark.parametrize("role", ["master_admin", "platform_admin", "lending_admin", "executive"])
def test_ravlo_staff_role_can_view_demo_center(db_session, client, role):
    staff = _make_staff(db_session, f"{role}@ravlohq.com", role=role)
    login_as(client, staff)

    resp = client.get("/admin/demo-center", follow_redirects=False)

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Guided AE sales walkthrough: the opening talk track, a per-role "Demo
# Guide" panel, and the closing script, so every AE runs the same demo
# instead of improvising a pitch.
# ---------------------------------------------------------------------------

def test_demo_center_shows_opening_and_closing_talk_track(db_session, client):
    staff = _make_staff(db_session, "opening-guide@ravlohq.com", role="executive")
    login_as(client, staff)

    resp = client.get("/admin/demo-center")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "BEFORE OPENING A DASHBOARD" in body
    assert "Can you tell me a little about how your team currently moves a file" in body
    assert "THE CLOSE" in body
    assert "which part of the operation would you want us to solve first" in body


def test_demo_center_shows_per_role_demo_guide(db_session, client):
    staff = _make_staff(db_session, "role-guide@ravlohq.com", role="executive")
    login_as(client, staff)

    resp = client.get("/admin/demo-center")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Demo Guide" in body
    # Loan officer talking point
    assert "The loan officer stays focused on originating" in body
    # Processor talking point
    assert "Processing sees the work that needs to move" in body
    # Underwriter talking point
    assert "the responsibility of the person using it" in body
    # Company admin talking point
    assert "creating an operating environment for your lending company" in body


def test_demo_dashboard_cards_are_ordered_by_workflow_narrative():
    from LoanMVP.routes.admin import _demo_dashboard_cards

    role_order = [card["role_key"] for card in _demo_dashboard_cards()]

    assert role_order == [
        "loan_officer",
        "processor",
        "underwriter",
        "borrower",
        "admin",
        "partner",
        "investor",
    ]


# ---------------------------------------------------------------------------
# Self-healing: a pre-existing row at a demo email (from earlier ad-hoc
# testing, a manual role change via System Users, etc.) must not stay stuck
# with the wrong role forever -- role_required() rejects a mismatched role
# and bounces the demo-login attempt straight to auth.login, which is
# exactly what made "Log in as Processor"/"Log in as Underwriter" silently
# fail in production while other roles kept working.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("role", ["processor", "underwriter"])
def test_demo_login_self_heals_a_stale_role_on_the_demo_account(db_session, client, role):
    from LoanMVP.models.admin import Company
    from LoanMVP.services.demo_environment_service import DEMO_ROLE_EMAILS

    # Simulate a demo account that already exists with the wrong role,
    # exactly like a pre-existing row would in production.
    stray_company = Company(name="Some Other Co", is_active=True)
    db_session.add(stray_company)
    db_session.commit()
    stray_user = User(
        email=DEMO_ROLE_EMAILS[role],
        role="borrower",
        company_id=stray_company.id,
        is_active=True,
    )
    db_session.add(stray_user)
    db_session.commit()

    staff = _make_staff(db_session, "letoya@ravlohq.com")
    login_as(client, staff)

    login_resp = client.post(f"/admin/demo-login/{role}", follow_redirects=False)
    assert login_resp.status_code == 302
    assert login_resp.headers["Location"] != "/auth/login"

    dashboard_resp = client.get(login_resp.headers["Location"], follow_redirects=False)

    assert dashboard_resp.status_code == 200
    healed = User.query.filter_by(email=DEMO_ROLE_EMAILS[role]).first()
    assert healed.role == role
    assert healed.company_id != stray_company.id
