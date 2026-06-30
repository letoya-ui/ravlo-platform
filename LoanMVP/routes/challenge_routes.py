"""
LoanMVP/routes/challenge_routes.py

Self-service challenge sign-up flow for Ravlo challenges.
Handles account creation, role assignment, and trial activation in one step.

Routes:
  GET  /challenge/<slug>          → marketing-style sign-up page
  POST /challenge/<slug>/join     → create/login account + activate trial
"""

from datetime import datetime, timedelta

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user

from LoanMVP.extensions import db
from LoanMVP.models.user_model import User

challenge_bp = Blueprint("challenge", __name__, url_prefix="/challenge")

# ── Challenge catalogue ──────────────────────────────────────────────────────
# slug → config
_CHALLENGES = {
    "investor": {
        "title":        "The 5-Investor Challenge",
        "tagline":      "We're turning 5 people into real estate investors.",
        "description":  "Get full platform access — Academy, Investor OS, every studio tool — free for 30 days. "
                        "Your only job: learn the craft, find a deal, run the numbers.",
        "cta":          "Start the Challenge",
        "spots":        "5 Spots Open",
        "trial_days":   30,
        "role":         "investor",
        "color":        "#5FA8FF",
        "success_url":  "investor.command_center",
        "perks": [
            "Full Investor OS access",
            "Ravlo Academy — all courses",
            "Deal Analyzer & Studio tools",
            "AI property research",
            "30 days, no credit card",
        ],
    },
    "lending": {
        "title":        "The Lending Challenge",
        "tagline":      "A smoother way to do business.",
        "description":  "We're choosing 5 lending professionals to experience how Ravlo Lending OS "
                        "streamlines every step of the loan process. One platform. One workflow.",
        "cta":          "Take the Challenge",
        "spots":        "5 Spots Open",
        "trial_days":   90,
        "role":         "loan_officer",
        "color":        "#a78bfa",
        "success_url":  "marketing.enter",
        "perks": [
            "Full Lending OS access",
            "Borrower pipeline management",
            "AI document processing",
            "Team workflow tools",
            "Up to 3 months free",
        ],
    },
}


def _get_challenge(slug):
    return _CHALLENGES.get(slug)


@challenge_bp.route("/<slug>", methods=["GET"])
def join_page(slug):
    ch = _get_challenge(slug)
    if not ch:
        flash("That challenge doesn't exist.", "warning")
        return redirect(url_for("marketing.home"))

    # Already in — send them to their dashboard
    if current_user.is_authenticated and current_user.trial_ends_at:
        return redirect(url_for(ch["success_url"]))

    return render_template(
        "marketing/challenge_join.html",
        ch=ch,
        slug=slug,
    )


@challenge_bp.route("/<slug>/join", methods=["POST"])
def join(slug):
    ch = _get_challenge(slug)
    if not ch:
        flash("That challenge doesn't exist.", "warning")
        return redirect(url_for("marketing.home"))

    full_name = (request.form.get("full_name") or "").strip()
    email     = (request.form.get("email") or "").strip().lower()
    password  = request.form.get("password") or ""

    if not email or not full_name:
        flash("Please fill in your name and email.", "danger")
        return render_template("marketing/challenge_join.html", ch=ch, slug=slug)

    # ── Logged-in user joining ───────────────────────────────────────────
    if current_user.is_authenticated:
        user = current_user._get_current_object()
    else:
        # Try to find existing account
        user = User.query.filter_by(email=email).first()

        if user:
            # Existing account — validate password
            if not password or not user.check_password(password):
                flash("We found an account with that email. Please enter your password to continue.", "warning")
                return render_template("marketing/challenge_join.html", ch=ch, slug=slug,
                                       prefill_email=email, prefill_name=full_name, show_password=True)
            login_user(user, remember=True)
        else:
            # New account — password required
            if not password or len(password) < 8:
                flash("Please choose a password (at least 8 characters).", "danger")
                return render_template("marketing/challenge_join.html", ch=ch, slug=slug,
                                       prefill_email=email, prefill_name=full_name)

            parts = full_name.split(None, 1)
            user = User(
                first_name  = parts[0] if parts else full_name,
                last_name   = parts[1] if len(parts) > 1 else "",
                username    = full_name,
                email       = email,
                role        = ch["role"],
                is_active   = True,
                subscription= "free",
            )
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            login_user(user, remember=True)

    # ── Activate trial ───────────────────────────────────────────────────
    if user.trial_ends_at is not None:
        flash("You've already used a challenge trial on this account.", "info")
        return redirect(url_for(ch["success_url"]))

    user.subscription  = "preview"
    user.trial_ends_at = datetime.utcnow() + timedelta(days=ch["trial_days"])

    # Ensure role is set correctly
    if user.role not in ("admin", "platform_admin", "master_admin"):
        user.role = ch["role"]

    try:
        from LoanMVP.services.subscriptions import sync_features_with_subscription
        db.session.flush()
        sync_features_with_subscription(user.id)
    except Exception:
        current_app.logger.exception("[challenge.join] sync_features failed")

    db.session.commit()

    days = ch["trial_days"]
    flash(
        f"You're in! Your {days}-day challenge starts now — welcome to Ravlo.",
        "success",
    )
    return redirect(url_for(ch["success_url"]))
