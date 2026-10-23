import os
import time
import requests
from typing import Any, Dict, Optional

from LoanMVP.utils.safe_http import safe_call

MASHVISOR_API_KEY = os.getenv("MASHVISOR_API_KEY", "")
MASHVISOR_BASE_URL = os.getenv("MASHVISOR_BASE_URL", "https://api.mashvisor.com").rstrip("/")
TIMEOUT = int(os.getenv("DEALFINDER_TIMEOUT", "20"))

_session = requests.Session()

# See the matching comment in mashvisor_client.py -- Mashvisor intermittently
# returns a 500 wrapping an internal 401, which looks transient on their end
# rather than a credentials problem. One retry recovers transient cases
# cheaply without masking a real, persistent outage.
_RETRYABLE_STATUS_CODES = {500, 502, 503, 504}
_RETRY_ATTEMPTS = 2
_RETRY_DELAY_SECONDS = 0.75


class MashvisorServiceError(Exception):
    pass


def _headers() -> Dict[str, str]:
    if not MASHVISOR_API_KEY:
        raise MashvisorServiceError("MASHVISOR_API_KEY is not configured.")
    return {
        "accept": "application/json",
        "x-api-key": MASHVISOR_API_KEY,
    }


def _get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{MASHVISOR_BASE_URL}{path}"
    last_exc: Optional[Exception] = None
    for attempt in range(1, _RETRY_ATTEMPTS + 1):
        try:
            res = safe_call(_session.get, url, headers=_headers(), params=params or {}, timeout=TIMEOUT)
            res.raise_for_status()
            return res.json()
        except requests.HTTPError as e:
            body = ""
            try:
                body = res.text[:400]
            except Exception:
                pass
            last_exc = MashvisorServiceError(f"Mashvisor HTTP error: {e}. body={body}")
            status_code = getattr(res, "status_code", None)
            if status_code in _RETRYABLE_STATUS_CODES and attempt < _RETRY_ATTEMPTS:
                time.sleep(_RETRY_DELAY_SECONDS)
                continue
            raise last_exc
        except Exception as e:
            raise MashvisorServiceError(f"Mashvisor request failed: {e}")

    raise last_exc


def safe_get(dct: Any, *keys: str, default=None):
    cur = dct
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def get_property_analytics(
    address: str = "",
    city: str = "",
    state: str = "",
    zip_code: str = "",
    property_type: str = "single_family",
) -> Dict[str, Any]:
    """
    IMPORTANT:
    Exact Mashvisor endpoint/params may depend on your API plan.
    Swap this path to the endpoint exposed in your account docs.
    """
    return _get(
        "/v1.1/client/property/analytics",
        params={
            "address": address,
            "city": city,
            "state": state,
            "zip_code": zip_code,
            "property_type": property_type,
        },
    )


def get_rental_comps(
    address: str = "",
    city: str = "",
    state: str = "",
    zip_code: str = "",
    strategy: str = "traditional",
) -> Dict[str, Any]:
    return _get(
        "/v1.1/client/rental-comps",
        params={
            "address": address,
            "city": city,
            "state": state,
            "zip_code": zip_code,
            "strategy": strategy,
        },
    )


def extract_core_fields(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Defensive mapper because plan-specific payloads may differ.
    """
    return {
        "traditional_rent": (
            safe_get(raw, "traditional", "rental_income")
            or safe_get(raw, "traditional_rental_income")
            or safe_get(raw, "rental_income")
        ),
        "traditional_cash_flow": (
            safe_get(raw, "traditional", "cash_flow")
            or safe_get(raw, "cash_flow")
        ),
        "traditional_cap_rate": (
            safe_get(raw, "traditional", "cap_rate")
            or safe_get(raw, "cap_rate")
        ),
        "traditional_coc": (
            safe_get(raw, "traditional", "cash_on_cash_return")
            or safe_get(raw, "cash_on_cash_return")
        ),
        "airbnb_rent": (
            safe_get(raw, "airbnb", "rental_income")
            or safe_get(raw, "airbnb_rental_income")
        ),
        "airbnb_cash_flow": (
            safe_get(raw, "airbnb", "cash_flow")
            or safe_get(raw, "airbnb_cash_flow")
        ),
        "airbnb_cap_rate": (
            safe_get(raw, "airbnb", "cap_rate")
            or safe_get(raw, "airbnb_cap_rate")
        ),
        "airbnb_coc": (
            safe_get(raw, "airbnb", "cash_on_cash_return")
            or safe_get(raw, "airbnb_cash_on_cash_return")
        ),
        "occupancy_rate": (
            safe_get(raw, "airbnb", "occupancy_rate")
            or safe_get(raw, "occupancy_rate")
        ),
        "days_on_market": raw.get("days_on_market"),
        "listing_price": raw.get("price") or raw.get("listing_price"),
        "price_per_sqft": raw.get("price_per_sqft"),
        "walk_score": raw.get("walk_score"),
        "raw": raw,
    }


def _find_lookup_value(content: Dict[str, Any], *keys: str):
    """Look for any of `keys` on `content` directly, then one level deep
    inside its values -- the Lookup response groups results by bed/bath
    configuration (content -> {"2bed2bath": {...}, "studio": {...}, ...}),
    so a field like median_rental_income often isn't top-level at all."""
    for key in keys:
        value = content.get(key)
        if value not in (None, ""):
            return value

    for sub in content.values():
        if not isinstance(sub, dict):
            continue
        for key in keys:
            value = sub.get(key)
            if value not in (None, ""):
                return value
    return None


def normalize_mashvisor_validation(result: Dict[str, Any]) -> Dict[str, Any]:
    prop = result.get("property") or {}
    lookup = result.get("lookup") or {}
    comps = result.get("comps") or {}

    prop_content = prop.get("content", prop) if isinstance(prop, dict) else {}
    if not isinstance(prop_content, dict):
        prop_content = {}
    lookup_content = lookup.get("content", lookup) if isinstance(lookup, dict) else {}
    if not isinstance(lookup_content, dict):
        lookup_content = {}
    comps_content = comps.get("content", comps) if isinstance(comps, dict) else {}
    if not isinstance(comps_content, dict):
        comps_content = {}

    # Extract property_id from the property response so it's available for
    # downstream callers (e.g. get_property_images).
    property_id = (
        prop_content.get("id")
        or prop_content.get("property_id")
        or lookup_content.get("id")
        or lookup_content.get("property_id")
    )

    return {
        "property_id": property_id,
        "airbnb_revenue": _find_lookup_value(
            lookup_content,
            "median_rental_income", "rental_income", "airbnb_rental_income", "monthly_revenue",
        ),
        "occupancy_rate": _find_lookup_value(
            lookup_content,
            "median_occupancy", "occupancy_rate", "airbnb_occupancy_rate",
        ),
        "adr": _find_lookup_value(
            lookup_content,
            "median_night_rate", "daily_rate", "adr", "average_daily_rate",
        ),
        "revpar": _find_lookup_value(lookup_content, "revpar"),
        "cash_flow": _find_lookup_value(lookup_content, "cash_flow"),
        "noi": _find_lookup_value(lookup_content, "noi"),
        "cash_on_cash_return": _find_lookup_value(
            lookup_content, "cash_on_cash_return", "coc",
        ),
        "confidence": _find_lookup_value(
            lookup_content, "data_quality", "confidence", "sample_size",
        ),
        "comps": (
            comps_content.get("list")
            or comps_content.get("comparables")
            or []
        ),
        "raw": result,
    }

def get_property_by_mls(mls_number: str) -> Dict[str, Any]:
    """
    Fetch property details from Mashvisor using MLS number.
    """
    if not mls_number:
        raise MashvisorServiceError("MLS number is required.")

    return _get(
        f"/v1.1/client/property/MLS/{mls_number}",
        params={}
    )
def normalize_mls_listing(raw: Dict[str, Any]) -> Dict[str, Any]:
    content = raw.get("content") or raw

    return {
        "mls_number": content.get("mls_id") or content.get("mls_number"),
        "address": content.get("address"),
        "city": content.get("city"),
        "state": content.get("state"),
        "zip_code": content.get("zip_code"),
        "price": content.get("price"),
        "beds": content.get("beds"),
        "baths": content.get("baths"),
        "sqft": content.get("sqft"),
        "lot_size": content.get("lot_size"),
        "property_type": content.get("property_type"),
        "year_built": content.get("year_built"),
        "description": content.get("description"),
        "photos": content.get("photos") or [],
        "raw": raw,
    }
