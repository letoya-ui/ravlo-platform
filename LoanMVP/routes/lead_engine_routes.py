# routes/lead_engine_routes.py
from flask import Blueprint, request, jsonify
import os, re, json
import openai

lead_engine_bp = Blueprint("lead_engine", __name__)

openai.api_key = os.getenv("OPENAI_API_KEY")

@lead_engine_bp.route("/lead-engine/ai_leads", methods=["POST"])
def lead_engine_ai_leads():
    data = request.get_json() or {}

    market = (data.get("market") or "United States").strip()
    audience = (data.get("audience") or "homebuyers and refinance borrowers").strip()
    product_focus = (data.get("product_focus") or "residential mortgage products").strip()
    count = int(data.get("count") or 5)

    prompt = f"""
Generate {count} realistic mortgage prospect leads for a lending business.
Target market: {market}.
Audience: {audience}.
Product focus: {product_focus}.
Return ONLY valid JSON as an array.
Each object must include: name, email, phone, message.
Use plausible sample contact info, not existing famous people.
"""

    try:
        completion = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        raw = completion.choices[0].message.content
    except Exception:
        return jsonify([])

    match = re.search(r"

\[[\s\S]*\]

", raw or "")
    if not match:
        return jsonify([])

    try:
        payload = json.loads(match.group(0))
    except Exception:
        payload = []

    leads = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        if not name:
            continue
        leads.append({
            "name": name,
            "email": (item.get("email") or "").strip() or None,
            "phone": (item.get("phone") or "").strip() or None,
            "message": (item.get("message") or "").strip() or None,
        })

    return jsonify(leads)
