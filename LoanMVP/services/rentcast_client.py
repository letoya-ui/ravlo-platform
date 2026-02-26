import requests
from flask import current_app


def rentcast_get(path: str, params: dict) -> dict:
    """
    Base RentCast GET helper. Returns dict:
      {status: ok|error, data|error, http_status}
    """
    base = current_app.config.get("RENTCAST_BASE_URL", "https://api.rentcast.io/v1").rstrip("/")
    api_key = (current_app.config.get("RENTCAST_API_KEY") or "").strip()
    timeout = int(current_app.config.get("RENTCAST_TIMEOUT", 12))

    if not api_key:
        return {"status": "error", "error": "rentcast_api_key_missing", "http_status": 401}

    url = f"{base}/{path.lstrip('/')}"
    headers = {"X-Api-Key": api_key, "Accept": "application/json"}

    try:
        r = requests.get(url, headers=headers, params=params, timeout=timeout)
        if r.status_code >= 400:
            return {
                "status": "error",
                "error": f"rentcast_http_{r.status_code}",
                "http_status": r.status_code,
                "details": r.text[:500],
            }
        return {"status": "ok", "data": r.json(), "http_status": r.status_code}
    except Exception as e:
        return {"status": "error", "error": str(e), "http_status": 0}