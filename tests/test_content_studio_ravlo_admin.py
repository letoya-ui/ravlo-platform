"""Regression tests for "advertise Ravlo OS" Content Studio templates.

Company admins (role="admin") had no VIP-role default at all -- like
internal loan officers before them, they have no Partner record, so
_default_vip_role_for_partner(None) fell back to "partner" and Content
Studio showed realtor listing templates. Two different populations use
role="admin" though: a customer lending company's own admin (who should
get loan-marketing templates, same as a loan officer) and Ravlo's own
admin/staff -- identified by staff-level roles or by belonging to Ravlo's
own Company record -- who should get a new, distinct set of templates for
advertising the Ravlo OS platform itself to prospective lending-company
clients.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User
from LoanMVP.models.vip_models import VIPProfile
from LoanMVP.routes.executive_new import _ravlo_company
from LoanMVP.services.elena_templates import TemplateType, templates_for_role

from tests.conftest import login_as


def _make_admin(db_session, company_name="Some Lending Co", email="admin@somelendingco.com"):
    company = Company(name=company_name, is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role="admin", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user, company


def test_templates_for_role_ravlo_admin_is_platform_content():
    templates = templates_for_role("ravlo_admin")

    assert TemplateType.PLATFORM_SALES_PITCH.value in templates
    assert TemplateType.PLATFORM_FEATURE_ANNOUNCEMENT.value in templates
    assert TemplateType.JUST_LISTED.value not in templates
    assert TemplateType.LENDING_RATE_ALERT.value not in templates


def test_ravlo_company_admin_gets_ravlo_admin_vip_role(db_session, client):
    ravlo_company = _ravlo_company()
    db_session.commit()

    user = User(email="ravlo-admin@ravlohq.com", role="admin", is_active=True, company_id=ravlo_company.id)
    db_session.add(user)
    db_session.commit()
    login_as(client, user)

    resp = client.get("/elena/template-studio")

    assert resp.status_code == 200
    profile = VIPProfile.query.filter_by(user_id=user.id).first()
    assert profile is not None
    assert profile.role_type == "ravlo_admin"

    body = resp.get_data(as_text=True)
    assert TemplateType.PLATFORM_SALES_PITCH.value in body


def test_customer_company_admin_gets_loan_officer_vip_role(db_session, client):
    user, _ = _make_admin(db_session)
    login_as(client, user)

    resp = client.get("/elena/template-studio")

    assert resp.status_code == 200
    profile = VIPProfile.query.filter_by(user_id=user.id).first()
    assert profile is not None
    assert profile.role_type == "loan_officer"

    body = resp.get_data(as_text=True)
    assert TemplateType.LENDING_RATE_ALERT.value in body
    assert TemplateType.PLATFORM_SALES_PITCH.value not in body


def test_ravlo_admin_back_button_goes_to_admin_dashboard(db_session, client):
    ravlo_company = _ravlo_company()
    db_session.commit()

    user = User(email="ravlo-admin2@ravlohq.com", role="admin", is_active=True, company_id=ravlo_company.id)
    db_session.add(user)
    db_session.commit()
    login_as(client, user)

    resp = client.get("/elena/template-studio")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "/admin/dashboard" in body
