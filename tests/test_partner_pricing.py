"""Regression tests for the Ravlo Partner pricing/billing consolidation:
one real Stripe Checkout flow (Solo/Professional/Business, setup fee +
monthly, replacing the old admin-approval placeholder that never actually
charged anyone), plus the new benefits that come with a paid plan --
unlimited self-serve listing landing pages for realtors, an in-app
landing-page request for other business types, and Ravlo Investor Leads
included free (no per-lead charge).
"""
import json

from LoanMVP.extensions import db
from LoanMVP.models.admin import BusinessInquiry
from LoanMVP.models.crm_models import Partner
from LoanMVP.models.elena_models import ElenaClient, ElenaListing
from LoanMVP.models.partner_models import PartnerLeadCharge
from LoanMVP.models.user_model import User
from LoanMVP.models.vip_models import VIPNotification, VIPProfile
from LoanMVP.routes.partners import PARTNER_PLANS, _charge_partner_for_lead

from tests.conftest import login_as


class _StripeObj(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item)


def _make_partner(db_session, email="partner@example.com", subscription_tier=None, is_realtor=False):
    user = User(email=email, role="partner", is_active=True, first_name="Pat", last_name="Partner")
    db_session.add(user)
    db_session.commit()
    partner = Partner(
        user_id=user.id, name="Test Business", subscription_tier=subscription_tier,
        category="Realtor" if is_realtor else "Contractor",
        type="Realtor" if is_realtor else "General Contractor",
    )
    db_session.add(partner)
    db_session.commit()
    return user, partner


def _make_realtor_with_listing(db_session, email="realtor@example.com"):
    user, partner = _make_partner(db_session, email=email, is_realtor=True)
    profile = VIPProfile(
        user_id=user.id, display_name="Test Realtor", business_name="Test Realty",
        role_type="realtor", brand_color="#123456",
    )
    db_session.add(profile)
    db_session.commit()
    listing = ElenaListing(
        address="123 Main St", city="Nashville", state="TN", zip_code="37203",
        beds=3, baths=2, sqft=1800, price=450000, description="Lovely home.",
        vip_profile_id=profile.id,
    )
    db_session.add(listing)
    db_session.commit()
    return user, partner, profile, listing


# ─── Real Stripe checkout ───────────────────────────────────────────────────

def test_checkout_builds_recurring_and_setup_fee_line_items(db_session, client, monkeypatch):
    user, partner = _make_partner(db_session, email="checkout-solo@example.com")
    login_as(client, user)
    client.application.config["STRIPE_BILLING_ENABLED"] = True

    import LoanMVP.routes.partners as partners_module

    captured = {}

    def fake_session_create(**kwargs):
        captured["kwargs"] = kwargs
        return _StripeObj(id="cs_test_1", url="https://checkout.stripe.com/partner-session")

    monkeypatch.setattr(partners_module.stripe.checkout.Session, "create", fake_session_create)

    resp = client.post("/partners/billing/subscribe-checkout/featured", follow_redirects=False)

    assert resp.status_code == 303
    assert resp.headers["Location"] == "https://checkout.stripe.com/partner-session"

    line_items = captured["kwargs"]["line_items"]
    assert len(line_items) == 2
    monthly = line_items[0]["price_data"]
    setup = line_items[1]["price_data"]
    assert monthly["unit_amount"] == PARTNER_PLANS["featured"]["monthly_cents"]
    assert monthly["recurring"] == {"interval": "month"}
    assert setup["unit_amount"] == PARTNER_PLANS["featured"]["setup_cents"]
    assert "recurring" not in setup
    assert captured["kwargs"]["metadata"]["partner_tier"] == "featured"


def test_checkout_rejects_free_tier(db_session, client):
    user, partner = _make_partner(db_session, email="checkout-free@example.com")
    login_as(client, user)
    client.application.config["STRIPE_BILLING_ENABLED"] = True

    resp = client.post("/partners/billing/subscribe-checkout/free", follow_redirects=True)

    assert resp.status_code == 200
    assert "not available for checkout" in resp.get_data(as_text=True)


def test_checkout_blocked_when_stripe_billing_disabled(db_session, client):
    user, partner = _make_partner(db_session, email="checkout-disabled@example.com")
    login_as(client, user)
    client.application.config["STRIPE_BILLING_ENABLED"] = False

    resp = client.post("/partners/billing/subscribe-checkout/premium", follow_redirects=True)

    assert resp.status_code == 200
    assert "not enabled yet" in resp.get_data(as_text=True)


def test_confirm_subscription_free_still_applies_immediately(db_session, client):
    user, partner = _make_partner(db_session, email="free-confirm@example.com", subscription_tier="Premium")
    login_as(client, user)

    resp = client.post("/partners/subscribe/Free/confirm", follow_redirects=True)

    assert resp.status_code == 200
    db_session.refresh(partner)
    assert partner.subscription_tier == "Free"
    assert partner.featured is False


# ─── Billing / Growth Plans pages render canonical pricing ──────────────────

def test_billing_page_shows_setup_and_monthly_price_for_each_tier(db_session, client):
    user, partner = _make_partner(db_session, email="billing-render@example.com")
    login_as(client, user)

    resp = client.get("/partners/billing")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "Solo" in body and "$149" in body and "499" in body
    assert "Professional" in body and "$399" in body and "1,499" in body
    assert "Business" in body and "$699" in body and "2,500" in body


def test_growth_plans_page_shows_same_pricing_and_posts_to_checkout(db_session, client):
    user, partner = _make_partner(db_session, email="growth-render@example.com")
    login_as(client, user)

    resp = client.get("/partners/upgrade")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "$149" in body and "$399" in body and "$699" in body
    assert 'action="/partners/billing/subscribe-checkout/featured"' in body
    assert 'action="/partners/billing/subscribe-checkout/premium"' in body
    assert 'action="/partners/billing/subscribe-checkout/enterprise"' in body


# ─── Free Ravlo Investor Leads on paid plans ────────────────────────────────

def test_paid_partner_lead_charge_is_waived_not_billed(db_session):
    _, partner = _make_partner(db_session, email="paid-lead@example.com", subscription_tier="Featured")

    charge = _charge_partner_for_lead(partner)

    assert charge.status == "waived"
    assert charge.amount == 0


def test_free_partner_lead_charge_attempts_real_charge(db_session, monkeypatch):
    _, partner = _make_partner(db_session, email="free-lead@example.com", subscription_tier="Free")
    partner.lead_price = 40.00
    partner.stripe_customer_id = "cus_test_free"
    partner.stripe_payment_method_id = "pm_test_free"
    db_session.commit()

    import LoanMVP.routes.partners as partners_module

    def fake_intent_create(**kwargs):
        return _StripeObj(id="pi_test_free")

    monkeypatch.setattr(partners_module.stripe.PaymentIntent, "create", fake_intent_create)

    charge = _charge_partner_for_lead(partner)

    assert charge.status == "paid"
    assert charge.amount == 40.00


def test_billing_page_tells_paid_partner_leads_are_included(db_session, client):
    user, partner = _make_partner(db_session, email="paid-leads-copy@example.com", subscription_tier="Premium")
    login_as(client, user)

    resp = client.get("/partners/billing")
    body = resp.get_data(as_text=True)

    assert "included free" in body


# ─── Landing page request (non-realtor business types) ──────────────────────

def test_request_landing_page_creates_inquiry_for_paid_business(db_session, client):
    user, partner = _make_partner(db_session, email="request-page@example.com", subscription_tier="Featured")
    login_as(client, user)

    resp = client.post(
        "/partners/request-landing-page", data={"notes": "Want it navy and gold."}, follow_redirects=True
    )

    assert resp.status_code == 200
    assert "reach out shortly" in resp.get_data(as_text=True)

    inquiry = BusinessInquiry.query.filter_by(email="request-page@example.com").first()
    assert inquiry is not None
    assert inquiry.inquiry_type == "partner_landing_page_request"
    assert inquiry.notes == "Want it navy and gold."


def test_billing_page_shows_request_card_for_paid_non_realtor(db_session, client):
    user, partner = _make_partner(db_session, email="show-request-card@example.com", subscription_tier="Featured")
    login_as(client, user)

    resp = client.get("/partners/billing")
    body = resp.get_data(as_text=True)

    assert "Request My Landing Page" in body


def test_billing_page_hides_request_card_for_free_partner(db_session, client):
    user, partner = _make_partner(db_session, email="hide-request-card@example.com", subscription_tier="Free")
    login_as(client, user)

    resp = client.get("/partners/billing")
    body = resp.get_data(as_text=True)

    assert "Request My Landing Page" not in body


# ─── Unlimited listing landing pages (realtors) ─────────────────────────────

def test_listing_detail_lazily_generates_public_token(db_session, client):
    user, partner, profile, listing = _make_realtor_with_listing(db_session, email="lazy-token@example.com")
    login_as(client, user)
    assert listing.public_token is None

    resp = client.get(f"/vip/realtor/listings/{listing.id}")

    assert resp.status_code == 200
    db_session.refresh(listing)
    assert listing.public_token is not None
    assert f"/p/listing/{listing.public_token}" in resp.get_data(as_text=True)


def test_listing_landing_page_renders_for_valid_token(db_session, client):
    _, partner, profile, listing = _make_realtor_with_listing(db_session, email="landing-render@example.com")
    listing.public_token = "listing-token-1"
    listing.photos_json = json.dumps(["https://example.com/photo1.jpg"])
    db_session.commit()

    resp = client.get("/p/listing/listing-token-1")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "123 Main St" in body
    assert "450,000" in body
    assert "https://example.com/photo1.jpg" in body


def test_listing_landing_page_404s_for_unknown_token(client):
    resp = client.get("/p/listing/does-not-exist")
    assert resp.status_code == 404


def test_listing_landing_inquiry_creates_client_and_notification(db_session, client):
    owner, partner, profile, listing = _make_realtor_with_listing(db_session, email="inquiry-owner@example.com")
    listing.public_token = "listing-token-2"
    db_session.commit()

    resp = client.post(
        "/p/listing/listing-token-2/inquire",
        data={"client_name": "Buyer Bob", "client_email": "bob@example.com", "message": "Can I tour this?"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "Thanks, Buyer Bob" in resp.get_data(as_text=True)

    inquiry = ElenaClient.query.filter_by(email="bob@example.com").first()
    assert inquiry is not None
    assert inquiry.vip_profile_id == profile.id
    assert "123 Main St" in inquiry.notes

    notification = VIPNotification.query.filter_by(vip_profile_id=profile.id).first()
    assert notification is not None


def test_listing_landing_inquiry_requires_name(db_session, client):
    _, partner, profile, listing = _make_realtor_with_listing(db_session, email="inquiry-noname@example.com")
    listing.public_token = "listing-token-3"
    db_session.commit()

    resp = client.post(
        "/p/listing/listing-token-3/inquire", data={"client_email": "noone@example.com"}, follow_redirects=True
    )

    assert resp.status_code == 200
    assert "Name is required" in resp.get_data(as_text=True)
    assert ElenaClient.query.filter_by(email="noone@example.com").first() is None
