"""
LoanMVP/routes/challenge_routes.py

Self-service challenge sign-up flow for Ravlo challenges.
Handles account creation, role assignment, and trial activation in one step.
Enforces a hard cap of MAX_SPOTS per challenge.

Routes:
  GET  /challenge/<slug>          → sign-up page (shows spots remaining)
  POST /challenge/<slug>/join     → create/login account + activate trial
"""

from datetime import datetime, timedelta

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user

from LoanMVP.extensions import db
from LoanMVP.models.user_model import User
from LoanMVP.models.company_finance_models import ChallengeEnrollment

challenge_bp = Blueprint("challenge", __name__, url_prefix="/challenge")

MAX_SPOTS = 5

_CHALLENGES = {
    "investor": {
        "title":       "The 5-Investor Challenge",
        "tagline":     "We're turning 5 people into real estate investors.",
        "description": "Get full platform access — Academy, Investor OS, every studio tool — free for 30 days. "
                       "Your only job: learn the craft, find a deal, run the numbers.",
        "cta":         "Start the Challenge",
        "trial_days":  30,
        "role":        "investor",
        "color":       "#5FA8FF",
        "success_url": "investor.command_center",
        "perks": [
            "Full Investor OS access",
            "Ravlo Academy — all courses",
            "Deal Analyzer & Studio tools",
            "AI property research",
            "30 days, no credit card",
        ],
    },
    "lending": {
        "title":       "The Lending Challenge",
        "tagline":     "A smoother way to do business.",
        "description": "We're choosing 5 lending professionals to experience how Ravlo Lending OS "
                       "streamlines every step of the loan process. One platform. One workflow.",
        "cta":         "Take the Challenge",
        "trial_days":  90,
        "role":        "loan_officer",
        "color":       "#a78bfa",
        "success_url": "marketing.enter",
        "perks": [
            "Full Lending OS access",
            "Borrower pipeline management",
            "AI document processing",
            "Team workflow tools",
            "Up to 3 months free",
        ],
    },
}


def _enrollment_count(slug):
    try:
        return ChallengeEnrollment.query.filter_by(slug=slug).count()
    except Exception:
        db.session.rollback()
        return 0


def _already_enrolled(user_id, slug):
    try:
        return ChallengeEnrollment.query.filter_by(user_id=user_id, slug=slug).first() is not None
    except Exception:
        db.session.rollback()
        return False


@challenge_bp.route("/<slug>", methods=["GET"])
def join_page(slug):
    ch = _CHALLENGES.get(slug)
    if not ch:
        flash("That challenge doesn't exist.", "warning")
        return redirect(url_for("marketing.home"))

    enrolled   = _enrollment_count(slug)
    spots_left = max(0, MAX_SPOTS - enrolled)
    full       = spots_left == 0

    # Already enrolled — send to dashboard
    if current_user.is_authenticated and _already_enrolled(current_user.id, slug):
        return redirect(url_for(ch["success_url"]))

    return render_template(
        "marketing/challenge_join.html",
        ch=ch,
        slug=slug,
        spots_left=spots_left,
        full=full,
        enrolled=enrolled,
    )


@challenge_bp.route("/<slug>/join", methods=["POST"])
def join(slug):
    ch = _CHALLENGES.get(slug)
    if not ch:
        flash("That challenge doesn't exist.", "warning")
        return redirect(url_for("marketing.home"))

    # Hard cap check
    enrolled   = _enrollment_count(slug)
    spots_left = max(0, MAX_SPOTS - enrolled)
    if spots_left == 0:
        flash("All spots for this challenge have been filled. Check back for the next round.", "warning")
        return render_template("marketing/challenge_join.html", ch=ch, slug=slug,
                               spots_left=0, full=True, enrolled=enrolled)

    full_name = (request.form.get("full_name") or "").strip()
    email     = (request.form.get("email") or "").strip().lower()
    password  = request.form.get("password") or ""

    if not email or not full_name:
        flash("Please fill in your name and email.", "danger")
        return render_template("marketing/challenge_join.html", ch=ch, slug=slug,
                               spots_left=spots_left, full=False, enrolled=enrolled)

    # ── Resolve user ─────────────────────────────────────────────────────
    if current_user.is_authenticated:
        user = current_user._get_current_object()
    else:
        user = User.query.filter_by(email=email).first()
        if user:
            if not password or not user.check_password(password):
                flash("We found an account with that email. Enter your password to continue.", "warning")
                return render_template("marketing/challenge_join.html", ch=ch, slug=slug,
                                       prefill_email=email, prefill_name=full_name,
                                       show_password=True, spots_left=spots_left,
                                       full=False, enrolled=enrolled)
            login_user(user, remember=True)
        else:
            if not password or len(password) < 8:
                flash("Please choose a password (at least 8 characters).", "danger")
                return render_template("marketing/challenge_join.html", ch=ch, slug=slug,
                                       prefill_email=email, prefill_name=full_name,
                                       spots_left=spots_left, full=False, enrolled=enrolled)
            parts = full_name.split(None, 1)
            user = User(
                first_name   = parts[0] if parts else full_name,
                last_name    = parts[1] if len(parts) > 1 else "",
                username     = full_name,
                email        = email,
                role         = ch["role"],
                is_active    = True,
                subscription = "free",
            )
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            login_user(user, remember=True)

    # ── Already enrolled in this challenge ───────────────────────────────
    if _already_enrolled(user.id, slug):
        flash("You're already enrolled in this challenge.", "info")
        return redirect(url_for(ch["success_url"]))

    # ── Activate trial ───────────────────────────────────────────────────
    if user.trial_ends_at is None:
        user.subscription  = "preview"
        user.trial_ends_at = datetime.utcnow() + timedelta(days=ch["trial_days"])
        if user.role not in ("admin", "platform_admin", "master_admin", "lending_admin", "executive"):
            user.role = ch["role"]
        try:
            from LoanMVP.services.subscriptions import sync_features_with_subscription
            db.session.flush()
            sync_features_with_subscription(user.id)
        except Exception:
            current_app.logger.exception("[challenge.join] sync_features failed")

    # ── Record enrollment ────────────────────────────────────────────────
    enrollment = ChallengeEnrollment(user_id=user.id, slug=slug)
    db.session.add(enrollment)
    db.session.commit()

    flash(f"You're in! Your {ch['trial_days']}-day challenge starts now — welcome to Ravlo.", "success")
    return redirect(url_for(ch["success_url"]))
