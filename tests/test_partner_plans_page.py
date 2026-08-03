"""Regression test for the public partner pricing page
(/partners/plans, LoanMVP/templates/marketing/partner_plans.html).

It used to advertise three tiers ("Basic Listing" $79, "Preferred Partner"
$99, "Featured Partner" $199) that had nothing to do with the real VIP
tier system (Free / Featured $79 / Premium $99 / Enterprise) used
everywhere else to gate partner features -- worst of all, "Preferred
Partner" wasn't a real tier at all: LoanMVP/routes/billing_webhook.py's
_norm_partner_tier() only recognizes featured/premium/enterprise, so a
"preferred" tier value falls through to "Preferred", which isn't in
VIP_ACCESS_TIERS or partner_has_pro_access's allowed set in vip.py/
partners.py -- meaning a real customer paying for that plan got zero
gated features.

This brings the page's tier names, prices, and features in line with
partners/upgrade.html's real Free/Featured/Premium plans.
"""


def test_partner_plans_page_shows_real_tier_names_and_prices(client):
    resp = client.get("/partners/plans")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Free" in body
    assert "$0" in body
    assert "Featured" in body
    assert "$79" in body
    assert "Premium" in body
    assert "$99" in body


def test_partner_plans_page_no_longer_shows_broken_tiers(client):
    resp = client.get("/partners/plans")

    body = resp.get_data(as_text=True)
    assert "Basic Listing" not in body
    assert "Preferred Partner" not in body
    assert "Featured Partner" not in body
    assert "$199" not in body


def test_partner_plans_page_features_match_the_real_tier_gates(client):
    resp = client.get("/partners/plans")

    body = resp.get_data(as_text=True)
    # Matches partners/upgrade.html's real per-tier feature lists, which
    # in turn match what vip.py/partners.py actually gate behind each tier.
    assert "Deal visibility" in body
    assert "Portfolio showcase" in body
    assert "Proposal builder" in body
    assert "Instant quote generator" in body
    assert "AI assist" in body


def test_partner_plans_page_ctas_point_to_registration_not_broken_checkout(client):
    resp = client.get("/partners/plans")

    body = resp.get_data(as_text=True)
    # The old CTAs posted to checkout.subscribe plans (basic_listing,
    # preferred_partner, featured_partner) whose Stripe metadata tiers
    # don't line up with the real gating tiers. New visitors should
    # register first, then pick a real tier from the app's own upgrade
    # flow (partners.subscribe), which is what /partners/plans links to
    # now instead.
    assert "/checkout/subscribe/basic_listing" not in body
    assert "/checkout/subscribe/preferred_partner" not in body
    assert "/checkout/subscribe/featured_partner" not in body
