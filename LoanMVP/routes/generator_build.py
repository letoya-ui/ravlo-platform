import os
import sys
import traceback

from flask import Blueprint, jsonify, request
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