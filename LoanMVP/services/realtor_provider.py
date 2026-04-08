import os
import requests
from typing import Dict, Any, Optional, List

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = "realtor.p.rapidapi.com"
RAPIDAPI_URL = "https://realtor.p.rapidapi.com/properties/v3/detail"


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
        home = (data.get("data") or {}).get("home")

        if not home:
            return None

        photos = _extract_photos(home.get("photos"))

        return {
            "status": "ok",
            "provider": "realtor",
            "property": {
                "price": home.get("price"),
                "beds": home.get("beds"),
                "baths": home.get("baths"),
                "sqft": home.get("sqft"),
                "status": home.get("status"),
                "days_on_market": home.get("days_on_market"),
                "description": home.get("description"),
                "photos": photos,
                "primary_photo": photos[0] if photos else None,
            },
            "raw": data,
        }

    except Exception as e:
        print("Realtor Provider Exception:", e)
        return None
