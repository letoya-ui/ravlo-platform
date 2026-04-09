import os
import requests
from typing import Dict, Any, List


class RentCastServiceError(Exception):
    pass


RENTCAST_BASE_URL = os.getenv("RENTCAST_BASE_URL", "https://api.rentcast.io/v1").rstrip("/")
RENTCAST_API_KEY = os.getenv("RENTCAST_API_KEY", "").strip()


def _rentcast_headers() -> Dict[str, str]:
    if not RENTCAST_API_KEY:
        raise RentCastServiceError("Missing RENTCAST_API_KEY")

    return {
        "X-Api-Key": RENTCAST_API_KEY,
        "Accept": "application/json",
    }


def _safe_get(url: str, params: Dict[str, Any], timeout: int = 12) -> Dict[str, Any]:
    try:
        resp = requests.get(url, headers=_rentcast_headers(), params=params, timeout=timeout)
    except requests.RequestException as e:
        raise RentCastServiceError(f"Request failed: {e}") from e

    if resp.status_code == 404:
        raise RentCastServiceError("No RentCast data found")

    if resp.status_code >= 400:
        raise RentCastServiceError(f"HTTP {resp.status_code}: {resp.text[:300]}")

    try:
        return resp.json() or {}
    except Exception as e:
        raise RentCastServiceError(f"Invalid JSON response: {e}") from e


def _full_address(address: str, city: str, state: str, zip_code: str = "") -> str:
    return " ".join(
        str(part).strip()
        for part in [f"{address},", city, f"{state}", zip_code]
        if str(part).strip()
    ).replace(", ", ", ").strip()


def get_rentcast_rent_estimate(
    address: str,
    city: str,
    state: str,
    zip_code: str = "",
    property_type: str = "single_family",
) -> Dict[str, Any]:
    url = f"{RENTCAST_BASE_URL}/avm/rent/long-term"
    params = {
        "address": _full_address(address, city, state, zip_code),
        "propertyType": property_type,
        "compCount": 5,
    }
    return _safe_get(url, params)


def get_rentcast_value_estimate(
    address: str,
    city: str,
    state: str,
    zip_code: str = "",
    property_type: str = "single_family",
) -> Dict[str, Any]:
    if not RENTCAST_API_KEY:
        raise RentCastServiceError("Missing RENTCAST_API_KEY")

    full_address = f"{address}, {city}, {state} {zip_code}".strip()
    url = f"{RENTCAST_BASE_URL}/avm/value"

    headers = {
        "X-Api-Key": RENTCAST_API_KEY,
        "Accept": "application/json",
    }

    params = {
        "address": full_address,
        "propertyType": property_type,
        "compCount": 5,
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=12)
    except requests.RequestException as e:
        raise RentCastServiceError(f"Request failed: {e}") from e

    if resp.status_code == 404:
        raise RentCastServiceError("No RentCast value estimate found")

    if resp.status_code >= 400:
        raise RentCastServiceError(f"HTTP {resp.status_code}: {resp.text[:300]}")

    try:
        return resp.json() or {}
    except Exception as e:
        raise RentCastServiceError(f"Invalid JSON response: {e}") from e


def get_rentcast_sale_listings(
    city: str,
    state: str,
    status: str = "Active",
    limit: int = 25,
) -> Dict[str, Any]:
    if not RENTCAST_API_KEY:
        raise RentCastServiceError("Missing RENTCAST_API_KEY")

    url = f"{RENTCAST_BASE_URL}/listings/sale"

    headers = {
        "X-Api-Key": RENTCAST_API_KEY,
        "Accept": "application/json",
    }

    params = {
        "city": city,
        "state": state,
        "status": status,
        "limit": limit,
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=12)
    except requests.RequestException as e:
        raise RentCastServiceError(f"Request failed: {e}") from e

    if resp.status_code == 404:
        raise RentCastServiceError("No RentCast sale listings found")

    if resp.status_code >= 400:
        raise RentCastServiceError(f"HTTP {resp.status_code}: {resp.text[:300]}")

    try:
        return resp.json() or {}
    except Exception as e:
        raise RentCastServiceError(f"Invalid JSON response: {e}") from e

def get_rentcast_sale_listings(
    city: str,
    state: str,
    status: str = "Active",
    limit: int = 10,
) -> List[Dict[str, Any]]:
    url = f"{RENTCAST_BASE_URL}/listings/sale"
    params = {
        "city": city,
        "state": state,
        "status": status,
        "limit": limit,
    }

    data = _safe_get(url, params)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        return (
            data.get("listings")
            or data.get("results")
            or data.get("data")
            or []
        )

    return []


def _normalize_address_for_match(value: str) -> str:
    return (
        (value or "")
        .lower()
        .replace(".", "")
        .replace(",", "")
        .replace("#", "")
        .replace("  ", " ")
        .strip()
    )


def find_rentcast_sale_listing(
    address: str,
    city: str,
    state: str,
    zip_code: str = "",
    limit: int = 25,
) -> Dict[str, Any]:
    """
    Best-effort matcher for an active sale listing in RentCast.
    Search by city/state, then try to match the address locally.
    """
    listings = get_rentcast_sale_listings(city=city, state=state, status="Active", limit=limit)
    target = _normalize_address_for_match(address)

    if not listings:
        return {}

    # exact-ish address match first
    for item in listings:
        listing_addr = _normalize_address_for_match(
            item.get("address")
            or item.get("formattedAddress")
            or item.get("line1")
            or item.get("streetAddress")
            or ""
        )
        if listing_addr and listing_addr == target:
            return item

    # fallback contains match
    for item in listings:
        listing_addr = _normalize_address_for_match(
            item.get("address")
            or item.get("formattedAddress")
            or item.get("line1")
            or item.get("streetAddress")
            or ""
        )
        if listing_addr and (target in listing_addr or listing_addr in target):
            return item

    return {}