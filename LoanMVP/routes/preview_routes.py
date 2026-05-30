# LoanMVP/routes/preview_routes.py
"""
Preview account routes.
- Investors on subscription='preview' can browse the platform freely for 1 week.
- Subscription trial (1 more week) is handled by Stripe after subscribing.
- This blueprint handles: subscription requests, admin approval, provisioning, and trial expiry.
Auto-registered by app.py dynamic blueprint loader.
"""
from datetime import datetime, timedelta
import secrets

from flask import (
    Blueprint, current_app, flash, redirect,
    render_template, request, url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func
from werkzeug.security import generate_password_hash

from LoanMVP.extensions import db
from LoanMVP.models.user_model import User
from LoanMVP.models.admin import SubscriptionRequest

preview_bp = Blueprint("preview", __name__, url_prefix="/preview")

_ADMIN_ROLES = {"admin", "platform_admin", "master_admin", "lending_admin", "executive"}
_PREVIEW_TRIAL_DAYS = 7  # 1 week free preview; Stripe handles the subscription trial week


def _is_admin(user):
    return (getattr(user, "role", "") or "").strip().lower() in _ADMIN_ROLES


# ─── Trial expired ────────────────────────────────────────────────────────────

@preview_bp.route("/trial-expired")
@login_required
def trial_expired():
    return render_template("layouts/trial_expired.html")


# ─── Investor: submit subscription request ──────────────────────────────────────────────

@preview_bp.route("/request-subscription", methods=["POST"])
@login_required
def request_subscription():
    sub = (getattr(current_user, "subscription", "") or "").strip().lower()
    if sub != "preview":
        flash("This action is only available for preview accounts.", "warning")
        return redirect(url_for("investor.command_center"))

    existing = SubscriptionRequest.query.filter_by(
        user_id=current_user.id, status="pending"
    ).first()
    if existing:
        flash("You already have a pending request — we'll be in touch soon.", "info")
        return redirect(url_for("investor.command_center"))

    message = (request.form.get("message") or "").strip()
    plan_requested = (request.form.get("plan_requested") or "Core").strip()

    req = SubscriptionRequest(
        user_id=current_user.id,
        message=message or None,
        plan_requested=plan_requested,
        status="pending",
    )
    db.session.add(req)
    db.session.commit()

    _notify_admin_of_request(current_user, plan_requested, message)

    flash("Request submitted! We'll be in touch within 24 hours.", "success")
    return redirect(url_for("preview.subscription_requested"))


@preview_bp.route("/subscription-requested")
@login_required
def subscription_requested():
    return render_template("investor/subscription_requested.html", title="Request Submitted")


# ─── Admin: list requests ─────────────────────────────────────────────────────────────

@preview_bp.route("/admin/subscription-requests")
@login_required
def admin_subscription_requests():
    if not _is_admin(current_user):
        flash("Access denied.", "danger")
        return redirect(url_for("auth.login"))

    pending = (
        SubscriptionRequest.query
        .filter_by(status="pending")
        .order_by(SubscriptionRequest.created_at.desc())
        .all()
    )
    reviewed = (
        SubscriptionRequest.query
        .filter(SubscriptionRequest.status != "pending")
        .order_by(SubscriptionRequest.reviewed_at.desc())
        .limit(50)
        .all()
    )

    user_ids = {r.user_id for r in pending + reviewed}
    user_map = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()}

    return render_template(
        "admin/subscription_requests.html",
        pending=pending,
        reviewed=reviewed,
        user_map=user_map,
        title="Subscription Requests",
    )


# ─── Admin: approve ────────────────────────────────────────────────────────────────────

@preview_bp.route("/admin/subscription-requests/<int:req_id>/approve", methods=["POST"])
@login_required
def approve_subscription_request(req_id):
    if not _is_admin(current_user):
        flash("Access denied.", "danger")
        return redirect(url_for("auth.login"))

    req = SubscriptionRequest.query.get_or_404(req_id)
    investor = User.query.get(req.user_id)
    if not investor:
        flash("Investor not found.", "danger")
        return redirect(url_for("preview.admin_subscription_requests"))

    plan = (request.form.get("plan") or req.plan_requested or "Core").strip().title()
    investor.subscription_plan = plan
    # trial_ends_at is intentionally not set here — Stripe handles the subscription trial

    req.status = "approved"
    req.reviewed_by = current_user.id
    req.reviewed_at = datetime.utcnow()
    req.notes = (request.form.get("notes") or "").strip() or None

    try:
        from LoanMVP.services.subscriptions import sync_features_with_subscription
        sync_features_with_subscription(investor.id)
    except Exception as exc:
        current_app.logger.warning("sync_features failed after approval: %s", exc)

    db.session.commit()
    _notify_investor_approved(investor, plan)

    flash(f"{investor.full_name} upgraded to {plan}.", "success")
    return redirect(url_for("preview.admin_subscription_requests"))


# ─── Admin: deny ───────────────────────────────────────────────────────────────────────

@preview_bp.route("/admin/subscription-requests/<int:req_id>/deny", methods=["POST"])
@login_required
def deny_subscription_request(req_id):
    if not _is_admin(current_user):
        flash("Access denied.", "danger")
        return redirect(url_for("auth.login"))

    req = SubscriptionRequest.query.get_or_404(req_id)
    req.status = "denied"
    req.reviewed_by = current_user.id
    req.reviewed_at = datetime.utcnow()
    req.notes = (request.form.get("notes") or "").strip() or None
    db.session.commit()

    flash("Request denied.", "info")
    return redirect(url_for("preview.admin_subscription_requests"))


# ─── Admin: grant preview access ──────────────────────────────────────────────────────

@preview_bp.route("/admin/grant-preview", methods=["POST"])
@login_required
def grant_preview_access():
    if not _is_admin(current_user):
        flash("Access denied.", "danger")
        return redirect(url_for("auth.login"))

    email = (request.form.get("email") or "").strip().lower()
    first_name = (request.form.get("first_name") or "").strip()
    last_name = (request.form.get("last_name") or "").strip()

    if not email:
        flash("Email is required.", "warning")
        return redirect(url_for("preview.admin_subscription_requests"))

    trial_end = datetime.utcnow() + timedelta(days=_PREVIEW_TRIAL_DAYS)

    existing = User.query.filter(func.lower(User.email) == email).first()
    if existing:
        existing.subscription = "preview"
        existing.trial_ends_at = trial_end
        db.session.commit()
        flash(f"Preview access granted to {email} (1-week trial).", "success")
        return redirect(url_for("preview.admin_subscription_requests"))

    temp_password = secrets.token_urlsafe(12)
    user = User(
        first_name=first_name or None,
        last_name=last_name or None,
        username=f"{first_name} {last_name}".strip() or email,
        email=email,
        role="investor",
        subscription="preview",
        trial_ends_at=trial_end,
        is_active=True,
        invite_accepted=True,
        onboarding_complete=True,
    )
    user.set_password(temp_password)
    db.session.add(user)
    db.session.flush()

    from LoanMVP.models.investor_models import InvestorProfile
    profile = InvestorProfile(
        user_id=user.id,
        full_name=f"{first_name} {last_name}".strip() or email,
        email=email,
    )
    db.session.add(profile)
    db.session.commit()

    _send_preview_welcome(email, first_name, temp_password)

    flash(f"Preview account created for {email}. Welcome email sent (1-week trial).", "success")
    return redirect(url_for("preview.admin_subscription_requests"))


# ─── Email helpers ───────────────────────────────────────────────────────────────────

def _notify_admin_of_request(investor, plan_requested, message):
    try:
        from LoanMVP.app import mail
        from flask_mail import Message as MailMessage
        admin_email = (
            current_app.config.get("OWNER_ADMIN_EMAIL")
            or current_app.config.get("MAIL_DEFAULT_SENDER")
        )
        if not admin_email:
            return
        msg = MailMessage(
            subject=f"[Ravlo] Subscription Request — {investor.full_name}",
            recipients=[admin_email],
            body=(
                f"Investor: {investor.full_name} ({investor.email})\n"
                f"Plan requested: {plan_requested}\n"
                f"Message: {message or 'N/A'}\n\n"
                f"Review: {url_for('preview.admin_subscription_requests', _external=True)}"
            ),
        )
        mail.send(msg)
    except Exception as exc:
        current_app.logger.warning("admin notify email failed: %s", exc)


def _notify_investor_approved(investor, plan):
    try:
        from LoanMVP.app import mail
        from flask_mail import Message as MailMessage
        msg = MailMessage(
            subject="Your Ravlo subscription is now active!",
            recipients=[investor.email],
            body=(
                f"Hi {investor.full_name},\n\n"
                f"Your subscription request has been approved — you're now on the {plan} plan.\n\n"
                f"Log in: {url_for('investor.command_center', _external=True)}\n\n"
                f"The Ravlo Team"
            ),
        )
        mail.send(msg)
    except Exception as exc:
        current_app.logger.warning("investor approval email failed: %s", exc)


def _send_preview_welcome(email, first_name, temp_password):
    try:
        from LoanMVP.app import mail
        from flask_mail import Message as MailMessage
        login_url = url_for("auth.login", _external=True)
        reset_url = url_for("auth.forgot_password", _external=True)
        msg = MailMessage(
            subject="You've been invited to preview Ravlo",
            recipients=[email],
            body=(
                f"Hi {first_name or 'there'},\n\n"
                f"You have 1 week of free preview access to Ravlo — the investor OS for real estate capital, deal analysis, and funding.\n\n"
                f"Log in: {login_url}\n"
                f"Email: {email}\n"
                f"Temporary password: {temp_password}\n\n"
                f"Change your password after logging in: {reset_url}\n\n"
                f"When you're ready for full access, click 'Request Full Access' from your dashboard.\n\n"
                f"The Ravlo Team"
            ),
        )
        mail.send(msg)
    except Exception as exc:
        current_app.logger.warning("preview welcome email failed: %s", exc)
