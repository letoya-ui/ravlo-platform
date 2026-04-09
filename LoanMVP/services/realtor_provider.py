import os
import requests
from typing import Dict, Any, Optional, List

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = os.getenv("REALTOR_RAPIDAPI_HOST", "realtor-search.p.rapidapi.com")
REALTOR_DETAIL_URL = os.getenv(
    "REALTOR_RAPIDAPI_URL",
    f"https://{RAPIDAPI_HOST}/properties/v3/detail",
)
REALTOR_SEARCH_URL = os.getenv(
    "REALTOR_RAPIDAPI_SEARCH_URL",
    f"https://{RAPIDAPI_HOST}/for-sale",
)
REALTOR_PHOTOS_URL = os.getenv(
    "REALTOR_RAPIDAPI_PHOTOS_URL",
    f"https://{RAPIDAPI_HOST}/propertyPhotos",
)
REALTOR_ESTIMATES_URL = os.getenv(
    "REALTOR_RAPIDAPI_ESTIMATES_URL",
    f"https://{RAPIDAPI_HOST}/estimates",
)


class RealtorProviderError(Exception):
    pass


def _headers(include_json: bool = False) -> Dict[str, str]:
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY or "",
        "X-RapidAPI-Host": RAPIDAPI_HOST,
    }
    if include_json:
        headers["content-type"] = "application/json"
    return headers


def _safe_list(val):
    if isinstance(val, list):
        return val
    return []


def _extract_photos(raw_photos: Any) -> List[str]:
    """
    Normalize Realtor.com photo objects into a clean list of URLs.
    """
    photos = []

    if isinstance(raw_photos, list):
        for p in raw_photos:
            if isinstance(p, str) and p.strip():
                photos.append(p.strip())
            elif isinstance(p, dict):
                url = (
                    p.get("href")
                    or p.get("url")
                    or p.get("src")
                    or p.get("photo")
                )
                if isinstance(url, str) and url.strip():
                    photos.append(url.strip())

    # Deduplicate
    clean = []
    seen = set()
    for url in photos:
        if url not in seen:
            clean.append(url)
            seen.add(url)

    return clean


def _first_dict(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, dict) and value:
            return value
    return {}


def _find_listing_node(data: Dict[str, Any]) -> Dict[str, Any]:
    data = data or {}

    direct = _first_dict(
        data.get("property"),
        _first_dict(data.get("data")).get("home"),
        _first_dict(data.get("data")).get("property"),
        _first_dict(data.get("data")).get("listing"),
        _first_dict(data.get("home")),
        _first_dict(data.get("listing")),
    )
    if direct:
        return direct

    for list_key in ("properties", "listings", "results", "home_search", "data"):
        container = data.get(list_key)
        if isinstance(container, list) and container:
            first = container[0]
            if isinstance(first, dict):
                return first
        if isinstance(container, dict):
            for nested_key in ("results", "listings", "properties", "homes"):
                nested = container.get(nested_key)
                if isinstance(nested, list) and nested:
                    first = nested[0]
                    if isinstance(first, dict):
                        return first

    return {}


def _pick(node: Dict[str, Any], *paths: tuple[str, ...]) -> Any:
    for path in paths:
        cur: Any = node
        ok = True
        for part in path:
            if not isinstance(cur, dict):
                ok = False
                break
            cur = cur.get(part)
            if cur is None:
                ok = False
                break
        if ok:
            return cur
    return None


def _normalize_listing_item(item: Dict[str, Any]) -> Dict[str, Any]:
    location = _first_dict(
        _pick(item, ("location",)),
        _pick(item, ("address",)),
        _pick(item, ("description",)),
    )

    photos = _extract_photos(
        _pick(
            item,
            ("photos",),
            ("primary_photo",),
            ("photo",),
            ("description", "photos"),
            ("location", "photos"),
        )
    )

    return {
        "property_id": _pick(item, ("property_id",), ("propertyId",), ("listing_id",), ("mls_id",), ("listing_id",)),
        "address": _pick(item, ("address", "line"), ("location", "address", "line"), ("description", "line"), ("address",), ("location", "address")),
        "address_line1": _pick(item, ("address", "line"), ("location", "address", "line"), ("description", "line")),
        "city": _pick(item, ("address", "city"), ("location", "address", "city"), ("location", "city"), ("description", "city")),
        "state": _pick(item, ("address", "state_code"), ("location", "address", "state_code"), ("location", "state_code"), ("description", "state_code")),
        "zip_code": _pick(item, ("address", "postal_code"), ("location", "address", "postal_code"), ("location", "postal_code"), ("description", "postal_code")),
        "price": _pick(item, ("list_price",), ("price",), ("description", "price")),
        "beds": _pick(item, ("beds",), ("description", "beds")),
        "baths": _pick(item, ("baths",), ("description", "baths_full"), ("description", "baths")),
        "square_feet": _pick(item, ("sqft",), ("description", "sqft"), ("description", "sold_price_per_sqft")),
        "lot_size_sqft": _pick(item, ("description", "lot_sqft"), ("lot_sqft",)),
        "year_built": _pick(item, ("description", "year_built"), ("year_built",)),
        "property_type": _pick(item, ("prop_type",), ("description", "type"), ("property_type",)),
        "status": _pick(item, ("status",), ("description", "status")),
        "days_on_market": _pick(item, ("days_on_mls",), ("days_on_market",), ("description", "days_on_mls")),
        "primary_photo": photos[0] if photos else None,
        "photos": photos,
        "raw": item,
    }


def _extract_listing_results(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidates = [
        data.get("results"),
        data.get("properties"),
        data.get("listings"),
        _pick(data, ("data", "results")),
        _pick(data, ("data", "home_search", "results")),
        _pick(data, ("data", "properties")),
        _pick(data, ("data", "listings")),
    ]

    for candidate in candidates:
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
    return []


def search_realtor_for_sale(
    *,
    location: str,
    limit: int = 20,
    offset: int = 0,
    sort: str = "relevance",
    days_on: int = 1,
    expand_search_radius: int = 0,
) -> List[Dict[str, Any]]:
    if not RAPIDAPI_KEY:
        return []

    params = {
        "location": location,
        "offset": offset,
        "limit": limit,
        "sort": sort,
        "days_on": days_on,
        "expand_search_radius": expand_search_radius,
    }

    try:
        resp = requests.get(REALTOR_SEARCH_URL, headers=_headers(), params=params, timeout=20)
        if not resp.ok:
            print("Realtor Search error:", resp.text[:300])
            return []
        data = resp.json()
    except Exception as e:
        print("Realtor Search exception:", e)
        return []

    listings = _extract_listing_results(data)
    return [_normalize_listing_item(item) for item in listings]


def fetch_realtor_data(address: str, city: str, state: str) -> Optional[Dict[str, Any]]:
    """
    Fetch listing data from Realtor.com via RapidAPI.
    Returns:
        {
            "status": "ok",
            "provider": "realtor",
            "property": {
                "price": ...,
                "photos": [...],
                "primary_photo": ...,
                "status": ...,
                "days_on_market": ...,
                "description": ...,
            },
            "raw": <full API response>
        }
    Or None if no listing found.
    """

    if not RAPIDAPI_KEY:
        print("Realtor Provider: RAPIDAPI_KEY missing")
        return None

    location_parts = [part.strip() for part in [address, city, state] if part and str(part).strip()]
    location_query = ", ".join(location_parts)

    def _fallback_search_result() -> Optional[Dict[str, Any]]:
        if not location_query:
            return None
        listings = search_realtor_for_sale(location=location_query, limit=10)
        if not listings:
            return None

        target_address = (address or "").strip().lower()
        target_city = (city or "").strip().lower()
        target_state = (state or "").strip().lower()

        selected = None
        for item in listings:
            item_address = (item.get("address") or item.get("address_line1") or "").strip().lower()
            item_city = (item.get("city") or "").strip().lower()
            item_state = (item.get("state") or "").strip().lower()
            if target_address and item_address and target_address in item_address:
                if (not target_city or target_city == item_city) and (not target_state or target_state == item_state):
                    selected = item
                    break

        if not selected:
            selected = listings[0]

        return {
            "status": "ok",
            "provider": "realtor_search",
            "property": {
                "price": selected.get("price"),
                "beds": selected.get("beds"),
                "baths": selected.get("baths"),
                "sqft": selected.get("square_feet"),
                "status": selected.get("status"),
                "days_on_market": selected.get("days_on_market"),
                "description": None,
                "photos": selected.get("photos") or [],
                "primary_photo": selected.get("primary_photo"),
            },
            "raw": selected.get("raw") or selected,
        }

    try:
        payload = {
            "address": address,
            "city": city,
            "state_code": state,
        }

        resp = requests.post(REALTOR_DETAIL_URL, json=payload, headers=_headers(include_json=True), timeout=15)

        if not resp.ok:
            print("Realtor Provider error:", resp.text[:300])
            return _fallback_search_result()

        data = resp.json()
        home = _find_listing_node(data)

        if not home:
            return _fallback_search_result()

        photos = _extract_photos(
            _pick(
                home,
                ("photos",),
                ("primary_photo",),
                ("photo",),
                ("description", "photos"),
                ("media", "photos"),
            )
        )

        price = _pick(
            home,
            ("price",),
            ("list_price",),
            ("listPrice",),
            ("list_price_min",),
            ("description", "price"),
        )
        beds = _pick(home, ("beds",), ("bedrooms",), ("description", "beds"))
        baths = _pick(home, ("baths",), ("bathrooms",), ("description", "baths"))
        sqft = _pick(home, ("sqft",), ("sqft_value",), ("building_size", "size"), ("description", "sqft"))
        status = _pick(home, ("status",), ("listing_status",), ("description", "status"))
        days_on_market = _pick(home, ("days_on_market",), ("days_on_realtor",), ("description", "days_on_market"))
        description = _pick(home, ("description",), ("description", "text"), ("description", "summary"))

        return {
            "status": "ok",
            "provider": "realtor",
            "property": {
                "price": price,
                "beds": beds,
                "baths": baths,
                "sqft": sqft,
                "status": status,
                "days_on_market": days_on_market,
                "description": description,
                "photos": photos,
                "primary_photo": photos[0] if photos else None,
            },
            "raw": data,
        }

    except Exception as e:
        print("Realtor Provider Exception:", e)
        return _fallback_search_result()


def fetch_realtor_photos(property_id: str | int | None) -> List[str]:
    if not RAPIDAPI_KEY or not property_id:
        return []

    try:
        resp = requests.get(
            REALTOR_PHOTOS_URL,
            headers=_headers(),
            params={"id": str(property_id)},
            timeout=15,
        )
        if not resp.ok:
            print("Realtor Photos error:", resp.text[:300])
            return []
        data = resp.json()
        photo_nodes = (
            data.get("photos")
            or _pick(data, ("data", "photos"))
            or _pick(data, ("property", "photos"))
            or _pick(data, ("data", "property", "photos"))
            or []
        )
        return _extract_photos(photo_nodes)
    except Exception as e:
        print("Realtor Photos exception:", e)
        return []


def fetch_realtor_estimate(property_id: str | int | None) -> Dict[str, Any]:
    if not RAPIDAPI_KEY or not property_id:
        return {}

    try:
        resp = requests.get(
            REALTOR_ESTIMATES_URL,
            headers=_headers(),
            params={"id": str(property_id)},
            timeout=15,
        )
        if not resp.ok:
            print("Realtor Estimate error:", resp.text[:300])
            return {}
        data = resp.json()
        estimate = _pick(data, ("estimate",)) or _pick(data, ("data", "estimate")) or data
        if not isinstance(estimate, dict):
            return {}
        return {
            "estimate": _pick(estimate, ("value",), ("price",), ("amount",), ("estimate",)),
            "low": _pick(estimate, ("low",), ("min",), ("estimate_low",)),
            "high": _pick(estimate, ("high",), ("max",), ("estimate_high",)),
        }
    except Exception as e:
        print("Realtor Estimate exception:", e)
        return {}
