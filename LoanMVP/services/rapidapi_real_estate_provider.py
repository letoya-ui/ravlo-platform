# LoanMVP/services/rapidapi_real_estate_provider.py

import os
import requests
from typing import Any, Dict, List, Optional


RAPIDAPI_REAL_ESTATE_KEY = os.getenv("RAPIDAPI_REAL_ESTATE_KEY")
RAPIDAPI_REAL_ESTATE_HOST = os.getenv(
    "RAPIDAPI_REAL_ESTATE_HOST",
    "all-in-one-real-estate-data-api.p.rapidapi.com",
)

BASE_URL = f"https://{RAPIDAPI_REAL_ESTATE_HOST}"


def _headers() -> Dict[str, str]:
    return {
        "x-rapidapi-key": RAPIDAPI_REAL_ESTATE_KEY or "",
        "x-rapidapi-host": RAPIDAPI_REAL_ESTATE_HOST,
    }


def _extract_photos(value: Any) -> List[str]:
    photos: List[str] = []

    def walk(node: Any):
        if not node:
            return

        if isinstance(node, str):
            if node.startswith("http"):
                photos.append(node.strip())
            return

        if isinstance(node, list):
            for item in node:
                walk(item)
            return

        if isinstance(node, dict):
            for key in (
                "url",
                "href",
                "src",
                "photo",
                "photoUrl",
                "photo_url",
                "image",
                "imageUrl",
                "image_url",
                "thumbnail",
                "full",
                "full_url",
                "highRes",
                "hiRes",
                "large",
                "large_url",
                "medium",
                "medium_url",
                "original",
                "original_url",
            ):
                val = node.get(key)
                if isinstance(val, str) and val.startswith("http"):
                    photos.append(val.strip())

            for key in (
                "photos",
                "images",
                "media",
                "gallery",
                "responsivePhotos",
                "mixedSources",
                "imageSources",
                "sources",
                "jpeg",
                "jpg",
                "webp",
                "data",
                "result",
                "results",
                "home",
                "home_search",
                "property",
                "listing",
                "listings",
            ):
                walk(node.get(key))

    walk(value)

    clean = []
    seen = set()

    for url in photos:
        if url not in seen:
            seen.add(url)
            clean.append(url)

    return clean


def fetch_zillow_photos(
    *,
    zpid: Optional[str] = None,
    property_url: Optional[str] = None,
    address: Optional[str] = None,
) -> List[str]:
    """
    Fallback photo lookup for the All-in-One Real Estate Data API.

    Best path when available:
    /real-estate/zillow/photos/{zpid}

    If Ravlo does not have a zpid yet, this returns [].
    Later, we can add a Zillow search/details lookup to find zpid by address.
    """
    if not RAPIDAPI_REAL_ESTATE_KEY:
        return []

    if not zpid:
        return []

    try:
        resp = requests.get(
            f"{BASE_URL}/real-estate/zillow/photos/{zpid}",
            headers=_headers(),
            timeout=20,
        )

        if not resp.ok:
            print("RapidAPI Real Estate photos error:", resp.text[:300])
            return []

        return _extract_photos(resp.json())

    except Exception as e:
        print("RapidAPI Real Estate photos exception:", e)
        return []


def fetch_rapidapi_real_estate_photos(property_data: Dict[str, Any]) -> List[str]:
    """
    Generic Ravlo helper. Feed this a normalized property/profile/raw match dict.
    """
    property_data = property_data or {}

    zpid = (
        property_data.get("zpid")
        or property_data.get("zillow_id")
        or property_data.get("zillowId")
        or property_data.get("zillow_property_id")
        or property_data.get("zillowPropertyId")
    )

    return fetch_zillow_photos(zpid=zpid)
