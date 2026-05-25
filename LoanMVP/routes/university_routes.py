"""
LoanMVP/routes/university_routes.py

Ravlo University — Flask integration
  GET  /university/portal   → full-screen React app shell
  POST /university/chat     → Anthropic API proxy (keeps key server-side)

Auto-registered by LoanMVP/app.py blueprint scanner.
"""

import os
import requests as http
from flask import Blueprint, render_template, request, jsonify, current_app
from LoanMVP.extensions import csrf

# ── Blueprint ──────────────────────────────────────────────────────────────
university_bp = Blueprint("university", __name__, url_prefix="/university")

_ANTHROPIC_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
_ANTHROPIC_URL  = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VER  = "2023-06-01"
_DEFAULT_MODEL  = "claude-opus-4-5"       # override via JSX payload if needed
_MAX_TOKENS_CAP = 2000                     # safety cap — JSX requests 1 000


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
