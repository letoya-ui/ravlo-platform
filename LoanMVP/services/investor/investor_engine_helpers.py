from __future__ import annotations

import os
import requests
from urllib.parse import urlparse
from flask import current_app


GPU_BASE_URL = os.getenv("GPU_BASE_URL", "").rstrip("/")
RENOVATION_ENGINE_URL = os.getenv("RENOVATION_ENGINE_URL", "").rstrip("/")
RENOVATION_API_KEY = os.getenv("RENOVATION_API_KEY", "")
SCOPE_ENGINE_URL = os.getenv("SCOPE_ENGINE_URL", "").rstrip("/")
SCOPE_ENGINE_API_KEY = os.getenv("SCOPE_ENGINE_API_KEY", "")

RENDER_TIMEOUT = 240
BLUEPRINT_RENDER_TIMEOUT = int(os.getenv("BLUEPRINT_RENDER_TIMEOUT", "90"))
FULL_BUILD_BLUEPRINT_TIMEOUT = int(os.getenv("FULL_BUILD_BLUEPRINT_TIMEOUT", "240"))
SCOPE_TIMEOUT = 45
UPLOAD_TIMEOUT = 240


def _engine_base_url() -> str:
    return (current_app.config.get("RENOVATION_ENGINE_URL") or "").rstrip("/")


def _engine_headers() -> dict:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "true",
    }
    api_key = (
        current_app.config.get("RENOVATION_API_KEY")
        or current_app.config.get("RENOVATION_ENGINE_API_KEY")
        or ""
    ).strip()
    if api_key:
        headers["X-API-Key"] = api_key
    return headers


def _scope_engine_headers() -> dict:
    headers = {}
    if SCOPE_ENGINE_API_KEY:
        headers["X-API-Key"] = SCOPE_ENGINE_API_KEY
    return headers


def _renovation_engine_url(path=""):
    return f"{RENOVATION_ENGINE_URL.rstrip('/')}{path}"


def _scope_engine_url(path=""):
    return f"{SCOPE_ENGINE_URL.rstrip('/')}{path}"


def _safe_engine_error_message(resp):
    content_type = (resp.headers.get("Content-Type") or "").lower()

    if "application/json" in content_type:
        try:
            payload = resp.json()
            if isinstance(payload, dict):
                return (
                    payload.get("detail")
                    or payload.get("message")
                    or payload.get("error")
                    or str(payload)[:300]
                )
        except Exception:
            pass

    return (resp.text or f"HTTP {resp.status_code}")[:300]


def _friendly_engine_timeout_message(url, timeout, error):
    host = (urlparse(url).netloc or url).strip()
    message = f"Renovation engine timed out after {timeout}s."
    if "ngrok" in host:
        message += " The ngrok tunnel or local render worker may be offline, sleeping, or still processing the image job."
    return f"{message} host={host} error={error}"


def _is_engine_timeout_error(error):
    text = str(error or "").lower()
    return "timed out" in text and "engine" in text


def _post_renovation_engine_json(path, payload, timeout=RENDER_TIMEOUT):
    url = _renovation_engine_url(path)
    headers = dict(_engine_headers() or {})
    headers.setdefault("Content-Type", "application/json")

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=timeout)
    except requests.Timeout as e:
        raise RuntimeError(_friendly_engine_timeout_message(url, timeout, e))
    except requests.RequestException as e:
        raise RuntimeError(f"Engine request failed. url={url} error={e}")

    content_type = (res.headers.get("Content-Type") or "").lower()
    body = res.text or ""
    snippet = body[:500]

    if not res.ok:
        if "text/html" in content_type or body.lstrip().lower().startswith("<!doctype html") or "<html" in body[:200].lower():
            raise RuntimeError(
                f"Engine returned HTML instead of JSON. url={url} status={res.status_code} content_type={content_type} body={snippet}"
            )
        raise RuntimeError(_safe_engine_error_message(res))

    if "application/json" not in content_type:
        raise RuntimeError(
            f"Engine returned non-JSON response. url={url} status={res.status_code} content_type={content_type} body={snippet}"
        )

    try:
        return res.json()
    except Exception as e:
        raise RuntimeError(
            f"Engine returned invalid JSON. url={url} status={res.status_code} content_type={content_type} error={e} body={snippet}"
        )


def _post_renovation_engine_multipart(path, files, data, timeout=UPLOAD_TIMEOUT):
    res = requests.post(
        _renovation_engine_url(path),
        files=files,
        data=data,
        headers=_engine_headers(),
        timeout=timeout,
    )
    if not res.ok:
        raise RuntimeError(_safe_engine_error_message(res))
    return res.json()


def _post_scope_engine_json(path, payload, timeout=SCOPE_TIMEOUT):
    res = requests.post(
        _scope_engine_url(path),
        json=payload,
        headers=_scope_engine_headers(),
        timeout=timeout,
    )
    if not res.ok:
        raise RuntimeError(_safe_engine_error_message(res))
    return res.json()