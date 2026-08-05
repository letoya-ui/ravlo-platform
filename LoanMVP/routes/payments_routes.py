# LoanMVP/routes/payments_routes.py
"""Payments capability: Stripe Connect onboarding + deposit/invoice
requests. Works for any workspace type (VIPProfile realtor/insurance/
contractor, StylistProfile salon, ...) -- see
LoanMVP/services/payments_service.py for the owner-resolution logic that
makes that possible.

Auto-registered by LoanMVP/app.py blueprint scanner.
"""
from datetime import datetime

import stripe
from flask import (
    Blueprint, abort, current_app, flash, jsonify, redirect,
    render_template, request, url_for,
)
from flask_login import current_user, login_required

from LoanMVP.extensions import csrf
from LoanMVP.models.payment_models import PaymentAccount, PaymentRequest
from LoanMVP.services.payments_service import (
    PaymentsServiceError,
    create_checkout_session_for_request,
    create_payment_request,
    get_or_create_payment_account,
    mark_payment_request_paid,
    owner_branding,
    resolve_current_owner,
    start_connect_onboarding,
    sync_connect_status,
)

payments_bp = Blueprint("payments", __name__, url_prefix="/payments")


# ─── Dashboard ──────────────────────────────────────────────────────────────

@payments_bp.get("/")
@login_required
def dashboard():
    owner_type, owner_id, display_name, brand_color, logo_url = resolve_current_owner(current_user)
    if not owner_type:
        abort(404)

    account = get_or_create_payment_account(owner_type, owner_id)
    payment_requests = (
        PaymentRequest.query.filter_by(payment_account_id=account.id)
        .order_by(PaymentRequest.created_at.desc())
        .all()
    )

    return render_template(
        "payments/dashboard.html",
        account=account,
        payment_requests=payment_requests,
        display_name=display_name,
    )


# ─── Stripe Connect onboarding ──────────────────────────────────────────────

@payments_bp.get("/connect/start")
@login_required
def connect_start():
    owner_type, owner_id, *_ = resolve_current_owner(current_user)
    if not owner_type:
        abort(404)

    account = get_or_create_payment_account(owner_type, owner_id)
    base = request.host_url.rstrip("/")

    try:
        link_url = start_connect_onboarding(
            account,
            email=current_user.email,
            refresh_url=base + url_for("payments.connect_refresh"),
            return_url=base + url_for("payments.connect_return"),
        )
    except PaymentsServiceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("payments.dashboard"))

    return redirect(link_url)


@payments_bp.get("/connect/refresh")
@login_required
def connect_refresh():
    # AccountLinks expire quickly -- just mint a fresh one.
    return redirect(url_for("payments.connect_start"))


@payments_bp.get("/connect/return")
@login_required
def connect_return():
    owner_type, owner_id, *_ = resolve_current_owner(current_user)
    if owner_type:
        account = get_or_create_payment_account(owner_type, owner_id)
        try:
            sync_connect_status(account)
            flash("Your Stripe account is connected.", "success")
        except PaymentsServiceError as exc:
            flash(str(exc), "error")
    return redirect(url_for("payments.dashboard"))


# ─── Payment requests ───────────────────────────────────────────────────────

@payments_bp.post("/requests/new")
@login_required
def create_request():
    owner_type, owner_id, *_ = resolve_current_owner(current_user)
    if not owner_type:
        abort(404)

    account = get_or_create_payment_account(owner_type, owner_id)
    if not account.is_ready_for_payments:
        flash("Connect your Stripe account before requesting a payment.", "error")
        return redirect(url_for("payments.dashboard"))

    title = (request.form.get("title") or "").strip()
    amount_raw = (request.form.get("amount") or "").strip()

    if not title or not amount_raw:
        flash("Title and amount are required.", "error")
        return redirect(url_for("payments.dashboard"))

    try:
        amount_cents = int(round(float(amount_raw) * 100))
    except ValueError:
        amount_cents = 0

    if amount_cents <= 0:
        flash("Enter a valid amount.", "error")
        return redirect(url_for("payments.dashboard"))

    payment_request = create_payment_request(
        account,
        title=title,
        amount_cents=amount_cents,
        description=request.form.get("description", ""),
        client_name=request.form.get("client_name", ""),
        client_email=request.form.get("client_email", ""),
        client_phone=request.form.get("client_phone", ""),
    )

    flash(
        "Payment request created. Share this link with your client: "
        + url_for("payments.public_pay_page", token=payment_request.confirmation_token, _external=True),
        "success",
    )
    return redirect(url_for("payments.dashboard"))


# ─── Public payer page (no auth) ────────────────────────────────────────────

@payments_bp.get("/pay/<token>")
def public_pay_page(token):
    payment_request = PaymentRequest.query.filter_by(confirmation_token=token).first_or_404()
    account = payment_request.payment_account
    display_name, brand_color, logo_url = owner_branding(account.owner_type, account.owner_id)

    return render_template(
        "payments/public_pay.html",
        payment_request=payment_request,
        display_name=display_name,
        brand_color=brand_color,
        logo_url=logo_url,
        paid=(request.args.get("paid") == "1" or payment_request.status == "paid"),
    )


@payments_bp.post("/pay/<token>/checkout")
def public_pay_checkout(token):
    payment_request = PaymentRequest.query.filter_by(confirmation_token=token).first_or_404()

    if payment_request.status == "paid":
        return redirect(url_for("payments.public_pay_page", token=token))

    base = request.host_url.rstrip("/")
    success_url = base + url_for("payments.public_pay_page", token=token) + "?paid=1"
    cancel_url = base + url_for("payments.public_pay_page", token=token)

    try:
        checkout_url = create_checkout_session_for_request(payment_request, success_url, cancel_url)
    except PaymentsServiceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("payments.public_pay_page", token=token))

    return redirect(checkout_url, code=303)


# ─── Stripe Connect webhook ─────────────────────────────────────────────────

@payments_bp.post("/webhook")
@csrf.exempt
def webhook():
    payload = request.get_data()
    sig = request.headers.get("Stripe-Signature", "")
    webhook_secret = current_app.config.get("STRIPE_CONNECT_WEBHOOK_SECRET", "")

    if not webhook_secret:
        current_app.logger.error("STRIPE_CONNECT_WEBHOOK_SECRET is not set — webhook rejected")
        return jsonify({"error": "Webhook secret not configured."}), 500

    try:
        event = stripe.Webhook.construct_event(payload, sig, webhook_secret)
    except stripe.error.SignatureVerificationError:
        current_app.logger.warning("Payments webhook: invalid signature")
        return jsonify({"error": "Invalid signature."}), 400
    except Exception as exc:
        current_app.logger.exception("Payments webhook: parse error")
        return jsonify({"error": str(exc)}), 400

    event_type = event["type"]
    data = event["data"]["object"]

    try:
        if event_type == "checkout.session.completed":
            _handle_checkout_completed(data)
        elif event_type == "account.updated":
            _handle_account_updated(data)
    except Exception:
        current_app.logger.exception(
            "Payments webhook handler failed for event=%s id=%s", event_type, event.get("id")
        )
        # Return 200 so Stripe doesn't retry on our application bugs.

    return jsonify({"status": "ok"}), 200


def _handle_checkout_completed(session):
    payment_request_id = (session.get("metadata") or {}).get("payment_request_id")
    if not payment_request_id:
        return

    payment_request = PaymentRequest.query.get(int(payment_request_id))
    if not payment_request or payment_request.status == "paid":
        return

    mark_payment_request_paid(payment_request, payment_intent_id=session.get("payment_intent") or "")


def _handle_account_updated(stripe_account):
    from LoanMVP.extensions import db

    account_id = stripe_account.get("id")
    if not account_id:
        return

    account = PaymentAccount.query.filter_by(stripe_connect_account_id=account_id).first()
    if not account:
        return

    account.stripe_connect_charges_enabled = bool(stripe_account.get("charges_enabled"))
    account.stripe_connect_payouts_enabled = bool(stripe_account.get("payouts_enabled"))
    if account.stripe_connect_charges_enabled and not account.stripe_connect_onboarded_at:
        account.stripe_connect_onboarded_at = datetime.utcnow()
    db.session.commit()
