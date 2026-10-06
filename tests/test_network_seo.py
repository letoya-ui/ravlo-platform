"""SEO fixes for the Network marketplace's public listing pages
(LoanMVP/routes/network_routes.py, templates/network/post_detail.html):

- post_detail() used to set page_title to the exact same string as the
  group feed page ("{group.name} Network | Ravlo") for every single post
  -- Google can't distinguish one listing from another, or match a
  listing to a relevant search, if every URL under a group shares one
  title and meta description.
- Listing pages (listing_type in product/service) had no structured
  data at all, so even a well-titled listing was just plain text to
  Google, not a flagged product/offer.
- Nothing told Google these pages exist -- no sitemap referenced them.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.network_models import NetworkPost
from LoanMVP.models.user_model import User
from LoanMVP.services.network_service import get_or_create_group

from tests.conftest import login_as


def _make_user(db_session, email):
    company = Company(name="SEO Test Co", is_active=True)
    db_session.add(company)
    db_session.commit()
    user = User(email=email, role="partner", is_active=True, company_id=company.id, first_name="Sam", last_name="Seller")
    db_session.add(user)
    db_session.commit()
    return user


def test_listing_post_title_differs_from_the_generic_feed_title(db_session, client):
    user = _make_user(db_session, "seller1@example.com")
    group = get_or_create_group("real-estate", name="Real Estate", description="")
    post = NetworkPost(
        group_id=group.id, author_user_id=user.id,
        body="Turnkey duplex, both units rented.",
        listing_type="product", title="3BR Duplex Opportunity",
        category="agents", price_label="$320,000",
    )
    db_session.add(post)
    db_session.commit()

    feed_title = client.get("/network/real-estate").get_data(as_text=True)
    assert "<title>Real Estate Network | Ravlo</title>" in feed_title

    resp = client.get(f"/network/real-estate/posts/{post.id}")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "<title>Real Estate Network | Ravlo</title>" not in body
    assert "3BR Duplex Opportunity" in body
    assert "$320,000" in body


def test_product_listing_includes_json_ld_with_price(db_session, client):
    user = _make_user(db_session, "seller2@example.com")
    group = get_or_create_group("real-estate", name="Real Estate", description="")
    post = NetworkPost(
        group_id=group.id, author_user_id=user.id,
        body="Move-in ready.", listing_type="product",
        title="3BR Duplex Opportunity", price_label="$320,000",
    )
    db_session.add(post)
    db_session.commit()

    body = client.get(f"/network/real-estate/posts/{post.id}").get_data(as_text=True)

    assert 'application/ld+json' in body
    assert '"@type": "Product"' in body
    assert '"name": "3BR Duplex Opportunity"' in body
    assert '"price": "320000"' in body


def test_plain_update_post_has_no_product_json_ld(db_session, client):
    user = _make_user(db_session, "poster3@example.com")
    group = get_or_create_group("real-estate", name="Real Estate", description="")
    post = NetworkPost(group_id=group.id, author_user_id=user.id, body="Just closed on a new deal!")
    db_session.add(post)
    db_session.commit()

    body = client.get(f"/network/real-estate/posts/{post.id}").get_data(as_text=True)
    assert 'application/ld+json' not in body


def test_network_sitemap_lists_the_feed_and_every_post(db_session, client):
    user = _make_user(db_session, "seller4@example.com")
    group = get_or_create_group("real-estate", name="Real Estate", description="")
    post = NetworkPost(group_id=group.id, author_user_id=user.id, body="Need a contractor quote.")
    db_session.add(post)
    db_session.commit()

    resp = client.get("/network/sitemap.xml")
    assert resp.status_code == 200
    assert resp.mimetype == "application/xml"

    body = resp.get_data(as_text=True)
    assert "/network/real-estate</loc>" in body
    assert f"/network/real-estate/posts/{post.id}</loc>" in body


def test_robots_txt_references_the_network_sitemap(client):
    body = client.get("/robots.txt").get_data(as_text=True)
    # /network/ isn't in the Disallow list, so it's crawlable by default --
    # this just confirms Google is pointed at the new sitemap to discover it.
    assert "Disallow: /network" not in body
    assert "/network/sitemap.xml" in body
