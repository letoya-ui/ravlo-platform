"""Regression tests for restoring Keyona's VIP insurance+realtor account.

Her Partner profile had gone missing in production. Elena and Jamaine already
had a self-healing mechanism -- _PARTNER_DASHBOARD_PRESETS in auth.py
auto-(re)creates a fully-activated Partner row every time their email logs in
or registers, so their VIP accounts can never be "lost" for good. Keyona
wasn't in that dict, so her account had no such recovery path. Separately,
_default_vip_role_for_partner() special-cased contractor+realtor into the
combined "contractor_realtor" role but had no matching case for
insurance+realtor, so even with a correctly-provisioned Partner, a fresh
VIPProfile for her would default to the plain "insurance" role instead of
the combined dashboard.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.crm_models import Partner
from LoanMVP.models.user_model import User
from LoanMVP.routes.auth import _ensure_partner_dashboard_profile, _PARTNER_DASHBOARD_PRESETS
from LoanMVP.routes.vip import _default_vip_role_for_partner

from tests.conftest import login_as


def test_keyona_has_a_dashboard_preset():
    assert "keyonahall@icloud.com" in _PARTNER_DASHBOARD_PRESETS
    preset = _PARTNER_DASHBOARD_PRESETS["keyonahall@icloud.com"]
    assert preset["active"] is True
    assert preset["approved"] is True
    assert preset["subscription_tier"] == "Premium"


def test_ensure_partner_dashboard_profile_recreates_missing_partner(db_session):
    company = Company(name="Keyona Co", is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()

    user = User(email="keyonahall@icloud.com", role="partner", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    assert Partner.query.filter_by(user_id=user.id).first() is None

    _ensure_partner_dashboard_profile(user)
    db_session.commit()

    partner = Partner.query.filter_by(user_id=user.id).first()
    assert partner is not None
    assert partner.active is True
    assert partner.approved is True
    assert partner.subscription_tier == "Premium"
    assert "insurance" in (partner.category or "").lower()


def test_ensure_partner_dashboard_profile_reactivates_existing_partner(db_session):
    company = Company(name="Keyona Co 2", is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()

    user = User(email="keyonahall@icloud.com", role="partner", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    partner = Partner(
        user_id=user.id,
        name="Keyona Hall",
        active=False,
        approved=False,
        subscription_tier="Free",
    )
    db_session.add(partner)
    db_session.commit()

    _ensure_partner_dashboard_profile(user)
    db_session.commit()

    db_session.refresh(partner)
    assert partner.active is True
    assert partner.approved is True
    assert partner.subscription_tier == "Premium"


def test_default_vip_role_for_dual_insurance_realtor_partner(db_session):
    partner = Partner(name="Keyona Hall", category="insurance", type="Insurance + Realtor")
    db_session.add(partner)
    db_session.commit()

    assert _default_vip_role_for_partner(partner) == "insurance_realtor"


def test_default_vip_role_for_insurance_only_partner_unchanged(db_session):
    partner = Partner(name="Solo Insurance Agent", category="insurance", type="Insurance")
    db_session.add(partner)
    db_session.commit()

    assert _default_vip_role_for_partner(partner) == "insurance"


def test_default_vip_role_for_realtor_only_partner_unchanged(db_session):
    partner = Partner(name="Solo Realtor", category="realtor", type="Realtor")
    db_session.add(partner)
    db_session.commit()

    assert _default_vip_role_for_partner(partner) == "realtor"
