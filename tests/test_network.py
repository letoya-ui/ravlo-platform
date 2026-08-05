"""Regression tests for Ravlo Network v1: one seeded "real-estate"
group, text posts, text comments. Deliberately exercises the
professional-label resolver across VIPProfile (several role_types) and
StylistProfile, the same two-model-tree split Payments had to handle, to
make sure post/comment bylines correctly label who's actually posting.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.network_models import NetworkComment, NetworkGroup, NetworkPost
from LoanMVP.models.salon_models import StylistProfile
from LoanMVP.models.user_model import User
from LoanMVP.models.vip_models import VIPProfile
from LoanMVP.services.network_service import get_or_create_group, resolve_professional_label

from tests.conftest import login_as


def _make_company(db_session, name):
    company = Company(name=name, is_active=True)
    db_session.add(company)
    db_session.commit()
    return company


def _make_user(db_session, email, role="partner", first_name="Test", last_name="User"):
    company = _make_company(db_session, f"{email} Co")
    user = User(email=email, role=role, is_active=True, company_id=company.id,
                first_name=first_name, last_name=last_name)
    db_session.add(user)
    db_session.commit()
    return user


def _make_vip_profile(db_session, user, role_type, business_name="Test Biz"):
    profile = VIPProfile(user_id=user.id, display_name=business_name, business_name=business_name, role_type=role_type)
    db_session.add(profile)
    db_session.commit()
    return profile


def _make_stylist_profile(db_session, user):
    profile = StylistProfile(user_id=user.id, company_id=user.company_id, full_name=user.full_name)
    db_session.add(profile)
    db_session.commit()
    return profile


# ─── Group seeding ──────────────────────────────────────────────────────────

def test_get_or_create_group_reuses_existing_row(db_session):
    group1 = get_or_create_group("real-estate", name="Real Estate")
    group2 = get_or_create_group("real-estate", name="Real Estate")

    assert group1.id == group2.id
    assert NetworkGroup.query.filter_by(slug="real-estate").count() == 1


def test_feed_seeds_the_real_estate_group_on_first_visit(client):
    resp = client.get("/network/real-estate")

    assert resp.status_code == 200
    assert NetworkGroup.query.filter_by(slug="real-estate").first() is not None


def test_unknown_group_slug_404s(client):
    resp = client.get("/network/not-a-real-group")
    assert resp.status_code == 404


# ─── Professional label resolution ─────────────────────────────────────────

def test_resolve_professional_label_for_realtor(db_session):
    user = _make_user(db_session, "realtor@example.com")
    _make_vip_profile(db_session, user, "realtor")

    assert resolve_professional_label(user) == "Realtor"


def test_resolve_professional_label_for_insurance_realtor(db_session):
    user = _make_user(db_session, "hybrid@example.com")
    _make_vip_profile(db_session, user, "insurance_realtor")

    assert resolve_professional_label(user) == "Insurance Agent & Realtor"


def test_resolve_professional_label_for_stylist(db_session):
    user = _make_user(db_session, "stylist@example.com", role="stylist")
    _make_stylist_profile(db_session, user)

    assert resolve_professional_label(user) == "Stylist"


def test_resolve_professional_label_defaults_to_member(db_session):
    user = _make_user(db_session, "noprofile@example.com")

    assert resolve_professional_label(user) == "Member"


def test_resolve_professional_label_does_not_create_a_vip_profile(db_session):
    user = _make_user(db_session, "readonly@example.com")

    resolve_professional_label(user)

    assert VIPProfile.query.filter_by(user_id=user.id).first() is None


# ─── Posting ────────────────────────────────────────────────────────────────

def test_create_post_requires_login(client):
    resp = client.post("/network/real-estate/posts", data={"body": "hello"}, follow_redirects=False)
    assert resp.status_code in (302, 401)
    assert NetworkPost.query.count() == 0


def test_create_post_succeeds_when_logged_in(db_session, client):
    user = _make_user(db_session, "poster@example.com", first_name="Pat", last_name="Poster")
    _make_vip_profile(db_session, user, "contractor")
    login_as(client, user)

    resp = client.post(
        "/network/real-estate/posts",
        data={"body": "Before & after kitchen remodel -- Tampa duplex."},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    post = NetworkPost.query.filter_by(author_user_id=user.id).first()
    assert post is not None
    assert "kitchen remodel" in post.body

    body = resp.get_data(as_text=True)
    assert "Pat Poster" in body
    assert "Contractor" in body


def test_create_post_rejects_empty_body(db_session, client):
    user = _make_user(db_session, "emptyposter@example.com")
    login_as(client, user)

    resp = client.post("/network/real-estate/posts", data={"body": "   "}, follow_redirects=True)

    assert resp.status_code == 200
    assert NetworkPost.query.count() == 0


def test_feed_shows_comment_count(db_session, client):
    author = _make_user(db_session, "author2@example.com")
    group = get_or_create_group("real-estate", name="Real Estate")
    post = NetworkPost(group_id=group.id, author_user_id=author.id, body="Looking for a contractor in Tampa.")
    db_session.add(post)
    db_session.commit()

    commenter = _make_user(db_session, "commenter@example.com")
    comment = NetworkComment(post_id=post.id, author_user_id=commenter.id, body="I can help.")
    db_session.add(comment)
    db_session.commit()

    resp = client.get("/network/real-estate")

    assert resp.status_code == 200
    assert "1 comment" in resp.get_data(as_text=True)


# ─── Commenting ─────────────────────────────────────────────────────────────

def test_create_comment_requires_login(db_session, client):
    author = _make_user(db_session, "author3@example.com")
    group = get_or_create_group("real-estate", name="Real Estate")
    post = NetworkPost(group_id=group.id, author_user_id=author.id, body="Need a lender recommendation.")
    db_session.add(post)
    db_session.commit()

    resp = client.post(
        f"/network/real-estate/posts/{post.id}/comments", data={"body": "Try Jane at ABC Lending."},
        follow_redirects=False,
    )

    assert resp.status_code in (302, 401)
    assert NetworkComment.query.count() == 0


def test_create_comment_succeeds_when_logged_in(db_session, client):
    author = _make_user(db_session, "author4@example.com")
    group = get_or_create_group("real-estate", name="Real Estate")
    post = NetworkPost(group_id=group.id, author_user_id=author.id, body="Duplex needs a property manager.")
    db_session.add(post)
    db_session.commit()

    commenter = _make_user(db_session, "commenter2@example.com", first_name="Cam", last_name="Commenter")
    _make_vip_profile(db_session, commenter, "property_manager")
    login_as(client, commenter)

    resp = client.post(
        f"/network/real-estate/posts/{post.id}/comments",
        data={"body": "I'd love to manage that property."},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    comment = NetworkComment.query.filter_by(post_id=post.id).first()
    assert comment is not None
    assert comment.author_user_id == commenter.id

    body = resp.get_data(as_text=True)
    assert "Cam Commenter" in body
    assert "Property Manager" in body


def test_post_detail_404s_for_post_in_a_different_group(db_session, client):
    other_group = get_or_create_group("beauty", name="Beauty")
    author = _make_user(db_session, "author5@example.com")
    post = NetworkPost(group_id=other_group.id, author_user_id=author.id, body="Wrong group post.")
    db_session.add(post)
    db_session.commit()

    resp = client.get(f"/network/real-estate/posts/{post.id}")
    assert resp.status_code == 404
