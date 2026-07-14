"""Regression tests: processor and underwriter are assignable roles on
the Executive Dashboard's System Users page (/system/users).

Before this fix, _ASSIGNABLE_ROLES (and the matching inline role list
in system/users.html's per-user "change role" dropdown) didn't include
processor or underwriter, even though both are ordinary supported
roles everywhere else in the app.
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


def _make_target_user(db_session, email="target@example.com", role="investor"):
    company = Company(name=f"Co {email}", is_active=True)
    db_session.add(company)
    db_session.commit()
    user = User(email=email, role=role, is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user


def test_system_users_page_offers_processor_and_underwriter(db_session, client):
    exec_user = _make_executive(db_session)
    login_as(client, exec_user)

    resp = client.get("/system/users")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Processor" in body
    assert "Underwriter" in body


def test_change_role_accepts_processor(db_session, client, app):
    exec_user = _make_executive(db_session, email="exec2@ravlohq.com")
    target = _make_target_user(db_session, email="future-processor@example.com")
    login_as(client, exec_user)
    app.config["WTF_CSRF_ENABLED"] = False

    resp = client.post(f"/system/change_role/{target.id}", data={"role": "processor"}, follow_redirects=False)

    assert resp.status_code == 302
    assert User.query.get(target.id).role == "processor"


def test_change_role_accepts_underwriter(db_session, client, app):
    exec_user = _make_executive(db_session, email="exec3@ravlohq.com")
    target = _make_target_user(db_session, email="future-underwriter@example.com")
    login_as(client, exec_user)
    app.config["WTF_CSRF_ENABLED"] = False

    resp = client.post(f"/system/change_role/{target.id}", data={"role": "underwriter"}, follow_redirects=False)

    assert resp.status_code == 302
    assert User.query.get(target.id).role == "underwriter"
