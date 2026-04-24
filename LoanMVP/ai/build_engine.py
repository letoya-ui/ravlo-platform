"""Build Studio engine -- calls the Renovation Engine /v1/build_concept endpoint."""

from __future__ import annotations

import os
import uuid
from flask import current_app

from LoanMVP.services.investor.investor_engine_helpers import (
    _post_renovation_engine_json,
    UPLOAD_TIMEOUT,
)

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
    engine_payload = {
        "mode": payload.get("mode", "exterior"),
        "project_name": payload.get("project_name", ""),
        "property_type": payload.get("property_type", "single_family"),
        "style": payload.get("style", "modern_farmhouse"),
        "blueprint_style": payload.get("blueprint_style", "technical_blueprint"),
        "description": payload.get("description", ""),
        "build_description": payload.get("description", ""),
        "lot_size": payload.get("lot_size", ""),
        "zoning": payload.get("zoning", ""),
        "location": payload.get("location", ""),
        "prompt_notes": payload.get("notes", ""),
        "count": 1,
        "steps": payload.get("steps", 20),
        "guidance": payload.get("guidance", 7.5),
        "strength": payload.get("strength", 0.65),
        "width": payload.get("width", 768),
        "height": payload.get("height", 768),
    }

    for source_key in (
        "image_base64",
        "image_url",
        "blueprint_image_base64",
        "blueprint_image_url",
        "site_image_base64",
        "site_image_url",
    ):
        if payload.get(source_key):
            engine_payload[source_key] = payload[source_key]

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
