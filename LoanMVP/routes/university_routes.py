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
import json
import re
import requests as http
from flask import Blueprint, render_template, request, jsonify, current_app, session
from flask_login import current_user
from LoanMVP.extensions import csrf
from LoanMVP.utils.safe_http import safe_call

university_bp = Blueprint("university", __name__, url_prefix="/academy")

_ANTHROPIC_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
_ANTHROPIC_URL  = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VER  = "2023-06-01"
_DEFAULT_MODEL  = "claude-opus-4-8"
_MAX_TOKENS_CAP = 2000

# ── Role → tier (platform users only) ─────────────────────────────────────
_ROLE_TIER = {
    "investor":      "elite",
    "partner":       "elite",
    "admin":         "elite",
    "master_admin":  "elite",
    "platform_admin": "elite",
    "executive":     "elite",
    "loan_officer":  "lending",
    "lending_admin": "lending",
    "processor":     "lending",
    "underwriter":   "lending",
    "realtor":       "elite",
    "property_mgmt": "elite",
    "contractor":    "elite",
    "account_executive": "elite",
}

# ── Role → track (null = unrestricted) ─────────────────────────────────────
_ROLE_TRACK = {
    "investor":      "investor",
    "partner":       "investor",
    "loan_officer":  "lending",
    "lending_admin": "lending",
    "processor":     "lending",
    "underwriter":   "lending",
    "realtor":       "realtor",
    "property_mgmt": "property_mgmt",
    "contractor":    "contractor",
    "admin":         "operations",
    "account_executive": "account_executive",
    # master_admin/executive see all tracks — no restriction
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
    """(tier_key, display_name, allowed_track) from Flask-Login user, or (None, None, None)."""
    try:
        if not current_user or not current_user.is_authenticated:
            return None, None, None
        role = (getattr(current_user, "role", "") or "").strip().lower()
        tier_key = _ROLE_TIER.get(role)
        if not tier_key:
            paid = (getattr(current_user, "university_tier", None) or "").strip().lower()
            if paid in _TIER_META:
                tier_key = paid
        if not tier_key:
            return None, None, None
        allowed_track = _ROLE_TRACK.get(role)  # None = unrestricted
        return tier_key, _user_display_name(current_user), allowed_track
    except Exception:
        current_app.logger.exception("_platform_access failed")
        return None, None, None


def _standalone_access() -> tuple:
    """(tier_key, display_name, allowed_track) from Flask session, or (None, None, None)."""
    try:
        a = session.get("academy_access") or {}
        t = a.get("tier", "")
        if t in _TIER_META:
            track = a.get("allowed_track") or None
            return t, a.get("name", "Member"), track
    except Exception:
        pass
    return None, None, None


def _current_access() -> tuple:
    """(tier_key, display_name, allowed_track) from any source, or (None, None, None)."""
    tier, name, track = _platform_access()
    if tier:
        return tier, name, track
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

    tier_key, display_name, allowed_track = _current_access()

    # Always serve the portal shell. The JSX handles the no-access UX.
    return render_template(
        "university/portal.html",
        server_tier=tier_key,
        server_user=display_name or "",
        server_track=allowed_track,
    )


# ── Code activation ────────────────────────────────────────────────────────

@university_bp.route("/activate", methods=["POST"])
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
def chat():
    """Proxy Anthropic API. Validates Academy session before forwarding."""
    tier_key, _, _track = _current_access()
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
        resp = safe_call(
            http.post,
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
            tier_key, _, _track = _current_access()
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
            from LoanMVP.services.ravlo_memory_service import log_ai_exchange
            log_ai_exchange(
                module="academy",
                feature="chat",
                prompt=json.dumps(messages, default=str)[:4000],
                response=ai_text,
                user_id=user_id,
                role_view=tier_key,
                provider="anthropic",
                model=body.get("model", _DEFAULT_MODEL),
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
def business_plan_generate():
    """Proxy Anthropic API for Business Plan tool. Validates Academy session."""
    tier_key, _, _track = _current_access()
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
        resp = safe_call(
            http.post,
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
            tier_key, _, _track = _current_access()
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
            from LoanMVP.services.ravlo_memory_service import log_ai_exchange
            log_ai_exchange(
                module="academy",
                feature="business_plan",
                prompt=json.dumps(messages, default=str)[:4000],
                response=ai_text,
                user_id=user_id,
                role_view=tier_key,
                provider="anthropic",
                model=body.get("model", _DEFAULT_MODEL),
            )
        except Exception:
            pass

        return jsonify(resp_data), resp.status_code
    except http.exceptions.Timeout:
        return jsonify({"error": "Plan generation timed out. Please try again."}), 504
    except Exception as exc:
        current_app.logger.error("academy /business-plan/generate error: %s", exc)
        return jsonify({"error": "Connection error. Please try again."}), 500


# ── Lesson content — generate once, cache forever ─────────────────────────

_LESSON_CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "static", "lesson_content_cache.json")

def _load_lesson_cache() -> dict:
    try:
        with open(_LESSON_CACHE_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_lesson_cache(cache: dict):
    try:
        os.makedirs(os.path.dirname(_LESSON_CACHE_PATH), exist_ok=True)
        with open(_LESSON_CACHE_PATH, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception as exc:
        current_app.logger.error("lesson cache write error: %s", exc)

def _fix_embedded_quotes(text: str, field: str) -> str:
    """Walk inside a named JSON string field and escape any bare double-quotes.

    The LLM sometimes outputs unescaped " inside a long string value (e.g. the
    'content' field).  Standard json.loads() fails; _escape_strings() can't fix
    it because unescaped quotes flip its in_string state.  This helper locates
    the field, then scans forward byte-by-byte treating an unescaped " as a
    closing-quote only when the look-ahead shows it is followed by the next JSON
    key or closing brace.
    """
    m = re.search(r'"' + re.escape(field) + r'"\s*:\s*"', text)
    if not m:
        return text
    pos = m.end()
    result = [text[:pos]]
    i = pos
    n = len(text)
    while i < n:
        c = text[i]
        if c == '\\' and i + 1 < n:
            result.append(c)
            result.append(text[i + 1])
            i += 2
            continue
        if c == '"':
            lookahead = text[i + 1: i + 60].lstrip()
            is_closing = lookahead.startswith('}') or bool(
                re.match(r',\s*"(?:keyPoints|quiz|objectives|content)"', lookahead)
            )
            if is_closing:
                result.append(c)
                result.append(text[i + 1:])
                return ''.join(result)
            else:
                result.append('\\"')
                i += 1
                continue
        result.append(c)
        i += 1
    return ''.join(result)


def _parse_ai_json(raw: str) -> dict:
    """Parse JSON from AI with aggressive repair for common LLM output issues."""
    # Attempt 1: direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Attempt 2: escape literal newlines/tabs inside string values
    def _escape_strings(text: str) -> str:
        chars = list(text)
        in_string = False
        escape_next = False
        out = []
        for ch in chars:
            if escape_next:
                out.append(ch)
                escape_next = False
            elif ch == '\\' and in_string:
                out.append(ch)
                escape_next = True
            elif ch == '"':
                in_string = not in_string
                out.append(ch)
            elif in_string and ch == '\n':
                out.append('\\n')
            elif in_string and ch == '\r':
                out.append('\\r')
            elif in_string and ch == '\t':
                out.append('\\t')
            else:
                out.append(ch)
        return ''.join(out)

    escaped = _escape_strings(raw)
    try:
        return json.loads(escaped)
    except json.JSONDecodeError:
        pass

    # Attempt 3: repair truncated JSON (close unclosed strings/arrays/objects)
    def _repair_truncated(text: str) -> str:
        repaired = text.rstrip()
        # If it ends mid-string, close the string
        in_str = False
        esc = False
        for ch in repaired:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = not in_str
        if in_str:
            repaired += '"'
        # Close open brackets/braces
        stack = []
        in_str2 = False
        esc2 = False
        for ch in repaired:
            if esc2:
                esc2 = False
                continue
            if ch == '\\' and in_str2:
                esc2 = True
                continue
            if ch == '"':
                in_str2 = not in_str2
                continue
            if in_str2:
                continue
            if ch in ('{', '['):
                stack.append('}' if ch == '{' else ']')
            elif ch in ('}', ']'):
                if stack:
                    stack.pop()
        # Remove trailing comma before closing
        repaired = repaired.rstrip()
        if repaired.endswith(','):
            repaired = repaired[:-1]
        repaired += ''.join(reversed(stack))
        return repaired

    repaired = _repair_truncated(escaped)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    # Attempt 4: try extracting from first { to handle any preamble
    match = re.search(r'\{', raw)
    if match:
        candidate = raw[match.start():]
        candidate = _escape_strings(candidate)
        candidate = _repair_truncated(candidate)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # Attempt 5: fix unescaped double-quotes inside the 'content' field, then
    # re-run newline escaping and truncation repair.
    fixed5 = _fix_embedded_quotes(raw, "content")
    fixed5 = _escape_strings(fixed5)
    try:
        return json.loads(fixed5)
    except json.JSONDecodeError:
        pass

    fixed5r = _repair_truncated(fixed5)
    try:
        return json.loads(fixed5r)
    except json.JSONDecodeError:
        pass

    # Attempt 6: same fix applied to the candidate extracted from attempt 4
    match = re.search(r'\{', raw)
    if match:
        cand6 = raw[match.start():]
        cand6 = _fix_embedded_quotes(cand6, "content")
        cand6 = _escape_strings(cand6)
        cand6 = _repair_truncated(cand6)
        try:
            return json.loads(cand6)
        except json.JSONDecodeError:
            pass

    # All repair attempts failed
    raise json.JSONDecodeError("All JSON repair attempts failed", raw, 0)


def _generate_lesson_content(title: str, description: str, course_title: str, unit_title: str) -> dict:
    """Call Anthropic to generate structured lesson content. Returns parsed dict."""
    system = (
        "You are a senior real estate instructor writing curriculum for Ravlo Academy — a platform used by "
        "working investors, lenders, realtors, and contractors. Your lessons teach people who are doing real deals, "
        "not reading theory. Every lesson must meet these standards:\n\n"
        "1. USE REAL NUMBERS. Always include actual figures, percentages, dollar amounts, and ratios "
        "(e.g. '70-75% ARV', '$15-22/sqft for drywall', '1.25x DSCR minimum', '6% cap rate'). Vague claims are useless.\n"
        "2. TEACH THE WHY. Don't just say what to do — explain why it matters and what goes wrong when it's ignored.\n"
        "3. INCLUDE A REAL SCENARIO. Every lesson needs at least one concrete example: a specific property, deal, or "
        "situation with real numbers that shows the concept in action.\n"
        "4. COMMON MISTAKES SECTION IS MANDATORY. This is where practitioners learn the most. Name the actual mistakes "
        "that cost money, not generic caution.\n"
        "5. WRITE AT PRACTITIONER LEVEL. Assume the reader is on their second or third deal — not a first-time reader "
        "of a real estate textbook. Skip basic definitions. Teach depth.\n\n"
        "Never give generic encouragement. Never say 'consult a professional' or 'do your research'. Give the answer."
    )
    prompt = f"""Generate a complete, high-quality lesson for this real estate course:

Course: {course_title}
Unit: {unit_title}
Lesson: {title}
Description: {description}

Return a JSON object with EXACTLY this structure:
{{
  "objectives": ["By the end of this lesson you will be able to [specific skill 1]", "...skill 2", "...skill 3"],
  "content": "Full lesson text — minimum 600 words. Format: opening paragraph (no header), then use **Section Header** (double asterisks) for 3-4 section titles. Use - bullet (dash space) for list items. REQUIRED sections: one section with a real worked example including actual numbers, one section titled **Common Mistakes** with 3-4 specific practitioner errors and why they happen.",
  "keyPoints": ["Specific takeaway with a real number or threshold", "Specific takeaway 2", "Specific takeaway 3", "Specific takeaway 4", "Specific takeaway 5"],
  "quiz": [
    {{"question": "Comprehension question testing the core concept — not a definition, but application of the idea.", "options": ["Plausible wrong answer", "Correct answer", "Plausible wrong answer", "Plausible wrong answer"], "correctIndex": 1, "explanation": "Explain why this is correct AND briefly why the other options are wrong."}},
    {{"question": "Scenario question: An investor/lender/professional is facing [real situation from the lesson]. What should they do?", "options": ["Option A", "Option B — correct", "Option C", "Option D"], "correctIndex": 1, "explanation": "Walk through the reasoning, referencing the numbers or concept from the lesson."}},
    {{"question": "Analysis question involving a number, calculation, or judgment call from the lesson content.", "options": ["Option A", "Option B", "Option C — correct", "Option D"], "correctIndex": 2, "explanation": "Show the calculation or reasoning that leads to the correct answer."}}
  ]
}}

Critical rules:
- objectives: 3 specific, measurable skills the student gains — start each with an active verb (calculate, identify, structure, evaluate, etc.)
- content: Must include a worked example with real dollar figures or percentages. Must have a **Common Mistakes** section.
- keyPoints: Each must be specific and actionable — include a number, threshold, or rule of thumb where possible.
- quiz: Questions must test whether the student can APPLY the lesson, not just recall it. All wrong options must be plausible (no obviously silly answers). correctIndex must match the correct option (0-indexed).
- Return ONLY the JSON object, no markdown fences, no extra text.
- CRITICAL JSON RULE: The content field is a single JSON string. Do NOT use double-quote characters (") anywhere inside string values — use single quotes (') instead for any quoted terms or dialogue. Do NOT include literal newline characters inside strings."""

    resp = safe_call(
        http.post,
        _ANTHROPIC_URL,
        headers={
            "x-api-key": _ANTHROPIC_KEY,
            "anthropic-version": _ANTHROPIC_VER,
            "content-type": "application/json",
        },
        json={
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 8192,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=90,
    )
    resp.raise_for_status()
    resp_data = resp.json()
    raw = resp_data["content"][0]["text"].strip()
    # Strip markdown fences if model added them anyway
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    # Detect truncation via stop_reason
    stop_reason = resp_data.get("stop_reason", "")
    if stop_reason == "max_tokens":
        current_app.logger.warning("lesson AI response was truncated (hit max_tokens)")
    try:
        return _parse_ai_json(raw)
    except Exception as parse_exc:
        current_app.logger.error(
            "lesson JSON parse failed (stop_reason=%s) — raw response (first 800 chars): %s",
            stop_reason, raw[:800]
        )
        raise parse_exc


@university_bp.route("/api/progress", methods=["GET"])
def api_progress():
    """Return completed lessons + XP for the current user."""
    tier_key, _, _track = _current_access()
    if not tier_key:
        return jsonify({"error": "Academy access required."}), 403

    completed = {}
    xp = 0

    if current_user.is_authenticated:
        try:
            from LoanMVP.models.training_models import AcademyLessonProgress
            from LoanMVP.extensions import db
            rows = AcademyLessonProgress.query.filter_by(user_id=current_user.id).all()
            for r in rows:
                key = f"{r.module_id}:{r.lesson_index}"
                completed[key] = True
                xp += 25
        except Exception as exc:
            current_app.logger.warning("progress fetch error: %s", exc)
    else:
        raw = session.get("academy_progress") or {}
        completed = raw.get("completed", {})
        xp = raw.get("xp", 0)

    return jsonify({"completed": completed, "xp": xp})


@university_bp.route("/api/progress/complete", methods=["POST"])
def api_progress_complete():
    """Mark a lesson complete and award XP."""
    tier_key, _, _track = _current_access()
    if not tier_key:
        return jsonify({"error": "Academy access required."}), 403

    payload = request.get_json(silent=True) or {}
    module_id = (payload.get("module_id") or "").strip()
    lesson_index = payload.get("lesson_index")

    if not module_id or lesson_index is None:
        return jsonify({"error": "module_id and lesson_index are required"}), 400

    try:
        lesson_index = int(lesson_index)
    except (TypeError, ValueError):
        return jsonify({"error": "lesson_index must be an integer"}), 400

    xp_awarded = 0

    if current_user.is_authenticated:
        try:
            from LoanMVP.models.training_models import AcademyLessonProgress
            from LoanMVP.extensions import db
            from datetime import datetime
            existing = AcademyLessonProgress.query.filter_by(
                user_id=current_user.id,
                module_id=module_id,
                lesson_index=lesson_index,
            ).first()
            if not existing:
                row = AcademyLessonProgress(
                    user_id=current_user.id,
                    module_id=module_id,
                    lesson_index=lesson_index,
                    completed_at=datetime.utcnow(),
                )
                db.session.add(row)
                db.session.commit()
                xp_awarded = 25
        except Exception as exc:
            current_app.logger.warning("progress save error: %s", exc)
    else:
        raw = session.get("academy_progress") or {"completed": {}, "xp": 0}
        key = f"{module_id}:{lesson_index}"
        if key not in raw["completed"]:
            raw["completed"][key] = True
            raw["xp"] = raw.get("xp", 0) + 25
            xp_awarded = 25
        session["academy_progress"] = raw

    return jsonify({"ok": True, "xp_awarded": xp_awarded})


@university_bp.route("/lesson-content", methods=["POST"])
def lesson_content():
    """Return structured lesson content. Generated by AI on first request, cached permanently."""
    tier_key, _, _track = _current_access()
    if not tier_key:
        return jsonify({"error": "Academy access required."}), 403
    if not _ANTHROPIC_KEY:
        return jsonify({"error": "AI not configured."}), 503

    payload = request.get_json(silent=True) or {}
    lesson_id   = (payload.get("lesson_id") or "").strip()
    title       = (payload.get("title") or "").strip()
    description = (payload.get("description") or "").strip()
    course_title = (payload.get("course_title") or "").strip()
    unit_title   = (payload.get("unit_title") or "").strip()

    if not lesson_id or not title:
        return jsonify({"error": "lesson_id and title are required"}), 400

    cache = _load_lesson_cache()
    if lesson_id in cache:
        return jsonify(cache[lesson_id])

    # Retry once on parse failure (LLM output can be non-deterministic)
    last_exc = None
    for attempt in range(2):
        try:
            data = _generate_lesson_content(title, description, course_title, unit_title)
            try:
                from LoanMVP.services.ravlo_memory_service import log_ai_exchange
                log_ai_exchange(
                    module="academy",
                    feature="lesson_generation",
                    prompt=f"{course_title} / {unit_title} / {title}: {description}"[:4000],
                    response=json.dumps(data, default=str)[:8000],
                    user_id=current_user.id if getattr(current_user, "is_authenticated", False) else None,
                    provider="anthropic",
                    model="claude-haiku-4-5-20251001",
                    object_type="lesson",
                    object_id=lesson_id,
                )
            except Exception:
                pass
            break
        except json.JSONDecodeError as exc:
            last_exc = exc
            if attempt == 0:
                current_app.logger.warning("lesson content parse failed (attempt 1), retrying: %s", exc)
                continue
        except Exception as exc:
            current_app.logger.exception("lesson content generation error")
            return jsonify({"error": "Could not generate lesson content. Please try again."}), 500
    else:
        current_app.logger.error("lesson content generation error after 2 attempts: %s", last_exc)
        return jsonify({"error": "Could not generate lesson content. Please try again."}), 500

    cache[lesson_id] = data
    _save_lesson_cache(cache)
    return jsonify(data)
