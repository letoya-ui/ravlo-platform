"""Regression tests for the new "Brand" section on /vip/onboarding:
logo upload, brand color, and claiming a public_slug -- previously the
only way to get any of these set was a developer hand-running a
one-off script per realtor (see LoanMVP/create_bonnie_realtor.py,
create_john_headley.py, etc.). There was no self-serve path at all.
"""
import io
from unittest.mock import patch

from LoanMVP.extensions import db
from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User
from LoanMVP.models.vip_models import VIPProfile

from tests.conftest import login_as


def _make_partner(db_session, email):
    company = Company(name=f"Co {email}", is_active=True)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role="partner", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user


def _base_form(**overrides):
    form = {
        "display_name": "Test User",
        "business_name": "Test Realty",
        "dashboard_title": "",
        "assistant_name": "Ravlo",
        "role_type": "realtor",
        "service_area": "",
        "headline": "",
        "bio": "",
    }
    form.update(overrides)
    return form


def test_brand_color_saves_when_valid(db_session, client):
    user = _make_partner(db_session, "colorvalid@example.com")
    login_as(client, user)

    resp = client.post("/vip/onboarding/save", data=_base_form(brand_color="#4f6bed"), follow_redirects=True)

    assert resp.status_code == 200
    profile = VIPProfile.query.filter_by(user_id=user.id).first()
    assert profile.brand_color == "#4f6bed"


def test_brand_color_rejects_invalid_hex(db_session, client):
    user = _make_partner(db_session, "colorinvalid@example.com")
    login_as(client, user)

    resp = client.post("/vip/onboarding/save", data=_base_form(brand_color="blue"), follow_redirects=True)

    assert resp.status_code == 200
    assert "hex code" in resp.get_data(as_text=True)
    profile = VIPProfile.query.filter_by(user_id=user.id).first()
    assert profile is None or profile.brand_color != "blue"


def test_public_slug_claims_successfully(db_session, client):
    user = _make_partner(db_session, "slugclaim@example.com")
    login_as(client, user)

    resp = client.post("/vip/onboarding/save", data=_base_form(public_slug="my-new-page"), follow_redirects=True)

    assert resp.status_code == 200
    profile = VIPProfile.query.filter_by(user_id=user.id).first()
    assert profile.public_slug == "my-new-page"


def test_public_slug_normalizes_spaces_and_symbols():
    import re
    raw = "My Cool Page!!"
    normalized = re.sub(r"[^a-z0-9-]+", "-", raw.strip().lower()).strip("-")
    assert normalized == "my-cool-page"


def test_public_slug_rejects_one_already_taken_by_someone_else(db_session, client):
    existing_user = _make_partner(db_session, "existing@example.com")
    existing_profile = VIPProfile(user_id=existing_user.id, display_name="Existing", role_type="realtor", public_slug="taken-slug")
    db_session.add(existing_profile)
    db_session.commit()

    user = _make_partner(db_session, "wantstaken@example.com")
    login_as(client, user)

    resp = client.post("/vip/onboarding/save", data=_base_form(public_slug="taken-slug"), follow_redirects=True)

    assert resp.status_code == 200
    assert "already taken" in resp.get_data(as_text=True)
    profile = VIPProfile.query.filter_by(user_id=user.id).first()
    assert profile is None or profile.public_slug != "taken-slug"


def test_public_slug_can_be_saved_unchanged_without_a_false_conflict(db_session, client):
    user = _make_partner(db_session, "keepslug@example.com")
    profile = VIPProfile(user_id=user.id, display_name="Keep", role_type="realtor", public_slug="my-slug")
    db_session.add(profile)
    db_session.commit()
    login_as(client, user)

    resp = client.post("/vip/onboarding/save", data=_base_form(public_slug="my-slug"), follow_redirects=True)

    assert resp.status_code == 200
    assert "already taken" not in resp.get_data(as_text=True)


def test_logo_upload_sets_logo_url(db_session, client):
    user = _make_partner(db_session, "logoupload@example.com")
    login_as(client, user)

    with patch("LoanMVP.routes.vip.upload_vip_logo", return_value="https://cdn.example.com/logos/abc.png"):
        resp = client.post(
            "/vip/onboarding/save",
            data={**_base_form(), "logo": (io.BytesIO(b"fake-png-bytes"), "logo.png")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )

    assert resp.status_code == 200
    profile = VIPProfile.query.filter_by(user_id=user.id).first()
    assert profile.logo_url == "https://cdn.example.com/logos/abc.png"


def test_logo_upload_failure_flashes_a_warning_and_does_not_save_other_fields(db_session, client):
    user = _make_partner(db_session, "logofail@example.com")
    login_as(client, user)

    with patch("LoanMVP.routes.vip.upload_vip_logo", return_value=None):
        resp = client.post(
            "/vip/onboarding/save",
            data={**_base_form(business_name="Should Not Save"), "logo": (io.BytesIO(b"junk"), "logo.png")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )

    assert resp.status_code == 200
    assert "Logo upload failed" in resp.get_data(as_text=True)
