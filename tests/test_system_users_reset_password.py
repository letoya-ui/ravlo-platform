"""Regression tests for system.reset_password: lets staff set a known
temporary password for an account directly from the System Users page.

Debugging a migrated/VIP account (e.g. Keyona's) often can't wait on
"Forgot Password" actually reaching the user's inbox. This lets staff set
a temporary password directly so they can log in as/verify the account.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_executive(db_session, email="exec@ravlohq.com"):
    company = Company.query.filter_by(name="Ravlo").first()
    if not company:
        company = Company(name="Ravlo", is_active=True)
        db_session.add(company)
        db_session.commit()
    user = User(email=email, role="executive", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user


def _make_target_user(db_session, email="target@example.com", role="partner"):
    company = Company(name=f"Co {email}", is_active=True)
    db_session.add(company)
    db_session.commit()
    user = User(email=email, role=role, is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user


def test_reset_password_sets_a_working_password(db_session, client, app):
    exec_user = _make_executive(db_session)
    target = _make_target_user(db_session, email="keyonahall@icloud.com")
    login_as(client, exec_user)
    app.config["WTF_CSRF_ENABLED"] = False

    resp = client.post(
        f"/system/reset_password/{target.id}",
        data={"password": "Temppass123"},
        follow_redirects=False,
    )

    assert resp.status_code == 302
    refreshed = User.query.get(target.id)
    assert refreshed.check_password("Temppass123")


def test_reset_password_rejects_short_passwords(db_session, client, app):
    exec_user = _make_executive(db_session, email="exec2@ravlohq.com")
    target = _make_target_user(db_session, email="target2@example.com")
    login_as(client, exec_user)
    app.config["WTF_CSRF_ENABLED"] = False

    resp = client.post(
        f"/system/reset_password/{target.id}",
        data={"password": "short"},
        follow_redirects=False,
    )

    assert resp.status_code == 302
    refreshed = User.query.get(target.id)
    assert not refreshed.check_password("short")


def test_users_page_renders_reset_password_button(db_session, client):
    exec_user = _make_executive(db_session, email="exec3@ravlohq.com")
    _make_target_user(db_session, email="vip-partner2@example.com")
    login_as(client, exec_user)

    resp = client.get("/system/users")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "system.reset_password" in body or "/reset_password/" in body
