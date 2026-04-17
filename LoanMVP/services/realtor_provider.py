import os
import requests
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = os.getenv(
    "REALTOR_RAPIDAPI_HOST",
    "us-real-estate-listings.p.rapidapi.com",
)

# GET endpoint on `us-real-estate-listings.p.rapidapi.com`. Accepts `id`,
# `url`, or `address` as query params.
REALTOR_DETAIL_URL = os.getenv(
    "REALTOR_RAPIDAPI_URL",
    f"https://{RAPIDAPI_HOST}/v2/property",
).strip()

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


def _host_for_url(url: str, fallback: str) -> str:
    try:
        parsed = urlparse(url or "")
        return parsed.netloc or fallback
    except Exception:
        return fallback


def _headers(include_json: bool = False, host: Optional[str] = None) -> Dict[str, str]:
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY or "",
        "X-RapidAPI-Host": host or RAPIDAPI_HOST,
    }
    if include_json:
        headers["content-type"] = "application/json"
    return headers


def _extract_photos(raw_photos: Any) -> List[str]:
    photos: List[str] = []

    def _ordered_photo_values(node: Dict[str, Any]) -> List[str]:
        return [
            node.get("full"),
            node.get("full_url"),
            node.get("fullSize"),
            node.get("full_size"),
            node.get("original"),
            node.get("original_url"),
            node.get("large"),
            node.get("large_url"),
            node.get("href"),
            node.get("url"),
            node.get("src"),
            node.get("photo"),
            node.get("image"),
            node.get("thumbnail"),
        ]

    if isinstance(raw_photos, list):
        for p in raw_photos:
            if isinstance(p, str) and p.strip():
                photos.append(p.strip())
            elif isinstance(p, dict):
                for url in _ordered_photo_values(p):
                    if isinstance(url, str) and url.strip():
                        photos.append(url.strip())
                        break

    elif isinstance(raw_photos, dict):
        for direct in _ordered_photo_values(raw_photos):
            if isinstance(direct, str) and direct.strip():
                photos.append(direct.strip())
                break

        for key in ("photos", "images", "media", "gallery"):
            nested = raw_photos.get(key)
            if nested:
                photos.extend(_extract_photos(nested))

    clean: List[str] = []
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


_LISTING_MARKER_KEYS = (
    "property_id",
    "propertyId",
    "listing_id",
    "mls_id",
    "list_price",
    "description",
    "photos",
    "home",
    "primary_photo",
)


def _looks_like_listing(candidate: Any) -> bool:
    if not isinstance(candidate, dict) or not candidate:
        return False
    return any(key in candidate for key in _LISTING_MARKER_KEYS)


def _find_listing_node(data: Dict[str, Any]) -> Dict[str, Any]:
    data = data or {}

    # The `/v2/property` endpoint on `us-real-estate-listings.p.rapidapi.com`
    # returns `{"data": {...listing fields...}}` — the listing dict is
    # directly under `data`, not nested under `data.home` / `data.property`.
    # Other realtor RapidAPI providers wrap it under intermediate keys, so we
    # check both the direct dict and the common nested shapes.
    data_block = data.get("data") if isinstance(data.get("data"), dict) else {}

    direct_candidates = [
        data.get("property"),
        data_block.get("home"),
        data_block.get("property"),
        data_block.get("listing"),
        data_block if _looks_like_listing(data_block) else None,
        data.get("home"),
        data.get("listing"),
        data if _looks_like_listing(data) else None,
    ]
    for candidate in direct_candidates:
        if isinstance(candidate, dict) and candidate:
            return candidate

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
    photos = _extract_photos(
        _pick(
            item,
            ("photos",),
            ("primary_photo",),
            ("photo",),
            ("description", "photos"),
            ("location", "photos"),
            ("media",),
        )
    )

    return {
        "property_id": _pick(item, ("property_id",), ("propertyId",), ("listing_id",), ("mls_id",)),
        "address": _pick(item, ("address", "line"), ("location", "address", "line"), ("description", "line"), ("address",), ("location", "address")),
        "address_line1": _pick(item, ("address", "line"), ("location", "address", "line"), ("description", "line")),
        "city": _pick(item, ("address", "city"), ("location", "address", "city"), ("location", "city"), ("description", "city")),
        "state": _pick(item, ("address", "state_code"), ("location", "address", "state_code"), ("location", "state_code"), ("description", "state_code")),
        "zip_code": _pick(item, ("address", "postal_code"), ("location", "address", "postal_code"), ("location", "postal_code"), ("description", "postal_code")),
        "price": _pick(item, ("list_price",), ("price",), ("description", "price")),
        "beds": _pick(item, ("beds",), ("bedrooms",), ("description", "beds")),
        "baths": _pick(item, ("baths",), ("bathrooms",), ("description", "baths_full"), ("description", "baths")),
        "square_feet": _pick(item, ("sqft",), ("square_feet",), ("description", "sqft")),
        "lot_size_sqft": _pick(item, ("description", "lot_sqft"), ("lot_sqft",)),
        "year_built": _pick(item, ("description", "year_built"), ("year_built",)),
        "property_type": _pick(item, ("prop_type",), ("description", "type"), ("property_type",)),
        "status": _pick(item, ("status",), ("listing_status",), ("description", "status")),
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
        resp = requests.get(
            REALTOR_SEARCH_URL,
            headers=_headers(host=_host_for_url(REALTOR_SEARCH_URL, RAPIDAPI_HOST)),
            params=params,
            timeout=20,
        )
        if not resp.ok:
            print("Realtor Search error:", resp.text[:300])
            return []
        data = resp.json()
    except Exception as e:
        print("Realtor Search exception:", e)
        return []

    listings = _extract_listing_results(data)
    return [_normalize_listing_item(item) for item in listings]


def fetch_realtor_data(
    address: str,
    city: str,
    state: str,
    zip_code: str = "",
) -> Optional[Dict[str, Any]]:
    """Fetch a single realtor.com listing matching the given address.

    Uses the `/v2/property` endpoint on `us-real-estate-listings.p.rapidapi.com`
    by default. The endpoint accepts `id`, `url`, or `address` as query params
    -- we build a freeform address string from the parts.
    """
    if not RAPIDAPI_KEY:
        return None

    location_parts = [
        part.strip()
        for part in [address, city, state, zip_code]
        if part and str(part).strip()
    ]
    location_query = ", ".join(location_parts)

    def _fallback_search_result() -> Optional[Dict[str, Any]]:
        if not location_query:
            return None

        listings = search_realtor_for_sale(location=location_query, limit=3)
        if not listings:
            return None

        selected = listings[0]
        return {
            "status": "ok",
            "provider": "realtor_search",
            "property": {
                "property_id": selected.get("property_id"),
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

    if not REALTOR_DETAIL_URL:
        return _fallback_search_result()

    if not location_query:
        return None

    try:
        resp = requests.get(
            REALTOR_DETAIL_URL,
            params={"address": location_query},
            headers=_headers(host=_host_for_url(REALTOR_DETAIL_URL, RAPIDAPI_HOST)),
            timeout=15,
        )

        if not resp.ok:
            body = (resp.text or "")[:300]
            print("Realtor Provider error:", body)
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

        # `description` in /v2/property is a full block dict. Prefer a text
        # summary when present, but fall back to the raw dict so downstream
        # callers can still pull fields like beds/baths/sqft from it.
        description = _pick(
            home,
            ("description", "text"),
            ("description", "summary"),
            ("description",),
        )

        return {
            "status": "ok",
            "provider": "realtor",
            "property": {
                "property_id": _pick(home, ("property_id",), ("propertyId",), ("listing_id",), ("mls_id",)),
                "price": _pick(home, ("list_price",), ("price",), ("listPrice",), ("list_price_min",), ("description", "price")),
                "beds": _pick(home, ("description", "beds"), ("beds",), ("bedrooms",)),
                "baths": _pick(home, ("description", "baths_consolidated"), ("description", "baths"), ("baths",), ("bathrooms",)),
                "sqft": _pick(home, ("description", "sqft"), ("sqft",), ("sqft_value",), ("building_size", "size")),
                "status": _pick(home, ("status",), ("listing_status",), ("description", "status")),
                "days_on_market": _pick(home, ("days_on_market",), ("days_on_realtor",), ("description", "days_on_market")),
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
            headers=_headers(host=_host_for_url(REALTOR_PHOTOS_URL, RAPIDAPI_HOST)),
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
            headers=_headers(host=_host_for_url(REALTOR_ESTIMATES_URL, RAPIDAPI_HOST)),
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
