"""
LoanMVP/routes/checkout_routes.py

Universal Stripe Checkout for all Ravlo subscription plans.

Routes:
  GET /checkout/subscribe/<plan>  → create Stripe Checkout session and redirect

Plan slugs:
  academy_pro, academy_starter
  pro, operator, explorer
  brokerage, loan_officer
  featured_partner, preferred_partner, basic_listing

Auto-registered by LoanMVP/app.py blueprint scanner.
"""

import stripe
from flask import Blueprint, current_app, jsonify, redirect, request, url_for
from flask_login import current_user, login_required

checkout_bp = Blueprint("checkout", __name__, url_prefix="/checkout")

# (price_config_key, metadata_key, metadata_value, success_endpoint)
_PLAN_MAP = {
    # Academy
    "academy_pro":       ("STRIPE_PRICE_ACADEMY_PRO",            "academy_tier",      "pro",          "university.portal"),
    "academy_starter":   ("STRIPE_PRICE_ACADEMY_STARTER",         "academy_tier",      "starter",      "university.portal"),
    # Investor platform
    "pro":               ("STRIPE_PRICE_PRO",                     "subscription_plan", "pro",          "marketing.enter"),
    "operator":          ("STRIPE_PRICE_OPERATOR",                "subscription_plan", "operator",     "marketing.enter"),
    "explorer":          ("STRIPE_PRICE_EXPLORER",                "subscription_plan", "explorer",     "marketing.enter"),
    # Lending
    "brokerage":         ("STRIPE_PRICE_BROKERAGE_SMALL_TEAM",    "subscription_plan", "brokerage",    "marketing.enter"),
    "loan_officer":      ("STRIPE_PRICE_INDIVIDUAL_LOAN_OFFICER", "subscription_plan", "loan_officer", "marketing.enter"),
    # Partner
    "featured_partner":  ("STRIPE_PRICE_FEATURED_PARTNER",        "partner_tier",      "featured",     "marketing.partners"),
    "preferred_partner": ("STRIPE_PRICE_PREFERRED_PARTNER",       "partner_tier",      "preferred",    "marketing.partners"),
    "basic_listing":     ("STRIPE_PRICE_BASIC_LISTING",           "partner_tier",      "basic",        "marketing.partners"),
}


@checkout_bp.route("/subscribe/<plan>")
def subscribe(plan):
    # Unauthenticated visitors (likely new users) → register, not login
    if not current_user.is_authenticated:
        return redirect(url_for("auth.register", plan=plan))

    cfg = _PLAN_MAP.get(plan)
    if not cfg:
        return jsonify({"error": "Unknown plan."}), 404

    price_key, meta_key, meta_value, success_endpoint = cfg
    price_id = current_app.config.get(price_key, "")

    if not price_id:
        current_app.logger.error(
            "checkout.subscribe: no price ID configured for plan=%s key=%s", plan, price_key
        )
        return jsonify({"error": "This plan is not currently available. Please contact us."}), 503

    if not current_app.config.get("STRIPE_BILLING_ENABLED"):
        return jsonify({"error": "Billing is not enabled on this server."}), 503

    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]

    base = request.host_url.rstrip("/")
    success_url = base + url_for(success_endpoint) + "?checkout=success&session_id={CHECKOUT_SESSION_ID}"

    # Return user to the page they came from on cancel, defaulting to /plans
    referrer = request.referrer or ""
    if referrer.startswith(base):
        cancel_url = referrer
    else:
        cancel_url = base + url_for("marketing.plans")

    stripe_customer_id = getattr(current_user, "stripe_customer_id", None) or None

    session_kwargs = dict(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        metadata={"user_id": str(current_user.id), meta_key: meta_value},
        success_url=success_url,
        cancel_url=cancel_url,
    )
    if stripe_customer_id:
        session_kwargs["customer"] = stripe_customer_id
    else:
        session_kwargs["customer_email"] = current_user.email

    try:
        session = stripe.checkout.Session.create(**session_kwargs)
    except stripe.error.StripeError as exc:
        current_app.logger.error("checkout.subscribe stripe error plan=%s: %s", plan, exc)
        return jsonify({"error": "Could not start checkout. Please try again."}), 502

    return redirect(session.url, code=303)
