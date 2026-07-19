"""Regression tests for the Ravlo Pricing Playbook encoded into the
Account Executive deal tool: the AE calculates a quote from the standard/
enterprise rate card (LoanMVP/services/ae_pricing.py) instead of typing
numbers from memory, and the resulting discount/deal-type flags decide
whether an AE can sign it immediately or whether Sales Manager / Executive
approval is required first.
"""
from decimal import Decimal

from flask import g

from LoanMVP.models.admin import BusinessInquiry, Company
from LoanMVP.models.user_model import User
from LoanMVP.extensions import db
from LoanMVP.services import ae_pricing

from tests.conftest import login_as


def _switch_to(client, user):
    """login_as() plus clearing Flask-Login's per-app-context user cache.

    The test fixtures push a single app context for the whole test
    (see tests/conftest.py), so flask_login's current_user (cached on
    `g` on first access) would otherwise keep resolving to whichever
    user was first loaded in this test even after the session cookie
    changes -- this mirrors login_as() but also drops that cache so a
    mid-test identity switch (AE -> Executive -> AE) actually takes
    effect on the next request.
    """
    login_as(client, user)
    g.pop("_login_user", None)


def _make_ae(db_session, email="ae@ravlohq.com"):
    company = Company.query.filter_by(name="Ravlo").first()
    if not company:
        company = Company(name="Ravlo", is_active=True)
        db_session.add(company)
        db_session.commit()
    user = User(email=email, role="account_executive", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user


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


def _make_deal(db_session, assigned_ae_id, company_name="Prospect Lending Co"):
    deal = BusinessInquiry(
        inquiry_type="license_application",
        company_name=company_name,
        contact_name="Pat Prospect",
        email="pat@prospectlending.com",
        status="new",
        assigned_ae_id=assigned_ae_id,
        ae_stage="prospect",
    )
    db_session.add(deal)
    db_session.commit()
    return deal


def _build_quote(client, deal_id, **fields):
    form = {"action_type": "build_quote"}
    form.update(fields)
    return client.post(f"/account-executive/deals/{deal_id}", data=form, follow_redirects=True)


# ----------------------------------------------------------------
#   ae_pricing.py -- pure rate-card / approval-rule unit tests
# ----------------------------------------------------------------

def test_standard_partner_plan_prices_match_the_playbook():
    assert ae_pricing.STANDARD_PARTNER_PLANS["solo"]["setup"] == Decimal("499")
    assert ae_pricing.STANDARD_PARTNER_PLANS["solo"]["monthly"] == Decimal("149")
    assert ae_pricing.STANDARD_PARTNER_PLANS["business"]["setup"] == Decimal("2500")
    assert ae_pricing.STANDARD_LENDING_PLANS["regional"]["monthly"] == Decimal("1499")


def test_enterprise_tier_lookup_by_user_count():
    assert ae_pricing.enterprise_tier_for_user_count(10)["setup"] == Decimal("5000")
    assert ae_pricing.enterprise_tier_for_user_count(50)["setup"] == Decimal("10000")
    assert ae_pricing.enterprise_tier_for_user_count(300)["monthly"] == Decimal("7500")
    assert ae_pricing.enterprise_tier_for_user_count(301) is None


def test_compute_quote_applies_discount_and_setup_waiver():
    setup, monthly = ae_pricing.compute_quote(Decimal("1499"), Decimal("399"), discount_percent=10, setup_fee_waived=200)
    assert setup == Decimal("1299.00")
    assert monthly == Decimal("359.10")


def test_ae_can_self_approve_within_authority():
    level = ae_pricing.required_approval_level(discount_percent=10, setup_fee_waived=500)
    assert level == "ae"


def test_discount_above_ae_authority_requires_sales_manager():
    level = ae_pricing.required_approval_level(discount_percent=15)
    assert level == "sales_manager"


def test_setup_waiver_above_ae_authority_requires_sales_manager():
    level = ae_pricing.required_approval_level(discount_percent=0, setup_fee_waived=501)
    assert level == "sales_manager"


def test_discount_over_20_percent_requires_executive():
    level = ae_pricing.required_approval_level(discount_percent=25)
    assert level == "executive"


def test_enterprise_deal_always_requires_executive():
    level = ae_pricing.required_approval_level(is_enterprise=True, discount_percent=0)
    assert level == "executive"


def test_white_label_always_requires_executive():
    level = ae_pricing.required_approval_level(is_white_label=True, discount_percent=0)
    assert level == "executive"


def test_multi_year_always_requires_executive():
    level = ae_pricing.required_approval_level(is_multi_year=True, discount_percent=0)
    assert level == "executive"


# ----------------------------------------------------------------
#   Wired into the deal tool
# ----------------------------------------------------------------

def test_building_a_quote_within_ae_authority_needs_no_approval(db_session, client):
    ae = _make_ae(db_session)
    deal = _make_deal(db_session, assigned_ae_id=ae.id)
    login_as(client, ae)

    resp = _build_quote(client, deal.id, pricing_plan="professional", discount_percent="5", setup_fee_waived="0")

    assert resp.status_code == 200
    refreshed = db.session.get(BusinessInquiry, deal.id)
    assert refreshed.approval_level_required == "ae"
    assert refreshed.approval_status == "not_required"
    assert refreshed.list_setup_fee == Decimal("1499.00")
    assert refreshed.contract_value == Decimal("1499.00") + Decimal("379.05") * 12


def test_building_an_over_authority_quote_requires_approval_and_blocks_signing(db_session, client):
    ae = _make_ae(db_session)
    deal = _make_deal(db_session, assigned_ae_id=ae.id)
    login_as(client, ae)

    _build_quote(client, deal.id, pricing_plan="business", discount_percent="30", setup_fee_waived="0")
    refreshed = db.session.get(BusinessInquiry, deal.id)
    assert refreshed.approval_level_required == "executive"
    assert refreshed.approval_status == "pending"

    resp = client.post(
        f"/account-executive/deals/{deal.id}",
        data={
            "action_type": "update_stage",
            "ae_stage": "signed",
            "contract_value": "10000",
            "commission_rate": "0.10",
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "requires Executive approval" in resp.get_data(as_text=True)
    still_pending = db.session.get(BusinessInquiry, deal.id)
    assert still_pending.ae_stage != "signed"


def test_enterprise_quote_requires_executive_approval(db_session, client):
    ae = _make_ae(db_session)
    deal = _make_deal(db_session, assigned_ae_id=ae.id)
    login_as(client, ae)

    _build_quote(client, deal.id, pricing_plan="enterprise", enterprise_user_count="50", discount_percent="0")

    refreshed = db.session.get(BusinessInquiry, deal.id)
    assert refreshed.approval_level_required == "executive"
    assert refreshed.approval_status == "pending"
    assert refreshed.list_setup_fee == Decimal("10000")


def test_ae_cannot_approve_their_own_quote(db_session, client):
    ae = _make_ae(db_session)
    deal = _make_deal(db_session, assigned_ae_id=ae.id)
    login_as(client, ae)

    _build_quote(client, deal.id, pricing_plan="business", discount_percent="30")

    resp = client.post(
        f"/account-executive/deals/{deal.id}",
        data={"action_type": "approve_quote"},
        follow_redirects=True,
    )

    assert "Only Ravlo staff can approve" in resp.get_data(as_text=True)
    refreshed = db.session.get(BusinessInquiry, deal.id)
    assert refreshed.approval_status == "pending"


def test_executive_can_approve_and_then_ae_can_sign(db_session, client):
    ae = _make_ae(db_session)
    executive = _make_executive(db_session)
    deal = _make_deal(db_session, assigned_ae_id=ae.id)

    _switch_to(client, ae)
    _build_quote(client, deal.id, pricing_plan="business", discount_percent="30")

    _switch_to(client, executive)
    approve_resp = client.post(
        f"/account-executive/deals/{deal.id}",
        data={"action_type": "approve_quote"},
        follow_redirects=True,
    )
    assert approve_resp.status_code == 200
    refreshed = db.session.get(BusinessInquiry, deal.id)
    assert refreshed.approval_status == "approved"
    assert refreshed.approved_by_id == executive.id

    _switch_to(client, ae)
    sign_resp = client.post(
        f"/account-executive/deals/{deal.id}",
        data={
            "action_type": "update_stage",
            "ae_stage": "signed",
            "signed_setup_fee": "2500",
            "signed_monthly_fee": "489.30",
            "setup_commission_rate": "0.15",
            "monthly_commission_rate": "0.08",
        },
        follow_redirects=True,
    )
    assert sign_resp.status_code == 200
    signed = db.session.get(BusinessInquiry, deal.id)
    assert signed.ae_stage == "signed"


def test_300_plus_users_has_no_enterprise_rate_card_lookup(db_session, client):
    ae = _make_ae(db_session)
    deal = _make_deal(db_session, assigned_ae_id=ae.id)
    login_as(client, ae)

    resp = _build_quote(client, deal.id, pricing_plan="enterprise", enterprise_user_count="500")

    assert resp.status_code == 200
    assert "Executive Quote" in resp.get_data(as_text=True)
    refreshed = db.session.get(BusinessInquiry, deal.id)
    assert refreshed.pricing_plan is None
