"""Ravlo Network's feed/post-detail routes were already publicly
viewable (no @login_required on the GET routes) -- the actual gap was
discoverability: the only link to it lived inside the logged-in VIP
sidebar, invisible to the site's real (mostly logged-out) traffic. These
tests cover the fix: a public nav link on the shared marketing layout,
and that the feed genuinely renders without a session.
"""
from LoanMVP.models.network_models import NetworkPost
from LoanMVP.services.network_service import get_or_create_group


def test_marketing_homepage_links_to_network(client):
    resp = client.get("/")
    resp = client.get(resp.headers["Location"]) if resp.status_code in (301, 302) else resp

    assert resp.status_code == 200
    assert '/network/real-estate' in resp.get_data(as_text=True)


def test_anonymous_visitor_can_read_the_feed_without_a_session(db_session, client):
    from LoanMVP.models.admin import Company
    from LoanMVP.models.user_model import User

    company = Company(name="Anon Test Co", is_active=True)
    db_session.add(company)
    db_session.commit()
    author = User(email="publicpost@example.com", role="partner", is_active=True, company_id=company.id)
    db_session.add(author)
    db_session.commit()

    group = get_or_create_group("real-estate", name="Real Estate")
    post = NetworkPost(group_id=group.id, author_user_id=author.id, body="Anyone need a Tampa inspector?")
    db_session.add(post)
    db_session.commit()

    resp = client.get("/network/real-estate")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Anyone need a Tampa inspector?" in body
    # Logged-out visitor sees a login prompt instead of the post composer.
    assert "to post or comment" in body
    assert 'name="body"' not in body
