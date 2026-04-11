from __future__ import annotations

import os
import uuid
import mimetypes
import base64
import requests
from io import BytesIO
from PIL import Image
import boto3

from flask import current_app

# -------------------------
# ENV / CONFIG
# -------------------------

SPACES_BUCKET = os.getenv("SPACES_BUCKET", "")
SPACES_REGION = os.getenv("SPACES_REGION", "")
SPACES_ENDPOINT = os.getenv("SPACES_ENDPOINT", "")
SPACES_KEY = os.getenv("SPACES_KEY", "")
SPACES_SECRET = os.getenv("SPACES_SECRET", "")
SPACES_CDN_BASE = os.getenv("SPACES_CDN_BASE", "").rstrip("/")


# -------------------------
# PHOTO NORMALIZATION
# -------------------------

def _normalize_photo_list(value) -> list[str]:
    photos = []

    if not value:
        return photos

    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                photos.append(item.strip())
            elif isinstance(item, dict):
                url = (
                    item.get("url")
                    or item.get("src")
                    or item.get("href")
                    or item.get("photo")
                    or item.get("image")
                )
                if isinstance(url, str) and url.strip():
                    photos.append(url.strip())

    elif isinstance(value, dict):
        for key in ("photos", "images", "media", "gallery"):
            nested = value.get(key)
            if nested:
                photos.extend(_normalize_photo_list(nested))

    # dedupe
    seen = set()
    clean = []
    for url in photos:
        if url not in seen:
            seen.add(url)
            clean.append(url)

    return clean


def _resolve_photo(primary=None, gallery=None):
    gallery = gallery or []
    if primary:
        return primary
    if gallery:
        return gallery[0]
    return ""


def _normalize_photo_urls(*sources):
    for source in sources:
        photos = _normalize_photo_list(source)
        if photos:
            return photos
    return []


# -------------------------
# SPACES CLIENT
# -------------------------

def _get_spaces_client():
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


# -------------------------
# IMAGE UTILS
# -------------------------

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


# -------------------------
# UPLOAD HELPERS
# -------------------------

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


# -------------------------
# MODEL ATTACH HELPERS
# -------------------------

def _persist_listing_photo_refs(model, photo_urls: list[str]):
    if not model:
        return

    if hasattr(model, "photo_gallery"):
        model.photo_gallery = photo_urls

    if hasattr(model, "primary_photo"):
        model.primary_photo = photo_urls[0] if photo_urls else None


def _try_upload_and_attach_listing_photos(model, raw_photos):
    normalized = _normalize_photo_list(raw_photos)
    if not normalized:
        return []

    uploaded = upload_listing_photos_to_spaces(normalized)
    _persist_listing_photo_refs(model, uploaded)
    return uploaded


def _store_saved_property_media(saved_property, photo_urls):
    if not saved_property:
        return

    if hasattr(saved_property, "photo_gallery"):
        saved_property.photo_gallery = photo_urls

    if hasattr(saved_property, "primary_photo"):
        saved_property.primary_photo = photo_urls[0] if photo_urls else None


def _saved_property_media(saved_property):
    if not saved_property:
        return {"primary_photo": None, "gallery": []}

    return {
        "primary_photo": getattr(saved_property, "primary_photo", None),
        "gallery": getattr(saved_property, "photo_gallery", []) or [],
    }


# -------------------------
# BUILD / RENOVATION IMAGE HELPERS
# -------------------------

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
