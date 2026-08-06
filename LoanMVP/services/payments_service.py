# LoanMVP/services/payments_service.py
"""Payments capability (Stripe Connect deposits/invoices).

This is the one place that knows how an owner_type string maps to a real
workspace model (VIPProfile, StylistProfile, ...). Everything else --
routes, templates, the webhook -- only ever deals in (owner_type,
owner_id) pairs and PaymentAccount/PaymentRequest rows, so adding a new
workspace type here later is a one-function change, not a new schema.
"""
import uuid
from datetime import datetime
from typing import Optional, Tuple

import stripe
from flask import current_app

from LoanMVP.extensions import db
from LoanMVP.models.payment_models import PaymentAccount, PaymentRequest


class PaymentsServiceError(Exception):
    pass


# ─── Owner resolution ───────────────────────────────────────────────────────

def resolve_current_owner(user) -> Tuple[Optional[str], Optional[int], Optional[str], Optional[str], Optional[str]]:
    """Returns (owner_type, owner_id, display_name, brand_color, logo_url)
    for whichever workspace the logged-in user actually runs, or all-None
    if they run neither. A stylist account is a completely separate model
    tree from VIPProfile (see salon_models.py), so this is the only branch
    point -- checked in order because a user is one or the other, never
    both.
    """
    from LoanMVP.models.salon_models import StylistProfile

    stylist = StylistProfile.query.filter_by(user_id=user.id).first()
    if stylist:
        return (
            "stylist_profile",
            stylist.id,
            stylist.full_name,
            stylist.brand_color,
            stylist.logo_url,
        )

    from LoanMVP.routes.vip import get_or_create_vip_profile

    vip_profile = get_or_create_vip_profile()
    if vip_profile:
        return (
            "vip_profile",
            vip_profile.id,
            vip_profile.business_name or vip_profile.display_name,
            vip_profile.brand_color,
            vip_profile.logo_url,
        )

    return None, None, None, None, None


def owner_branding(owner_type: str, owner_id: int) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Returns (display_name, brand_color, logo_url) for an
    (owner_type, owner_id) pair -- used by the public payer page, which has
    no logged-in user to resolve from."""
    if owner_type == "stylist_profile":
        from LoanMVP.models.salon_models import StylistProfile

        stylist = StylistProfile.query.get(owner_id)
        if not stylist:
            return None, None, None
        return stylist.full_name, stylist.brand_color, stylist.logo_url

    if owner_type == "vip_profile":
        from LoanMVP.models.vip_models import VIPProfile

        profile = VIPProfile.query.get(owner_id)
        if not profile:
            return None, None, None
        return (profile.business_name or profile.display_name), profile.brand_color, profile.logo_url

    return None, None, None


# ─── PaymentAccount ─────────────────────────────────────────────────────────

def get_or_create_payment_account(owner_type: str, owner_id: int) -> PaymentAccount:
    account = PaymentAccount.query.filter_by(owner_type=owner_type, owner_id=owner_id).first()
    if account:
        return account

    account = PaymentAccount(owner_type=owner_type, owner_id=owner_id)
    db.session.add(account)
    db.session.commit()
    return account


def _stripe_configured():
    stripe.api_key = current_app.config.get("STRIPE_SECRET_KEY", "")
    if not stripe.api_key:
        raise PaymentsServiceError("Stripe is not configured on this server.")


def start_connect_onboarding(account: PaymentAccount, email: str, refresh_url: str, return_url: str) -> str:
    """Creates the Stripe Express account (if this workspace hasn't
    started one yet) and returns a fresh AccountLink URL to send the user
    to. AccountLinks expire quickly, so this is safe -- and necessary --
    to call again on every "Connect Stripe" click."""
    _stripe_configured()

    if not account.stripe_connect_account_id:
        stripe_account = stripe.Account.create(
            type="express",
            email=email or None,
            capabilities={
                "card_payments": {"requested": True},
                "transfers": {"requested": True},
            },
        )
        account.stripe_connect_account_id = stripe_account.id
        db.session.commit()

    account_link = stripe.AccountLink.create(
        account=account.stripe_connect_account_id,
        refresh_url=refresh_url,
        return_url=return_url,
        type="account_onboarding",
    )
    return account_link.url


def sync_connect_status(account: PaymentAccount) -> PaymentAccount:
    """Live-fetches the connected account's charges_enabled/payouts_enabled
    from Stripe. Called both from the onboarding return route (for a snappy
    "you're all set" without waiting on the webhook) and from the
    account.updated webhook handler."""
    if not account.stripe_connect_account_id:
        return account

    _stripe_configured()
    stripe_account = stripe.Account.retrieve(account.stripe_connect_account_id)

    account.stripe_connect_charges_enabled = bool(stripe_account.get("charges_enabled"))
    account.stripe_connect_payouts_enabled = bool(stripe_account.get("payouts_enabled"))
    if account.stripe_connect_charges_enabled and not account.stripe_connect_onboarded_at:
        account.stripe_connect_onboarded_at = datetime.utcnow()
    db.session.commit()
    return account


# ─── PaymentRequest ─────────────────────────────────────────────────────────

def create_payment_request(
    account: PaymentAccount,
    title: str,
    amount_cents: int,
    description: str = "",
    client_name: str = "",
    client_email: str = "",
    client_phone: str = "",
) -> PaymentRequest:
    payment_request = PaymentRequest(
        payment_account_id=account.id,
        title=title,
        description=description or None,
        amount_cents=amount_cents,
        client_name=client_name or None,
        client_email=client_email or None,
        client_phone=client_phone or None,
        confirmation_token=uuid.uuid4().hex,
    )
    db.session.add(payment_request)
    db.session.commit()
    return payment_request


def create_checkout_session_for_request(
    payment_request: PaymentRequest, success_url: str, cancel_url: str, expires_at: int = None
) -> str:
    """Builds a destination-charge Checkout Session: Ravlo stays merchant
    of record, but the funds land directly in the workspace's connected
    Stripe account (payment_intent_data.transfer_data.destination).
    application_fee_amount is intentionally left unset -- no platform fee
    percentage has been decided yet.

    expires_at (Unix timestamp) is used by callers that hold a resource --
    e.g. a booking slot -- for only as long as the session stays open
    (Stripe requires it be 30 min-24h out); omitted for a plain payment
    request, which keeps Stripe's default 24h expiry."""
    account = payment_request.payment_account
    if not account.is_ready_for_payments:
        raise PaymentsServiceError("This workspace has not finished connecting Stripe yet.")

    _stripe_configured()

    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": payment_request.title,
                        "description": payment_request.description or None,
                    },
                    "unit_amount": payment_request.amount_cents,
                },
                "quantity": 1,
            }
        ],
        payment_intent_data={
            "transfer_data": {"destination": account.stripe_connect_account_id},
        },
        customer_email=payment_request.client_email or None,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"payment_request_id": str(payment_request.id)},
        **({"expires_at": expires_at} if expires_at else {}),
    )

    payment_request.stripe_checkout_session_id = session.id
    db.session.commit()
    return session.url


def mark_payment_request_paid(payment_request: PaymentRequest, payment_intent_id: str = "") -> PaymentRequest:
    payment_request.status = "paid"
    payment_request.paid_at = datetime.utcnow()
    if payment_intent_id:
        payment_request.stripe_payment_intent_id = payment_intent_id
    db.session.commit()
    return payment_request
