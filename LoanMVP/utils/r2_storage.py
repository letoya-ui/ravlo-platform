import os
import uuid
import boto3
from botocore.client import Config

def _r2_client():
    account_id = os.environ["R2_ACCOUNT_ID"]
    endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )

def r2_put_bytes(
    data: bytes,
    *,
    subdir: str,
    content_type: str = "image/png",
    filename: str | None = None
) -> dict:
    """
    Upload bytes to R2.
    Returns: {"key": "...", "url": "..."}
    """
    bucket = os.environ["R2_BUCKET"]
    public_base = os.environ.get("R2_PUBLIC_BASE_URL", "").rstrip("/")

    filename = filename or f"{uuid.uuid4().hex}.png"
    key = f"{subdir.strip('/')}/{filename}"

    s3 = _r2_client()
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
        CacheControl="public, max-age=31536000, immutable",
    )

    url = f"{public_base}/{key}" if public_base else key
    return {"key": key, "url": url}
