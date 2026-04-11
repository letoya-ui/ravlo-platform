import os
import uuid

try:
    import boto3
    from botocore.client import Config
except ModuleNotFoundError:
    boto3 = None
    Config = None


def _spaces_client():
    if boto3 is None or Config is None:
        raise RuntimeError("boto3 is required for Spaces/R2 uploads but is not installed.")

    endpoint_url = os.environ["SPACES_ENDPOINT"]  # ex: https://ravlo-images.sfo3.digitaloceanspaces.com

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=os.environ["SPACES_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["SPACES_SECRET_ACCESS_KEY"],
        region_name=os.environ.get("SPACES_REGION", "sfo3"),
        config=Config(signature_version="s3v4"),
    )


def spaces_put_bytes(
    data: bytes,
    *,
    subdir: str,
    content_type: str = "image/png",
    filename: str | None = None,
) -> dict:
    bucket = os.environ["SPACES_BUCKET"]
    public_base = os.environ.get("SPACES_PUBLIC_BASE_URL", "").rstrip("/")

    filename = filename or f"{uuid.uuid4().hex}.png"
    key = f"{subdir.strip('/')}/{filename}"

    s3 = _spaces_client()
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
        ACL="public-read",
        CacheControl="public, max-age=31536000, immutable",
    )

    url = f"{public_base}/{key}" if public_base else key
    print("SPACES bucket:", bucket)
    print("SPACES key:", key)
    print("SPACES url:", url)

    return {"key": key, "url": url}
