"""Regression tests for Build Studio's "Unable to load saved blueprint"
400 error on production.

_persist_image_b64() (cloud_studio_service.py) tries DigitalOcean Spaces
first, but falls back to writing the generated blueprint/room image to
the app's own local static folder when Spaces isn't configured -- which
returns a site-relative URL like
"/static/uploads/studios/cloud/<file>.png", not an absolute http(s) URL.

download_image_bytes() (investor_media_helpers.py) is what
generate_build_room() calls to re-read a previously-saved blueprint
before generating a new room. It unconditionally ran the URL through
_is_image_url(), which rejects anything without an http(s) scheme --
so a locally-saved blueprint could never be re-downloaded, always
returning None and producing a 400 "Unable to load saved blueprint"
every time Spaces isn't configured (exactly the production log this
fixes: BUILD ROOM LOOKUP found a real blueprint_url, but the POST to
generate-room still 400'd).
"""
import os

from unittest.mock import patch

from LoanMVP.models.admin import Company
from LoanMVP.models.borrowers import Deal
from LoanMVP.models.investor_models import InvestorProfile
from LoanMVP.models.user_model import User
from LoanMVP.services.investor.investor_media_helpers import download_image_bytes

from tests.conftest import login_as


def _make_investor(db_session, email="investor@example.com"):
    company = Company(name="Local Blueprint Co", is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role="investor", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    profile = InvestorProfile(user_id=user.id, full_name="Ivy Vestor")
    db_session.add(profile)
    db_session.commit()
    return user, profile


def test_download_image_bytes_reads_local_static_fallback_file(app):
    with app.app_context():
        rel_dir = os.path.join("uploads", "studios", "cloud")
        abs_dir = os.path.join(app.static_folder, rel_dir)
        os.makedirs(abs_dir, exist_ok=True)
        abs_path = os.path.join(abs_dir, "test_blueprint.png")
        with open(abs_path, "wb") as f:
            f.write(b"fake png bytes")

        try:
            result = download_image_bytes(f"/static/{rel_dir}/test_blueprint.png".replace(os.sep, "/"))
            assert result == b"fake png bytes"
        finally:
            os.remove(abs_path)


def test_download_image_bytes_returns_none_for_missing_local_file(app):
    with app.app_context():
        result = download_image_bytes("/static/uploads/studios/cloud/does-not-exist.png")
        assert result is None


def test_download_image_bytes_still_rejects_non_image_listing_pages(app):
    with app.app_context():
        result = download_image_bytes("https://www.zillow.com/homedetails/123-main-st")
        assert result is None


def _make_deal_with_local_blueprint(db_session, user, blueprint_url):
    build_project = {
        "blueprint": {"image_url": blueprint_url},
        "blueprint_first": {"image_url": blueprint_url},
    }
    deal = Deal(
        user_id=user.id,
        title="Local Blueprint Deal",
        results_json={"build_project": build_project},
    )
    db_session.add(deal)
    db_session.commit()
    return deal


def test_generate_build_room_succeeds_with_local_static_blueprint(db_session, client, app):
    """End-to-end: the exact production scenario -- a blueprint saved to
    the local static fallback, then generate-room re-reading it -- must
    no longer 400."""
    user, profile = _make_investor(db_session)

    rel_dir = os.path.join("uploads", "studios", "cloud")
    abs_dir = os.path.join(app.static_folder, rel_dir)
    os.makedirs(abs_dir, exist_ok=True)
    abs_path = os.path.join(abs_dir, "e2e_blueprint.png")
    with open(abs_path, "wb") as f:
        f.write(b"fake blueprint bytes long enough")

    blueprint_url = "/static/uploads/studios/cloud/e2e_blueprint.png"
    deal = _make_deal_with_local_blueprint(db_session, user, blueprint_url)
    login_as(client, user)

    try:
        with patch("LoanMVP.routes.investor_routes._engine_or_dalle") as mock_engine, \
             patch("LoanMVP.routes.investor_routes._upload_after_images_from_b64", return_value=["https://example.com/kitchen-1.png"]):
            mock_engine.return_value = {"images_base64": ["ZmFrZQ=="], "seed": 1, "job_id": "abc", "meta": {}}

            resp = client.post(
                "/investor/deal-studio/build-studio/generate-room",
                data={
                    "deal_id": str(deal.id),
                    "room_type": "kitchen",
                    "floor": "main",
                    "style": "modern_farmhouse",
                },
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
    finally:
        os.remove(abs_path)
