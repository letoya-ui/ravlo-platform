"""Rehab Studio engine -- calls the Renovation Engine /v1/renovate endpoint."""

from __future__ import annotations

from LoanMVP.services.investor.investor_engine_helpers import (
    _post_renovation_engine_json,
    RENDER_TIMEOUT,
)


def run_rehab_concept(payload):
    """Call the Renovation Engine to generate a rehab concept.

    Parameters
    ----------
    payload : dict
        Keys accepted by the engine's ``RenovateRequest``:
        preset, mode, room_type, image_base64, image_url, prompt,
        negative_prompt, steps, guidance, strength, width, height, etc.

    Returns
    -------
    dict
        The JSON response from the engine (images_base64, job_id, seed, meta, ...).
    """
    engine_payload = {
        "preset": payload.get("preset", "luxury_modern"),
        "mode": payload.get("mode", "hgtv"),
        "room_type": payload.get("room_type", "living room"),
        "room_focus": payload.get("room_type", "living room"),
        "count": 1,
        "steps": payload.get("steps", 18),
        "guidance": payload.get("guidance", 7.2),
        "strength": payload.get("strength", 0.58),
        "width": payload.get("width", 768),
        "height": payload.get("height", 768),
    }

    # Image input (required for rehab)
    if payload.get("image_base64"):
        engine_payload["image_base64"] = payload["image_base64"]
    if payload.get("image_url"):
        engine_payload["image_url"] = payload["image_url"]

    # Optional prompt overrides
    if payload.get("prompt"):
        engine_payload["prompt"] = payload["prompt"]
    if payload.get("negative_prompt"):
        engine_payload["negative_prompt"] = payload["negative_prompt"]
    if payload.get("desired_updates"):
        engine_payload["desired_updates"] = payload["desired_updates"]
    if payload.get("prompt_notes"):
        engine_payload["prompt_notes"] = payload["prompt_notes"]

    return _post_renovation_engine_json(
        "/v1/renovate",
        engine_payload,
        timeout=RENDER_TIMEOUT,
    )
