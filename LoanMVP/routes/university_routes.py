"""
LoanMVP/routes/university_routes.py

Ravlo University — Flask integration
  GET  /university/portal   → full-screen React app shell
  POST /university/chat     → Anthropic API proxy (keeps key server-side)
  APP  context_processor    → injects university_access into every template

Auto-registered by LoanMVP/app.py blueprint scanner.
"""

import os
import requests as http
from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import current_user
from LoanMVP.extensions import csrf

# ── Blueprint ──────────────────────────────────────────────────────────────
university_bp = Blueprint("university", __name__, url_prefix="/university")

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
}


def _university_access_for_user(user):
    """Return the tier meta dict for a logged-in user, or None."""
    try:
        if not user or not user.is_authenticated:
            return None
        role = (getattr(user, "role", "") or "").strip().lower()
        tier_key = _ROLE_TIER.get(role)
        if not tier_key:
            return None
        meta = dict(_TIER_META[tier_key])
        meta["tier_key"] = tier_key
        return meta
    except Exception:
        return None


# ── App-wide context processor ─────────────────────────────────────────────
# Injects `university_access` into EVERY template in the app so any settings
# page (investor, partner, employee) can {% include 'university/_access_card.html' %}
@university_bp.app_context_processor
def inject_university_access():
    return {"university_access": _university_access_for_user(current_user)}


# ── Portal shell ───────────────────────────────────────────────────────────
@university_bp.route("/portal")
def portal():
    """Serves the full-screen React shell. Marked noindex — SEO lives at /university."""
    return render_template("university/portal.html")


# ── Anthropic proxy ────────────────────────────────────────────────────────
@university_bp.route("/chat", methods=["POST"])
@csrf.exempt
def chat():
    """
    Proxy Anthropic API so the key never hits the browser.
    Accepts the same JSON body the JSX sends:
      { model, max_tokens, system, messages }
    """
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
        current_app.logger.error("university /chat error: %s", exc)
        return jsonify({"error": "Connection error. Please try again."}), 500
