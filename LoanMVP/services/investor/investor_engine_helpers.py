from __future__ import annotations

import os
import time
from urllib.parse import urlparse

import requests
from flask import current_app


GPU_BASE_URL = os.getenv("GPU_BASE_URL", "").rstrip("/")
RENOVATION_ENGINE_URL = os.getenv("RENOVATION_ENGINE_URL", "").rstrip("/")
RENOVATION_API_KEY = os.getenv("RENOVATION_API_KEY", "")
SCOPE_ENGINE_URL = os.getenv("SCOPE_ENGINE_URL", "").rstrip("/")
SCOPE_ENGINE_API_KEY = os.getenv("SCOPE_ENGINE_API_KEY", "")

RENDER_TIMEOUT = 240
BLUEPRINT_RENDER_TIMEOUT = int(os.getenv("BLUEPRINT_RENDER_TIMEOUT", "240"))
FULL_BUILD_BLUEPRINT_TIMEOUT = int(os.getenv("FULL_BUILD_BLUEPRINT_TIMEOUT", "240"))
SCOPE_TIMEOUT = 45
UPLOAD_TIMEOUT = 240

ENGINE_MAX_ATTEMPTS = int(os.getenv("ENGINE_MAX_ATTEMPTS", "3"))
ENGINE_RETRY_BACKOFF_BASE = float(os.getenv("ENGINE_RETRY_BACKOFF_BASE", "1.5"))

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
RETRYABLE_ERROR_TEXT = (
    "err_ngrok_3004",
    "ngrok gateway error",
    "invalid or incomplete http response",
    "upstream connect error",
    "upstream request timeout",
    "temporarily unavailable",
    "bad gateway",
    "gateway timeout",
    "service unavailable",
)


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


def _renovation_engine_url(path: str = "") -> str:
    base = _engine_base_url() or RENOVATION_ENGINE_URL
    return f"{base.rstrip('/')}{path}"


def _scope_engine_url(path: str = "") -> str:
    return f"{SCOPE_ENGINE_URL.rstrip('/')}{path}"


def _truncate_text(value: str, limit: int = 500) -> str:
    value = (value or "").strip()
    if len(value) <= limit:
        return value
    return value[:limit]


def _safe_engine_error_message(resp: requests.Response) -> str:
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


def _friendly_engine_timeout_message(url: str, timeout: int | float, error: Exception) -> str:
    host = (urlparse(url).netloc or url).strip()
    message = f"Renovation engine timed out after {timeout}s."
    if "ngrok" in host:
        message += " The ngrok tunnel or local render worker may be offline, sleeping, or still processing the image job."
    return f"{message} host={host} error={error}"


def _is_engine_timeout_error(error: Exception | str | None) -> bool:
    text = str(error or "").lower()
    return "timed out" in text and "engine" in text


def _is_probably_html(body: str, content_type: str) -> bool:
    start = (body or "")[:200].lstrip().lower()
    return (
        "text/html" in (content_type or "")
        or start.startswith("<!doctype html")
        or start.startswith("<html")
    )


def _response_snippet(resp: requests.Response, limit: int = 500) -> str:
    try:
        return _truncate_text(resp.text or "", limit=limit)
    except Exception:
        return ""


def _retry_delay_seconds(attempt_number: int) -> float:
    return ENGINE_RETRY_BACKOFF_BASE * attempt_number


def _response_text_indicates_retry(body: str) -> bool:
    lowered = (body or "").lower()
    return any(token in lowered for token in RETRYABLE_ERROR_TEXT)


def _should_retry_response(resp: requests.Response) -> bool:
    if resp.status_code in RETRYABLE_STATUS_CODES:
        return True

    body = _response_snippet(resp, limit=1000)
    if _response_text_indicates_retry(body):
        return True

    return False


def _log_engine_attempt(
    *,
    event: str,
    url: str,
    attempt: int,
    timeout: int | float,
    status_code: int | None = None,
    content_type: str | None = None,
    body: str | None = None,
    error: str | None = None,
) -> None:
    logger = getattr(current_app, "logger", None)
    if not logger:
        return

    payload = {
        "event": event,
        "url": url,
        "attempt": attempt,
        "timeout": timeout,
        "status_code": status_code,
        "content_type": content_type,
        "body": _truncate_text(body or "", 500),
        "error": _truncate_text(error or "", 500),
    }

    try:
        logger.warning("engine_request_event=%s", payload)
    except Exception:
        pass


def _post_renovation_engine_json(path, payload, timeout=RENDER_TIMEOUT, max_attempts=ENGINE_MAX_ATTEMPTS):
    url = _renovation_engine_url(path)
    headers = dict(_engine_headers() or {})
    headers.setdefault("Content-Type", "application/json")

    last_error = None

    for attempt in range(1, max(1, max_attempts) + 1):
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=timeout)
        except requests.Timeout as e:
            last_error = RuntimeError(_friendly_engine_timeout_message(url, timeout, e))
            _log_engine_attempt(
                event="timeout",
                url=url,
                attempt=attempt,
                timeout=timeout,
                error=str(last_error),
            )
            if attempt < max_attempts:
                time.sleep(_retry_delay_seconds(attempt))
                continue
            raise last_error

        except requests.RequestException as e:
            last_error = RuntimeError(f"Engine request failed. url={url} error={e}")
            _log_engine_attempt(
                event="request_exception",
                url=url,
                attempt=attempt,
                timeout=timeout,
                error=str(last_error),
            )
            if attempt < max_attempts:
                time.sleep(_retry_delay_seconds(attempt))
                continue
            raise last_error

        content_type = (res.headers.get("Content-Type") or "").lower()
        body = _response_snippet(res, limit=1000)

        if not res.ok:
            _log_engine_attempt(
                event="non_ok_response",
                url=url,
                attempt=attempt,
                timeout=timeout,
                status_code=res.status_code,
                content_type=content_type,
                body=body,
            )

            if _should_retry_response(res) and attempt < max_attempts:
                time.sleep(_retry_delay_seconds(attempt))
                continue

            if _is_probably_html(body, content_type):
                raise RuntimeError(
                    f"Engine returned HTML instead of JSON. "
                    f"url={url} status={res.status_code} content_type={content_type} body={body[:500]}"
                )

            raise RuntimeError(_safe_engine_error_message(res))

        if "application/json" not in content_type:
            _log_engine_attempt(
                event="non_json_response",
                url=url,
                attempt=attempt,
                timeout=timeout,
                status_code=res.status_code,
                content_type=content_type,
                body=body,
            )

            if (_response_text_indicates_retry(body) or _is_probably_html(body, content_type)) and attempt < max_attempts:
                time.sleep(_retry_delay_seconds(attempt))
                continue

            raise RuntimeError(
                f"Engine returned non-JSON response. "
                f"url={url} status={res.status_code} content_type={content_type} body={body[:500]}"
            )

        try:
            return res.json()
        except Exception as e:
            last_error = RuntimeError(
                f"Engine returned invalid JSON. "
                f"url={url} status={res.status_code} content_type={content_type} error={e} body={body[:500]}"
            )
            _log_engine_attempt(
                event="invalid_json",
                url=url,
                attempt=attempt,
                timeout=timeout,
                status_code=res.status_code,
                content_type=content_type,
                body=body,
                error=str(e),
            )
            if attempt < max_attempts:
                time.sleep(_retry_delay_seconds(attempt))
                continue
            raise last_error

    raise last_error or RuntimeError(f"Engine request failed after retries. url={url}")


def _post_renovation_engine_multipart(path, files, data, timeout=UPLOAD_TIMEOUT, max_attempts=ENGINE_MAX_ATTEMPTS):
    url = _renovation_engine_url(path)
    headers = _engine_headers()
    headers.pop("Content-Type", None)

    last_error = None

    for attempt in range(1, max(1, max_attempts) + 1):
        try:
            res = requests.post(
                url,
                files=files,
                data=data,
                headers=headers,
                timeout=timeout,
            )
        except requests.Timeout as e:
            last_error = RuntimeError(_friendly_engine_timeout_message(url, timeout, e))
            _log_engine_attempt(
                event="multipart_timeout",
                url=url,
                attempt=attempt,
                timeout=timeout,
                error=str(last_error),
            )
            if attempt < max_attempts:
                time.sleep(_retry_delay_seconds(attempt))
                continue
            raise last_error

        except requests.RequestException as e:
            last_error = RuntimeError(f"Engine multipart request failed. url={url} error={e}")
            _log_engine_attempt(
                event="multipart_request_exception",
                url=url,
                attempt=attempt,
                timeout=timeout,
                error=str(last_error),
            )
            if attempt < max_attempts:
                time.sleep(_retry_delay_seconds(attempt))
                continue
            raise last_error

        content_type = (res.headers.get("Content-Type") or "").lower()
        body = _response_snippet(res, limit=1000)

        if not res.ok:
            _log_engine_attempt(
                event="multipart_non_ok_response",
                url=url,
                attempt=attempt,
                timeout=timeout,
                status_code=res.status_code,
                content_type=content_type,
                body=body,
            )
            if _should_retry_response(res) and attempt < max_attempts:
                time.sleep(_retry_delay_seconds(attempt))
                continue
            raise RuntimeError(_safe_engine_error_message(res))

        if "application/json" not in content_type:
            _log_engine_attempt(
                event="multipart_non_json_response",
                url=url,
                attempt=attempt,
                timeout=timeout,
                status_code=res.status_code,
                content_type=content_type,
                body=body,
            )
            if (_response_text_indicates_retry(body) or _is_probably_html(body, content_type)) and attempt < max_attempts:
                time.sleep(_retry_delay_seconds(attempt))
                continue
            raise RuntimeError(
                f"Engine returned non-JSON multipart response. "
                f"url={url} status={res.status_code} content_type={content_type} body={body[:500]}"
            )

        try:
            return res.json()
        except Exception as e:
            last_error = RuntimeError(
                f"Engine returned invalid JSON for multipart request. "
                f"url={url} status={res.status_code} content_type={content_type} error={e} body={body[:500]}"
            )
            _log_engine_attempt(
                event="multipart_invalid_json",
                url=url,
                attempt=attempt,
                timeout=timeout,
                status_code=res.status_code,
                content_type=content_type,
                body=body,
                error=str(e),
            )
            if attempt < max_attempts:
                time.sleep(_retry_delay_seconds(attempt))
                continue
            raise last_error

    raise last_error or RuntimeError(f"Engine multipart request failed after retries. url={url}")


def _post_scope_engine_json(path, payload, timeout=SCOPE_TIMEOUT):
    url = _scope_engine_url(path)
    try:
        res = requests.post(
            url,
            json=payload,
            headers=_scope_engine_headers(),
            timeout=timeout,
        )
    except requests.Timeout as e:
        raise RuntimeError(f"Scope engine timed out after {timeout}s. url={url} error={e}")
    except requests.RequestException as e:
        raise RuntimeError(f"Scope engine request failed. url={url} error={e}")

    if not res.ok:
        raise RuntimeError(_safe_engine_error_message(res))

    content_type = (res.headers.get("Content-Type") or "").lower()
    if "application/json" not in content_type:
        body = _response_snippet(res, limit=500)
        raise RuntimeError(
            f"Scope engine returned non-JSON response. "
            f"url={url} status={res.status_code} content_type={content_type} body={body}"
        )

    try:
        return res.json()
    except Exception as e:
        body = _response_snippet(res, limit=500)
        raise RuntimeError(
            f"Scope engine returned invalid JSON. "
            f"url={url} status={res.status_code} content_type={content_type} error={e} body={body}"
        )