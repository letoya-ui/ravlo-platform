"""Build Studio engine -- calls the Renovation Engine /v1/build_concept endpoint."""

from __future__ import annotations

import os
import uuid
from flask import current_app

from LoanMVP.services.investor.investor_engine_helpers import (
    _post_renovation_engine_json,
    UPLOAD_TIMEOUT,
)

BUILD_MODES = {
    "scope",
    "blueprint",
    "siteplan",
    "exterior_from_blueprint",
    "exterior_from_photo",
    "build_package",
}

DESIGN_MODES = {
    "interior_from_photo",
    "interior_from_prompt",
    "exterior_style_variation",
    "room_finish_variation",
}

DEAL_MODES = {
    "deal_summary",
    "investment_thesis",
    "risk_review",
    "renovation_strategy",
    "full_deal_package",
}

try:
    from LoanMVP.services.cost_index import (
        build_location_cost_context,
        apply_multiplier_to_engine_response,
    )
except Exception:  # pragma: no cover
    build_location_cost_context = None
    apply_multiplier_to_engine_response = None


def save_generated_image(image_bytes, folder="uploads/studios"):
    """Persist raw image bytes under static/<folder> and return the relative path."""
    filename = f"{uuid.uuid4().hex}.png"
    relative_path = f"{folder}/{filename}"
    absolute_path = os.path.join(current_app.root_path, "static", relative_path)

    os.makedirs(os.path.dirname(absolute_path), exist_ok=True)

    with open(absolute_path, "wb") as f:
        f.write(image_bytes)

    return relative_path


def run_build_concept(payload):
    """Call the Renovation Engine to generate a build concept.

    Parameters
    ----------
    payload : dict
        Keys accepted by the engine's ``BuildConceptRequest``:
        project_name, property_type, style, description, lot_size,
        zoning, location, notes, mode, room_type, floor, image_base64,
        image_url, etc.

    Returns
    -------
    dict
        The JSON response from the engine (images_base64, job_id, seed, meta, ...).
    """
    intent = payload.get("intent") or payload.get("build_mode") or payload.get("mode") or "build_package"
    if intent not in BUILD_MODES:
        intent = "build_package" if intent in {"build", "build_studio", "package"} else "exterior_from_photo"

    image_outputs = payload.get("output_modes") or payload.get("outputs")
    if not image_outputs:
        if intent == "scope":
            image_outputs = []
        elif intent == "blueprint":
            image_outputs = ["blueprint"]
        elif intent == "siteplan":
            image_outputs = ["siteplan"]
        elif intent == "exterior_from_photo":
            image_outputs = ["exterior_front", "exterior_back"]
        else:
            image_outputs = ["blueprint", "siteplan", "exterior_front", "exterior_back"]

    engine_payload = {
        "mode": "build_studio" if intent == "build_package" else intent,
        "intent": intent,
        "project_name": payload.get("project_name", ""),
        "property_type": payload.get("property_type", "single_family"),
        "style": payload.get("style", "modern_farmhouse"),
        "blueprint_style": payload.get("blueprint_style", "technical_blueprint"),
        "description": payload.get("description", ""),
        "build_description": payload.get("build_description", payload.get("description", "")),
        "lot_size": payload.get("lot_size", ""),
        "zoning": payload.get("zoning", ""),
        "location": payload.get("location", ""),
        "prompt_notes": payload.get("prompt_notes", payload.get("notes", "")),
        "special_features": payload.get("special_features", ""),
        "stories": payload.get("stories"),
        "number_of_stories": payload.get("number_of_stories"),
        "number_of_floors": payload.get("number_of_floors"),
        "floor_count": payload.get("floor_count"),
        "square_feet_target": payload.get("square_feet_target") or payload.get("square_feet"),
        "project_size": payload.get("project_size") or payload.get("square_feet_target") or payload.get("square_feet"),
        "bedrooms": payload.get("bedrooms") or payload.get("beds"),
        "bathrooms": payload.get("bathrooms") or payload.get("baths"),
        "garage": payload.get("garage"),
        "finish_level": payload.get("finish_level") or payload.get("finish_quality"),
        "market_cost_multiplier": payload.get("market_cost_multiplier"),
        "exterior_view": payload.get("exterior_view"),
        "preserve_existing_exterior": payload.get("preserve_existing_exterior"),
        "preserve_structure": payload.get("preserve_structure"),
        "count": 1,
        "steps": payload.get("steps", 20),
        "guidance": payload.get("guidance", 7.5),
        "strength": payload.get("strength", 0.65),
        "width": payload.get("width", 768),
        "height": payload.get("height", 768),
        "outputs": image_outputs,
        "output_modes": image_outputs,
        "scope": payload.get("scope") or {},
        "materials": payload.get("materials") or [],
        "phases": payload.get("phases") or [],
        "timeline": payload.get("timeline") or {},
        "risks": payload.get("risks") or [],
        "images": payload.get("images") or {},
    }

    if payload.get("negative_prompt"):
        engine_payload["negative_prompt"] = payload["negative_prompt"]

    for source_key in (
        "image_base64",
        "image_url",
        "blueprint_image_base64",
        "blueprint_image_url",
        "site_image_base64",
        "site_image_url",
        "reference_image_base64",
        "reference_image_url",
        "exterior_image_base64",
        "exterior_image_url",
        "front_exterior_image_base64",
        "front_exterior_image_url",
        "back_exterior_image_base64",
        "back_exterior_image_url",
        "rear_exterior_image_base64",
        "rear_exterior_image_url",
    ):
        if payload.get(source_key):
            engine_payload[source_key] = payload[source_key]

    for list_key in ("outputs", "output_modes"):
        if payload.get(list_key):
            engine_payload[list_key] = payload[list_key]

    for quality_key in (
        "output_type",
        "render_type",
        "camera_view",
        "composition",
        "avoid_output_types",
        "allow_text",
        "allow_logos",
        "single_image_output",
        "avoid_collage",
    ):
        if quality_key in payload:
            engine_payload[quality_key] = payload[quality_key]

    # Interior-specific fields
    if payload.get("room_type"):
        engine_payload["room_type"] = payload["room_type"]
    if payload.get("floor"):
        engine_payload["floor"] = payload["floor"]

    cost_ctx = None
    if build_location_cost_context is not None:
        try:
            cost_ctx = build_location_cost_context(
                zip_code=payload.get("zip_code"),
                state=payload.get("state"),
                category="new_build",
                scope=payload.get("scope"),
            )
            engine_payload["location_cost_context"] = cost_ctx
        except Exception:
            cost_ctx = None

    response = _post_renovation_engine_json(
        "/v1/build_concept",
        engine_payload,
        timeout=UPLOAD_TIMEOUT,
    )

    if cost_ctx and apply_multiplier_to_engine_response is not None:
        try:
            apply_multiplier_to_engine_response(response, cost_ctx.get("factor"))
            if isinstance(response, dict):
                response.setdefault("location_cost_context", cost_ctx)
        except Exception:
            pass

    return response
