import os
import sys
import requests
import traceback

from flask import Blueprint, jsonify, request, current_app
from LoanMVP.extensions import csrf


RENOVATION_ENGINE_PATH = os.environ.get(
    "RENOVATION_ENGINE_PATH",
    r"C:\Users\letoy\OneDrive\Mobile uploads\Documents\GitHub\renovation-engine",
)

if RENOVATION_ENGINE_PATH and RENOVATION_ENGINE_PATH not in sys.path:
    sys.path.insert(0, RENOVATION_ENGINE_PATH)


from generator.build.chat import build_studio_chat


generator_build_bp = Blueprint(
    "generator_build",
    __name__,
    url_prefix="/api/generator/build",
)


@generator_build_bp.post("/chat")
@csrf.exempt
def build_chat():
    try:
        data = request.get_json(silent=True) or {}

        messages = data.get("messages") or []
        current_spec = data.get("spec") or {}

        result = build_studio_chat(
            messages=messages,
            current_spec=current_spec,
        )

        return jsonify(result)

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
            timeout=600,
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
        return jsonify(
            {
                "status": "error",
                "message": str(exc),
            }
        ), 500