from __future__ import annotations

import logging
import os
import uuid
import mimetypes
import base64
import requests
from io import BytesIO
from urllib.parse import urlparse, parse_qs

from LoanMVP.utils.safe_http import safe_call
try:
    from PIL import Image as _PILImage
    Image = _PILImage
except ImportError:
    Image = None  # Pillow not installed — photo-resize features disabled

logger = logging.getLogger(__name__)

try:
    import boto3
except ModuleNotFoundError:
    boto3 = None

from flask import current_app


def _photo_score(url: str | None) -> int:
    value = str(url or "").lower()
    if not value:
        return -10_000

    score = 0

    penalties = (
        "thumbnail",
        "thumb",
        "small",
        "tiny",
        "100x100",
        "150x150",
        "200x200",
        "300x",
        "avatar",
        "icon",
    )
    bonuses = (
        "full",
        "original",
        "orig",
        "large",
        "xl",
        "2048",
        "1920",
        "1600",
        "1200",
        "hero",
    )

    for token in penalties:
        if token in value:
            score -= 40

    for token in bonuses:
        if token in value:
            score += 20

    if value.startswith("https://"):
        score += 2

    return score


SPACES_BUCKET = os.getenv("SPACES_BUCKET", "")
SPACES_REGION = os.getenv("SPACES_REGION", "")
SPACES_ENDPOINT = os.getenv("SPACES_ENDPOINT", "")
SPACES_KEY = os.getenv("SPACES_ACCESS_KEY_ID", "") or os.getenv("SPACES_KEY", "")
SPACES_SECRET = os.getenv("SPACES_SECRET_ACCESS_KEY", "") or os.getenv("SPACES_SECRET", "")
SPACES_CDN_BASE = (os.getenv("SPACES_PUBLIC_BASE_URL", "") or os.getenv("SPACES_CDN_BASE", "")).rstrip("/")


def _normalize_photo_list(value, _depth: int = 0) -> list[str]:
    photos = []

    if not value:
        return photos

    if _depth > 3:
        return photos

    # Keys that hold a direct image URL inside a photo dict, ordered by
    # preference (largest / highest-quality first).  Includes common keys
    # returned by ATTOM, RentCast, Mashvisor, Realtor, and Zillow APIs.
    _DIRECT_URL_KEYS = (
        "full", "full_url", "fullSize", "full_size",
        "original", "original_url",
        "large", "large_url",
        "medium", "medium_url",
        "highRes", "high_res", "highResUrl", "high_res_url",
        "imgSrc", "img_src",
        "imageUrl", "image_url", "imageURL",
        "photoUrl", "photo_url", "photoURL",
        "primaryPhoto", "primary_photo", "primaryPhotoUrl", "primary_photo_url",
        "mainImage", "main_image", "listingImage", "listing_image",
        "coverImage", "cover_image",
        "hiRes", "hi_res",
        "sourceUrl", "source_url",
        "assetUrl", "asset_url",
        "cdnUrl", "cdn_url",
        "picture", "pictureUrl", "picture_url",
        "secure_url", "public_url", "cdn_url",
        "url", "src", "href",
        "photo", "image",
        "thumbnail",
    )

    # Keys that hold nested collections of photos.
    _NESTED_COLLECTION_KEYS = (
        "photos", "images", "media", "gallery", "variants",
        "photoUrls", "photo_urls",
        "imageUrls", "image_urls",
        "photoLinks", "photo_links",
        "mediaUrls", "media_urls",
        "listingPhotos", "listing_photos",
        "listingImages", "listing_images",
        "propertyPhotos", "property_photos",
        "propertyImages", "property_images",
        "responsivePhotos", "responsive_photos",
        "mixedSources", "mixed_sources",
        "imageSources", "image_sources",
        "photoSources", "photo_sources",
        "jpeg", "jpg", "webp",
        "sources", "source",
        "carouselPhotos", "carousel_photos",
        "galleryUrls", "gallery_urls",
        "extra_images",
        "data", "result", "results",
        "home", "home_search", "property", "listing", "listings",
        "description", "location",
    )

    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                photos.append(item.strip())
            elif isinstance(item, dict):
                best = None
                for key in _DIRECT_URL_KEYS:
                    candidate = item.get(key)
                    if isinstance(candidate, str) and candidate.strip():
                        best = candidate.strip()
                        break
                if best:
                    photos.append(best)

                for key in _NESTED_COLLECTION_KEYS:
                    nested = item.get(key)
                    if nested:
                        photos.extend(_normalize_photo_list(nested, _depth + 1))

    elif isinstance(value, dict):
        direct_url = None
        for key in _DIRECT_URL_KEYS:
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                direct_url = candidate.strip()
                break
            if candidate and not isinstance(candidate, str):
                photos.extend(_normalize_photo_list(candidate, _depth + 1))
        if direct_url:
            photos.append(direct_url)

        for key in _NESTED_COLLECTION_KEYS:
            nested = value.get(key)
            if nested:
                photos.extend(_normalize_photo_list(nested, _depth + 1))

    elif isinstance(value, str) and value.strip():
        photos.append(value.strip())

    seen = set()
    clean = []
    for url in photos:
        url = _unwrap_proxy_url(url)
        if url and url not in seen and not _is_map_tile_url(url):
            seen.add(url)
            clean.append(url)

    clean.sort(key=_photo_score, reverse=True)
    return clean


def _is_map_tile_url(url):
    """Return True if *url* is an OpenStreetMap (or similar) map-tile URL."""
    if not url:
        return False
    lower = str(url).lower()
    return "tile.openstreetmap.org" in lower or "tiles.mapbox.com" in lower


def _resolve_photo(primary=None, gallery=None):
    candidates = _normalize_photo_urls(primary, gallery)
    return candidates[0] if candidates else ""


def _normalize_photo_urls(*sources):
    merged = []
    seen = set()

    for source in sources:
        for url in _normalize_photo_list(source):
            if url not in seen:
                seen.add(url)
                merged.append(url)

    merged.sort(key=_photo_score, reverse=True)
    return merged


def _get_spaces_client():
    if boto3 is None:
        raise RuntimeError("boto3 is required for Spaces uploads but is not installed.")

    return boto3.client(
        "s3",
        region_name=SPACES_REGION,
        endpoint_url=SPACES_ENDPOINT,
        aws_access_key_id=SPACES_KEY,
        aws_secret_access_key=SPACES_SECRET,
    )


def _public_spaces_url(key: str) -> str:
    if SPACES_CDN_BASE:
        return f"{SPACES_CDN_BASE}/{key}"
    return f"{SPACES_ENDPOINT}/{SPACES_BUCKET}/{key}"


_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


_LISTING_PAGE_RULES: list[tuple[str, str]] = [
    # (hostname_suffix, path_substring)
    ("realtor.com", "/realestateandhomes-detail/"),
    ("zillow.com", "/homedetails/"),
    ("zillow.com", "/homes/"),
    ("redfin.com", "/listing/"),
    ("redfin.com", "/property/"),
    ("trulia.com", "/property/"),
    ("homes.com", "/listing/"),
    ("realtor.com", "/property-overview/"),
]


def _is_image_url(url: str) -> bool:
    """Return False for URLs that are clearly HTML listing pages, not images."""
    if not url or not url.startswith(("http://", "https://")):
        return False
    parsed = urlparse(url)
    host = parsed.hostname or ""
    path = parsed.path.lower()
    for host_suffix, path_pattern in _LISTING_PAGE_RULES:
        if host.endswith(host_suffix) and path_pattern in path:
            return False
    return True


def _unwrap_proxy_url(url: str) -> str:
    """Extract the original URL from a proxied /api/property_tool_image?src= URL."""
    if not url:
        return url
    if "property_tool_image" in url and "src=" in url:
        parsed = urlparse(url)
        src = parse_qs(parsed.query).get("src", [""])[0]
        if src:
            return src
    return url


def download_image_bytes(url: str) -> bytes | None:
    url = _unwrap_proxy_url(url)

    # Site-relative path (e.g. "/static/uploads/studios/cloud/<file>.png"),
    # what _persist_image_b64()'s local-disk fallback returns when
    # DigitalOcean Spaces isn't configured -- _is_image_url() below rejects
    # anything without an http(s) scheme, so an HTTP round-trip can never
    # fetch this; read it straight off disk instead.
    if url and url.startswith("/static/"):
        try:
            local_path = os.path.join(current_app.static_folder, url[len("/static/"):])
            if os.path.isfile(local_path):
                with open(local_path, "rb") as f:
                    return f.read()
            logger.info("Local static file not found: %s", local_path)
        except Exception as exc:
            logger.info("Local static file read failed for %s: %s", url[:200], exc)
        return None

    if not _is_image_url(url):
        logger.info("Skipping non-image URL: %s", url[:200])
        return None
    try:
        res = safe_call(requests.get, url, timeout=15, headers=_BROWSER_HEADERS)
        if not res.ok:
            logger.info("Image download returned %s for %s", res.status_code, url[:200])
            return None
        content_type = res.headers.get("Content-Type", "")
        if content_type and not content_type.startswith("image/"):
            logger.info("Non-image content-type '%s' for %s", content_type, url[:200])
            return None
        if len(res.content) < 1000:
            logger.info("Suspiciously small response (%d bytes) for %s", len(res.content), url[:200])
            return None
        return res.content
    except Exception as exc:
        logger.info("Image download failed for %s: %s", url[:200], exc)
    return None


def to_png_bytes(image_bytes: bytes) -> bytes:
    img = Image.open(BytesIO(image_bytes)).convert("RGBA")
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def to_webp_bytes(image_bytes: bytes) -> bytes:
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    out = BytesIO()
    img.save(out, format="WEBP", quality=85)
    return out.getvalue()


def upload_listing_photos_to_spaces(photos: list[str], prefix="listing") -> list[str]:
    if not photos:
        return []

    try:
        client = _get_spaces_client()
    except Exception as exc:
        logger.warning("Cannot create Spaces client, skipping photo upload: %s", exc)
        return []

    uploaded_urls = []

    for url in photos:
        try:
            raw = download_image_bytes(url)
            if not raw:
                continue

            key = f"{prefix}/{uuid.uuid4().hex}.webp"
            webp = to_webp_bytes(raw)

            client.put_object(
                Bucket=SPACES_BUCKET,
                Key=key,
                Body=webp,
                ACL="public-read",
                ContentType="image/webp",
            )

            uploaded_urls.append(_public_spaces_url(key))
            logger.info("Uploaded listing photo to Spaces: %s -> %s", url[:120], _public_spaces_url(key)[:120])
        except Exception as exc:
            logger.warning("Failed to upload listing photo %s: %s", url[:200], exc)
            continue

    logger.info("Uploaded %d/%d listing photos to Spaces", len(uploaded_urls), len(photos))
    return uploaded_urls


def _persist_listing_photo_refs(model, photo_urls: list[str]):
    if not model:
        return

    if hasattr(model, "photo_gallery"):
        model.photo_gallery = photo_urls

    if hasattr(model, "primary_photo"):
        model.primary_photo = photo_urls[0] if photo_urls else None

    if hasattr(model, "listing_photos_json"):
        model.listing_photos_json = photo_urls

    if hasattr(model, "photos_json"):
        model.photos_json = photo_urls

    if hasattr(model, "image_url"):
        model.image_url = photo_urls[0] if photo_urls else getattr(model, "image_url", None)


def _store_saved_property_media(saved_property, photo_urls):
    if not saved_property:
        return

    if hasattr(saved_property, "photo_gallery"):
        saved_property.photo_gallery = photo_urls

    if hasattr(saved_property, "primary_photo"):
        saved_property.primary_photo = photo_urls[0] if photo_urls else None

    if hasattr(saved_property, "listing_photos_json"):
        saved_property.listing_photos_json = photo_urls

    if hasattr(saved_property, "photos_json"):
        saved_property.photos_json = photo_urls

    if hasattr(saved_property, "image_url") and photo_urls:
        saved_property.image_url = photo_urls[0]


def _saved_property_media(saved_property):
    if not saved_property:
        return {"primary_photo": None, "gallery": []}

    raw_gallery = (
        getattr(saved_property, "photo_gallery", None)
        or getattr(saved_property, "listing_photos_json", None)
        or getattr(saved_property, "photos_json", None)
        or []
    )

    raw_primary = (
        getattr(saved_property, "primary_photo", None)
        or getattr(saved_property, "image_url", None)
    )

    gallery = _normalize_photo_urls(raw_primary, raw_gallery)
    primary = _resolve_photo(raw_primary, gallery)

    return {
        "primary_photo": primary,
        "gallery": gallery,
    }


def _extract_listing_photos_from_payload(payload) -> list[str]:
    if not isinstance(payload, dict):
        return []

    return _normalize_photo_urls(
        payload.get("listing_photos"),
        payload.get("photos"),
        payload.get("images"),
        payload.get("media"),
        payload.get("gallery"),
        payload.get("image_url"),
        payload.get("imageUrl"),
        payload.get("primary_photo"),
        payload.get("primaryPhoto"),
        payload.get("primaryPhotoUrl"),
        payload.get("photo"),
        payload.get("photo_url"),
        payload.get("photoUrl"),
        payload.get("thumbnail"),
        payload.get("photo_links"),
        payload.get("photoLinks"),
        payload.get("image_urls"),
        payload.get("imageUrls"),
        payload.get("property_photos"),
        payload.get("propertyPhotos"),
        payload.get("listing_images"),
        payload.get("listingImages"),
        payload.get("raw"),
        (payload.get("workspace_analysis") or {}).get("listing_photos") if isinstance(payload.get("workspace_analysis"), dict) else None,
        (payload.get("workspace_analysis") or {}).get("photos") if isinstance(payload.get("workspace_analysis"), dict) else None,
        (payload.get("workspace_analysis") or {}).get("image_url") if isinstance(payload.get("workspace_analysis"), dict) else None,
    )


def _try_upload_and_attach_listing_photos(payload=None, saved_property=None, deal=None):
    """
    Expected by api_property_tool_save and api_property_tool_save_and_analyze.

    Returns a list of dicts:
    [
        {"url": "https://..."},
        ...
    ]
    """
    payload = payload or {}
    raw_photos = _extract_listing_photos_from_payload(payload)
    if not raw_photos:
        return []

    uploaded_urls = upload_listing_photos_to_spaces(raw_photos)
    if not uploaded_urls:
        return []

    _store_saved_property_media(saved_property, uploaded_urls)
    _persist_listing_photo_refs(deal, uploaded_urls)

    return [{"url": url} for url in uploaded_urls]


def _upload_before_image(image_bytes: bytes, prefix="before") -> str | None:
    if not image_bytes:
        return None

    try:
        client = _get_spaces_client()
        key = f"{prefix}/{uuid.uuid4().hex}.png"

        client.put_object(
            Bucket=SPACES_BUCKET,
            Key=key,
            Body=image_bytes,
            ACL="public-read",
            ContentType="image/png",
        )

        return _public_spaces_url(key)
    except Exception as exc:
        logger.warning("Spaces upload unavailable, falling back to inline data URI: %s", exc)
        return "data:image/png;base64," + base64.b64encode(image_bytes).decode()


def _upload_after_images_from_b64(images_b64, prefix="after") -> list[str]:
    urls = []

    # images_b64 may be a list ["b64..."] or a dict {"mode": "b64..."} depending
    # on whether the GPU engine or the OpenAI fallback produced it.
    if isinstance(images_b64, dict):
        items = [v for v in images_b64.values() if v]
    else:
        items = [b for b in (images_b64 or []) if b]

    try:
        client = _get_spaces_client()
    except Exception as exc:
        logger.warning("Spaces upload unavailable, falling back to inline data URIs: %s", exc)
        client = None

    for b64 in items:
        try:
            image_bytes = BytesIO(base64.b64decode(b64)).getvalue()
            webp = to_webp_bytes(image_bytes)

            if client is None:
                urls.append("data:image/webp;base64," + base64.b64encode(webp).decode())
                continue

            key = f"{prefix}/{uuid.uuid4().hex}.webp"

            client.put_object(
                Bucket=SPACES_BUCKET,
                Key=key,
                Body=webp,
                ACL="public-read",
                ContentType="image/webp",
            )

            urls.append(_public_spaces_url(key))
        except Exception as exc:
            logger.warning("Failed to upload build image to Spaces: %s", exc)
            continue

    return urls


def _upload_build_images_from_b64(images_b64: list[str], prefix="build") -> list[str]:
    return _upload_after_images_from_b64(images_b64, prefix=prefix)
