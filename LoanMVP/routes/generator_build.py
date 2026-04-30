import os
import cv2
import sys
import requests
import traceback
import asyncio
from types import SimpleNamespace
from flask import Blueprint, jsonify, request, current_app
from LoanMVP.extensions import csrf


RENOVATION_ENGINE_PATH = os.environ.get(
    "RENOVATION_ENGINE_PATH",
    r"C:\Users\letoy\OneDrive\Mobile uploads\Documents\GitHub\renovation-engine",
)

if RENOVATION_ENGINE_PATH and RENOVATION_ENGINE_PATH not in sys.path:
    sys.path.insert(0, RENOVATION_ENGINE_PATH)


from generator.build.chat import build_studio_chat
from generation import run_build_generation, run_build_studio_generation

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

        intent = spec.get("intent") or "build_package"

        engine_url = (
            current_app.config.get("RENOVATION_ENGINE_URL")
            or os.getenv("RENOVATION_ENGINE_URL")
            or ""
        ).rstrip("/")

        if engine_url:
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

        req = SimpleNamespace(
            mode=(
                "exterior_from_blueprint"
                if intent == "exterior_from_blueprint"
                else "build_studio"
            ),
            outputs=spec.get("outputs") or ["blueprint", "exterior_front", "exterior_back"],
            project_name=spec.get("project_name"),
            property_type=spec.get("property_type"),
            style=spec.get("style"),
            prompt_notes=spec.get("notes"),
            build_description=spec.get("notes"),
            special_features=spec.get("special_features"),
            exterior_view=spec.get("exterior_view") or "front",
            preserve_layout=spec.get("preserve_layout", True),
            blueprint_image_url=spec.get("blueprint_url"),
            reference_image_url=spec.get("reference_image_url"),
            image_url=spec.get("reference_image_url") or spec.get("blueprint_url"),
            stories=spec.get("stories"),
            roof_style=spec.get("roof_style"),
            siding_material=spec.get("siding_material"),
            window_style=spec.get("window_style"),
        )

        if intent == "exterior_from_blueprint":
            result = asyncio.run(run_build_generation(req))
        else:
            result = asyncio.run(run_build_studio_generation(req))

        return jsonify(result)

    except Exception as exc:
        traceback.print_exc()
        return jsonify(
            {
                "status": "error",
                "message": str(exc),
            }
        ), 500