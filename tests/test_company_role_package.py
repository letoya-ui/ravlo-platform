"""Regression tests for Company.enabled_roles -- the per-company Lending OS
role package.

Built for a new partner who wants only loan_officer/admin/processor/borrower
(no underwriter) on their workspace, with their processors handling
underwriting themselves. Every existing company has `enabled_roles` unset,
which must keep behaving exactly like today (every role available) --
only a company explicitly put on a restricted package should ever see a
narrowed invite list.
"""
from LoanMVP.extensions import db
from LoanMVP.models.admin import ALL_COMPANY_ROLES, Company
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_company(db_session, name="Role Package Co", **kwargs):
    company = Company(name=name, is_active=True, subscription_tier="team", max_users=25, **kwargs)
    db_session.add(company)
    db_session.commit()
    return company


def _make_user(db_session, company, email, role):
    user = User(email=email, role=role, is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user


# ── Company model helpers ──

def test_unset_enabled_roles_means_every_role_available(db_session):
    company = _make_company(db_session)
    assert company.enabled_roles is None
    assert company.get_enabled_roles() == set(ALL_COMPANY_ROLES)
    assert company.has_role_enabled("underwriter") is True


def test_restricted_enabled_roles_narrows_the_set(db_session):
    company = _make_company(
        db_session, name="No-UW Co",
        enabled_roles=["admin", "loan_officer", "processor", "borrower"],
    )
    assert company.has_role_enabled("underwriter") is False
    assert company.has_role_enabled("processor") is True
    assert company.get_enabled_roles() == {"admin", "loan_officer", "processor", "borrower"}


# ── invite_team_member() ──

def test_invite_page_only_lists_enabled_roles(db_session, client):
    company = _make_company(
        db_session, name="No-UW Invite Co",
        enabled_roles=["admin", "loan_officer", "processor", "borrower"],
    )
    admin_user = _make_user(db_session, company, "admin@noUW.example.com", "admin")
    login_as(client, admin_user)

    body = client.get(f"/admin/company/{company.id}/team/invite").get_data(as_text=True)

    assert '"loan_officer"' in body or "loan_officer" in body
    assert "Underwriter" not in body


def test_invite_rejects_disabled_role(db_session, client):
    company = _make_company(
        db_session, name="No-UW Reject Co",
        enabled_roles=["admin", "loan_officer", "processor", "borrower"],
    )
    admin_user = _make_user(db_session, company, "admin2@noUW.example.com", "admin")
    login_as(client, admin_user)

    resp = client.post(
        f"/admin/company/{company.id}/team/invite",
        data={"email": "newuw@example.com", "role": "underwriter"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "Invalid role selected" in resp.get_data(as_text=True)
    from LoanMVP.models.admin import UserInvite
    assert UserInvite.query.filter_by(email="newuw@example.com").first() is None


def test_invite_allows_enabled_role(db_session, client):
    company = _make_company(
        db_session, name="No-UW Allow Co",
        enabled_roles=["admin", "loan_officer", "processor", "borrower"],
    )
    admin_user = _make_user(db_session, company, "admin3@noUW.example.com", "admin")
    login_as(client, admin_user)

    resp = client.post(
        f"/admin/company/{company.id}/team/invite",
        data={"email": "newproc@example.com", "role": "processor"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    from LoanMVP.models.admin import UserInvite
    assert UserInvite.query.filter_by(email="newproc@example.com").first() is not None


# ── company_settings() roles_package action ──

def test_company_admin_cannot_change_role_package(db_session, client):
    company = _make_company(db_session, name="Self-Serve Co")
    admin_user = _make_user(db_session, company, "selfserve@example.com", "admin")
    login_as(client, admin_user)

    resp = client.post(
        f"/admin/company/{company.id}/settings",
        data={"action_type": "roles_package", "enabled_roles": ["admin", "borrower"]},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "Only Ravlo staff" in resp.get_data(as_text=True)
    company = Company.query.get(company.id)
    assert company.enabled_roles is None


def test_platform_admin_can_restrict_role_package(db_session, client):
    company = _make_company(db_session, name="Platform-Set Co")
    platform_user = _make_user(db_session, company, "platform@example.com", "platform_admin")
    login_as(client, platform_user)

    resp = client.post(
        f"/admin/company/{company.id}/settings",
        data={
            "action_type": "roles_package",
            "enabled_roles": ["admin", "loan_officer", "processor", "borrower"],
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200
    company = Company.query.get(company.id)
    assert company.enabled_roles == ["admin", "borrower", "loan_officer", "processor"]
    assert company.has_role_enabled("underwriter") is False


def test_platform_admin_can_reset_role_package(db_session, client):
    company = _make_company(
        db_session, name="Reset Co",
        enabled_roles=["admin", "borrower"],
    )
    platform_user = _make_user(db_session, company, "platform2@example.com", "platform_admin")
    login_as(client, platform_user)

    resp = client.post(
        f"/admin/company/{company.id}/settings",
        data={"action_type": "roles_package_reset"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    company = Company.query.get(company.id)
    assert company.enabled_roles is None
    assert company.has_role_enabled("underwriter") is True


def test_roles_package_rejects_empty_selection(db_session, client):
    company = _make_company(db_session, name="Empty Selection Co")
    platform_user = _make_user(db_session, company, "platform3@example.com", "platform_admin")
    login_as(client, platform_user)

    resp = client.post(
        f"/admin/company/{company.id}/settings",
        data={"action_type": "roles_package"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "Select at least one role" in resp.get_data(as_text=True)
    company = Company.query.get(company.id)
    assert company.enabled_roles is None
