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

That was fixed, but the individual-tier card ("Professional Plan", $299
setup/$99mo) was never updated when partners.py's PARTNER_PLANS was
restructured to Solo/Professional/Business -- it drifted out of sync
with the real Solo tier ($499 setup/$149mo), so this marketing page and
the real Growth Plans/billing page inside the app quoted two different
prices for the same individual plan. This brings the page in line with
the real, current setup-fee-plus-monthly pricing model:
  - Solo Plan             -- $499 setup, $149/mo  (individual partners,
                              matches partners.py's PARTNER_PLANS["featured"])
  - Enterprise           -- $2,500 setup, $499/mo  (single-department teams)
  - Enterprise+          -- starts at $5,000 setup, $999/mo+  (multi-workspace)
"""


def test_partner_plans_page_shows_real_tier_names_and_prices(client):
    resp = client.get("/partners/plans")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Solo Plan" in body
    assert "$499" in body
    assert "$149" in body
    assert "Enterprise" in body
    assert "$2,500" in body
    assert "$999" in body
    assert "$5,000" in body


def test_partner_plans_page_no_longer_shows_broken_tiers(client):
    resp = client.get("/partners/plans")

    body = resp.get_data(as_text=True)
    assert "Basic Listing" not in body
    assert "Preferred Partner" not in body
    assert "Featured Partner" not in body
    assert "$199" not in body
    assert "$79" not in body


def test_partner_plans_page_individual_tier_matches_real_solo_pricing(client):
    # The individual tier here must always match partners.py's real
    # PARTNER_PLANS["featured"] (display_name "Solo") -- these two pages
    # quoting different numbers for the same plan is exactly the bug
    # this test guards against.
    from LoanMVP.routes.partners import PARTNER_PLANS

    solo = PARTNER_PLANS["featured"]
    setup_dollars = f"${solo['setup_cents'] // 100:,}"
    monthly_dollars = f"${solo['monthly_cents'] // 100}"

    resp = client.get("/partners/plans")
    body = resp.get_data(as_text=True)

    assert setup_dollars in body
    assert monthly_dollars in body
    # Stale numbers from before the Solo/Professional/Business restructure
    # must not reappear.
    assert "$299" not in body
    assert "$99<" not in body


def test_partner_plans_page_features_match_real_tiers(client):
    resp = client.get("/partners/plans")

    body = resp.get_data(as_text=True)
    assert "1 Professional Workspace" in body
    assert "AI Copilot" in body
    assert "Content Studio" in body
    assert "Unlimited users" in body
    assert "Team CRM" in body
    assert "One unified dashboard" in body
    assert "Shared contacts" in body


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
