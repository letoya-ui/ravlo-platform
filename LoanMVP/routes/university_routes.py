"""
LoanMVP/routes/university_routes.py

Ravlo Academy — standalone AI learning platform, fully separate from the
main Ravlo investor platform.

Three paths into the portal (all enforced server-side):

  1. Platform role  — Ravlo investors, partners, and lending staff get free
                      access based on their Flask-Login user role.

  2. Stripe session — After a paid checkout, the portal's success-redirect
                      carries ?checkout=success&session_id=... and we
                      retrieve the Stripe session to set Flask session
                      ["academy_access"]. No platform account required.

  3. Access code    — POST /academy/activate validates a code server-side
                      and stores the tier in Flask session. Used for:
                      - Built-in codes (RAVLO-ELITE, RAVLO-LENDING)
                      - White-label company codes (ACADEMY_ACCESS_CODES env var,
                        format: "CODE1:tier,CODE2:tier")

Routes:
  GET  /academy/portal                  → React shell (tier injected from session)
  POST /academy/activate                → validate code, store Academy session
  POST /academy/chat                    → Anthropic proxy (checks session)
  GET  /academy/business-plan           → Business Plan tool shell
  POST /academy/business-plan/generate  → Anthropic proxy (checks session)

Auto-registered by LoanMVP/app.py blueprint scanner.
"""

import os
import requests as http
from flask import Blueprint, render_template, request, jsonify, current_app, session
from flask_login import current_user
from LoanMVP.extensions import csrf

university_bp = Blueprint("university", __name__, url_prefix="/academy")

_ANTHROPIC_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
_ANTHROPIC_URL  = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VER  = "2023-06-01"
_DEFAULT_MODEL  = "claude-opus-4-5"
_MAX_TOKENS_CAP = 2000

# ── Role → tier (platform users only) ─────────────────────────────────────
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

# ── Tier metadata (matches ACCESS_TIERS in the JSX) ───────────────────────
_TIER_META = {
    "elite": {
        "label":       "Elite Access",
        "badge":       "ELITE",
        "color":       "#D4AF6A",
        "description": "Ravlo Investors & Partners — Complimentary",
        "perks":       ["Unlimited AI Coaching", "All 6 Modules", "1-on-1 Success Plans", "Priority Support"],
    },
    "lending": {
        "label":       "Lending Team",
        "badge":       "TEAM",
        "color":       "#6AB4D4",
        "description": "Ravlo Lending Staff — Employment Benefit",
        "perks":       ["Unlimited AI Coaching", "Loan Modules", "Commercial Training", "Deal Review"],
    },
    "pro": {
        "label":       "Pro Access",
        "badge":       "PRO",
        "color":       "#B06AD4",
        "description": "Independent Realtors & Investors — Active Subscriber",
        "perks":       ["Unlimited AI Coaching", "All Modules", "Success Plans", "Community Access"],
    },
    "starter": {
        "label":       "Starter Access",
        "badge":       "STARTER",
        "color":       "#6AD4A0",
        "description": "New to Real Estate — Active Subscriber",
        "perks":       ["Core AI Coaching", "3 Modules", "Basic Success Plan"],
    },
}

# Built-in access codes (always active — no config required)
_BUILTIN_CODES = {
    "RAVLO-ELITE":    "elite",
    "RAVLO-LENDING":  "lending",
}


# ── Access helpers ─────────────────────────────────────────────────────────

def _get_company_codes() -> dict:
    """Return all valid codes → tier_key, merging built-ins + env var config.

    ACADEMY_ACCESS_CODES env format: "REMAX-TEAM:elite,ACME-LO:lending"
    White-label companies get a code; their staff enter it at the portal.
    """
    codes = dict(_BUILTIN_CODES)
    extra = (current_app.config.get("ACADEMY_ACCESS_CODES") or "").strip()
    for pair in extra.split(","):
        if ":" in pair:
            c, t = pair.split(":", 1)
            c, t = c.strip().upper(), t.strip().lower()
            if c and t in _TIER_META:
                codes[c] = t
    return codes


def _platform_access() -> tuple:
    """(tier_key, display_name) from Flask-Login user, or (None, None)."""
    try:
        if not current_user or not current_user.is_authenticated:
            return None, None
        role = (getattr(current_user, "role", "") or "").strip().lower()
        tier_key = _ROLE_TIER.get(role)
        if not tier_key:
            paid = (getattr(current_user, "university_tier", None) or "").strip().lower()
            if paid in _TIER_META:
                tier_key = paid
        if not tier_key:
            return None, None
        return tier_key, _user_display_name(current_user)
    except Exception:
        return None, None


def _standalone_access() -> tuple:
    """(tier_key, display_name) from Flask session['academy_access'], or (None, None)."""
    try:
        a = session.get("academy_access") or {}
        t = a.get("tier", "")
        if t in _TIER_META:
            return t, a.get("name", "Member")
    except Exception:
        pass
    return None, None


def _current_access() -> tuple:
    """(tier_key, display_name) from any source, or (None, None)."""
    tier, name = _platform_access()
    if tier:
        return tier, name
    return _standalone_access()


def _user_display_name(user) -> str:
    for attr in ("full_name", "first_name", "name"):
        val = (getattr(user, attr, None) or "").strip()
        if val:
            return val.title()
    email = getattr(user, "email", "") or ""
    return email.split("@")[0].title() or "Member"


def _activate_from_stripe_session(session_id: str):
    """Retrieve Stripe checkout session and store Academy access in Flask session."""
    try:
        import stripe as stripe_lib
        stripe_lib.api_key = current_app.config.get("STRIPE_SECRET_KEY", "")
        s = stripe_lib.checkout.Session.retrieve(session_id)
        tier = ((s.get("metadata") or {}).get("academy_tier") or "").lower()
        if tier in _TIER_META:
            details = s.get("customer_details") or {}
            email = details.get("email") or ""
            raw_name = details.get("name") or ""
            name = (raw_name or email.split("@")[0] or "Member").title()
            session["academy_access"] = {"tier": tier, "name": name, "email": email}
            session.permanent = True
    except Exception as exc:
        current_app.logger.warning("Academy post-checkout activation failed: %s", exc)


# ── App-wide context processor ─────────────────────────────────────────────
def _university_access_for_user(user):
    """Legacy helper used by the app-wide context processor."""
    try:
        if not user or not user.is_authenticated:
            return None
        role = (getattr(user, "role", "") or "").strip().lower()
        tier_key = _ROLE_TIER.get(role)
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


@university_bp.app_context_processor
def inject_university_access():
    return {"university_access": _university_access_for_user(current_user)}


# ── Portal shell ───────────────────────────────────────────────────────────

@university_bp.route("/portal")
def portal():
    """
    Academy portal. No platform login required.

    If the visitor has an active Academy session (any source), the tier is
    injected into window.RAVLO_ACADEMY before the JSX loads — it skips the
    code-entry screen and goes straight to onboarding or dashboard.

    If there is no session, the tier is null and the JSX shows the landing
    screen where visitors can enter an access code or click to subscribe.
    This is the correct flow for white-label company users and new visitors.
    """
    # Activate from Stripe checkout redirect (?checkout=success&session_id=...)
    if request.args.get("checkout") == "success":
        sid = request.args.get("session_id", "")
        if sid:
            _activate_from_stripe_session(sid)

    tier_key, display_name = _current_access()

    # Always serve the portal shell. The JSX handles the no-access UX.
    return render_template(
        "university/portal.html",
        server_tier=tier_key,
        server_user=display_name or "",
    )


# ── Code activation ────────────────────────────────────────────────────────

@university_bp.route("/activate", methods=["POST"])
@csrf.exempt
def activate():
    """
    Validate an access code server-side and store an Academy session.

    Called by the JSX landing screen when a user enters a code.
    Works for built-in codes, white-label company codes, and future
    per-seat codes.
    """
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip().upper()
    name = (data.get("name") or "Member").strip().title()

    if not code:
        return jsonify({"error": "Access code is required."}), 400

    tier_key = _get_company_codes().get(code)
    if not tier_key:
        return jsonify({"error": "Access code not recognized. Contact your Ravlo representative."}), 403

    session["academy_access"] = {"tier": tier_key, "name": name, "code": code}
    session.permanent = True
    return jsonify({"tier": tier_key, "name": name}), 200


# ── Business Plan tool ─────────────────────────────────────────────────────

@university_bp.route("/business-plan")
def business_plan():
    return render_template("academy/business_plan.html")


# ── Anthropic proxy — /academy/chat ───────────────────────────────────────

@university_bp.route("/chat", methods=["POST"])
@csrf.exempt
def chat():
    """Proxy Anthropic API. Validates Academy session before forwarding."""
    tier_key, _ = _current_access()
    if not tier_key:
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
        resp_data = resp.json()

        try:
            ai_text = (resp_data.get("content") or [{}])[0].get("text", "")
            tier_key, _ = _current_access()
            user_id = current_user.id if current_user.is_authenticated else None
            from LoanMVP.services.training_service import log_academy_chat
            log_academy_chat(
                messages=messages,
                ai_response=ai_text,
                tier=tier_key,
                feature="chat",
                system_prompt=body.get("system", ""),
                model=body.get("model", _DEFAULT_MODEL),
                user_id=user_id,
            )
        except Exception:
            pass

        return jsonify(resp_data), resp.status_code
    except http.exceptions.Timeout:
        return jsonify({"error": "AI coach timed out. Please try again."}), 504
    except Exception as exc:
        current_app.logger.error("academy /chat error: %s", exc)
        return jsonify({"error": "Connection error. Please try again."}), 500


# ── Anthropic proxy — /academy/business-plan/generate ─────────────────────

@university_bp.route("/business-plan/generate", methods=["POST"])
@csrf.exempt
def business_plan_generate():
    """Proxy Anthropic API for Business Plan tool. Validates Academy session."""
    tier_key, _ = _current_access()
    if not tier_key:
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
        resp_data = resp.json()

        try:
            ai_text = (resp_data.get("content") or [{}])[0].get("text", "")
            tier_key, _ = _current_access()
            user_id = current_user.id if current_user.is_authenticated else None
            from LoanMVP.services.training_service import log_academy_chat
            log_academy_chat(
                messages=messages,
                ai_response=ai_text,
                tier=tier_key,
                feature="business_plan",
                system_prompt=body.get("system", ""),
                model=body.get("model", _DEFAULT_MODEL),
                user_id=user_id,
            )
        except Exception:
            pass

        return jsonify(resp_data), resp.status_code
    except http.exceptions.Timeout:
        return jsonify({"error": "Plan generation timed out. Please try again."}), 504
    except Exception as exc:
        current_app.logger.error("academy /business-plan/generate error: %s", exc)
        return jsonify({"error": "Connection error. Please try again."}), 500
