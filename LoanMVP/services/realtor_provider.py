import os
import requests
from typing import Dict, Any, Optional, List

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = os.getenv("REALTOR_RAPIDAPI_HOST", "realtor-search.p.rapidapi.com")
RAPIDAPI_URL = os.getenv(
    "REALTOR_RAPIDAPI_URL",
    f"https://{RAPIDAPI_HOST}/properties/v3/detail",
)


class RealtorProviderError(Exception):
    pass


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

    try:
        payload = {
            "address": address,
            "city": city,
            "state_code": state,
        }

        headers = {
            "content-type": "application/json",
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": RAPIDAPI_HOST,
        }

        resp = requests.post(RAPIDAPI_URL, json=payload, headers=headers, timeout=15)

        if not resp.ok:
            print("Realtor Provider error:", resp.text[:300])
            return None

        data = resp.json()
        home = _find_listing_node(data)

        if not home:
            return None

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
        return None
