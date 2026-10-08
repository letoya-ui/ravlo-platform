"""Regression tests for making ElenaListing public landing pages
(/p/listing/<token>) actually discoverable on Google, not just reachable
by someone who already has the exact URL.

Three real gaps fixed here:
1. listing_landing.html was hardcoded to <meta name="robots"
   content="noindex, follow"> -- explicitly telling every search engine
   not to index these pages at all, with no per-listing title/description/
   structured data either.
2. ElenaListing.public_token is nullable and was only ever generated
   lazily in vip.py's realtor_listing_detail() (an authenticated route) --
   a listing a realtor had never clicked into from their own dashboard had
   no public URL, so the realtor's own public landing page couldn't even
   link to it.
3. Nothing crawlable referenced these pages: the realtor landing page's
   listing cards weren't links, the per-realtor sitemap didn't include
   them, and no sitemap index pointed Google at the (potentially many)
   per-realtor sitemaps in the first place.
"""
from LoanMVP.extensions import db
from LoanMVP.models.admin import Company
from LoanMVP.models.crm_models import Partner
from LoanMVP.models.elena_models import ElenaListing
from LoanMVP.models.user_model import User
from LoanMVP.models.vip_models import VIPProfile


def _make_realtor(db_session, email, slug):
    company = Company(name=f"Co {email}", is_active=True)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role="partner", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    db_session.add(Partner(
        user_id=user.id, name=email, category="realtor", type="Realtor", subscription_tier="Premium",
    ))

    profile = VIPProfile(
        user_id=user.id, display_name="Jordan Realtor", role_type="realtor",
        public_slug=slug, marketplace_enabled="yes", markets_json='["Nashville"]',
    )
    db_session.add(profile)
    db_session.commit()
    return user, profile


def _make_listing(db_session, vip_profile_id, address="123 Demo St", beds=3, baths=2,
                   sqft=1800, price=450000, status="active", public_token=None):
    listing = ElenaListing(
        address=address, city="Nashville", state="TN", zip_code="37201",
        beds=beds, baths=baths, sqft=sqft, price=price,
        market="Nashville", status=status, vip_profile_id=vip_profile_id,
        public_token=public_token,
    )
    db_session.add(listing)
    db_session.commit()
    return listing


def test_listing_landing_page_is_indexable_not_blocked(db_session, client):
    user, profile = _make_realtor(db_session, "seo1@example.com", "seo-realtor-1")
    listing = _make_listing(db_session, profile.id, public_token="tok-indexable-1")

    resp = client.get("/p/listing/tok-indexable-1")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'content="index, follow"' in body
    assert "noindex" not in body


def test_listing_landing_page_has_real_meta_description_and_title(db_session, client):
    user, profile = _make_realtor(db_session, "seo2@example.com", "seo-realtor-2")
    _make_listing(
        db_session, profile.id, address="456 Oak Ave", beds=3, baths=2, price=450000,
        public_token="tok-meta-1",
    )

    body = client.get("/p/listing/tok-meta-1").get_data(as_text=True)

    assert "456 Oak Ave" in body
    assert "3 bed" in body
    assert "2 bath" in body
    assert "$450,000" in body
    assert 'name="description"' in body


def test_listing_landing_page_has_json_ld_with_price(db_session, client):
    user, profile = _make_realtor(db_session, "seo3@example.com", "seo-realtor-3")
    _make_listing(db_session, profile.id, price=399000, public_token="tok-jsonld-1")

    body = client.get("/p/listing/tok-jsonld-1").get_data(as_text=True)

    assert '"@type": "Product"' in body
    assert '"price": "399000"' in body
    assert '"@type": "Offer"' in body


def test_realtor_page_generates_public_token_for_listing_missing_one(db_session, client):
    user, profile = _make_realtor(db_session, "seo4@example.com", "seo-realtor-4")
    listing = _make_listing(db_session, profile.id, public_token=None)
    assert listing.public_token is None

    resp = client.get("/p/seo-realtor-4")
    assert resp.status_code == 200

    db_session.refresh(listing)
    assert listing.public_token is not None


def test_realtor_landing_page_links_to_listing_detail_page(db_session, client):
    user, profile = _make_realtor(db_session, "seo5@example.com", "seo-realtor-5")
    _make_listing(db_session, profile.id, address="789 Elm St", public_token="tok-link-1")

    body = client.get("/p/seo-realtor-5").get_data(as_text=True)

    assert "/p/listing/tok-link-1" in body


def test_realtor_sitemap_includes_listing_pages(db_session, client):
    user, profile = _make_realtor(db_session, "seo6@example.com", "seo-realtor-6")
    _make_listing(db_session, profile.id, public_token="tok-sitemap-1")

    resp = client.get("/p/seo-realtor-6/sitemap.xml")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "/p/listing/tok-sitemap-1" in body


def test_realtor_sitemap_generates_tokens_for_untouched_listings(db_session, client):
    user, profile = _make_realtor(db_session, "seo7@example.com", "seo-realtor-7")
    listing = _make_listing(db_session, profile.id, public_token=None)

    resp = client.get("/p/seo-realtor-7/sitemap.xml")

    assert resp.status_code == 200
    db_session.refresh(listing)
    assert listing.public_token is not None
    assert f"/p/listing/{listing.public_token}" in resp.get_data(as_text=True)


def test_sitemap_index_lists_marketplace_enabled_realtor_sitemaps(db_session, client):
    user, profile = _make_realtor(db_session, "seo8@example.com", "seo-realtor-8")

    resp = client.get("/p/sitemap_index.xml")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "<sitemapindex" in body
    assert "/p/seo-realtor-8/sitemap.xml" in body


def test_robots_txt_references_the_listing_sitemap_index(client):
    body = client.get("/robots.txt").get_data(as_text=True)
    assert "/p/sitemap_index.xml" in body
