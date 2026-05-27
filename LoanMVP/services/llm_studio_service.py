"""LLM-backed fallback for studio image generation and deal analysis.

Used when the GPU Renovation Engine is unavailable.
  - Image generation  → DALL-E 3 (OpenAI)
  - Deal analysis     → Claude (Anthropic)

Set AI_IMAGE_BACKEND=openai to bypass the engine entirely, or just let
the engine callers catch RuntimeError and call these helpers as a fallback.
"""

from __future__ import annotations

import json
import logging
import os
import uuid

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Clients (lazy — only imported when called so missing packages don't crash)
# ---------------------------------------------------------------------------

def _openai_client():
    from openai import OpenAI
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    return OpenAI(api_key=key)


def _anthropic_client():
    import anthropic
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")
    return anthropic.Anthropic(api_key=key)


# ---------------------------------------------------------------------------
# Image generation — DALL-E 3
# ---------------------------------------------------------------------------

_MODE_PREFIX = {
    "blueprint": (
        "Precise architectural floor-plan blueprint, clean black lines on white paper, "
        "top-down orthographic view, room layout visible, no text labels, no dimensions, "
        "no title block, no watermarks"
    ),
    "siteplan": (
        "Clean architectural site plan, bird's-eye aerial view, property boundary, "
        "building footprint, driveway, landscaping, no text labels, no watermarks"
    ),
    "exterior_front": (
        "Photorealistic architectural exterior rendering, front elevation, "
        "professional CGI quality, natural daylight, landscaped yard, no text or watermarks"
    ),
    "exterior_back": (
        "Photorealistic architectural exterior rendering, rear elevation, "
        "professional CGI quality, natural daylight, no text or watermarks"
    ),
    "interior": (
        "Photorealistic interior design rendering, professional staging, "
        "natural light, high-end finishes, no text or watermarks"
    ),
    "siteplan_aerial": (
        "Aerial site plan rendering, overhead view, property boundaries, "
        "building footprint, no text or watermarks"
    ),
}

_NEGATIVE_SUFFIX = (
    "No collage, no grid, no multiple views in one image, no text overlays, "
    "no watermarks, no labels, no dimension lines, single coherent image only."
)


def _dalle_prompt(mode: str, payload: dict) -> str:
    prefix = _MODE_PREFIX.get(mode) or _MODE_PREFIX["exterior_front"]
    parts = [prefix]

    if payload.get("property_type"):
        parts.append(payload["property_type"].replace("_", " "))
    if payload.get("style"):
        parts.append(f"{payload['style'].replace('_', ' ')} architectural style")
    if payload.get("description"):
        parts.append(payload["description"][:300])
    if payload.get("stories") or payload.get("floor_count") or payload.get("number_of_floors"):
        n = payload.get("stories") or payload.get("floor_count") or payload.get("number_of_floors")
        parts.append(f"{n}-story")
    if payload.get("bedrooms"):
        parts.append(f"{payload['bedrooms']} bedrooms")
    if payload.get("square_feet_target"):
        parts.append(f"approximately {payload['square_feet_target']} sq ft")
    if payload.get("location"):
        parts.append(f"located in {payload['location']}")
    if payload.get("special_features"):
        parts.append(payload["special_features"][:200])

    parts.append("presentation-ready, photorealistic")
    parts.append(_NEGATIVE_SUFFIX)

    return ", ".join(p.strip() for p in parts if p.strip())


def dalle_generate_images(payload: dict) -> dict:
    """Call DALL-E 3 for each requested output mode.

    Returns a dict shaped like the Renovation Engine response so callers
    don't need to change their parsing logic:
      {
        "images_base64": {"blueprint": "...", "exterior_front": "...", ...},
        "job_id": "<uuid>",
        "seed": 0,
        "meta": {"provider": "openai/dall-e-3"},
        "ok": True,
      }
    """
    client = _openai_client()

    output_modes = (
        payload.get("output_modes")
        or payload.get("outputs")
        or ["exterior_front"]
    )

    images_b64: dict[str, str | None] = {}
    errors: list[str] = []

    for mode in output_modes:
        prompt = _dalle_prompt(mode, payload)
        try:
            resp = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                n=1,
                size="1024x1024",
                quality="hd",
                response_format="b64_json",
            )
            images_b64[mode] = resp.data[0].b64_json
            log.info("DALL-E 3 generated %s OK", mode)
        except Exception as exc:
            log.error("DALL-E 3 failed for mode=%s: %s", mode, exc)
            errors.append(f"{mode}: {exc}")
            images_b64[mode] = None

    result = {
        "images_base64": images_b64,
        "job_id": uuid.uuid4().hex,
        "seed": 0,
        "meta": {
            "provider": "openai/dall-e-3",
            "errors": errors,
        },
        "ok": not errors or any(v for v in images_b64.values()),
    }

    # Fire-and-forget training data log (b64 URLs are logged after upload by callers)
    try:
        from LoanMVP.services.training_service import log_studio_batch
        feature = payload.get("feature") or payload.get("mode") or "studio"
        log_studio_batch(
            feature=feature,
            provider="dalle3",
            payload=payload,
            images_b64_or_urls={k: "" for k in images_b64 if images_b64[k]},
            is_urls=False,
        )
    except Exception:
        pass

    return result


# ---------------------------------------------------------------------------
# Deal analysis — Claude
# ---------------------------------------------------------------------------

_DEAL_SYSTEM = (
    "You are Ravlo Deal Architect, an expert real estate investment analyst. "
    "You produce structured, realistic investment strategy recommendations. "
    "Always respond with valid JSON only — no markdown, no prose outside the JSON."
)

_DEAL_SCHEMA = """{
  "strategies": [
    {
      "name": "Strategy Name",
      "type": "fix_flip|rental|development|brrrr|wholesale",
      "headline": "One-line investor-facing summary",
      "description": "2-3 sentence plain-English description",
      "estimated_profit": 45000,
      "estimated_roi": 18.5,
      "timeline_months": 6,
      "risk_level": "low|medium|high",
      "pros": ["pro 1", "pro 2"],
      "cons": ["con 1"],
      "capital_required": 80000,
      "exit_strategy": "sell|refi|hold"
    }
  ],
  "market_notes": "Brief market context sentence",
  "recommendation": "Top recommended strategy name"
}"""


def claude_deal_analysis(payload: dict) -> dict:
    """Generate deal architect strategies and analysis using Claude.

    Returns a dict with a ``strategies`` list and supporting fields.
    Falls back to an empty result dict on any error so callers don't crash.
    """
    client = _anthropic_client()

    address      = payload.get("property_address") or payload.get("address") or "unknown"
    prop_type    = payload.get("property_type") or "residential"
    budget       = payload.get("budget") or "not specified"
    zoning       = payload.get("zoning") or "not specified"
    lot_size     = payload.get("lot_size") or "not specified"
    state        = payload.get("state") or ""
    zip_code     = payload.get("zip_code") or ""
    notes        = payload.get("notes") or ""
    strategy_goal = payload.get("strategy_goal") or "maximize return"

    user_msg = (
        f"Analyze this real estate opportunity and return exactly 3 investment strategies.\n\n"
        f"Property: {address}\n"
        f"Type: {prop_type}\n"
        f"State: {state}  ZIP: {zip_code}\n"
        f"Budget: {budget}\n"
        f"Zoning: {zoning}\n"
        f"Lot size: {lot_size}\n"
        f"Goal: {strategy_goal}\n"
        f"Notes: {notes}\n\n"
        f"Respond with a JSON object matching this schema exactly:\n{_DEAL_SCHEMA}"
    )

    try:
        response = _anthropic_client().messages.create(
            model="claude-opus-4-7",
            max_tokens=2048,
            system=_DEAL_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text.strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        result = json.loads(raw)
        result.setdefault("meta", {})
        result["meta"]["provider"] = "anthropic/claude"
        return result

    except json.JSONDecodeError as exc:
        log.error("Claude deal analysis returned invalid JSON: %s", exc)
        return {"strategies": [], "error": "Invalid JSON from Claude", "meta": {"provider": "anthropic/claude"}}
    except Exception as exc:
        log.error("Claude deal analysis failed: %s", exc)
        return {"strategies": [], "error": str(exc), "meta": {"provider": "anthropic/claude"}}
