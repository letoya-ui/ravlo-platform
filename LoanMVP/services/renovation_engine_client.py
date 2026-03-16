import os
import requests
from typing import Optional

RENOVATION_ENGINE_URL = os.getenv("RENOVATION_ENGINE_URL", "http://renovation-engine:8000")


class RenovationEngineError(Exception):
    pass


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
):
    endpoint = f"{api_url.rstrip('/')}/v1/renovate-upload"

    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key

    files = {
        "image": (
            file_storage.filename or "upload.jpg",
            file_storage.stream,
            file_storage.mimetype or "application/octet-stream",
        )
    }

    data = {
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
            endpoint,
            headers=headers,
            files=files,
            data=data,
            timeout=300,
        )
        response.raise_for_status()
        return response.json()

    except requests.RequestException as e:
        raise RenovationEngineError(f"Renovation generator failed: {str(e)}") from e

def generate_concept(payload):
    """
    Sends a generation request to the Renovation Engine Docker service.
    """
    response = requests.post(
        f"{RENOVATION_ENGINE_URL}/generate",
        json=payload,
        timeout=180
    )
    response.raise_for_status()
    return response.json()