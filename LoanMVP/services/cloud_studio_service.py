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
from typing import Optional

log = logging.getLogger(__name__)

_OPENAI_IMAGE_MODEL = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1")
_ANTHROPIC_MODEL = os.environ.get("CLOUD_STUDIO_CLAUDE_MODEL", "claude-sonnet-4-6")


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

def _blueprint_prompt(spec: dict) -> str:
    prop = (spec.get("property_type") or "single-family home").replace("_", " ")
    stories = spec.get("stories") or "2"
    style = (spec.get("style") or "modern").replace("_", " ")
    beds = spec.get("bedrooms", "")
    baths = spec.get("bathrooms", "")
    sq = spec.get("square_feet_target") or spec.get("square_feet", "")
    desc = spec.get("description") or spec.get("special_features") or ""

    details = []
    if beds:
        details.append(f"{beds} bedrooms")
    if baths:
        details.append(f"{baths} bathrooms")
    if sq:
        details.append(f"{sq} sq ft")
    detail_str = ", ".join(details)

    return (
        f"Professional architectural floor plan blueprint, top-down view, clean black lines "
        f"on white background, room labels, dimensions, {stories}-story {style} {prop}"
        + (f", {detail_str}" if detail_str else "")
        + (f", {desc}" if desc else "")
        + ". CAD technical drawing style, no people, white background, professional drafting quality."
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
    return (
        f"Photorealistic {view_label} exterior architectural render, {stories}-story {style} {prop}"
        + (f", {siding} siding" if siding else "")
        + (f", {roof} roof" if roof else "")
        + (f", {features}" if features else "")
        + ". Professional real estate photography, bright natural daylight, blue sky, "
        "manicured landscaping, no people, ultra-realistic 8K architectural visualization."
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

def _generate_image_url(prompt: str, size: str = "1024x1024") -> str:
    """Generate one image and return a persisted URL."""
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
        return _persist_image_b64(b64_data)

    url = getattr(item, "url", None)
    if url:
        return url

    raise RuntimeError("OpenAI returned no image data")


def _persist_image_b64(b64_data: str) -> str:
    """Save base64 image to Spaces (preferred) or local static. Returns public URL."""
    filename = f"{uuid.uuid4().hex}.png"
    img_bytes = base64.b64decode(b64_data)

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

    text = message.content[0].text.strip()
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
                url = _generate_image_url(_blueprint_prompt(spec), "1024x1024")
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
