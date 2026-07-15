"""
Cloud Studio Service — OpenAI (gpt-image-1) + Claude fallback for Build Studio,
Design Studio, Deal Architect, and Project Build when the GPU engine is offline.

Every generation is automatically captured by the training logging already wired
into generator_build._build_generate_response(), so switching to this backend
doesn't break data collection for future Replicate LoRA training.

Usage (automatic):
    Set RENOVATION_ENGINE_URL="" or leave it unset.
    generator_build._build_generate_response() calls run_cloud_generation(spec).

Env vars required:
    OPENAI_API_KEY      — for gpt-image-1 image generation
    ANTHROPIC_API_KEY   — for Claude deal/scope analysis
"""

from __future__ import annotations

import base64
import logging
import os
import uuid
from io import BytesIO
from typing import Optional

import requests

log = logging.getLogger(__name__)

_OPENAI_IMAGE_MODEL = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1")
_ANTHROPIC_MODEL = os.environ.get("CLOUD_STUDIO_CLAUDE_MODEL", "claude-sonnet-5")


# ---------------------------------------------------------------------------
# API clients
# ---------------------------------------------------------------------------

def _openai_client():
    from openai import OpenAI
    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    return OpenAI(api_key=key)


def _anthropic_client():
    import anthropic
    key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured.")
    return anthropic.Anthropic(api_key=key)


# ---------------------------------------------------------------------------
# Prompt builders — tuned for architectural realism
# ---------------------------------------------------------------------------

_REAR_OUTDOOR_LIVING_KEYWORDS = (
    "back porch", "rear porch", "back patio", "rear patio",
    "back deck", "rear deck", "lanai", "veranda", "sunroom",
    "screened porch", "covered patio",
)


def _mentions_rear_outdoor_living(*texts) -> bool:
    combined = " ".join(str(t or "").lower() for t in texts)
    return any(keyword in combined for keyword in _REAR_OUTDOOR_LIVING_KEYWORDS)


def _is_garage_requested(spec: dict) -> bool:
    value = spec.get("garage")
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def _stories_count(spec: dict) -> int:
    try:
        return int(str(spec.get("stories") or "1").strip())
    except (TypeError, ValueError):
        return 1


def _blueprint_prompt(spec: dict, floor_number: int = 1, total_floors: int = 1) -> str:
    """Prompt for one floor's plan. For multi-story projects, a single
    generation asked to draw every floor in one sheet is unreliable (an
    image model tends to draw just one floor's plan even when told the
    home has N stories) -- run_cloud_generation() instead calls this once
    per floor with floor_number/total_floors set, and composites the
    results deterministically. floor_number/total_floors default to a
    plain single-floor prompt when the caller doesn't need per-floor
    generation (total_floors == 1)."""
    prop = (spec.get("property_type") or "single-family home").replace("_", " ")
    style = (spec.get("style") or "modern").replace("_", " ")
    beds = spec.get("bedrooms", "")
    baths = spec.get("bathrooms", "")
    sq = spec.get("square_feet_target") or spec.get("square_feet", "")
    desc = spec.get("description") or spec.get("special_features") or ""
    is_ground_floor = floor_number <= 1

    details = []
    if total_floors > 1:
        # Split rooms across floors instead of listing whole-home bed/bath
        # counts identically on every floor's plan.
        if is_ground_floor:
            details.append("entry foyer, living room, kitchen, dining area")
            if _is_garage_requested(spec):
                details.append("attached garage")
        else:
            if beds:
                details.append(f"{beds} bedrooms total in the home")
            if baths:
                details.append(f"{baths} bathrooms total in the home")
    else:
        if beds:
            details.append(f"{beds} bedrooms")
        if baths:
            details.append(f"{baths} bathrooms")
        if sq:
            details.append(f"{sq} sq ft")
        if _is_garage_requested(spec):
            details.append("attached garage")
    detail_str = ", ".join(details)

    if total_floors > 1:
        floor_label = "ground floor" if is_ground_floor else f"floor {floor_number}"
        floor_context = f"{floor_label} ({floor_number} of {total_floors}) of a {total_floors}-story {style} {prop}"
        single_floor_note = (
            " Show only this one floor's plan -- do not include any other floor's rooms or a multi-panel/split "
            "sheet in this image."
        )
    else:
        floor_context = f"single-story {style} {prop}"
        single_floor_note = ""

    door_note = (
        " Main entry door on the front-facing wall, opening onto the front porch, not on a side or rear wall."
        if is_ground_floor else ""
    )

    return (
        f"Professional architectural floor plan blueprint, top-down view, clean black lines "
        f"on white background, room labels, dimensions, {floor_context}"
        + (f", {detail_str}" if detail_str else "")
        + (f", {desc}" if desc else "")
        + ". CAD technical drawing style, no people, white background, professional drafting quality."
        + door_note
        + single_floor_note
    )


def _siteplan_prompt(spec: dict) -> str:
    prop = (spec.get("property_type") or "single-family home").replace("_", " ")
    style = (spec.get("style") or "modern").replace("_", " ")
    lot = spec.get("lot_size") or ""
    return (
        f"Professional architectural site plan, top-down aerial view, property boundary lines, "
        f"building footprint, driveway, landscaping zones, {style} {prop}"
        + (f", {lot} lot" if lot else "")
        + ". Clean technical drawing, labeled areas, professional civil engineering style, white background."
    )


def _exterior_prompt(spec: dict, view: str = "front") -> str:
    prop = (spec.get("property_type") or "single-family home").replace("_", " ")
    stories = spec.get("stories") or "2"
    style = (spec.get("style") or "modern").replace("_", " ")
    siding = spec.get("siding_material") or ""
    roof = spec.get("roof_style") or ""
    features = spec.get("special_features") or spec.get("description") or ""

    view_label = "front" if view == "front" else "rear"
    if view == "front":
        entry_note = " Entry door centered and forward-facing on the front elevation, opening onto the front porch, matching the floor plan."
        if _is_garage_requested(spec):
            entry_note += " Include an attached garage with a visible garage door on the front elevation, matching the floor plan."
    elif _mentions_rear_outdoor_living(spec.get("notes"), spec.get("special_features"), spec.get("description")):
        entry_note = " Show a covered porch/deck/patio connecting to the yard on the rear facade."
    else:
        entry_note = " Plain rear facade matching the floor plan: rear windows and a simple rear door only, no covered porch, deck, or patio."

    return (
        f"Photorealistic {view_label} exterior architectural render, {stories}-story {style} {prop}"
        + (f", {siding} siding" if siding else "")
        + (f", {roof} roof" if roof else "")
        + (f", {features}" if features else "")
        + ". Professional real estate photography, bright natural daylight, blue sky, "
        "manicured landscaping, no people, ultra-realistic 8K architectural visualization."
        + entry_note
    )


def _interior_prompt(spec: dict) -> str:
    room = spec.get("room_type") or "living room"
    style = (
        spec.get("interior_style")
        or spec.get("design_style")
        or spec.get("style")
        or "modern"
    ).replace("_", " ")
    materials = spec.get("target_materials") or spec.get("design_notes") or ""
    updates = spec.get("desired_updates") or spec.get("description") or ""
    return (
        f"Photorealistic {room} interior renovation render, {style} design"
        + (f", {materials}" if materials else "")
        + (f", {updates}" if updates else "")
        + ". Professional interior design photography, natural lighting, high-end finishes, "
        "no people, ultra-realistic 8K architectural photography."
    )


# ---------------------------------------------------------------------------
# Image generation via OpenAI
# ---------------------------------------------------------------------------

def _generate_image_bytes(prompt: str, size: str = "1024x1024") -> bytes:
    """Generate one image and return its raw PNG bytes, without persisting."""
    client = _openai_client()
    resp = client.images.generate(
        model=_OPENAI_IMAGE_MODEL,
        prompt=prompt,
        size=size,
        n=1,
    )

    item = resp.data[0]
    b64_data = getattr(item, "b64_json", None)
    if b64_data:
        return base64.b64decode(b64_data)

    url = getattr(item, "url", None)
    if url:
        resp2 = requests.get(url, timeout=60)
        resp2.raise_for_status()
        return resp2.content

    raise RuntimeError("OpenAI returned no image data")


def _generate_image_url(prompt: str, size: str = "1024x1024") -> str:
    """Generate one image and return a persisted URL."""
    return _persist_image_bytes(_generate_image_bytes(prompt, size))


def _composite_floor_plans(floor_images: list[bytes]) -> bytes:
    """Combine separately-generated per-floor plan images into one
    side-by-side sheet. Asking an image model to draw every floor of a
    multi-story home correctly in a single generation is unreliable (it
    tends to draw just one floor's plan regardless of how the prompt is
    worded) -- generating each floor on its own and compositing them here
    guarantees the right floor count instead of hoping for it."""
    from PIL import Image as PILImage

    if len(floor_images) == 1:
        return floor_images[0]

    images = [PILImage.open(BytesIO(b)).convert("RGB") for b in floor_images]
    target_height = min(img.height for img in images)
    resized = []
    for img in images:
        if img.height != target_height:
            ratio = target_height / img.height
            img = img.resize((max(1, int(img.width * ratio)), target_height))
        resized.append(img)

    gap = 24
    total_width = sum(img.width for img in resized) + gap * (len(resized) - 1)
    canvas = PILImage.new("RGB", (total_width, target_height), "white")
    x = 0
    for img in resized:
        canvas.paste(img, (x, 0))
        x += img.width + gap

    out = BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue()


def _generate_blueprint_url(spec: dict) -> str:
    """Generate the blueprint output: one floor for single-story projects,
    or one floor at a time composited into a single side-by-side sheet for
    multi-story projects (see _composite_floor_plans)."""
    total_floors = _stories_count(spec)
    if total_floors <= 1:
        return _generate_image_url(_blueprint_prompt(spec), "1024x1024")

    floor_images = [
        _generate_image_bytes(_blueprint_prompt(spec, floor_number=n, total_floors=total_floors), "1024x1024")
        for n in range(1, total_floors + 1)
    ]
    return _persist_image_bytes(_composite_floor_plans(floor_images))


def _persist_image_bytes(img_bytes: bytes) -> str:
    """Save raw PNG bytes to Spaces (preferred) or local static. Returns public URL."""
    filename = f"{uuid.uuid4().hex}.png"

    # Try DigitalOcean Spaces first
    try:
        from LoanMVP.services.investor.investor_media_helpers import (
            _get_spaces_client,
            SPACES_BUCKET,
            _public_spaces_url,
        )
        client = _get_spaces_client()
        key = f"studio/cloud/{filename}"
        client.put_object(
            Bucket=SPACES_BUCKET,
            Key=key,
            Body=img_bytes,
            ACL="public-read",
            ContentType="image/png",
        )
        return _public_spaces_url(key)
    except Exception:
        pass

    # Fall back to local static folder
    from flask import current_app
    folder = "uploads/studios/cloud"
    static_dir = os.path.join(current_app.root_path, "static", folder)
    os.makedirs(static_dir, exist_ok=True)
    filepath = os.path.join(static_dir, filename)
    with open(filepath, "wb") as f:
        f.write(img_bytes)
    return f"/static/{folder}/{filename}"


def _persist_image_b64(b64_data: str) -> str:
    """Save base64 image to Spaces (preferred) or local static. Returns public URL."""
    return _persist_image_bytes(base64.b64decode(b64_data))


# ---------------------------------------------------------------------------
# Deal/scope analysis via Claude
# ---------------------------------------------------------------------------

def _run_deal_analysis(spec: dict) -> dict:
    """Use Claude to produce scope, materials, phases, timeline, and risks."""
    import json

    client = _anthropic_client()

    prop = (spec.get("property_type") or "single-family").replace("_", " ")
    style = (spec.get("style") or "modern").replace("_", " ")
    stories = spec.get("stories") or "2"
    desc = spec.get("description") or spec.get("build_description") or ""
    location = spec.get("location") or spec.get("address") or ""
    notes = spec.get("notes") or spec.get("special_features") or ""
    lot = spec.get("lot_size") or ""
    zoning = spec.get("zoning") or ""
    beds = spec.get("bedrooms") or ""
    baths = spec.get("bathrooms") or ""
    sq = spec.get("square_feet_target") or spec.get("square_feet") or ""

    prompt = f"""You are a senior commercial real estate development analyst and licensed architect.
Analyze this build project and return a comprehensive development package as JSON.

Project:
- Type: {prop}
- Style: {style}
- Stories: {stories}
- Bedrooms: {beds}, Bathrooms: {baths}
- Target sq ft: {sq}
- Location: {location}
- Lot size: {lot}, Zoning: {zoning}
- Description: {desc}
- Notes: {notes}

Return ONLY valid JSON — no markdown, no commentary:
{{
  "scope": {{
    "intent": "build_package",
    "property_type": "{prop}",
    "project_name": "string",
    "stories": "{stories}",
    "bedrooms": "{beds}",
    "bathrooms": "{baths}",
    "target_square_feet": "{sq}",
    "location": "{location}",
    "notes": "string"
  }},
  "materials": [
    {{"category": "string", "selection": "string", "finish_level": "standard|premium|luxury", "notes": "string"}}
  ],
  "phases": [
    {{"name": "string", "owner": "string", "status": "draft|queued", "deliverable": "string"}}
  ],
  "timeline": {{
    "planning_days": 0,
    "design_days": 0,
    "estimated_build_weeks": 0,
    "critical_path": ["string"]
  }},
  "risks": [
    {{"level": "low|medium|high", "type": "string", "message": "string"}}
  ]
}}"""

    message = client.messages.create(
        model=_ANTHROPIC_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    # Claude's response can include non-text blocks (e.g. a ThinkingBlock)
    # before the actual text -- content[0] isn't reliably the text block.
    text_block = next((block for block in message.content if getattr(block, "type", None) == "text"), None)
    if text_block is None:
        raise RuntimeError("Claude deal analysis response contained no text block.")
    text = text_block.text.strip()
    if text.startswith("```"):
        text = text.strip("`").replace("json", "", 1).strip()
    return json.loads(text)


# ---------------------------------------------------------------------------
# Output mode routing
# ---------------------------------------------------------------------------

def _resolve_output_modes(spec: dict) -> list:
    modes = spec.get("output_modes") or []
    if modes:
        return modes

    studio = (spec.get("studio") or spec.get("task") or "").lower()
    intent = (spec.get("intent") or spec.get("build_mode") or "").lower()

    if "interior" in studio or "design" in studio:
        return ["interior"]
    if intent == "blueprint":
        return ["blueprint"]
    if intent == "siteplan":
        return ["siteplan"]
    if intent == "exterior_from_blueprint":
        return ["blueprint", "siteplan", "exterior_front", "exterior_back"]
    if intent == "exterior_from_photo":
        return ["exterior_front", "exterior_back"]
    return ["blueprint", "siteplan", "exterior_front", "exterior_back"]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_cloud_generation(spec: dict) -> dict:
    """
    Generate build/design outputs using OpenAI (images) + Claude (analysis).
    Returns a response dict in the same format expected by generator_build's
    _normalize_generator_outputs() and _build_intelligence_package().
    """
    output_modes = _resolve_output_modes(spec)
    outputs: dict = {}
    errors: dict = {}

    # ── Image generation ──────────────────────────────────────────────────────
    for mode in output_modes:
        try:
            if mode == "blueprint":
                url = _generate_blueprint_url(spec)
                outputs["blueprint"] = {"image_url": url, "images": [url], "output_mode": "blueprint"}

            elif mode == "siteplan":
                url = _generate_image_url(_siteplan_prompt(spec), "1024x1024")
                outputs["siteplan"] = {"image_url": url, "images": [url], "output_mode": "siteplan"}

            elif mode in ("exterior_front", "exterior"):
                url = _generate_image_url(_exterior_prompt(spec, "front"), "1536x1024")
                outputs["exterior"] = {"image_url": url, "images": [url], "output_mode": "exterior_front"}

            elif mode == "exterior_back":
                url = _generate_image_url(_exterior_prompt(spec, "back"), "1536x1024")
                outputs["exterior_back"] = {"image_url": url, "images": [url], "output_mode": "exterior_back"}

            elif mode == "interior":
                url = _generate_image_url(_interior_prompt(spec), "1024x1024")
                outputs["interior"] = {"image_url": url, "images": [url], "output_mode": "interior"}

        except Exception as exc:
            log.warning("Cloud generation failed for mode %s: %s", mode, exc)
            errors[mode] = str(exc)

    # ── Deal/scope analysis via Claude ────────────────────────────────────
    analysis: dict = {}
    try:
        analysis = _run_deal_analysis(spec)
    except Exception as exc:
        log.warning("Cloud deal analysis (Claude) failed: %s", exc)

    # ── Build response in renovation engine format ────────────────────────
    primary_url = ""
    for key in ("exterior", "blueprint", "siteplan", "interior"):
        block = outputs.get(key)
        if isinstance(block, dict) and block.get("image_url"):
            primary_url = block["image_url"]
            break

    all_urls = [
        v["image_url"]
        for v in outputs.values()
        if isinstance(v, dict) and v.get("image_url")
    ]

    result: dict = {
        "status": "ok",
        "provider": "openai_cloud",
        "image_url": primary_url,
        "images": all_urls,
    }

    # Mirror the output key aliases that _normalize_generator_outputs expects
    for key, block in outputs.items():
        result[key] = block
        result[f"{key}_result"] = block

    # Nest under "build" so _candidate_payload_blocks finds the outputs
    result["build"] = {"outputs": outputs, "image_url": primary_url, "spec": spec}

    if analysis:
        result["scope"] = analysis.get("scope", {})
        result["materials"] = analysis.get("materials", [])
        result["phases"] = analysis.get("phases", [])
        result["timeline"] = analysis.get("timeline", {})
        result["risks"] = analysis.get("risks", [])

    if errors:
        result["generation_errors"] = errors

    return result
