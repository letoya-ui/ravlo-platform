"""Regression tests for "Create Content" on the Lending OS (loan officer)
sidebar.

Content Studio (elena.template_studio) already had a fully-built lending
template set (rate alerts, pre-approval, refinance, etc. -- see
LENDING_TEMPLATES in elena_templates.py) but nothing routed an internal
Lending OS loan officer into it correctly: get_or_create_vip_profile() only
infers the content role from Partner.category, and an internal loan officer
(LoanOfficerProfile holder) has no Partner record, so their auto-created
VIPProfile defaulted to role_type="partner" -> realtor listing templates,
not loan templates. The Back button also pointed at the VIP realtor
dashboard, which a plain internal loan officer can't access (no VIP tier),
so it would have bounced them into an "upgrade to Premium" redirect loop.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.loan_officer_model import LoanOfficerProfile
from LoanMVP.models.user_model import User
from LoanMVP.models.vip_models import VIPProfile
from LoanMVP.services.elena_templates import TemplateType, templates_for_role

from tests.conftest import login_as


def _make_loan_officer(db_session, email="lo@example.com"):
    company = Company(name="Some Lending Co", is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role="loan_officer", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    profile = LoanOfficerProfile(user_id=user.id, name="Lonnie Officer", email=email)
    db_session.add(profile)
    db_session.commit()
    return user


def test_templates_for_role_loan_officer_is_lending_content():
    templates = templates_for_role("loan_officer")

    assert TemplateType.LENDING_RATE_ALERT.value in templates
    assert TemplateType.LENDING_PRE_APPROVAL.value in templates
    assert TemplateType.JUST_LISTED.value not in templates


def test_internal_loan_officer_gets_loan_officer_vip_role(db_session, client):
    user = _make_loan_officer(db_session)
    login_as(client, user)

    resp = client.get("/elena/template-studio")

    assert resp.status_code == 200
    profile = VIPProfile.query.filter_by(user_id=user.id).first()
    assert profile is not None
    assert profile.role_type == "loan_officer"


def test_internal_loan_officer_content_studio_shows_lending_templates(db_session, client):
    user = _make_loan_officer(db_session, email="lo2@example.com")
    login_as(client, user)

    resp = client.get("/elena/template-studio")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert TemplateType.LENDING_RATE_ALERT.value in body


def test_internal_loan_officer_back_button_goes_to_lending_os_dashboard(db_session, client):
    user = _make_loan_officer(db_session, email="lo3@example.com")
    login_as(client, user)

    resp = client.get("/elena/template-studio")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "/loan_officer/dashboard" in body


def test_existing_stuck_partner_profile_self_heals_to_loan_officer(db_session, client):
    """An account created before this fix existed already has a VIPProfile
    stuck on role_type="partner" -- get_or_create_vip_profile() only set
    defaults for brand-new profiles, so it never self-corrected. Confirm it
    now heals on the next visit instead of staying wrong forever."""
    user = _make_loan_officer(db_session, email="lo4@example.com")
    stale_profile = VIPProfile(user_id=user.id, display_name="Lonnie Officer", role_type="partner")
    db_session.add(stale_profile)
    db_session.commit()

    login_as(client, user)
    resp = client.get("/elena/template-studio")

    assert resp.status_code == 200
    profile = VIPProfile.query.filter_by(user_id=user.id).first()
    assert profile.id == stale_profile.id
    assert profile.role_type == "loan_officer"

    body = resp.get_data(as_text=True)
    assert TemplateType.LENDING_RATE_ALERT.value in body


def test_deliberately_chosen_role_type_is_not_overwritten(db_session, client):
    """Self-healing only upgrades the generic "partner" fallback -- it must
    never clobber a role_type the user deliberately picked via
    /vip/onboarding, even if their account role is loan_officer."""
    user = _make_loan_officer(db_session, email="lo5@example.com")
    chosen_profile = VIPProfile(user_id=user.id, display_name="Lonnie Officer", role_type="insurance_realtor")
    db_session.add(chosen_profile)
    db_session.commit()

    login_as(client, user)
    client.get("/elena/template-studio")

    profile = VIPProfile.query.filter_by(user_id=user.id).first()
    assert profile.role_type == "insurance_realtor"
