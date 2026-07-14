"""Regression tests: processor and underwriter are valid roles when
adding/inviting someone directly onto the Ravlo internal team.

Before this fix, RAVLO_STAFF_ROLES (the dropdown used by both
admin.link_staff_member and admin.invite_staff_member on the Ravlo
Staff page) only offered platform_admin/master_admin/admin/
intelligence/account_executive -- there was no way to bring an
in-house processor or underwriter onto Ravlo's own company via that
page, even though those are ordinary, fully-supported roles everywhere
else in the app (e.g. the per-customer-company team invite flow
already listed them).
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User
from LoanMVP.extensions import db

from tests.conftest import login_as


def _make_platform_admin(db_session, email="owner@ravlohq.com"):
    company = Company.query.filter_by(email_domain="ravlohq.com").first()
    if not company:
        company = Company(name="Ravlo HQ", email_domain="ravlohq.com", is_active=True)
        db_session.add(company)
        db_session.commit()

    user = User(email=email, role="platform_admin", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user


def test_processor_and_underwriter_are_offered_on_staff_page(db_session, client):
    admin = _make_platform_admin(db_session)
    login_as(client, admin)

    resp = client.get("/admin/staff")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Processor" in body
    assert "Underwriter" in body


def test_link_staff_member_can_set_existing_user_to_processor(db_session, client, app):
    admin = _make_platform_admin(db_session, email="owner2@ravlohq.com")
    other_company = Company(name="Some Other Co", is_active=True)
    db_session.add(other_company)
    db_session.commit()
    target = User(email="future-processor@example.com", role="investor", is_active=True, company_id=other_company.id)
    db_session.add(target)
    db_session.commit()

    login_as(client, admin)
    app.config["WTF_CSRF_ENABLED"] = False
    resp = client.post(
        "/admin/staff/link",
        data={"email": "future-processor@example.com", "role": "processor"},
        follow_redirects=False,
    )

    assert resp.status_code == 302
    updated = User.query.get(target.id)
    assert updated.role == "processor"
    assert updated.company_id == Company.query.filter_by(email_domain="ravlohq.com").first().id


def test_invite_staff_member_accepts_underwriter_role(db_session, client, app):
    from LoanMVP.models.admin import UserInvite

    admin = _make_platform_admin(db_session, email="owner3@ravlohq.com")
    login_as(client, admin)
    app.config["WTF_CSRF_ENABLED"] = False

    resp = client.post(
        "/admin/staff/invite",
        data={"first_name": "New", "last_name": "Underwriter", "email": "new-uw@example.com", "role": "underwriter"},
        follow_redirects=False,
    )

    assert resp.status_code == 302
    invite = UserInvite.query.filter_by(email="new-uw@example.com").first()
    assert invite is not None
    assert invite.role == "underwriter"
