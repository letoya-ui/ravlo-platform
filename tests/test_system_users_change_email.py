"""Regression tests for system.change_email: lets staff correct a user's
email directly from the System Users page.

Migrated/manually-created accounts (e.g. VIP partners imported from an
old system) can end up with the wrong email on file -- which silently
breaks both login and "Forgot Password" (the account is real, but no
email the user actually checks matches it), and there was previously no
way to fix this short of direct database access.
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


def test_change_email_updates_the_users_email(db_session, client, app):
    exec_user = _make_executive(db_session)
    target = _make_target_user(db_session, email="old-migrated-email@example.com")
    login_as(client, exec_user)
    app.config["WTF_CSRF_ENABLED"] = False

    resp = client.post(
        f"/system/change_email/{target.id}",
        data={"email": "keyonahall@icloud.com"},
        follow_redirects=False,
    )

    assert resp.status_code == 302
    assert User.query.get(target.id).email == "keyonahall@icloud.com"


def test_change_email_lowercases_and_strips_input(db_session, client, app):
    exec_user = _make_executive(db_session, email="exec2@ravlohq.com")
    target = _make_target_user(db_session, email="old2@example.com")
    login_as(client, exec_user)
    app.config["WTF_CSRF_ENABLED"] = False

    client.post(
        f"/system/change_email/{target.id}",
        data={"email": "  KeyonaHall@ICloud.com  "},
        follow_redirects=False,
    )

    assert User.query.get(target.id).email == "keyonahall@icloud.com"


def test_change_email_rejects_invalid_email(db_session, client, app):
    exec_user = _make_executive(db_session, email="exec3@ravlohq.com")
    target = _make_target_user(db_session, email="old3@example.com")
    login_as(client, exec_user)
    app.config["WTF_CSRF_ENABLED"] = False

    resp = client.post(
        f"/system/change_email/{target.id}",
        data={"email": "not-an-email"},
        follow_redirects=False,
    )

    assert resp.status_code == 302
    assert User.query.get(target.id).email == "old3@example.com"


def test_change_email_rejects_duplicate_email(db_session, client, app):
    exec_user = _make_executive(db_session, email="exec4@ravlohq.com")
    target = _make_target_user(db_session, email="old4@example.com")
    _make_target_user(db_session, email="taken@example.com")
    login_as(client, exec_user)
    app.config["WTF_CSRF_ENABLED"] = False

    resp = client.post(
        f"/system/change_email/{target.id}",
        data={"email": "taken@example.com"},
        follow_redirects=False,
    )

    assert resp.status_code == 302
    assert User.query.get(target.id).email == "old4@example.com"


def test_users_page_renders_email_edit_form(db_session, client):
    exec_user = _make_executive(db_session, email="exec5@ravlohq.com")
    _make_target_user(db_session, email="vip-partner@example.com")
    login_as(client, exec_user)

    resp = client.get("/system/users")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "system.change_email" in body or "/change_email/" in body
    assert 'id="userSearchInput"' in body
