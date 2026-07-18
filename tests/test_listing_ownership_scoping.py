"""Regression tests for scoping ElenaListing (and its flyers) to a real
owner (vip_profile_id).

ElenaListing previously had no ownership field at all -- only a loose
"market" text string. Any realtor whose profile had no configured market
(or who shared a market string with another partner) saw every listing
on the platform, including other partners' demo/test data, plus the
auto-generated flyers tied to those listings. This adds real ownership
and scopes every "my listings" read (dashboard, listings page, public
landing page, recent flyers) to it, and closes IDORs on the listing
detail/delete/status routes that let any realtor touch any other
realtor's listing by id.
"""
from LoanMVP.extensions import db
from LoanMVP.models.admin import Company
from LoanMVP.models.crm_models import Partner
from LoanMVP.models.elena_models import ElenaFlyer, ElenaListing
from LoanMVP.models.user_model import User
from LoanMVP.models.vip_models import VIPProfile

from tests.conftest import login_as


def _make_realtor(db_session, email, slug):
    company = Company(name=f"Co {email}", is_active=True)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role="partner", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    partner = Partner(
        user_id=user.id,
        name=email,
        category="realtor",
        type="Realtor",
        subscription_tier="Premium",
    )
    db_session.add(partner)

    profile = VIPProfile(
        user_id=user.id,
        display_name=email,
        role_type="realtor",
        public_slug=slug,
        marketplace_enabled="yes",
        markets_json='["Nashville"]',
    )
    db_session.add(profile)
    db_session.commit()
    return user, profile


def _make_listing(db_session, vip_profile_id, address="123 Demo St", market="Nashville", status="active"):
    listing = ElenaListing(
        address=address,
        city="Nashville",
        state="TN",
        zip_code="37201",
        market=market,
        status=status,
        vip_profile_id=vip_profile_id,
    )
    db_session.add(listing)
    db_session.commit()
    return listing


def _make_flyer(db_session, listing_id, flyer_type="listing"):
    flyer = ElenaFlyer(flyer_type=flyer_type, property_address="123 Demo St", listing_id=listing_id, body="body")
    db_session.add(flyer)
    db_session.commit()
    return flyer


def test_dashboard_loads_without_error_for_a_realtor_with_no_listings(db_session, client):
    user_a, _ = _make_realtor(db_session, "realtora@example.com", "realtor-a")

    login_as(client, user_a)
    resp = client.get("/vip/realtor")

    assert resp.status_code == 200


def test_realtor_listings_page_excludes_other_realtors_listings(db_session, client):
    user_a, profile_a = _make_realtor(db_session, "realtora2@example.com", "realtor-a2")
    user_b, profile_b = _make_realtor(db_session, "realtorb2@example.com", "realtor-b2")
    _make_listing(db_session, profile_a.id, address="111 Owned By A")
    _make_listing(db_session, profile_b.id, address="222 Owned By B")

    login_as(client, user_a)
    resp = client.get("/vip/realtor/listings")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "111 Owned By A" in body
    assert "222 Owned By B" not in body


def test_recent_flyers_excludes_other_realtors_flyers(db_session, client):
    user_a, profile_a = _make_realtor(db_session, "realtora3@example.com", "realtor-a3")
    _, profile_b = _make_realtor(db_session, "realtorb3@example.com", "realtor-b3")
    listing_b = _make_listing(db_session, profile_b.id, address="333 B Listing")
    _make_flyer(db_session, listing_b.id)

    login_as(client, user_a)
    resp = client.get("/vip/realtor")

    assert resp.status_code == 200
    assert "333 B Listing" not in resp.get_data(as_text=True)


def test_public_landing_page_excludes_other_realtors_listings(db_session, client):
    _, profile_a = _make_realtor(db_session, "realtora4@example.com", "realtor-a4")
    _, profile_b = _make_realtor(db_session, "realtorb4@example.com", "realtor-b4")
    _make_listing(db_session, profile_a.id, address="444 A Public Listing")
    _make_listing(db_session, profile_b.id, address="555 B Public Listing")

    resp = client.get("/p/realtor-a4")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "444 A Public Listing" in body
    assert "555 B Public Listing" not in body


def test_new_listing_created_via_form_gets_owner_set(db_session, client, app):
    user_a, profile_a = _make_realtor(db_session, "realtora5@example.com", "realtor-a5")
    login_as(client, user_a)
    app.config["WTF_CSRF_ENABLED"] = False

    resp = client.post(
        "/elena/listings/new",
        data={
            "address": "666 New Listing Way",
            "city": "Nashville",
            "state": "TN",
            "zip_code": "37201",
        },
        follow_redirects=False,
    )

    assert resp.status_code == 302
    listing = ElenaListing.query.filter_by(address="666 New Listing Way").first()
    assert listing is not None
    assert listing.vip_profile_id == profile_a.id


def test_cannot_delete_another_realtors_listing(db_session, client, app):
    user_a, profile_a = _make_realtor(db_session, "realtora6@example.com", "realtor-a6")
    _, profile_b = _make_realtor(db_session, "realtorb6@example.com", "realtor-b6")
    listing_b = _make_listing(db_session, profile_b.id, address="777 B Not Deletable")

    login_as(client, user_a)
    app.config["WTF_CSRF_ENABLED"] = False

    resp = client.post(f"/vip/realtor/listings/{listing_b.id}/delete", follow_redirects=False)

    assert resp.status_code == 302
    assert db.session.get(ElenaListing, listing_b.id) is not None


def test_cannot_change_status_of_another_realtors_listing(db_session, client, app):
    user_a, profile_a = _make_realtor(db_session, "realtora7@example.com", "realtor-a7")
    _, profile_b = _make_realtor(db_session, "realtorb7@example.com", "realtor-b7")
    listing_b = _make_listing(db_session, profile_b.id, address="888 B Status Locked", status="active")

    login_as(client, user_a)
    app.config["WTF_CSRF_ENABLED"] = False

    client.post(f"/vip/realtor/listings/{listing_b.id}/status", data={"status": "sold"})

    refreshed = db.session.get(ElenaListing, listing_b.id)
    assert refreshed.status == "active"


def test_cannot_view_another_realtors_listing_detail(db_session, client):
    user_a, profile_a = _make_realtor(db_session, "realtora8@example.com", "realtor-a8")
    _, profile_b = _make_realtor(db_session, "realtorb8@example.com", "realtor-b8")
    listing_b = _make_listing(db_session, profile_b.id, address="999 B Private")

    login_as(client, user_a)
    resp = client.get(f"/vip/realtor/listings/{listing_b.id}", follow_redirects=True)

    assert resp.status_code == 200
    assert "999 B Private" not in resp.get_data(as_text=True)
