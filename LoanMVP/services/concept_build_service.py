"""
concept_build_service.py
------------------------------------
Orchestrates AI-powered concept generation for:
- Master front exterior concept
- Rear exterior concept
- Draft blueprint / floor plan
- Site plan

This service keeps outputs tied to one concept package by using
a shared bundle_job_id and the front exterior as the master design anchor.
"""

import os
import uuid
import requests
from datetime import datetime

from LoanMVP.utils.safe_http import safe_call


AI_ENGINE_BASE_URL = os.getenv("RENOVATION_ENGINE_URL", "http://localhost:8000")
AI_ENGINE_API_KEY = os.getenv("RENOVATION_ENGINE_API_KEY", "")


def _post_engine(path, payload, timeout=240):
    url = f"{AI_ENGINE_BASE_URL.rstrip('/')}{path}"

    headers = {}
    if AI_ENGINE_API_KEY:
        headers["x-api-key"] = AI_ENGINE_API_KEY

    try:
        res = safe_call(requests.post, url, json=payload, headers=headers, timeout=timeout)
        res.raise_for_status()
        return res.json()
    except Exception as exc:
        return {
            "error": True,
            "message": str(exc),
            "payload_mode": payload.get("mode"),
            "payload_output_mode": payload.get("output_mode"),
        }


def _first_image_url(engine_response):
    """
    Your platform route usually uploads base64 images separately.
    If the engine already returns image_url, use it.
    Otherwise return None and let the caller upload images_base64.
    """
    if not isinstance(engine_response, dict):
        return None

    if engine_response.get("image_url"):
        return engine_response["image_url"]

    images = engine_response.get("images") or []
    if images:
        return images[0]

    return None


_BUILD_INIT_IMAGE_KEYS = (
    "image_url",
    "reference_image_url",
    "image_base64",
    "reference_image_base64",
)

_BUILD_COMPAT_IMAGE_KEYS = (
    "site_image_url",
    "site_image_base64",
    "blueprint_image_url",
    "blueprint_image_base64",
    "exterior_image_url",
    "exterior_image_base64",
    "front_exterior_image_url",
    "front_exterior_image_base64",
    "back_exterior_image_url",
    "back_exterior_image_base64",
    "rear_exterior_image_url",
    "rear_exterior_image_base64",
)


def _strip_init_images(payload, *, strip_master=False):
    for key in (*_BUILD_INIT_IMAGE_KEYS, *_BUILD_COMPAT_IMAGE_KEYS):
        payload.pop(key, None)
    if strip_master:
        for key in ("master_exterior_reference_url", "front_style_reference_url", "exterior_front_url"):
            payload.pop(key, None)
    payload["init_img"] = None
    payload["use_image"] = False
    return payload


def _log_build_source_state(payload, mode):
    init_img_loaded = any(bool(payload.get(key)) for key in _BUILD_INIT_IMAGE_KEYS)
    print(
        "[build]",
        "mode=", mode,
        "init_img_loaded=", init_img_loaded,
        "image_url=", bool(payload.get("image_url")),
        "reference_image_url=", bool(payload.get("reference_image_url")),
        "site_context_url=", bool(payload.get("site_context_url")),
    )


def _base_payload(
    *,
    bundle_job_id,
    project_name="",
    property_type="single_family",
    description="",
    style="modern_luxury",
    lot_size=None,
    zoning=None,
    location=None,
    number_of_floors=2,
    bedrooms=None,
    bathrooms=None,
    square_feet=None,
):
    payload = {
        "generation_family": "build",
        "generator_family": "build",
        "generator_type": "build",
        "studio": "build_studio",
        "studio_type": "build_studio",
        "bundle_job_id": bundle_job_id,

        "project_name": project_name,
        "property_type": property_type,
        "style": style,
        "preset": style,
        "description": description,
        "build_description": description,
        "lot_size": lot_size or "",
        "zoning": zoning or "",
        "location": location or "",
        "stories": number_of_floors,
        "number_of_floors": number_of_floors,
        "floor_count": number_of_floors,

        "count": 1,
        "width": 1024,
        "height": 1024,
    }

    if bedrooms is not None:
        payload["bedrooms"] = bedrooms

    if bathrooms is not None:
        payload["bathrooms"] = bathrooms

    if square_feet is not None:
        payload["square_feet"] = square_feet
        payload["square_feet_target"] = square_feet

    return payload


def run_concept_build(
    land_image_url: str = "",
    description: str = "",
    style: str = "modern_luxury",
    lot_size: str = None,
    project_name: str = "",
    property_type: str = "single_family",
    zoning: str = None,
    location: str = None,
    number_of_floors: int = 2,
    bedrooms: int = None,
    bathrooms: float = None,
    square_feet: int = None,
):
    bundle_job_id = uuid.uuid4().hex
    generated_at = datetime.utcnow().isoformat()

    results = {}

    # 1. Master front exterior
    front_payload = _base_payload(
        bundle_job_id=bundle_job_id,
        project_name=project_name,
        property_type=property_type,
        description=description,
        style=style,
        lot_size=lot_size,
        zoning=zoning,
        location=location,
        number_of_floors=number_of_floors,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        square_feet=square_feet,
    )
    front_payload.update({
        "mode": "exterior",
        "output_mode": "exterior_front",
        "task": "build_exterior_front",
        "exterior_view": "front",
        "camera_view": "street_view",
        "source_role": "text_architectural_context",
        "reference_role": "master_front_exterior_generation",
        "site_context_url": land_image_url or "",
        "prompt": (
            "MASTER DESIGN ANCHOR. Generate the street-facing front exterior of the home. "
            "This front exterior defines the architectural identity for the whole build package. "
            "Use a coherent buildable residential design with consistent massing, roof geometry, "
            "window rhythm, material palette, curb appeal, front entry, and landscaping. "
            f"Style: {style}. Description: {description}."
        ),
        "prompt_notes": (
            "Generate one photorealistic front exterior rendering only. "
            "Do not create a rear view, floor plan, site plan, collage, labels, or presentation board."
        ),
        "steps": 32,
        "guidance": 9.0,
        "strength": 0.25,
        "use_image": False,
        "init_img": None,
    })

    _strip_init_images(front_payload)
    _log_build_source_state(front_payload, "exterior_front")
    front = _post_engine("/v1/build_concept", front_payload)
    if front.get("error"):
        return front

    master_exterior_url = _first_image_url(front) or ""
    results["exterior_front"] = front

    # 2. Rear exterior, anchored to front if URL is available
    rear_payload = _base_payload(
        bundle_job_id=bundle_job_id,
        project_name=project_name,
        property_type=property_type,
        description=description,
        style=style,
        lot_size=lot_size,
        zoning=zoning,
        location=location,
        number_of_floors=number_of_floors,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        square_feet=square_feet,
    )
    rear_payload.update({
        "mode": "exterior",
        "output_mode": "exterior_back",
        "task": "build_exterior_back",
        "exterior_view": "back",
        "camera_view": "rear_yard_view",
        "source_role": "text_plus_architectural_context",
        "reference_role": "front_exterior_style_anchor" if master_exterior_url else "text_architectural_context",
        "generation_mode": "rear_from_front_style_anchor" if master_exterior_url else "text_to_rear_exterior",
        "site_context_url": land_image_url or "",
        "master_exterior_reference_url": master_exterior_url,
        "preserve_style": True,
        "preserve_materials": True,
        "preserve_massing": False,
        "preserve_camera": False,
        "preserve_composition": False,
        "style_reference_only": False,
        "pipe_mode": "depth",
        "rear_depth_scale": 0.10,
        "controlnet_scale": 0.10,
        "prompt": (
            "rear elevation of the same home, backyard-facing facade, rear patio doors, "
            "rear glazing, backyard landscaping, pool-facing composition, private rear architecture, "
            "same materials and roofline, different composition from front exterior"
        ),
        "prompt_notes": (
            "This must clearly be the rear/backyard exterior, not a second front exterior rendering."
        ),
        "negative_prompt": (
            "front facade, front entry, street-facing elevation, curb appeal composition, "
            "driveway-focused composition, garage-forward composition, same image as front"
        ),
        "steps": 30,
        "guidance": 7.8,
        "strength": 0.18,
    })

    rear = _post_engine("/v1/build_concept", rear_payload)
    if rear.get("error"):
        return rear
    results["exterior_back"] = rear

    # 3. Blueprint, text-only for beta
    blueprint_payload = _base_payload(
        bundle_job_id=bundle_job_id,
        project_name=project_name,
        property_type=property_type,
        description=description,
        style=style,
        lot_size=lot_size,
        zoning=zoning,
        location=location,
        number_of_floors=number_of_floors,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        square_feet=square_feet,
    )
    blueprint_payload.update({
        "mode": "blueprint",
        "output_mode": "blueprint",
        "task": "build_blueprint",
        "reference_role": "text_program_only",
        "source_role": "text_program_only",
        "blueprint_constrained": False,
        "site_context_url": "",
        "prompt": (
            "Generate a clean top-down architectural floor plan for the same home concept "
            "as the master exterior. Use the same floor count, residential program, scale, "
            "and buildable massing implied by the master exterior. Output a single legible "
            "architectural plan with walls, rooms, doors, windows, stairs, kitchen fixtures, "
            "bathroom fixtures, closets, and simple furniture blocks."
        ),
        "prompt_notes": (
            "Do not use satellite imagery, trees, grass, site photo texture, aerial map visuals, "
            "landscape photography, exterior rendering style, collage, labels, or presentation board."
        ),
        "negative_prompt": (
            "trees, grass, aerial imagery, satellite image, site photo, landscape photo, "
            "photorealistic exterior, facade, street view, title block, fake text, watermark"
        ),
        "steps": 30,
        "guidance": 6.8,
        "strength": 0.0,
    })
    _strip_init_images(blueprint_payload, strip_master=True)
    _log_build_source_state(blueprint_payload, "blueprint")

    blueprint = _post_engine("/v1/build_concept", blueprint_payload)
    if blueprint.get("error"):
        return blueprint
    results["blueprint"] = blueprint

    # 4. Site plan, text-generated with land/site image as metadata only
    siteplan_payload = _base_payload(
        bundle_job_id=bundle_job_id,
        project_name=project_name,
        property_type=property_type,
        description=description,
        style=style,
        lot_size=lot_size,
        zoning=zoning,
        location=location,
        number_of_floors=number_of_floors,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        square_feet=square_feet,
    )
    siteplan_payload.update({
        "mode": "siteplan",
        "output_mode": "siteplan",
        "task": "build_siteplan",
        "reference_role": "site_context_reference",
        "source_role": "site_context",
        "site_context_url": land_image_url or "",
        "prompt": (
            "Create a site development plan for the same home concept as the master exterior. "
            "Use the lot/site image only as site context, not as a blueprint or exterior render. "
            "Show parcel boundary, building footprint, driveway, parking, walkways, patio or yard zones, "
            "hardscape, landscaping zones, setbacks, and orientation. Keep the building footprint "
            "consistent with the same home package."
        ),
        "prompt_notes": (
            "Output one clean top-down site development plan only. No photorealistic exterior, "
            "no floor plan sheet, no collage, no fake labels."
        ),
        "steps": 32,
        "guidance": 7.0,
        "strength": 0.0,
    })
    _strip_init_images(siteplan_payload, strip_master=True)
    siteplan_payload["site_context_url"] = land_image_url or ""
    siteplan_payload["reference_role"] = "site_context_metadata"
    _log_build_source_state(siteplan_payload, "siteplan")

    siteplan = _post_engine("/v1/build_concept", siteplan_payload)
    if siteplan.get("error"):
        return siteplan
    results["siteplan"] = siteplan

    return {
        "status": "ok",
        "bundle_job_id": bundle_job_id,
        "master_exterior_reference_url": master_exterior_url,
        "results": results,
        "description": description,
        "style": style,
        "lot_size": lot_size,
        "generated_at": generated_at,
    }
