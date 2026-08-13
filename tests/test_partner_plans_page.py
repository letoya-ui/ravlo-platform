"""Regression test for the public partner pricing page
(/partners/plans, LoanMVP/templates/marketing/partner_plans.html).

It used to advertise three tiers ("Basic Listing" $79, "Preferred Partner"
$99, "Featured Partner" $199) that had nothing to do with any real,
current pricing -- worst of all, "Preferred Partner" wasn't a real tier
at all: LoanMVP/routes/billing_webhook.py's _norm_partner_tier() only
recognizes featured/premium/enterprise, so a "preferred" tier value falls
through to "Preferred", which isn't in VIP_ACCESS_TIERS or
partner_has_pro_access's allowed set in vip.py/partners.py -- meaning a
real customer paying for that plan got zero gated features.

That was patched once (a "Professional Plan" / "Enterprise" / "Enterprise+"
lineup), but it drifted again in two ways: the individual tier's price
went stale ($299/$99 instead of the real $499/$149), and -- worse --
"Enterprise" and "Enterprise+" described functionality (unlimited seats
per partner account, "Realtor, Insurance, Property Management, and
Investor CRMs" unified under one dashboard, shared contacts across
workspaces) that was never built: Partner.user_id is a unique 1:1 column
(LoanMVP/models/crm_models.py), VIPProfile is one role per user, and
PARTNER_PAID_PLAN_KEYS in partners.py only recognizes
featured/premium/enterprise -- there is no "Enterprise+" tier anywhere
in the backend. Same bug class as "Preferred Partner," just not wired to
a broken checkout this time.

The page now renders directly from partners.py's PARTNER_PLANS (the same
data source partners/billing.html and partners/upgrade.html use), so the
three real paid tiers -- Solo, Professional, Business -- and this page
can never quote different numbers or made-up features again.
"""

from LoanMVP.routes.partners import PARTNER_PLANS


def test_partner_plans_page_shows_real_tier_names_and_prices(client):
    resp = client.get("/partners/plans")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    for key in ("featured", "premium", "enterprise"):
        plan = PARTNER_PLANS[key]
        assert f"{plan['display_name']} Plan" in body
        assert f"${plan['setup_cents'] // 100:,}" in body
        assert f"${plan['monthly_cents'] // 100}" in body
        for feature in plan["features"]:
            assert feature in body


def test_partner_plans_page_no_longer_shows_broken_tiers(client):
    resp = client.get("/partners/plans")

    body = resp.get_data(as_text=True)
    assert "Basic Listing" not in body
    assert "Preferred Partner" not in body
    assert "Featured Partner" not in body
    assert "$199" not in body
    assert "$79" not in body


def test_partner_plans_page_does_not_advertise_unbuilt_enterprise_tiers(client):
    # "Enterprise" / "Enterprise+" as separate multi-workspace/unlimited-
    # seat tiers were never implemented (Partner.user_id is unique 1:1,
    # no seats/team-member model exists) -- the page must not advertise
    # them, and the stale individual-tier price must not reappear either.
    resp = client.get("/partners/plans")

    body = resp.get_data(as_text=True)
    assert "Enterprise+" not in body
    assert "Multi-Workspace" not in body
    assert "Unlimited users" not in body
    assert "$299" not in body
    assert "$99<" not in body


def test_partner_plans_page_does_not_publicly_name_real_customers(client):
    resp = client.get("/partners/plans")

    body = resp.get_data(as_text=True)
    assert "Keyona" not in body
    assert "John Headley" not in body


def test_partner_plans_page_ctas_point_to_sales_not_broken_checkout(client):
    resp = client.get("/partners/plans")

    body = resp.get_data(as_text=True)
    # The old CTAs posted to checkout.subscribe plans (basic_listing,
    # preferred_partner, featured_partner) whose Stripe metadata tiers
    # don't line up with any real gating tiers. These plans carry setup
    # fees and custom scoping, so every tier routes to Contact instead.
    assert "/checkout/subscribe/basic_listing" not in body
    assert "/checkout/subscribe/preferred_partner" not in body
    assert "/checkout/subscribe/featured_partner" not in body
