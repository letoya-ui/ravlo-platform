from __future__ import annotations

import os
import uuid
import mimetypes
import base64
import requests
from io import BytesIO
from PIL import Image

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
SPACES_KEY = os.getenv("SPACES_KEY", "")
SPACES_SECRET = os.getenv("SPACES_SECRET", "")
SPACES_CDN_BASE = os.getenv("SPACES_CDN_BASE", "").rstrip("/")


def _normalize_photo_list(value) -> list[str]:
    photos = []

    if not value:
        return photos

    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                photos.append(item.strip())
            elif isinstance(item, dict):
                ordered = [
                    item.get("full"),
                    item.get("full_url"),
                    item.get("fullSize"),
                    item.get("full_size"),
                    item.get("original"),
                    item.get("original_url"),
                    item.get("large"),
                    item.get("large_url"),
                    item.get("url"),
                    item.get("src"),
                    item.get("href"),
                    item.get("photo"),
                    item.get("image"),
                    item.get("thumbnail"),
                ]
                best = None
                for candidate in ordered:
                    if isinstance(candidate, str) and candidate.strip():
                        best = candidate.strip()
                        break
                if best:
                    photos.append(best)

                for key in ("photos", "images", "media", "gallery", "variants"):
                    nested = item.get(key)
                    if nested:
                        photos.extend(_normalize_photo_list(nested))

    elif isinstance(value, dict):
        direct_url = (
            value.get("full")
            or value.get("full_url")
            or value.get("fullSize")
            or value.get("full_size")
            or value.get("original")
            or value.get("original_url")
            or value.get("large")
            or value.get("large_url")
            or value.get("url")
            or value.get("src")
            or value.get("href")
            or value.get("photo")
            or value.get("image")
            or value.get("thumbnail")
        )
        if isinstance(direct_url, str) and direct_url.strip():
            photos.append(direct_url.strip())

        for key in ("photos", "images", "media", "gallery", "variants"):
            nested = value.get(key)
            if nested:
                photos.extend(_normalize_photo_list(nested))

    elif isinstance(value, str) and value.strip():
        photos.append(value.strip())

    seen = set()
    clean = []
    for url in photos:
        if url not in seen and not _is_map_tile_url(url):
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


def download_image_bytes(url: str) -> bytes | None:
    try:
        res = requests.get(url, timeout=10)
        if res.ok:
            return res.content
    except Exception:
        pass
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

    client = _get_spaces_client()
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
        except Exception:
            continue

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

    gallery = (
        getattr(saved_property, "photo_gallery", None)
        or getattr(saved_property, "listing_photos_json", None)
        or getattr(saved_property, "photos_json", None)
        or []
    )

    primary = (
        getattr(saved_property, "primary_photo", None)
        or getattr(saved_property, "image_url", None)
        or (gallery[0] if gallery else None)
    )

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
        payload.get("primary_photo"),
        payload.get("photo"),
        payload.get("thumbnail"),
        (payload.get("workspace_analysis") or {}).get("listing_photos") if isinstance(payload.get("workspace_analysis"), dict) else None,
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


def _upload_after_images_from_b64(images_b64: list[str], prefix="after") -> list[str]:
    urls = []
    client = _get_spaces_client()

    for b64 in images_b64:
        try:
            image_bytes = BytesIO(base64.b64decode(b64)).getvalue()
            webp = to_webp_bytes(image_bytes)

            key = f"{prefix}/{uuid.uuid4().hex}.webp"

            client.put_object(
                Bucket=SPACES_BUCKET,
                Key=key,
                Body=webp,
                ACL="public-read",
                ContentType="image/webp",
            )

            urls.append(_public_spaces_url(key))
        except Exception:
            continue

    return urls


def _upload_build_images_from_b64(images_b64: list[str], prefix="build") -> list[str]:
    return _upload_after_images_from_b64(images_b64, prefix=prefix)
