import os
import re
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


def _safe_get(url: str, params: Dict[str, Any], timeout: int = 12) -> Any:
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


def _extract_listing_items(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        items = payload.get("listings") or payload.get("results") or payload.get("data") or []
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]

    return []


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
    url = f"{RENTCAST_BASE_URL}/avm/value"
    params = {
        "address": _full_address(address, city, state, zip_code),
        "propertyType": property_type,
        "compCount": 5,
    }
    return _safe_get(url, params)


def get_rentcast_sale_listings(
    city: str = "",
    state: str = "",
    zip_code: str = "",
    status: str = "Active",
    limit: int = 10,
) -> List[Dict[str, Any]]:
    url = f"{RENTCAST_BASE_URL}/listings/sale"
    params: Dict[str, Any] = {
        "status": status,
        "limit": limit,
    }
    if city and state:
        params["city"] = city
        params["state"] = state
    if zip_code:
        params["zipCode"] = zip_code

    if "city" not in params and "zipCode" not in params:
        return []

    return _extract_listing_items(_safe_get(url, params))


def normalize_rentcast_sale_listing(item: Dict[str, Any]) -> Dict[str, Any]:
    item = item or {}

    # Extract photos from the raw listing data.  RentCast may return photos
    # under several keys; collect them all so the orchestrator can score and
    # rank them later.
    raw_photos = item.get("photos") or item.get("images") or []
    if isinstance(raw_photos, str):
        raw_photos = [raw_photos]
    elif not isinstance(raw_photos, list):
        raw_photos = []
    photo_list: List[str] = []
    for entry in raw_photos:
        if isinstance(entry, str) and entry.strip():
            photo_list.append(entry.strip())
        elif isinstance(entry, dict):
            url = (
                entry.get("url")
                or entry.get("href")
                or entry.get("src")
                or entry.get("photo")
                or entry.get("image")
            )
            if isinstance(url, str) and url.strip():
                photo_list.append(url.strip())

    primary_photo = (
        item.get("imgSrc")
        or item.get("primaryPhotoUrl")
        or item.get("primaryPhoto")
        or (photo_list[0] if photo_list else None)
    )

    return {
        "property_id": item.get("id") or item.get("propertyId") or item.get("listingId"),
        "address": item.get("formattedAddress") or item.get("address") or item.get("line1") or item.get("streetAddress"),
        "city": item.get("city"),
        "state": item.get("state"),
        "zip_code": item.get("zipCode") or item.get("zip"),
        "price": item.get("price") or item.get("listPrice"),
        "beds": item.get("bedrooms") or item.get("beds"),
        "baths": item.get("bathrooms") or item.get("baths"),
        "square_feet": item.get("squareFootage") or item.get("sqft"),
        "lot_size_sqft": item.get("lotSize") or item.get("lotSizeSqFt"),
        "year_built": item.get("yearBuilt"),
        "property_type": item.get("propertyType"),
        "status": item.get("status"),
        "days_on_market": item.get("daysOnMarket"),
        "latitude": item.get("latitude"),
        "longitude": item.get("longitude"),
        "primary_photo": primary_photo,
        "photos": photo_list,
        "raw": item,
    }


def _normalize_address_for_match(value: str) -> str:
    replacements = {
        " street": " st",
        " avenue": " ave",
        " road": " rd",
        " drive": " dr",
        " lane": " ln",
        " court": " ct",
        " place": " pl",
        " boulevard": " blvd",
        " terrace": " ter",
        " highway": " hwy",
        " parkway": " pkwy",
        " north": " n",
        " south": " s",
        " east": " e",
        " west": " w",
    }

    normalized = f" {((value or '').lower())} "
    normalized = normalized.replace(".", " ").replace(",", " ").replace("#", " ")
    normalized = re.sub(r"\bapartment\b|\bapt\b|\bunit\b|\bsuite\b", " ", normalized)
    for original, replacement in replacements.items():
        normalized = normalized.replace(original, replacement)

    return (
        normalized
        .replace("-", " ")
        .replace("/", " ")
        .strip()
        .replace("  ", " ")
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
    listings = get_rentcast_sale_listings(city=city, state=state, zip_code=zip_code, status="Active", limit=limit)
    target = _normalize_address_for_match(address)
    zip_digits = "".join(ch for ch in str(zip_code or "") if ch.isdigit())

    if not listings:
        return {}

    scoped_listings = listings
    if zip_digits:
        filtered = [
            item for item in listings
            if "".join(ch for ch in str(item.get("zipCode") or item.get("zip") or "") if ch.isdigit()) == zip_digits
        ]
        if filtered:
            scoped_listings = filtered

    # exact-ish address match first
    for item in scoped_listings:
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
    for item in scoped_listings:
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
