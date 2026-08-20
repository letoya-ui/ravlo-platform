"""A CSRF failure almost always just means a form sat open long enough for
the session to time out (PERMANENT_SESSION_LIFETIME is 30 minutes) -- not a
real error. app.handle_csrf_error() used to only handle this gracefully for
the auth blueprint; every other authenticated form (e.g. VIP onboarding)
got a confusing, 500-styled page with a 400 status instead. See
LoanMVP.app.handle_csrf_error.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_executive(db_session, email="csrf-exec@ravlohq.com"):
    company = Company.query.filter_by(name="Ravlo").first()
    if not company:
        company = Company(name="Ravlo", is_active=True)
        db_session.add(company)
        db_session.commit()
    user = User(email=email, role="executive", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user


def _make_target_user(db_session, email="csrf-target@example.com"):
    company = Company(name=f"Co {email}", is_active=True)
    db_session.add(company)
    db_session.commit()
    user = User(email=email, role="partner", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user


def test_csrf_failure_on_a_non_auth_form_redirects_instead_of_500ing(db_session, client, app):
    exec_user = _make_executive(db_session)
    target = _make_target_user(db_session)
    login_as(client, exec_user)
    app.config["WTF_CSRF_ENABLED"] = True
    try:
        resp = client.post(
            f"/system/reset_password/{target.id}",
            data={"password": "Temppass123"},  # no csrf_token -- simulates a stale/expired session
            headers={"Referer": "http://localhost/system/users"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert resp.headers["Location"] == "http://localhost/system/users"

        refreshed = User.query.get(target.id)
        assert not refreshed.check_password("Temppass123")  # request was rejected, not applied

        with client.session_transaction() as sess:
            flashes = sess.get("_flashes", [])
        assert any("session timed out" in msg.lower() for _cat, msg in flashes)
    finally:
        app.config["WTF_CSRF_ENABLED"] = False


def test_csrf_failure_with_no_referrer_falls_back_to_login(db_session, client, app):
    exec_user = _make_executive(db_session, email="csrf-exec2@ravlohq.com")
    target = _make_target_user(db_session, email="csrf-target2@example.com")
    login_as(client, exec_user)
    app.config["WTF_CSRF_ENABLED"] = True
    try:
        resp = client.post(
            f"/system/reset_password/{target.id}",
            data={"password": "Temppass123"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/auth/login")
    finally:
        app.config["WTF_CSRF_ENABLED"] = False


def test_csrf_failure_ignores_an_off_site_referrer(db_session, client, app):
    exec_user = _make_executive(db_session, email="csrf-exec3@ravlohq.com")
    target = _make_target_user(db_session, email="csrf-target3@example.com")
    login_as(client, exec_user)
    app.config["WTF_CSRF_ENABLED"] = True
    try:
        resp = client.post(
            f"/system/reset_password/{target.id}",
            data={"password": "Temppass123"},
            headers={"Referer": "http://evil.example.com/phish"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/auth/login")
    finally:
        app.config["WTF_CSRF_ENABLED"] = False
