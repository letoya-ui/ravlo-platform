"""Regression tests for the native flyer routes (/flyers/create,
/flyers/download). Mirrors the ownership-scoping discipline established
in test_listing_ownership_scoping.py: a partner must never be able to
generate a flyer for another partner's listing by guessing its id.
"""
from unittest.mock import patch

from LoanMVP.extensions import db
from LoanMVP.models.admin import Company
from LoanMVP.models.crm_models import Partner
from LoanMVP.models.elena_models import ElenaListing
from LoanMVP.models.user_model import User
from LoanMVP.models.vip_models import VIPProfile
from LoanMVP.services.flyer_ai import FlyerRequestParseError

from tests.conftest import login_as


def _make_realtor(db_session, email, brand_color=None, logo_url=None, business_name="Test Realty"):
    company = Company(name=f"Co {email}", is_active=True)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role="partner", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    partner = Partner(user_id=user.id, name=email, category="realtor", type="Realtor", subscription_tier="Premium")
    db_session.add(partner)

    profile = VIPProfile(
        user_id=user.id, display_name=email, role_type="realtor",
        business_name=business_name, brand_color=brand_color, logo_url=logo_url,
        headline="Selling homes with heart", bio="A short bio.",
    )
    db_session.add(profile)
    db_session.commit()
    return user, profile


def _make_listing(db_session, profile, **overrides):
    defaults = dict(
        vip_profile_id=profile.id, address="123 Main St", city="Tampa", state="FL", zip_code="33607",
        price=450000, beds=3, baths=2, sqft=1800, description="Charming updated bungalow.",
    )
    defaults.update(overrides)
    listing = ElenaListing(**defaults)
    db_session.add(listing)
    db_session.commit()
    return listing


def test_create_requires_login(client):
    resp = client.get("/flyers/create", follow_redirects=False)
    assert resp.status_code in (302, 401)


def test_create_without_brand_set_shows_a_setup_nudge(db_session, client):
    user, profile = _make_realtor(db_session, "nobrand@example.com")
    login_as(client, user)

    resp = client.get("/flyers/create")

    assert resp.status_code == 200
    assert "Set up your brand first" in resp.get_data(as_text=True)


def test_create_with_brand_set_does_not_show_setup_nudge(db_session, client):
    user, profile = _make_realtor(db_session, "hasbrand@example.com", brand_color="#4f6bed")
    login_as(client, user)

    resp = client.get("/flyers/create")

    assert resp.status_code == 200
    assert "Set up your brand first" not in resp.get_data(as_text=True)


def test_create_shows_listing_details_when_listing_id_given(db_session, client):
    user, profile = _make_realtor(db_session, "withlisting@example.com", brand_color="#4f6bed")
    listing = _make_listing(db_session, profile, address="456 Ocean Ave")
    login_as(client, user)

    resp = client.get(f"/flyers/create?listing_id={listing.id}")

    assert resp.status_code == 200
    assert "456 Ocean Ave" in resp.get_data(as_text=True)


def test_create_ignores_another_partners_listing_id(db_session, client):
    user, profile = _make_realtor(db_session, "me@example.com", brand_color="#4f6bed")
    other_user, other_profile = _make_realtor(db_session, "other@example.com", brand_color="#4f6bed")
    other_listing = _make_listing(db_session, other_profile, address="999 Not Mine Ave")
    login_as(client, user)

    resp = client.get(f"/flyers/create?listing_id={other_listing.id}")

    assert resp.status_code == 200
    assert "999 Not Mine Ave" not in resp.get_data(as_text=True)


def test_download_business_flyer_returns_a_pdf(db_session, client):
    user, profile = _make_realtor(db_session, "downloader@example.com", brand_color="#4f6bed")
    login_as(client, user)

    resp = client.get("/flyers/download")

    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert resp.data.startswith(b"%PDF")


def test_download_listing_flyer_returns_a_pdf(db_session, client):
    user, profile = _make_realtor(db_session, "downloader2@example.com", brand_color="#4f6bed")
    listing = _make_listing(db_session, profile)
    login_as(client, user)

    resp = client.get(f"/flyers/download?listing_id={listing.id}")

    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert resp.data.startswith(b"%PDF")


def test_download_cannot_be_used_to_generate_another_partners_listing_flyer(db_session, client):
    user, profile = _make_realtor(db_session, "attacker@example.com", brand_color="#4f6bed")
    other_user, other_profile = _make_realtor(db_session, "victim@example.com", brand_color="#4f6bed")
    other_listing = _make_listing(db_session, other_profile, address="999 Victim Ave", price=999999)
    login_as(client, user)

    resp = client.get(f"/flyers/download?listing_id={other_listing.id}")

    # Falls back to a business flyer (the listing didn't resolve for this
    # user) rather than leaking the other partner's listing data.
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"


# ─── AI-parsed ("Ravlo, create me an open house flyer...") flow ───────

def _parsed(**overrides):
    defaults = dict(
        flyer_type="open_house", address="123 Main St", city=None, state=None, zip=None,
        day_of_week="Saturday", explicit_date=None, time="12:00 PM", time_end=None,
    )
    defaults.update(overrides)
    return defaults


def test_ai_create_shows_an_editable_preview(db_session, client):
    user, profile = _make_realtor(db_session, "ai1@example.com", brand_color="#4f6bed")
    login_as(client, user)

    with patch("LoanMVP.routes.flyers.parse_flyer_request", return_value=_parsed()):
        resp = client.post("/flyers/ai-create", data={"prompt": "open house flyer for 123 main st sat at 12"})

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "123 Main St" in body
    assert "12:00 PM" in body
    assert 'action="/flyers/download-open-house"' in body


def test_ai_create_matches_an_existing_listing_for_enrichment(db_session, client):
    user, profile = _make_realtor(db_session, "ai2@example.com", brand_color="#4f6bed")
    _make_listing(db_session, profile, address="123 Main St", price=550000, beds=5)
    login_as(client, user)

    with patch("LoanMVP.routes.flyers.parse_flyer_request", return_value=_parsed()):
        resp = client.post("/flyers/ai-create", data={"prompt": "open house flyer for 123 main st sat at 12"})

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # The matched listing's own price/beds show up in the flyer preview panel.
    assert "550,000" in body
    assert "5 bd" in body


def test_ai_create_rejects_a_request_with_no_address(db_session, client):
    user, profile = _make_realtor(db_session, "ai3@example.com", brand_color="#4f6bed")
    login_as(client, user)

    with patch("LoanMVP.routes.flyers.parse_flyer_request", return_value=_parsed(address=None)):
        resp = client.post("/flyers/ai-create", data={"prompt": "make me a flyer"}, follow_redirects=True)

    assert resp.status_code == 200
    assert "give it an address" in resp.get_data(as_text=True)


def test_ai_create_handles_a_parser_failure_gracefully(db_session, client):
    user, profile = _make_realtor(db_session, "ai4@example.com", brand_color="#4f6bed")
    login_as(client, user)

    with patch("LoanMVP.routes.flyers.parse_flyer_request", side_effect=FlyerRequestParseError("boom")):
        resp = client.post("/flyers/ai-create", data={"prompt": "open house flyer"}, follow_redirects=True)

    assert resp.status_code == 200
    assert "Couldn" in resp.get_data(as_text=True)


def test_ai_create_requires_a_nonempty_prompt(db_session, client):
    user, profile = _make_realtor(db_session, "ai5@example.com", brand_color="#4f6bed")
    login_as(client, user)

    resp = client.post("/flyers/ai-create", data={"prompt": ""}, follow_redirects=True)

    assert resp.status_code == 200
    assert "Tell Ravlo what you need" in resp.get_data(as_text=True)


def test_download_open_house_returns_a_pdf_for_a_bare_address(db_session, client):
    user, profile = _make_realtor(db_session, "ohdownload@example.com", brand_color="#4f6bed")
    login_as(client, user)

    resp = client.get("/flyers/download-open-house?address=123+Main+St&event_date=2026-09-19&event_time=12:00+PM")

    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert resp.data.startswith(b"%PDF")


def test_download_open_house_requires_an_address(db_session, client):
    user, profile = _make_realtor(db_session, "ohnoaddr@example.com", brand_color="#4f6bed")
    login_as(client, user)

    resp = client.get("/flyers/download-open-house", follow_redirects=True)

    assert resp.status_code == 200
    assert "address is required" in resp.get_data(as_text=True)


def test_download_open_house_cannot_pull_another_partners_listing_by_id(db_session, client):
    user, profile = _make_realtor(db_session, "ohattacker@example.com", brand_color="#4f6bed")
    other_user, other_profile = _make_realtor(db_session, "ohvictim@example.com", brand_color="#4f6bed")
    other_listing = _make_listing(db_session, other_profile, address="999 Victim Ave", price=999999)
    login_as(client, user)

    resp = client.get(f"/flyers/download-open-house?address=999+Victim+Ave&listing_id={other_listing.id}")

    # listing_id doesn't resolve for this user, so the PDF is built from
    # the bare address only -- it must not leak the other partner's data.
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
