import os
from typing import Any, Dict, Optional

import requests


RENOVATION_ENGINE_URL = os.getenv(
    "RENOVATION_ENGINE_URL",
    "http://renovation-engine:8000",
)


class RenovationEngineError(Exception):
    pass


def _headers(api_key: Optional[str] = None) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if api_key:
        headers["X-API-Key"] = api_key
    return headers


def _post_json(
    endpoint: str,
    payload: Dict[str, Any],
    *,
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: int = 300,
) -> Dict[str, Any]:
    base_url = (api_url or RENOVATION_ENGINE_URL).rstrip("/")

    try:
        response = requests.post(
            f"{base_url}{endpoint}",
            json=payload,
            headers=_headers(api_key),
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        detail = ""
        response = getattr(exc, "response", None)
        if response is not None:
            try:
                detail = f" Response: {response.text}"
            except Exception:
                detail = ""
        raise RenovationEngineError(
            f"Renovation engine request failed at {endpoint}: {exc}.{detail}"
        ) from exc


def call_renovation_engine_upload(
    *,
    file_storage,
    prompt: str,
    api_url: str,
    api_key: Optional[str] = None,
    negative_prompt: str = "",
    preset: str = "modern",
    mode: str = "photo",
    width: int = 1024,
    height: int = 1024,
    steps: int = 30,
    guidance: float = 7.5,
    strength: float = 0.75,
    count: int = 1,
    seed: Optional[int] = None,
    controlnet_scale: float = 0.8,
    generation_family: str = "rehab",
):
    """
    Upload route for old photo-preserving rehab.

    Design Studio should usually send base64/json to /v1/build_concept instead.
    """
    family = (generation_family or "rehab").strip().lower()
    endpoint = "/v1/renovate-upload"

    headers = _headers(api_key)

    files = {
        "image": (
            file_storage.filename or "upload.jpg",
            file_storage.stream,
            file_storage.mimetype or "application/octet-stream",
        )
    }

    data = {
        "generation_family": family,
        "generator_family": family,
        "studio": "rehab_studio" if family == "rehab" else "design_studio",
        "studio_type": "rehab_studio" if family == "rehab" else "design_studio",
        "task": "photo_rehab" if family == "rehab" else "interior_design",
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "preset": preset,
        "mode": mode,
        "width": str(width),
        "height": str(height),
        "steps": str(steps),
        "guidance": str(guidance),
        "strength": str(strength),
        "count": str(count),
        "controlnet_scale": str(controlnet_scale),
    }

    if seed is not None:
        data["seed"] = str(seed)

    try:
        response = requests.post(
            f"{api_url.rstrip('/')}{endpoint}",
            headers=headers,
            files=files,
            data=data,
            timeout=300,
        )
        response.raise_for_status()
        return response.json()

    except requests.RequestException as exc:
        detail = ""
        response = getattr(exc, "response", None)
        if response is not None:
            try:
                detail = f" Response: {response.text}"
            except Exception:
                detail = ""
        raise RenovationEngineError(
            f"Renovation generator upload failed: {exc}.{detail}"
        ) from exc


def generate_design_concept(
    payload: Dict[str, Any],
    *,
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: int = 300,
) -> Dict[str, Any]:
    """
    Prompt-led Design Studio / Build Concept route.

    Use this for:
    - Design Studio text-to-image
    - Design Studio image-guided interior concepts
    - blueprint-to-interior concepts
    """
    payload = dict(payload)
    payload.setdefault("generation_family", "design")
    payload.setdefault("generator_family", "design")
    payload.setdefault("generator_type", "design")
    payload.setdefault("studio", "design_studio")
    payload.setdefault("studio_type", "design_studio")
    payload.setdefault("task", "interior_design")
    payload.setdefault("mode", "interior")
    payload.setdefault("output_mode", "interior")
    payload.setdefault("steps", 34)
    payload.setdefault("guidance", 9.6)
    payload.setdefault("strength", 0.86)

    return _post_json(
        "/v1/build_concept",
        payload,
        api_url=api_url,
        api_key=api_key,
        timeout=timeout,
    )


def generate_rehab_mockup(
    payload: Dict[str, Any],
    *,
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: int = 300,
) -> Dict[str, Any]:
    """
    Photo-preserving Rehab Studio route.

    Use this for:
    - construction/rehab mockups
    - existing photo renovation
    - preserve existing property/photo more strongly
    """
    payload = dict(payload)
    payload.setdefault("generation_family", "rehab")
    payload.setdefault("generator_family", "rehab")
    payload.setdefault("studio", "rehab_studio")
    payload.setdefault("studio_type", "rehab_studio")
    payload.setdefault("task", "photo_rehab")
    payload.setdefault("mode", "hgtv")
    payload.setdefault("steps", 32)
    payload.setdefault("guidance", 8.5)
    payload.setdefault("strength", 0.62)

    return _post_json(
        "/v1/renovate",
        payload,
        api_url=api_url,
        api_key=api_key,
        timeout=timeout,
    )


def generate_concept(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Backward-compatible dispatcher.

    Design goes to /v1/build_concept.
    Rehab goes to /v1/renovate.
    """
    family = (
        payload.get("generation_family")
        or payload.get("generator_family")
        or payload.get("generator_type")
        or payload.get("studio")
        or "design"
    )
    family = str(family).lower()

    if family in {"rehab", "rehab_studio", "photo_rehab", "hgtv"}:
        return generate_rehab_mockup(payload)

    return generate_design_concept(payload)