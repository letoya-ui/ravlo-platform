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

    if mode == "interior":
        if payload.get("room_type"):
            parts.append(f"{payload['room_type'].replace('_', ' ')} room")
        if payload.get("style"):
            parts.append(f"{payload['style'].replace('_', ' ')} interior design style")
        if payload.get("finish_level"):
            parts.append(f"{payload['finish_level'].replace('_', ' ')} finishes")
        if payload.get("target_materials"):
            parts.append(payload["target_materials"][:250])
        # Pull the full AI-crafted design direction from whichever field is populated
        creative = (
            payload.get("engine_prompt")
            or payload.get("prompt_notes")
            or payload.get("desired_updates")
            or payload.get("prompt")
            or payload.get("description")
            or ""
        )
        if creative:
            parts.append(creative[:500])
        if payload.get("notes") or payload.get("design_notes") or payload.get("interior_notes"):
            notes = (
                payload.get("notes")
                or payload.get("design_notes")
                or payload.get("interior_notes")
            )
            parts.append(notes[:200])
    else:
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
        "meta": {"provider": "openai/gpt-image-1"},
        "ok": True,
      }
    """
    client = _openai_client()

    # Prefer an explicit list; fall back to the single-mode fields used by the
    # interior/design routes ("output_mode", "mode"), then exterior as last resort.
    _single = payload.get("output_mode") or payload.get("mode")
    output_modes = list(
        payload.get("output_modes")
        or payload.get("outputs")
        or ([_single] if _single else ["exterior_front"])
    )

    # When both an exterior and a blueprint are requested, generate the exterior
    # first so the blueprint can be derived from it — keeping both images
    # architecturally consistent (same house).
    _exterior_modes = ("exterior_front", "exterior")
    _needs_derivation = "blueprint" in output_modes and any(m in output_modes for m in _exterior_modes)
    if _needs_derivation:
        ext_mode = next((m for m in _exterior_modes if m in output_modes), None)
        if ext_mode and output_modes.index(ext_mode) > output_modes.index("blueprint"):
            output_modes.remove(ext_mode)
            output_modes.insert(0, ext_mode)

    images_b64: dict[str, str | None] = {}
    errors: list[str] = []

    for mode in output_modes:
        # Blueprint — derive from the exterior image when available so both
        # outputs show the same house design.
        if mode == "blueprint" and _needs_derivation:
            ext_b64 = next(
                (images_b64.get(m) for m in _exterior_modes if images_b64.get(m)),
                None,
            )
            if ext_b64:
                try:
                    import base64 as _b64
                    import io
                    image_file = io.BytesIO(_b64.b64decode(ext_b64))
                    image_file.name = "exterior.png"
                    resp = client.images.edit(
                        model="gpt-image-1",
                        image=image_file,
                        prompt=(
                            "Precise architectural floor-plan blueprint of this exact house. "
                            "Top-down orthographic view, clean black lines on white paper, "
                            "room layout visible, walls as thick lines, openings for doors and "
                            "windows, no text labels, no dimensions, no title block, no watermarks, "
                            "single plan only."
                        ),
                        n=1,
                        size="1024x1024",
                    )
                    item = resp.data[0]
                    b64 = getattr(item, "b64_json", None)
                    if not b64:
                        url = getattr(item, "url", None)
                        if url:
                            import urllib.request
                            import base64 as _b64m
                            with urllib.request.urlopen(url) as r:
                                b64 = _b64m.b64encode(r.read()).decode()
                    images_b64[mode] = b64
                    log.info("gpt-image-1 derived blueprint from exterior OK")
                    continue
                except Exception as exc:
                    log.warning(
                        "gpt-image-1 blueprint-from-exterior failed, falling back to independent: %s", exc
                    )

        prompt = _dalle_prompt(mode, payload)
        try:
            resp = client.images.generate(
                model="gpt-image-1",
                prompt=prompt,
                n=1,
                size="1024x1024",
                quality="high",
            )
            item = resp.data[0]
            b64 = getattr(item, "b64_json", None)
            if not b64:
                url = getattr(item, "url", None)
                if url:
                    import base64 as _b64
                    import urllib.request
                    with urllib.request.urlopen(url) as r:
                        b64 = _b64.b64encode(r.read()).decode()
            images_b64[mode] = b64
            log.info("gpt-image-1 generated %s OK", mode)
        except Exception as exc:
            log.error("gpt-image-1 failed for mode=%s: %s", mode, exc)
            exc_str = str(exc)
            # Billing hard-limit is unrecoverable for all modes — raise immediately
            # so callers can surface a clear message rather than silently returning
            # empty images that produce a confusing "Upload failed" error.
            if "billing_hard_limit_reached" in exc_str or "billing hard limit" in exc_str.lower():
                raise RuntimeError(
                    "Image generation is temporarily unavailable: your OpenAI account billing "
                    "limit has been reached. Please increase the limit in your OpenAI dashboard "
                    "and try again."
                ) from exc
            errors.append(f"{mode}: {exc}")
            images_b64[mode] = None

    result = {
        "images_base64": images_b64,
        "job_id": uuid.uuid4().hex,
        "seed": 0,
        "meta": {
            "provider": "openai/gpt-image-1",
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
            model="claude-sonnet-5",
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


_BUDGET_SYSTEM = (
    "You are Ravlo Design Studio's budget estimator, an expert residential renovation "
    "cost estimator. You produce realistic, US-market line-item cost estimates. "
    "Always respond with valid JSON only — no markdown, no prose outside the JSON."
)

_BUDGET_SCHEMA = """{
  "cost_low": 12500,
  "cost_high": 18000,
  "summary": "One or two sentence plain-English summary of the estimate",
  "line_items": [
    {"category": "Materials", "name": "Flooring", "cost_low": 3000, "cost_high": 4500},
    {"category": "Labor", "name": "Installation", "cost_low": 2000, "cost_high": 3000}
  ]
}"""


def claude_design_budget_estimate(payload: dict) -> dict:
    """Generate a Design/Rehab Studio room budget estimate using Claude.

    Mirrors the shape the Renovation Engine's /v1/design_studio/generate_budget
    endpoint returns (cost_low, cost_high, summary, line_items, meta) so callers
    don't need to branch on which provider produced the estimate.
    """
    room_type = payload.get("room_type") or payload.get("room_focus") or "room"
    style = payload.get("style") or payload.get("design_style") or "modern"
    finish_level = payload.get("finish_level") or "standard"
    rehab_level = payload.get("rehab_level") or "medium"
    sqft = payload.get("room_square_feet") or payload.get("square_feet") or "not specified"
    budget_min = payload.get("budget_min")
    budget_max = payload.get("budget_max")
    target_materials = payload.get("target_materials") or "not specified"
    notes = payload.get("desired_updates") or payload.get("design_notes") or ""
    market_multiplier = payload.get("market_cost_multiplier")

    user_msg = (
        f"Estimate a renovation/design budget for this project.\n\n"
        f"Room / focus: {room_type}\n"
        f"Style: {style}\n"
        f"Finish level: {finish_level}\n"
        f"Rehab level: {rehab_level}\n"
        f"Square feet: {sqft}\n"
        f"Target materials: {target_materials}\n"
        f"Investor's budget range: {budget_min or 'not specified'}–{budget_max or 'not specified'}\n"
        f"Notes: {notes}\n"
        f"Local cost multiplier vs. national average: {market_multiplier or 1.0}\n\n"
        f"Respond with a JSON object matching this schema exactly:\n{_BUDGET_SCHEMA}"
    )

    try:
        response = _anthropic_client().messages.create(
            model="claude-sonnet-5",
            max_tokens=1536,
            system=_BUDGET_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text.strip()

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
        log.error("Claude budget estimate returned invalid JSON: %s", exc)
        return {
            "cost_low": 0, "cost_high": 0, "summary": "", "line_items": [],
            "error": "Invalid JSON from Claude", "meta": {"provider": "anthropic/claude"},
        }
    except Exception as exc:
        log.error("Claude budget estimate failed: %s", exc)
        return {
            "cost_low": 0, "cost_high": 0, "summary": "", "line_items": [],
            "error": str(exc), "meta": {"provider": "anthropic/claude"},
        }


_BORROWER_EXPLAINER_SYSTEM = (
    "You are Ravlo's borrower assistant. You explain a borrower's loan status, "
    "open conditions, and required documents in plain, reassuring English. "
    "You must only state facts present in the data provided below — never invent "
    "amounts, dates, dollar figures, approval decisions, or requirements that are "
    "not in the data. If the data doesn't answer the borrower's question, say so "
    "plainly instead of guessing. Always respond with valid JSON only — no markdown, "
    "no prose outside the JSON."
)

_BORROWER_EXPLAINER_SCHEMA = """{
  "summary": "2-3 sentence plain-English status summary",
  "next_steps": ["Specific, actionable next step", "..."],
  "documents_needed": ["Document or condition name still outstanding", "..."],
  "flags": ["Anything high-severity or urgent the borrower should notice"]
}"""


def claude_borrower_explainer(payload: dict) -> dict:
    """Explain a borrower's loan status/conditions/documents using Claude.

    ``payload`` must contain a ``context`` dict (from
    ``borrower_ai_service._shape_context``) and may contain a free-text
    ``question``. Falls back to an empty/error result on any failure so the
    caller can fall back to the deterministic template explanation.
    """
    context = payload.get("context") or {}
    question = payload.get("question") or "What's my current status and what do I need to do next?"

    user_msg = (
        f"Here is the borrower's loan data:\n{json.dumps(context, default=str)}\n\n"
        f"Borrower's question: {question}\n\n"
        f"Respond with a JSON object matching this schema exactly:\n{_BORROWER_EXPLAINER_SCHEMA}"
    )

    try:
        response = _anthropic_client().messages.create(
            model="claude-sonnet-5",
            max_tokens=1024,
            system=_BORROWER_EXPLAINER_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text.strip()

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
        log.error("Claude borrower explainer returned invalid JSON: %s", exc)
        return {
            "summary": "", "next_steps": [], "documents_needed": [], "flags": [],
            "error": "Invalid JSON from Claude", "meta": {"provider": "anthropic/claude"},
        }
    except Exception as exc:
        log.error("Claude borrower explainer failed: %s", exc)
        return {
            "summary": "", "next_steps": [], "documents_needed": [], "flags": [],
            "error": str(exc), "meta": {"provider": "anthropic/claude"},
        }
