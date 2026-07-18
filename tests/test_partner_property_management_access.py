"""Regression tests for extending /property access to VIP partners whose
business includes property management (e.g. Keyona Hall's Key Signature
Enterprise -- real estate, property management, and insurance).

Three separate gaps this closes:
1. role_required("investor", "property", "lending_admin") had no way for
   a partner account to pass -- /property was entirely investor/staff-only.
2. _current_investor_profile() only ever looked up an existing
   InvestorProfile; a partner has none, so even once let in, their
   dashboard/list queries would resolve to an empty result set
   (_owned_properties_query() returns Property.query.filter(db.false())
   when there's no profile), and creating a property would silently
   orphan it (owner_investor_id=None).
2. auth.py's post_login_redirect() only ran _ensure_partner_dashboard_profile
   (which applies _PARTNER_DASHBOARD_PRESETS -- category/type/etc.) when
   role == "partner" exactly. An account created with role="realtor"
   directly (a distinct, valid role in PARTNER_ROLES) never got its Partner
   row populated from the preset, so category/type stayed blank and
   _default_vip_role_for_partner() could never resolve anything beyond the
   generic fallback.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.crm_models import Partner
from LoanMVP.models.investor_models import InvestorProfile
from LoanMVP.models.property import Property
from LoanMVP.models.user_model import User
from LoanMVP.routes.auth import _PARTNER_DASHBOARD_PRESETS
from LoanMVP.utils.decorators import partner_offers_property_management

from tests.conftest import login_as


def _make_company(db_session, name="PM Partner Co"):
    company = Company.query.filter_by(name=name).first()
    if not company:
        company = Company(name=name, is_active=True)
        db_session.add(company)
        db_session.commit()
    return company


def _make_pm_partner(db_session, email="keyonahall@icloud.com"):
    company = _make_company(db_session)
    user = User(email=email, role="partner", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    partner = Partner(
        user_id=user.id,
        name="Keyona Hall",
        category="insurance",
        type="Real Estate, Property Management & Insurance",
    )
    db_session.add(partner)
    db_session.commit()
    return user, partner


def _make_plain_realtor(db_session, email="plainrealtor@example.com"):
    company = _make_company(db_session, name="Plain Realtor Co")
    user = User(email=email, role="partner", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    partner = Partner(user_id=user.id, name="Plain Realtor", category="realtor", type="Realtor")
    db_session.add(partner)
    db_session.commit()
    return user, partner


def test_partner_offers_property_management_detects_the_business_line(db_session):
    user, _ = _make_pm_partner(db_session)
    assert partner_offers_property_management(user) is True


def test_partner_offers_property_management_false_for_plain_realtor(db_session):
    user, _ = _make_plain_realtor(db_session)
    assert partner_offers_property_management(user) is False


def test_pm_partner_can_reach_property_dashboard(db_session, client):
    user, _ = _make_pm_partner(db_session)
    login_as(client, user)

    resp = client.get("/property/dashboard")

    assert resp.status_code == 200


def test_plain_partner_is_blocked_from_property_dashboard(db_session, client):
    user, _ = _make_plain_realtor(db_session)
    login_as(client, user)

    resp = client.get("/property/dashboard", follow_redirects=False)

    assert resp.status_code == 302


def test_pm_partner_gets_a_scoping_investor_profile_and_sees_own_properties(db_session, client, app):
    user, _ = _make_pm_partner(db_session)
    login_as(client, user)
    app.config["WTF_CSRF_ENABLED"] = False

    resp = client.post(
        "/property/new",
        data={"address": "42 Rental Row", "city": "Nashville", "state": "TN"},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    profile = InvestorProfile.query.filter_by(user_id=user.id).first()
    assert profile is not None

    prop = Property.query.filter_by(address="42 Rental Row").first()
    assert prop is not None
    assert prop.owner_investor_id == profile.id

    dashboard_resp = client.get("/property/dashboard")
    assert dashboard_resp.status_code == 200
    assert "42 Rental Row" in dashboard_resp.get_data(as_text=True)


def test_post_login_redirect_heals_partner_row_even_when_role_is_realtor(db_session, client):
    """Reproduces the exact scenario reported: an account created with
    role="realtor" (not the generic "partner") never got _PARTNER_DASHBOARD_PRESETS
    applied, so Keyona's real category/type never landed on her Partner row."""
    company = _make_company(db_session, name="Realtor Role Co")
    user = User(email="keyonahall@icloud.com", role="realtor", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    assert Partner.query.filter_by(user_id=user.id).first() is None

    login_as(client, user)
    client.get("/auth/post-login-redirect")

    partner = Partner.query.filter_by(user_id=user.id).first()
    assert partner is not None
    preset = _PARTNER_DASHBOARD_PRESETS["keyonahall@icloud.com"]
    assert partner.category == preset["category"]
    assert partner.type == preset["type"]
