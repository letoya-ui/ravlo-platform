from flask import Blueprint, jsonify, request

try:
    from generator.build.chat import build_studio_chat
except Exception:
    build_studio_chat = None


generator_build_bp = Blueprint(
    "generator_build",
    __name__,
    url_prefix="/api/generator/build",
)


@generator_build_bp.post("/chat")
def build_chat():
    if build_studio_chat is None:
        return jsonify(
            {
                "status": "error",
                "assistant_message": (
                    "Build Studio chat is not available because the renovation engine "
                    "chat module could not be imported."
                ),
                "spec": {},
                "missing_fields": [],
                "next_questions": [],
            }
        ), 500

    data = request.get_json(silent=True) or {}

    messages = data.get("messages") or []
    current_spec = data.get("spec") or {}

    result = build_studio_chat(
        messages=messages,
        current_spec=current_spec,
    )

    return jsonify(result)