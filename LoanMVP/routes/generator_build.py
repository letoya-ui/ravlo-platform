import os
import requests
import traceback
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from flask import Blueprint, current_app, jsonify, request
from LoanMVP.extensions import csrf
from openai import OpenAI


generator_build_bp = Blueprint(
    "generator_build",
    __name__,
    url_prefix="/api/generator/build",
)


def _build_chat_prompt(messages, current_spec=None):
    current_spec = current_spec or {}

    return f"""
You are Ravlo Build Studio.

Help the user create a clear build specification before generation.

Return ONLY valid JSON in this shape:

{{
  "status": "needs_more_info" or "ready",
  "assistant_message": "Natural language response to the user.",
  "spec": {{
    "intent": "",
    "property_type": "",
    "style": "",
    "preserve_layout": true,
    "blueprint_url": "",
    "reference_image_url": "",
    "exterior_view": "front",
    "finish_level": "",
    "stories": "",
    "roof_style": "",
    "siding_material": "",
    "window_style": "",
    "special_features": "",
    "notes": ""
  }},
  "missing_fields": [],
  "next_questions": []
}}

Current spec:
{current_spec}

Conversation:
{messages}
""".strip()


def _safe_json(text):
    import json

    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`").replace("json", "", 1).strip()

    try:
        return json.loads(text)
    except Exception:
        return {
            "status": "needs_more_info",
            "assistant_message": text or "I need a little more information before generating.",
            "spec": {},
            "missing_fields": [],
            "next_questions": [],
        }


@generator_build_bp.post("/chat")
@csrf.exempt
def build_chat():
    try:
        data = request.get_json(silent=True) or {}
        messages = data.get("messages") or []
        current_spec = data.get("spec") or {}

        client = OpenAI(api_key=current_app.config.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY"))

        response = client.chat.completions.create(
            model=current_app.config.get("AI_MODEL") or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are Ravlo Build Studio. Return only valid JSON."},
                {"role": "user", "content": _build_chat_prompt(messages, current_spec)},
            ],
            temperature=0.25,
        )

        return jsonify(_safe_json(response.choices[0].message.content))

    except Exception as exc:
        traceback.print_exc()
        return jsonify(
            {
                "status": "error",
                "assistant_message": str(exc),
                "spec": {},
                "missing_fields": [],
                "next_questions": [],
            }
        ), 500


@generator_build_bp.post("/generate")
@csrf.exempt
def build_generate():
    try:
        data = request.get_json(silent=True) or {}
        spec = data.get("spec") or data

        engine_url = (
            current_app.config.get("RENOVATION_ENGINE_URL")
            or os.getenv("RENOVATION_ENGINE_URL")
            or ""
        ).rstrip("/")

        print("FORWARDING TO RENOVATION_ENGINE_URL =", engine_url)

        if not engine_url:
            return jsonify(
                {
                    "status": "error",
                    "message": "RENOVATION_ENGINE_URL is not configured.",
                }
            ), 500

        response = requests.post(
            f"{engine_url}/api/generator/build/generate",
            json={"spec": spec},
            headers={"ngrok-skip-browser-warning": "true"},
            timeout=600,
            verify=False,  # dev/ngrok only
        )

        try:
            payload = response.json()
        except Exception:
            payload = {
                "status": "error",
                "message": response.text,
            }

        return jsonify(payload), response.status_code

    except Exception as exc:
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(exc)}), 500