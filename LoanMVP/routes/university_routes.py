"""
LoanMVP/routes/university_routes.py

Ravlo Academy — Flask integration
  GET  /academy/portal              → full-screen React app shell
  POST /academy/chat                → Anthropic API proxy (keeps key server-side)
  GET  /academy/business-plan       → AI Business Plan tool shell
  POST /academy/business-plan/generate → Anthropic proxy for business plan
  APP  context_processor            → injects university_access into every template

Auto-registered by LoanMVP/app.py blueprint scanner.
"""

import os
import requests as http
from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for
from flask_login import current_user, login_required
from LoanMVP.extensions import csrf

# ── Blueprint ──────────────────────────────────────────────────────────────
university_bp = Blueprint("university", __name__, url_prefix="/academy")

_ANTHROPIC_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
_ANTHROPIC_URL  = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VER  = "2023-06-01"
_DEFAULT_MODEL  = "claude-opus-4-5"       # override via JSX payload if needed
_MAX_TOKENS_CAP = 2000                     # safety cap — JSX requests 1 000

# ── Role → University tier mapping ─────────────────────────────────────────
#   elite   → Ravlo investors & partners (free, code: RAVLO-ELITE)
#   lending → Ravlo lending staff         (free, code: RAVLO-LENDING)
_ROLE_TIER = {
    "investor":      "elite",
    "partner":       "elite",
    "admin":         "elite",
    "master_admin":  "elite",
    "executive":     "elite",
    "loan_officer":  "lending",
    "lending_admin": "lending",
    "processor":     "lending",
    "underwriter":   "lending",
}

_TIER_META = {
    "elite": {
        "label":       "Elite Access",
        "code":        "RAVLO-ELITE",
        "badge":       "ELITE",
        "color":       "#D4AF6A",
        "bg":          "rgba(212,175,106,0.10)",
        "border":      "rgba(212,175,106,0.30)",
        "icon":        "◆",
        "description": "Ravlo Investors & Partners — Complimentary",
        "perks":       ["Unlimited AI Coaching", "All 6 Modules", "1-on-1 Success Plans", "Priority Support"],
    },
    "lending": {
        "label":       "Lending Team",
        "code":        "RAVLO-LENDING",
        "badge":       "TEAM",
        "color":       "#6AB4D4",
        "bg":          "rgba(106,180,212,0.10)",
        "border":      "rgba(106,180,212,0.30)",
        "icon":        "◈",
        "description": "Ravlo Lending Staff — Employment Benefit",
        "perks":       ["Unlimited AI Coaching", "Loan Modules", "Commercial Training", "Deal Review"],
    },
    "pro": {
        "label":       "Pro Access",
        "code":        "",
        "badge":       "PRO",
        "color":       "#B06AD4",
        "bg":          "rgba(176,106,212,0.10)",
        "border":      "rgba(176,106,212,0.30)",
        "icon":        "●",
        "description": "Independent Realtors & Investors — Active Subscriber",
        "perks":       ["Unlimited AI Coaching", "All Modules", "Success Plans", "Community Access"],
    },
    "starter": {
        "label":       "Starter Access",
        "code":        "",
        "badge":       "STARTER",
        "color":       "#6AD4A0",
        "bg":          "rgba(106,212,160,0.10)",
        "border":      "rgba(106,212,160,0.30)",
        "icon":        "○",
        "description": "New to Real Estate — Active Subscriber",
        "perks":       ["Core AI Coaching", "3 Modules", "Basic Success Plan"],
    },
}


def _university_access_for_user(user):
    """Return the tier meta dict for a logged-in user, or None.

    Priority: role-based free access > paid university_tier from Stripe.
    """
    try:
        if not user or not user.is_authenticated:
            return None

        # Role-based access (investors, partners, lending staff — free)
        role = (getattr(user, "role", "") or "").strip().lower()
        tier_key = _ROLE_TIER.get(role)

        # Paid tier from Stripe webhook
        if not tier_key:
            paid = (getattr(user, "university_tier", None) or "").strip().lower()
            if paid in _TIER_META:
                tier_key = paid

        if not tier_key:
            return None

        meta = dict(_TIER_META[tier_key])
        meta["tier_key"] = tier_key
        return meta
    except Exception:
        return None


def _user_display_name(user) -> str:
    """Best-effort display name from available user fields."""
    for attr in ("full_name", "first_name", "name"):
        val = (getattr(user, attr, None) or "").strip()
        if val:
            return val.title()
    email = getattr(user, "email", "") or ""
    return email.split("@")[0].title() or "Member"


# ── App-wide context processor ─────────────────────────────────────────────
# Injects `university_access` into EVERY template in the app so any settings
# page (investor, partner, employee) can {% include 'university/_access_card.html' %}
@university_bp.app_context_processor
def inject_university_access():
    return {"university_access": _university_access_for_user(current_user)}


# ── Portal shell ───────────────────────────────────────────────────────────
@university_bp.route("/portal")
@login_required
def portal():
    """Serves the full-screen React shell. Requires auth + active Academy tier."""
    access = _university_access_for_user(current_user)
    if not access:
        # No valid tier — bounce to academy page so they can subscribe
        return redirect(url_for("marketing.academy") + "#tiers")

    return render_template(
        "university/portal.html",
        server_tier=access["tier_key"],
        server_user=_user_display_name(current_user),
    )


# ── Business Plan tool ─────────────────────────────────────────────────────
@university_bp.route("/business-plan")
def business_plan():
    """AI Business Plan generator — standalone tool."""
    return render_template("academy/business_plan.html")


# ── Anthropic proxy ────────────────────────────────────────────────────────
@university_bp.route("/chat", methods=["POST"])
@csrf.exempt
def chat():
    """Proxy Anthropic API. Requires auth + active Academy tier."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Authentication required."}), 401
    if not _university_access_for_user(current_user):
        return jsonify({"error": "Academy access required."}), 403
    if not _ANTHROPIC_KEY:
        return jsonify({"error": "AI coach is not configured on this server."}), 503

    payload = request.get_json(silent=True) or {}
    messages = payload.get("messages", [])
    if not messages:
        return jsonify({"error": "messages are required"}), 400

    body = {
        "model":      payload.get("model", _DEFAULT_MODEL),
        "max_tokens": min(int(payload.get("max_tokens", 1000)), _MAX_TOKENS_CAP),
        "system":     payload.get("system", ""),
        "messages":   messages,
    }

    try:
        resp = http.post(
            _ANTHROPIC_URL,
            headers={
                "x-api-key":         _ANTHROPIC_KEY,
                "anthropic-version": _ANTHROPIC_VER,
                "content-type":      "application/json",
            },
            json=body,
            timeout=45,
        )
        return jsonify(resp.json()), resp.status_code

    except http.exceptions.Timeout:
        return jsonify({"error": "AI coach timed out. Please try again."}), 504
    except Exception as exc:
        current_app.logger.error("academy /chat error: %s", exc)
        return jsonify({"error": "Connection error. Please try again."}), 500


# ── Business Plan proxy ────────────────────────────────────────────────────
@university_bp.route("/business-plan/generate", methods=["POST"])
@csrf.exempt
def business_plan_generate():
    """Proxy Anthropic API for Business Plan tool. Requires auth + active Academy tier."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Authentication required."}), 401
    if not _university_access_for_user(current_user):
        return jsonify({"error": "Academy access required."}), 403
    if not _ANTHROPIC_KEY:
        return jsonify({"error": "AI coach is not configured on this server."}), 503

    payload = request.get_json(silent=True) or {}
    messages = payload.get("messages", [])
    if not messages:
        return jsonify({"error": "messages are required"}), 400

    body = {
        "model":      payload.get("model", _DEFAULT_MODEL),
        "max_tokens": min(int(payload.get("max_tokens", 1000)), _MAX_TOKENS_CAP),
        "system":     payload.get("system", ""),
        "messages":   messages,
    }

    try:
        resp = http.post(
            _ANTHROPIC_URL,
            headers={
                "x-api-key":         _ANTHROPIC_KEY,
                "anthropic-version": _ANTHROPIC_VER,
                "content-type":      "application/json",
            },
            json=body,
            timeout=60,
        )
        return jsonify(resp.json()), resp.status_code

    except http.exceptions.Timeout:
        return jsonify({"error": "Plan generation timed out. Please try again."}), 504
    except Exception as exc:
        current_app.logger.error("academy /business-plan/generate error: %s", exc)
        return jsonify({"error": "Connection error. Please try again."}), 500
