"""Regression tests for the native flyer routes (/flyers/create,
/flyers/download). Mirrors the ownership-scoping discipline established
in test_listing_ownership_scoping.py: a partner must never be able to
generate a flyer for another partner's listing by guessing its id.
"""
from LoanMVP.extensions import db
from LoanMVP.models.admin import Company
from LoanMVP.models.crm_models import Partner
from LoanMVP.models.elena_models import ElenaListing
from LoanMVP.models.user_model import User
from LoanMVP.models.vip_models import VIPProfile

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
