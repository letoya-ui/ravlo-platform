"""
Preview account management — grant free 15-day access, handle trial expiry,
process subscription requests from preview users.
"""

import secrets
from datetime import datetime, timedelta

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from flask_mail import Message as MailMessage
from werkzeug.security import generate_password_hash

from LoanMVP.app import mail
from LoanMVP.extensions import db, csrf
from LoanMVP.models.user_model import User
from LoanMVP.models.admin import SubscriptionRequest

_PREVIEW_TRIAL_DAYS = 15

preview_bp = Blueprint("preview", __name__, url_prefix="/preview")


# ---------------------------------------------------------
# Trial-expired wall
# ---------------------------------------------------------

@preview_bp.route("/trial-expired")
def trial_expired():
    return render_template("layouts/trial_expired.html")


# ---------------------------------------------------------
# Public: grant preview access (called from admin or script)
# ---------------------------------------------------------

def grant_preview_access(user: User) -> None:
    """Set subscription=preview and start the 15-day trial clock."""
    user.subscription = "preview"
    user.trial_ends_at = datetime.utcnow() + timedelta(days=_PREVIEW_TRIAL_DAYS)


# ---------------------------------------------------------
# Admin-initiated: create a new preview investor account
# ---------------------------------------------------------

@preview_bp.route("/create", methods=["POST"])
@login_required
def create_preview_account():
    """Admin endpoint to create a preview investor account and email credentials."""
    if (current_user.role or "").strip().lower() not in (
        "admin", "platform_admin", "master_admin", "lending_admin"
    ):
        return jsonify({"error": "Forbidden"}), 403

    first_name = (request.form.get("first_name") or "").strip()
    last_name = (request.form.get("last_name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()

    if not email:
        flash("Email is required.", "warning")
        return redirect(url_for("admin.dashboard"))

    existing = User.query.filter_by(email=email).first()
    if existing:
        flash(f"User {email} already exists.", "warning")
        return redirect(url_for("admin.dashboard"))

    temp_password = secrets.token_urlsafe(10)
    user = User(
        first_name=first_name or None,
        last_name=last_name or None,
        email=email,
        role="investor",
        is_active=True,
        onboarding_complete=True,
        invite_accepted=True,
    )
    user.set_password(temp_password)
    grant_preview_access(user)
    db.session.add(user)
    db.session.commit()

    _send_preview_welcome(user, temp_password)
    flash(f"Preview account created for {email}.", "success")
    return redirect(url_for("admin.dashboard"))


# ---------------------------------------------------------
# Subscription request (preview user clicks "Request Access")
# ---------------------------------------------------------

@preview_bp.route("/request-access", methods=["POST"])
@csrf.exempt
@login_required
def request_full_access():
    plan = (request.form.get("plan") or "Core").strip()
    message = (request.form.get("message") or "").strip()

    existing = SubscriptionRequest.query.filter_by(
        user_id=current_user.id, status="pending"
    ).first()
    if not existing:
        sr = SubscriptionRequest(
            user_id=current_user.id,
            plan_requested=plan,
            message=message or None,
        )
        db.session.add(sr)
        db.session.commit()
        _notify_admin_subscription_request(current_user, plan)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True})
    flash("Your request has been submitted. We'll reach out shortly.", "success")
    return redirect(request.referrer or url_for("investor.command_center"))


# ---------------------------------------------------------
# Admin: approve subscription request
# ---------------------------------------------------------

@preview_bp.route("/approve/<int:request_id>", methods=["POST"])
@login_required
def approve_subscription_request(request_id):
    if (current_user.role or "").strip().lower() not in (
        "admin", "platform_admin", "master_admin", "lending_admin"
    ):
        return jsonify({"error": "Forbidden"}), 403

    sr = SubscriptionRequest.query.get_or_404(request_id)
    sr.status = "approved"
    sr.reviewed_by = current_user.id
    sr.reviewed_at = datetime.utcnow()

    user = sr.user
    plan_slug = (sr.plan_requested or "core").strip().lower()
    alias = {"core": "core", "explorer": "core", "operator": "operator", "pro": "operator"}
    user.subscription = alias.get(plan_slug, "core")
    user.trial_ends_at = None  # trial replaced by paid subscription

    db.session.commit()

    flash(f"Approved {user.email} on {user.subscription} plan.", "success")
    return redirect(url_for("admin.dashboard"))


# ---------------------------------------------------------
# Email helpers
# ---------------------------------------------------------

def _send_preview_welcome(user: User, temp_password: str) -> None:
    try:
        name = user.first_name or user.email
        msg = MailMessage(
            subject="Your Ravlo Preview Account is Ready",
            recipients=[user.email],
        )
        msg.html = f"""
        <div style="font-family:Inter,sans-serif;max-width:560px;margin:0 auto;padding:32px 24px;color:#0f1117;">
          <img src="https://ravlohq.com/static/images/ravlo-logo-dark.png"
               alt="Ravlo" style="height:32px;margin-bottom:28px;">
          <h2 style="font-size:22px;font-weight:700;margin:0 0 12px;">
            Welcome to Ravlo, {name}!
          </h2>
          <p style="font-size:15px;line-height:1.6;color:#374151;">
            Your free <strong>2-week preview account</strong> is all set.
            Explore the Investor OS, run deal analyses, and see what Ravlo can do for your portfolio.
          </p>
          <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;padding:20px 24px;margin:24px 0;">
            <p style="margin:0 0 6px;font-size:13px;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;">Your login</p>
            <p style="margin:0 0 4px;font-size:15px;"><strong>Email:</strong> {user.email}</p>
            <p style="margin:0;font-size:15px;"><strong>Temporary password:</strong> {temp_password}</p>
          </div>
          <a href="https://ravlohq.com/auth/login"
             style="display:inline-block;background:#1a56db;color:#fff;font-weight:600;padding:12px 28px;border-radius:8px;text-decoration:none;font-size:15px;">
            Log In to Ravlo
          </a>
          <p style="margin-top:28px;font-size:13px;color:#9ca3af;">
            Your preview expires in 15 days. Questions? Reply to this email — we read everything.
          </p>
        </div>
        """
        mail.send(msg)
    except Exception as e:
        print(f"[preview] welcome email failed: {e}")


def _notify_admin_subscription_request(user: User, plan: str) -> None:
    try:
        from LoanMVP.routes.auth import _owner_admin_email
        admin_email = _owner_admin_email()
        if not admin_email:
            return
        msg = MailMessage(
            subject=f"[Ravlo] Subscription request — {user.email}",
            recipients=[admin_email],
        )
        msg.body = (
            f"User {user.first_name or ''} {user.last_name or ''} <{user.email}> "
            f"has requested a {plan} subscription upgrade.\n\n"
            f"Review at https://ravlohq.com/admin/dashboard"
        )
        mail.send(msg)
    except Exception as e:
        print(f"[preview] admin notification failed: {e}")
