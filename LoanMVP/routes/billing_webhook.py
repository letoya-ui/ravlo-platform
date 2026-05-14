# LoanMVP/routes/billing_webhook.py
"""Stripe webhook handler.

Receives and verifies Stripe event notifications. Handles subscription
lifecycle for both investor users and partner users.

Event coverage:
  checkout.session.completed      → activate subscription from metadata
  customer.subscription.updated   → sync plan changes / renewals
  customer.subscription.deleted   → downgrade to free / core
  invoice.payment_succeeded       → ensure plan stays active
  invoice.payment_failed          → flag billing_status = 'past_due'
"""

from datetime import datetime

import stripe
from flask import Blueprint, current_app, jsonify, request

from LoanMVP.extensions import db, csrf

billing_webhook_bp = Blueprint("billing_webhook", __name__, url_prefix="/stripe")

# ─── Plan-name normalization ───────────────────────────────────────────────────

_PARTNER_TIER_NORM = {
    "featured":   "Featured",
    "premium":    "Premium",
    "enterprise": "Enterprise",
}

_INVESTOR_PLAN_ALIAS = {
    "free":       "core",
    "starter":    "core",
    "individual": "core",
    "team":       "pro",
    "premium":    "pro",
    "active":     "pro",
}

_VIP_PARTNER_TIERS = {"featured", "premium", "enterprise"}


def _norm_partner_tier(raw: str) -> str:
    key = (raw or "").strip().lower()
    return _PARTNER_TIER_NORM.get(key, key.title() if key else "")


def _norm_investor_plan(raw: str) -> str:
    key = (raw or "").strip().lower()
    return _INVESTOR_PLAN_ALIAS.get(key, key or "core")


# ─── Model helpers (imported lazily to avoid circular deps at module load) ────

def _get_user(user_id):
    from LoanMVP.models import User
    try:
        return User.query.get(int(user_id))
    except (TypeError, ValueError):
        return None


def _get_partner_by_user(user_id):
    from LoanMVP.models.crm_models import Partner
    try:
        return Partner.query.filter_by(user_id=int(user_id)).first()
    except (TypeError, ValueError):
        return None


def _get_partner_by_stripe_customer(customer_id: str):
    from LoanMVP.models.crm_models import Partner
    if not customer_id:
        return None
    return Partner.query.filter_by(stripe_customer_id=customer_id).first()


def _get_user_by_stripe_customer(customer_id: str):
    from LoanMVP.models import User
    if not customer_id:
        return None
    return User.query.filter_by(stripe_customer_id=customer_id).first()


# ─── Activation helpers ───────────────────────────────────────────────────────

def _activate_partner_tier(partner, tier: str, customer_id: str = None):
    normalized = _norm_partner_tier(tier)
    if not normalized:
        return
    partner.subscription_tier = normalized
    partner.approved = True
    partner.active = True
    partner.status = "Active"
    partner.featured = tier.lower() in _VIP_PARTNER_TIERS
    if customer_id and not partner.stripe_customer_id:
        partner.stripe_customer_id = customer_id


def _activate_investor_plan(user, plan: str, customer_id: str = None):
    slug = _norm_investor_plan(plan)
    alias_map = {
        "free": "core",
        "starter": "core",
        "individual": "core",
        "team": "pro",
        "premium": "pro",
        "active": "pro",
    }
    user.subscription = alias_map.get(slug, slug or "core")
    if customer_id and not getattr(user, "stripe_customer_id", None):
        try:
            user.stripe_customer_id = customer_id
        except AttributeError:
            pass


def _deactivate_partner(partner):
    partner.subscription_tier = "Free"
    partner.featured = False


def _deactivate_investor(user):
    user.subscription = "core"


# ─── Event handlers ───────────────────────────────────────────────────────────

def _handle_checkout_completed(session):
    """Activate subscription immediately when Stripe confirms checkout paid."""
    metadata = session.get("metadata") or {}
    user_id = metadata.get("user_id")
    partner_tier = metadata.get("partner_tier", "")
    sub_plan = metadata.get("subscription_plan", "")
    customer_id = session.get("customer") or ""

    if not user_id:
        current_app.logger.warning("webhook checkout.session.completed: no user_id in metadata")
        return

    user = _get_user(user_id)
    if not user:
        current_app.logger.warning("webhook checkout.session.completed: user %s not found", user_id)
        return

    # Store stripe_customer_id on user for future subscription event lookups
    if customer_id:
        try:
            if not getattr(user, "stripe_customer_id", None):
                user.stripe_customer_id = customer_id
        except AttributeError:
            pass

    if partner_tier:
        partner = _get_partner_by_user(user_id)
        if partner:
            _activate_partner_tier(partner, partner_tier, customer_id)
            current_app.logger.info(
                "webhook: activated partner tier=%s for user=%s", partner_tier, user_id
            )
        else:
            current_app.logger.warning(
                "webhook checkout.session.completed: no partner for user %s", user_id
            )
    elif sub_plan:
        _activate_investor_plan(user, sub_plan, customer_id)
        current_app.logger.info(
            "webhook: activated investor plan=%s for user=%s", sub_plan, user_id
        )

    db.session.commit()


def _handle_subscription_updated(subscription):
    """Sync plan when Stripe reports a subscription change (renewal, upgrade, etc.)."""
    customer_id = subscription.get("customer") or ""
    status = subscription.get("status") or ""

    # Active statuses from Stripe: active, trialing, past_due
    if status not in ("active", "trialing", "past_due"):
        return

    metadata = subscription.get("metadata") or {}
    user_id = metadata.get("user_id")
    partner_tier = metadata.get("partner_tier", "")
    sub_plan = metadata.get("subscription_plan", "")

    # Try partner lookup first (by customer_id, then metadata)
    partner = _get_partner_by_stripe_customer(customer_id)
    if partner:
        existing = (partner.subscription_tier or "").strip().lower()
        if partner_tier:
            _activate_partner_tier(partner, partner_tier, customer_id)
        elif existing in _VIP_PARTNER_TIERS:
            pass  # keep existing tier on renewal when metadata is missing
        db.session.commit()
        current_app.logger.info(
            "webhook subscription.updated: partner %s status=%s", partner.id, status
        )
        return

    # Investor lookup
    user = _get_user_by_stripe_customer(customer_id) or (
        _get_user(user_id) if user_id else None
    )
    if user and sub_plan:
        _activate_investor_plan(user, sub_plan, customer_id)
        db.session.commit()
        current_app.logger.info(
            "webhook subscription.updated: user %s plan=%s status=%s", user.id, sub_plan, status
        )


def _handle_subscription_deleted(subscription):
    """Downgrade when Stripe reports a subscription cancellation."""
    customer_id = subscription.get("customer") or ""
    metadata = subscription.get("metadata") or {}
    user_id = metadata.get("user_id")

    partner = _get_partner_by_stripe_customer(customer_id)
    if partner:
        _deactivate_partner(partner)
        db.session.commit()
        current_app.logger.info(
            "webhook subscription.deleted: partner %s downgraded to Free", partner.id
        )
        return

    user = _get_user_by_stripe_customer(customer_id) or (
        _get_user(user_id) if user_id else None
    )
    if user:
        _deactivate_investor(user)
        db.session.commit()
        current_app.logger.info(
            "webhook subscription.deleted: user %s downgraded to core", user.id
        )


def _handle_invoice_payment_failed(invoice):
    """Flag past_due when a renewal payment fails."""
    customer_id = invoice.get("customer") or ""

    partner = _get_partner_by_stripe_customer(customer_id)
    if partner:
        current_app.logger.warning(
            "webhook invoice.payment_failed: partner %s stripe_customer=%s",
            partner.id, customer_id,
        )
        # Don't immediately revoke — Stripe will retry and send subscription.deleted
        # if all retries fail. Just log.
        return

    user = _get_user_by_stripe_customer(customer_id)
    if user:
        current_app.logger.warning(
            "webhook invoice.payment_failed: user %s stripe_customer=%s",
            user.id, customer_id,
        )


def _handle_invoice_payment_succeeded(invoice):
    """Confirm plan stays active on a successful recurring payment."""
    customer_id = invoice.get("customer") or ""
    billing_reason = invoice.get("billing_reason") or ""

    # Only re-activate on subscription renewals (not the initial checkout invoice)
    if billing_reason not in ("subscription_cycle", "subscription_update"):
        return

    partner = _get_partner_by_stripe_customer(customer_id)
    if partner:
        # Ensure it's marked active after a successful renewal
        if not partner.active:
            partner.active = True
            db.session.commit()
        return

    user = _get_user_by_stripe_customer(customer_id)
    if user:
        current_app.logger.info(
            "webhook invoice.payment_succeeded: user %s subscription renewed", user.id
        )


# ─── Webhook endpoint ─────────────────────────────────────────────────────────

@billing_webhook_bp.post("/webhook")
@csrf.exempt
def stripe_webhook():
    payload = request.get_data()
    sig = request.headers.get("Stripe-Signature", "")
    webhook_secret = current_app.config.get("STRIPE_WEBHOOK_SECRET", "")

    if not webhook_secret:
        current_app.logger.error("STRIPE_WEBHOOK_SECRET is not set — webhook rejected")
        return jsonify({"error": "Webhook secret not configured."}), 500

    try:
        event = stripe.Webhook.construct_event(payload, sig, webhook_secret)
    except stripe.error.SignatureVerificationError:
        current_app.logger.warning("Stripe webhook: invalid signature")
        return jsonify({"error": "Invalid signature."}), 400
    except Exception as exc:
        current_app.logger.exception("Stripe webhook: parse error")
        return jsonify({"error": str(exc)}), 400

    event_type = event["type"]
    data = event["data"]["object"]

    _HANDLERS = {
        "checkout.session.completed":    _handle_checkout_completed,
        "customer.subscription.updated": _handle_subscription_updated,
        "customer.subscription.deleted": _handle_subscription_deleted,
        "invoice.payment_succeeded":     _handle_invoice_payment_succeeded,
        "invoice.payment_failed":        _handle_invoice_payment_failed,
    }

    handler = _HANDLERS.get(event_type)
    if handler:
        try:
            handler(data)
        except Exception:
            current_app.logger.exception(
                "Stripe webhook handler failed for event=%s id=%s",
                event_type, event.get("id"),
            )
            # Return 200 so Stripe doesn't retry on our application bugs.
            # Stripe retries on 5xx, which could flood us.

    return jsonify({"status": "ok"}), 200
