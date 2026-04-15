# routes/lead_engine_routes.py

from flask import Blueprint, request, jsonify
import os
import json
import re
from typing import Any
from openai import OpenAI

lead_engine_bp = Blueprint("lead_engine", __name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MAX_LEADS_PER_REQUEST = 15

VALID_LEAD_TYPES = {"purchase", "refinance", "investor"}
VALID_TIMELINES = {"immediate", "30 days", "60-90 days", "6+ months", "unknown"}


def _safe_int(value: Any, default: int = 5) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(value, high))


def _clean_email(value: Any) -> str | None:
    email = (value or "").strip().lower()
    if not email:
        return None
    if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return email
    return None


def _clean_phone(value: Any) -> str | None:
    phone = (value or "").strip()
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 10:
        return None
    return phone


def _extract_json_array(text: str) -> list[dict[str, Any]]:
    if not text:
        return []

    text = text.strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass

    match = re.search(r"\[[\s\S]*\]", text)
    if not match:
        return []

    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _normalize_loan_amount(value: Any) -> int | None:
    if isinstance(value, str):
        cleaned = re.sub(r"[^\d.]", "", value)
        if not cleaned:
            return None
        try:
            return int(float(cleaned))
        except Exception:
            return None

    if isinstance(value, (int, float)):
        return int(value)

    return None


def _normalize_intent_score(value: Any) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        score = 50
    return _clamp(score, 0, 100)


def _normalize_lead_type(value: Any) -> str:
    lead_type = (value or "purchase").strip().lower()
    return lead_type if lead_type in VALID_LEAD_TYPES else "purchase"


def _normalize_timeline(value: Any) -> str:
    timeline = (value or "unknown").strip().lower()
    if timeline in VALID_TIMELINES:
        return timeline
    return "unknown"


def _normalize_ai_lead(item: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None

    name = (item.get("name") or "").strip()
    if not name:
        return None

    return {
        "name": name,
        "email": _clean_email(item.get("email")),
        "phone": _clean_phone(item.get("phone")),
        "lead_type": _normalize_lead_type(item.get("lead_type")),
        "persona": (item.get("persona") or "general_borrower").strip(),
        "credit_range": (item.get("credit_range") or "unknown").strip(),
        "income_type": (item.get("income_type") or "unknown").strip(),
        "timeline": _normalize_timeline(item.get("timeline")),
        "loan_amount_estimate": _normalize_loan_amount(item.get("loan_amount_estimate")),
        "pain_point": (item.get("pain_point") or "").strip() or None,
        "intent_score": _normalize_intent_score(item.get("intent_score")),
        "ai_summary": (item.get("ai_summary") or "").strip() or None,
        "suggested_first_message": (item.get("suggested_first_message") or "").strip() or None,
        "next_action": (item.get("next_action") or "Call within 5 minutes").strip(),
        "source": (item.get("source") or "AI Lead Engine").strip(),
    }


def _build_capture_lead(data: dict[str, Any]) -> dict[str, Any]:
    name = (data.get("name") or data.get("full_name") or "").strip()
    email = _clean_email(data.get("email"))
    phone = _clean_phone(data.get("phone"))

    lead_type = _normalize_lead_type(data.get("lead_type") or data.get("loan_purpose") or "purchase")
    timeline = _normalize_timeline(data.get("timeline") or data.get("timeframe") or "unknown")
    source = (data.get("source") or "Website").strip()

    loan_amount_estimate = _normalize_loan_amount(
        data.get("loan_amount_estimate") or data.get("estimated_loan_amount")
    )

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "lead_type": lead_type,
        "persona": (data.get("persona") or "inbound_borrower").strip(),
        "credit_range": (data.get("credit_range") or "unknown").strip(),
        "income_type": (data.get("income_type") or "unknown").strip(),
        "timeline": timeline,
        "loan_amount_estimate": loan_amount_estimate,
        "pain_point": (data.get("pain_point") or data.get("message") or "").strip() or None,
        "intent_score": _normalize_intent_score(data.get("intent_score")),
        "ai_summary": None,
        "suggested_first_message": None,
        "next_action": "Call within 5 minutes",
        "source": source,
        "message": (data.get("message") or "").strip() or None,
        "city": (data.get("city") or "").strip() or None,
        "state": (data.get("state") or "").strip() or None,
        "zip_code": (data.get("zip_code") or "").strip() or None,
        "first_time_buyer": bool(data.get("first_time_buyer", False)),
        "consent_to_contact": bool(data.get("consent_to_contact", True)),
    }


def _dedupe_key(lead: dict[str, Any]) -> tuple[str, str, str]:
    return (
        (lead.get("email") or "").lower(),
        re.sub(r"\D", "", lead.get("phone") or ""),
        (lead.get("name") or "").lower(),
    )


def _score_capture_lead(lead: dict[str, Any]) -> int:
    score = 35

    if lead.get("phone"):
        score += 15
    if lead.get("email"):
        score += 10
    if lead.get("timeline") == "immediate":
        score += 20
    elif lead.get("timeline") == "30 days":
        score += 15
    elif lead.get("timeline") == "60-90 days":
        score += 10

    if lead.get("loan_amount_estimate"):
        amt = lead["loan_amount_estimate"]
        if amt >= 500000:
            score += 12
        elif amt >= 250000:
            score += 8
        else:
            score += 4

    if lead.get("lead_type") == "investor":
        score += 8

    if lead.get("pain_point"):
        score += 5

    return _clamp(score, 0, 100)


def _generate_ai_enrichment(lead: dict[str, Any]) -> tuple[str | None, str | None, str]:
    prompt = f"""
You are a mortgage sales assistant.

Given this inbound borrower lead, generate:
1. a short ai_summary
2. a suggested_first_message as an SMS
3. a next_action

Return ONLY valid JSON object with keys:
- ai_summary
- suggested_first_message
- next_action

Lead data:
Name: {lead.get("name")}
Lead type: {lead.get("lead_type")}
Persona: {lead.get("persona")}
Credit range: {lead.get("credit_range")}
Income type: {lead.get("income_type")}
Timeline: {lead.get("timeline")}
Loan amount estimate: {lead.get("loan_amount_estimate")}
Pain point: {lead.get("pain_point")}
Source: {lead.get("source")}
Message: {lead.get("message")}
City: {lead.get("city")}
State: {lead.get("state")}
First-time buyer: {lead.get("first_time_buyer")}
Intent score: {lead.get("intent_score")}
""".strip()

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "You generate only JSON for mortgage lead follow-up assistance."
                },
                {
                    "role": "user",
                    "content": prompt
                },
            ],
            temperature=0.6,
        )

        raw = completion.choices[0].message.content or "{}"
        obj = json.loads(raw)

        ai_summary = (obj.get("ai_summary") or "").strip() or None
        suggested_first_message = (obj.get("suggested_first_message") or "").strip() or None
        next_action = (obj.get("next_action") or "Call within 5 minutes").strip()

        return ai_summary, suggested_first_message, next_action
    except Exception:
        return None, None, "Call within 5 minutes"


@lead_engine_bp.route("/lead-engine/health", methods=["GET"])
def lead_engine_health():
    return jsonify({
        "ok": True,
        "service": "lead_engine",
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
    }), 200


@lead_engine_bp.route("/lead-engine/ai_leads", methods=["POST"])
def lead_engine_ai_leads():
    data = request.get_json(silent=True) or {}

    market = (data.get("market") or "United States").strip()
    audience = (data.get("audience") or "homebuyers and refinance borrowers").strip()
    product_focus = (data.get("product_focus") or "residential mortgage products").strip()
    count = _clamp(_safe_int(data.get("count"), 5), 1, MAX_LEADS_PER_REQUEST)

    prompt = f"""
You are a mortgage lead intelligence system for loan officers.

Generate {count} synthetic mortgage borrower leads for sales demonstration, CRM testing,
recruiting demos, and pipeline simulation.

Market: {market}
Audience: {audience}
Product focus: {product_focus}

Return ONLY a valid JSON object with a single key called "leads".
The value must be a JSON array.
Do not include markdown.
Do not include code fences.
Do not include commentary.

Each lead object must include:
- name
- email
- phone
- lead_type
- persona
- credit_range
- income_type
- timeline
- loan_amount_estimate
- pain_point
- intent_score
- ai_summary
- suggested_first_message
- next_action
- source

Rules:
- All leads must be fictional and synthetic.
- Do not use real people, celebrities, or public figures.
- Keep contact info plausible but fake.
- Vary the lead profiles.
- Make the leads useful for loan officer outreach.
- lead_type should be one of: purchase, refinance, investor
- intent_score should be an integer from 0 to 100
- source should be "AI Lead Engine"
""".strip()

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "You generate only structured JSON for mortgage lead simulations."
                },
                {
                    "role": "user",
                    "content": prompt
                },
            ],
            temperature=0.8,
        )
        raw = completion.choices[0].message.content or "{}"
    except Exception as e:
        return jsonify({
            "ok": False,
            "count": 0,
            "leads": [],
            "error": f"OpenAI request failed: {str(e)}"
        }), 500

    payload = []
    try:
        parsed_obj = json.loads(raw)
        if isinstance(parsed_obj, dict) and isinstance(parsed_obj.get("leads"), list):
            payload = parsed_obj["leads"]
    except Exception:
        payload = _extract_json_array(raw)

    normalized_leads = []
    seen = set()

    for item in payload:
        lead = _normalize_ai_lead(item)
        if not lead:
            continue

        key = _dedupe_key(lead)
        if key in seen:
            continue
        seen.add(key)
        normalized_leads.append(lead)

    return jsonify({
        "ok": True,
        "count": len(normalized_leads),
        "market": market,
        "audience": audience,
        "product_focus": product_focus,
        "leads": normalized_leads,
    }), 200


@lead_engine_bp.route("/lead-engine/capture", methods=["POST"])
def lead_engine_capture():
    """
    Real inbound capture route.
    Use this for:
    - website forms
    - landing pages
    - Meta lead ads
    - Google ads lead forms
    - Zapier / Make webhooks
    - partner referral submissions
    """
    data = request.get_json(silent=True) or {}

    lead = _build_capture_lead(data)

    if not lead["name"]:
        return jsonify({
            "ok": False,
            "error": "Name is required."
        }), 400

    if not lead["email"] and not lead["phone"]:
        return jsonify({
            "ok": False,
            "error": "At least one contact field is required: email or phone."
        }), 400

    lead["intent_score"] = _score_capture_lead(lead)

    ai_summary, suggested_first_message, next_action = _generate_ai_enrichment(lead)
    lead["ai_summary"] = ai_summary
    lead["suggested_first_message"] = suggested_first_message
    lead["next_action"] = next_action

    return jsonify({
        "ok": True,
        "lead": lead,
    }), 200