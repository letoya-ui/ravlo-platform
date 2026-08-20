# LoanMVP/routes/renter_routes.py
"""Renter portal: tenants log in to view their rent status/history, pay
rent online, and file maintenance requests. A property manager invites a
specific Tenant record from property_routes.py's unit_detail() page; the
invite link carries a signed token (renter_invite_service.py) rather than
a server-side row, since the tenant has no session/account yet.

Rent is collected through the landlord's own Stripe Connect account (see
payments_service.py's investor_profile branch) -- Ravlo never touches the
money, same destination-charge pattern as every other workspace type.

Auto-registered by LoanMVP/app.py blueprint scanner.
"""
from datetime import date
from decimal import Decimal

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user
from sqlalchemy.exc import IntegrityError

from LoanMVP.extensions import db
from LoanMVP.models.property import MaintenanceRequest, RentPayment, Tenant
from LoanMVP.models.user_model import User
from LoanMVP.services.payments_service import (
    PaymentsServiceError,
    create_checkout_session_for_request,
    create_payment_request,
    get_or_create_payment_account,
)
from LoanMVP.services.renter_invite_service import decode_invite_token
from LoanMVP.utils.decorators import role_required

renter_bp = Blueprint("renter", __name__, url_prefix="/renter")

MAINTENANCE_PRIORITIES = ["low", "medium", "high", "urgent"]


def _unique_username(base: str, fallback: str = "") -> str:
    """Mirrors auth.py's _unique_username -- User.username has a unique DB
    constraint, so two tenants named the same thing can't collide."""
    base = (base or fallback or "").strip()
    if not base:
        return base
    candidate = base
    suffix = 1
    while User.query.filter_by(username=candidate).first():
        suffix += 1
        candidate = f"{base} {suffix}"
    return candidate


def _split_name(full_name: str):
    parts = (full_name or "").split(None, 1)
    first = parts[0] if parts else None
    last = parts[1] if len(parts) > 1 else None
    return first, last


def _get_owned_tenant_or_404() -> Tenant:
    tenant = Tenant.query.filter_by(user_id=current_user.id).first()
    if not tenant:
        abort(404)
    return tenant


# ─── Invite acceptance (public -- token carries the authorization) ─────────

@renter_bp.route("/invite/<token>", methods=["GET", "POST"])
def accept_invite(token):
    tenant_id = decode_invite_token(token)
    tenant = Tenant.query.get(tenant_id) if tenant_id else None

    if not tenant:
        flash("This invite link is invalid or has expired. Ask your property manager to resend it.", "error")
        return redirect(url_for("auth.login"))

    if tenant.user_id:
        flash("This invite has already been used. Please log in.", "info")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        email = (request.form.get("email") or tenant.email or "").strip().lower()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not email or not password:
            flash("Please complete all fields.", "error")
            return redirect(url_for("renter.accept_invite", token=token))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("renter.accept_invite", token=token))

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return redirect(url_for("renter.accept_invite", token=token))

        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists. Please log in instead.", "error")
            return redirect(url_for("auth.login"))

        first, last = _split_name(tenant.full_name)
        user = User(
            username=_unique_username(tenant.full_name, fallback=email),
            email=email,
            first_name=first,
            last_name=last,
            role="renter",
            is_active=True,
            onboarding_complete=True,
        )
        user.set_password(password)
        db.session.add(user)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            flash("Something went wrong creating your account. Please try again.", "error")
            return redirect(url_for("renter.accept_invite", token=token))

        tenant.user_id = user.id
        if not tenant.email:
            tenant.email = email
        db.session.commit()

        login_user(user)
        flash("Welcome! Your renter portal account is ready.", "success")
        return redirect(url_for("renter.dashboard"))

    return render_template("renter/accept_invite.html", tenant=tenant, token=token)


# ─── Dashboard ──────────────────────────────────────────────────────────────

def _ensure_current_rent_charge_posted(tenant, unit):
    """A PM who never manually logs a rent charge would otherwise leave the
    tenant with nothing to pay -- no rows, no Pay button, no way forward.
    Auto-post the current period's charge from the lease's monthly_rent so
    there's always something payable once the lease is active, instead of
    the tenant's first payment depending on a manual step on the PM side."""
    if not tenant.is_active or not tenant.monthly_rent:
        return
    today = date.today()
    if tenant.lease_start and today < tenant.lease_start:
        return
    if tenant.lease_end and today > tenant.lease_end:
        return

    period_month = today.replace(day=1)
    already_posted = RentPayment.query.filter_by(
        tenant_id=tenant.id, period_month=period_month,
    ).first()
    if already_posted:
        return

    db.session.add(RentPayment(
        unit_id=unit.id,
        tenant_id=tenant.id,
        period_month=period_month,
        amount_due=tenant.monthly_rent,
        amount_paid=Decimal("0"),
        status="unpaid",
    ))
    db.session.commit()


@renter_bp.get("/dashboard")
@login_required
@role_required("renter")
def dashboard():
    tenant = _get_owned_tenant_or_404()
    unit = tenant.unit

    _ensure_current_rent_charge_posted(tenant, unit)

    rent_payments = (
        RentPayment.query.filter_by(tenant_id=tenant.id)
        .order_by(RentPayment.period_month.desc())
        .all()
    )
    # Scoped to requests this renter personally filed, not every request
    # ever logged against the unit -- MaintenanceRequest has no tenant_id,
    # and a unit can have had other tenants before this one.
    maintenance_requests = (
        MaintenanceRequest.query.filter_by(reported_by_user_id=current_user.id)
        .order_by(MaintenanceRequest.created_at.desc())
        .all()
    )

    if request.args.get("paid") == "1":
        flash("Payment received — it may take a minute to reflect below.", "success")

    return render_template(
        "renter/dashboard.html",
        tenant=tenant,
        unit=unit,
        rent_payments=rent_payments,
        maintenance_requests=maintenance_requests,
        today=date.today(),
        active_tab="dashboard",
    )


# ─── Maintenance requests ───────────────────────────────────────────────────

@renter_bp.route("/maintenance/new", methods=["GET", "POST"])
@login_required
@role_required("renter")
def maintenance_new():
    tenant = _get_owned_tenant_or_404()
    unit = tenant.unit

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        if not title:
            flash("A title is required.", "danger")
            return redirect(url_for("renter.maintenance_new"))

        priority = (request.form.get("priority") or "medium").strip().lower()
        req = MaintenanceRequest(
            unit_id=unit.id,
            reported_by_user_id=current_user.id,
            title=title,
            description=(request.form.get("description") or "").strip() or None,
            priority=priority if priority in MAINTENANCE_PRIORITIES else "medium",
            status="open",
        )
        db.session.add(req)
        db.session.commit()
        flash("Maintenance request submitted.", "success")
        return redirect(url_for("renter.dashboard"))

    return render_template(
        "renter/maintenance_new.html",
        unit=unit,
        priorities=MAINTENANCE_PRIORITIES,
        active_tab="maintenance",
    )


# ─── Pay rent ────────────────────────────────────────────────────────────────

@renter_bp.post("/pay/<int:rent_payment_id>")
@login_required
@role_required("renter")
def pay_rent(rent_payment_id):
    tenant = _get_owned_tenant_or_404()
    rent_payment = RentPayment.query.get_or_404(rent_payment_id)
    if rent_payment.tenant_id != tenant.id:
        abort(404)

    if rent_payment.status == "paid":
        flash("This period is already paid.", "info")
        return redirect(url_for("renter.dashboard"))

    investor_profile = tenant.unit.property_ref.owner_investor
    if not investor_profile:
        flash("This property has no landlord account connected for online payments yet.", "error")
        return redirect(url_for("renter.dashboard"))

    account = get_or_create_payment_account("investor_profile", investor_profile.id)
    if not account.is_ready_for_payments:
        flash("Your landlord hasn't finished connecting their Stripe account yet — online payment isn't available.", "error")
        return redirect(url_for("renter.dashboard"))

    outstanding = (rent_payment.amount_due or Decimal("0")) - (rent_payment.amount_paid or Decimal("0"))
    if outstanding <= 0:
        flash("There's no outstanding balance for this period.", "info")
        return redirect(url_for("renter.dashboard"))

    payment_request = rent_payment.payment_request
    if not payment_request or payment_request.status == "paid":
        payment_request = create_payment_request(
            account,
            title=f"Rent — {rent_payment.period_month.strftime('%B %Y')}",
            amount_cents=int(round(outstanding * 100)),
            client_name=tenant.full_name,
            client_email=current_user.email,
        )
        rent_payment.payment_request_id = payment_request.id
        db.session.commit()

    base = request.host_url.rstrip("/")
    success_url = base + url_for("renter.dashboard") + "?paid=1"
    cancel_url = base + url_for("renter.dashboard")

    try:
        checkout_url = create_checkout_session_for_request(payment_request, success_url, cancel_url)
    except PaymentsServiceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("renter.dashboard"))

    return redirect(checkout_url, code=303)
