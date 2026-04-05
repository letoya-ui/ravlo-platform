import os
import requests
from typing import Any, Dict, Optional

ATTOM_API_KEY = os.getenv("ATTOM_API_KEY", "")
ATTOM_BASE_URL = os.getenv("ATTOM_BASE_URL", "https://api.gateway.attomdata.com").rstrip("/")
TIMEOUT = int(os.getenv("DEALFINDER_TIMEOUT", "20"))

_session = requests.Session()


class AttomServiceError(Exception):
    pass


def _headers() -> Dict[str, str]:
    if not ATTOM_API_KEY:
        raise AttomServiceError("ATTOM_API_KEY is not configured.")
    return {
        "accept": "application/json",
        "apikey": ATTOM_API_KEY,
    }


def _get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{ATTOM_BASE_URL}{path}"
    try:
        res = _session.get(url, headers=_headers(), params=params or {}, timeout=TIMEOUT)
        res.raise_for_status()
        return res.json()
    except requests.HTTPError as e:
        body = ""
        try:
            body = res.text[:400]
        except Exception:
            pass
        raise AttomServiceError(f"ATTOM HTTP error: {e}. body={body}")
    except Exception as e:
        raise AttomServiceError(f"ATTOM request failed: {e}")


def search_property_by_address(address1: str, address2: str) -> Dict[str, Any]:
    return _get(
        "/propertyapi/v1.0.0/property/detail",
        params={
            "address1": address1,
            "address2": address2,
        },
    )


def search_property_expanded(
    address: str = "",
    city: str = "",
    state: str = "",
    postalcode: str = "",
) -> Dict[str, Any]:
    address1 = (address or "").strip()
    address2_parts = [p.strip() for p in [city, state] if p and str(p).strip()]
    address2 = ", ".join(address2_parts)
    if postalcode:
        address2 = f"{address2} {postalcode}".strip()

    if not address1 or not address2:
        raise AttomServiceError("ATTOM search requires address and city/state.")

    return search_property_by_address(address1=address
