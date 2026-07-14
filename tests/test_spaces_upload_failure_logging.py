"""Regression test for a production incident: after Spaces credentials were
added to the environment, full builds started failing with
"RuntimeError: Upload failed for exterior_front" and no further detail.

_upload_after_images_from_b64() (investor_media_helpers.py) swallowed the
underlying boto3/S3 exception with a bare `except Exception: continue`,
so whatever put_object actually failed with (bad credentials, wrong
bucket/endpoint, an ACL the bucket doesn't allow, etc.) never reached the
logs -- only the generic "Upload failed for <mode>" surfaced, with no way
to diagnose it further. The sibling function upload_listing_photos_to_spaces
already logs this correctly; this brings the build-image path in line with
that existing pattern.
"""
import base64
import logging

from LoanMVP.services.investor import investor_media_helpers as media


def test_upload_after_images_logs_the_underlying_spaces_error(monkeypatch, caplog):
    class _FakeClient:
        def put_object(self, **kwargs):
            raise Exception("SignatureDoesNotMatch: the request signature we calculated does not match")

    monkeypatch.setattr(media, "_get_spaces_client", lambda: _FakeClient())
    monkeypatch.setattr(media, "to_webp_bytes", lambda image_bytes: image_bytes)

    fake_image_b64 = base64.b64encode(b"fake-image-bytes").decode()

    with caplog.at_level(logging.WARNING, logger="LoanMVP.services.investor.investor_media_helpers"):
        urls = media._upload_after_images_from_b64([fake_image_b64], prefix="build")

    assert urls == []
    assert any("SignatureDoesNotMatch" in record.message for record in caplog.records)
