import os
import requests
from typing import Any, Dict, Optional

MASHVISOR_API_KEY = os.getenv("MASHVISOR_API_KEY", "")
MASHVISOR_BASE_URL = os.getenv("MASHVISOR_BASE_URL", "https://api.mashvisor.com").rstrip("/")
TIMEOUT = int(os.getenv("DEALFINDER_TIMEOUT", "20"))

_session = requests.Session()


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
        raise MashvisorServiceError(f"Mashvisor HTTP error: {e}. body={body}")
    except Exception as e:
        raise MashvisorServiceError(f"Mashvisor request failed: {e}")


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


def normalize_mashvisor_validation(result: Dict[str, Any]) -> Dict[str, Any]:
    lookup = result.get("lookup") or {}
    comps = result.get("comps") or {}

    lookup_content = lookup.get("content", lookup)
    comps_content = comps.get("content", comps)

    return {
        "airbnb_revenue": (
            lookup_content.get("rental_income")
            or lookup_content.get("airbnb_rental_income")
            or lookup_content.get("monthly_revenue")
        ),
        "occupancy_rate": (
            lookup_content.get("occupancy_rate")
            or lookup_content.get("airbnb_occupancy_rate")
        ),
        "adr": (
            lookup_content.get("daily_rate")
            or lookup_content.get("adr")
            or lookup_content.get("average_daily_rate")
        ),
        "revpar": lookup_content.get("revpar"),
        "cash_flow": lookup_content.get("cash_flow"),
        "noi": lookup_content.get("noi"),
        "cash_on_cash_return": (
            lookup_content.get("cash_on_cash_return")
            or lookup_content.get("coc")
        ),
        "confidence": (
            lookup_content.get("data_quality")
            or lookup_content.get("confidence")
            or lookup_content.get("sample_size")
        ),
        "comps": (
            comps_content.get("list")
            or comps_content.get("comparables")
            or []
        ),
        "raw": result,
    }