"""Regression tests for the personal referral-link program.

Every Ravlo user can get a personal referral link (/r/<code>) from
account.profile. Visiting it stashes the code in the session; when the
visitor signs up through auth.register or auth.register_borrower, a
Referral row attributes the new account to the referrer. Also covers the
mobile_api.partner_referrals() IDOR fix -- before Referral existed, that
route always returned an empty payload (an ImportError no-op); once a
real Referral model exists, the old "fall back to Referral.query.all()"
branch would have leaked every user's referrals to any authenticated
caller, so it must be scoped to the current user only.
"""
from unittest.mock import patch

from LoanMVP.extensions import db
from LoanMVP.models.admin import Company
from LoanMVP.models.referral_models import Referral
from LoanMVP.models.user_model import User
from LoanMVP.services.referral_service import (
    get_or_create_referral_code,
    record_referral_signup,
)

from tests.conftest import login_as


def _make_user(db_session, email="referrer@example.com", role="investor"):
    company = Company(name="Referral Co", is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role=role, is_active=True, company_id=company.id)
    user.set_password("password123")
    db_session.add(user)
    db_session.commit()
    return user


# ---------------------------------------------------------------------------
# get_or_create_referral_code
# ---------------------------------------------------------------------------

def test_get_or_create_referral_code_generates_and_persists(db_session):
    user = _make_user(db_session)
    assert user.referral_code is None

    code = get_or_create_referral_code(user)
    assert code
    assert user.referral_code == code

    # Idempotent: calling again returns the same code, no new one generated.
    assert get_or_create_referral_code(user) == code


def test_referral_codes_are_unique_across_users(db_session):
    user_a = _make_user(db_session, email="a@example.com")
    user_b = _make_user(db_session, email="b@example.com")

    code_a = get_or_create_referral_code(user_a)
    code_b = get_or_create_referral_code(user_b)
    assert code_a != code_b


# ---------------------------------------------------------------------------
# record_referral_signup
# ---------------------------------------------------------------------------

def test_record_referral_signup_creates_referral(db_session):
    referrer = _make_user(db_session, email="referrer2@example.com")
    code = get_or_create_referral_code(referrer)
    new_user = _make_user(db_session, email="friend@example.com")

    referral = record_referral_signup(new_user, code)

    assert referral is not None
    assert referral.referrer_user_id == referrer.id
    assert referral.referred_user_id == new_user.id
    assert referral.referred_email == "friend@example.com"
    assert referral.status == "signed_up"


def test_record_referral_signup_invalid_code_is_noop(db_session):
    new_user = _make_user(db_session, email="friend2@example.com")
    assert record_referral_signup(new_user, "NOTAREALCODE") is None
    assert Referral.query.count() == 0


def test_record_referral_signup_self_referral_is_noop(db_session):
    user = _make_user(db_session, email="solo@example.com")
    code = get_or_create_referral_code(user)
    assert record_referral_signup(user, code) is None
    assert Referral.query.count() == 0


def test_record_referral_signup_does_not_double_count(db_session):
    referrer = _make_user(db_session, email="referrer3@example.com")
    code = get_or_create_referral_code(referrer)
    new_user = _make_user(db_session, email="friend3@example.com")

    first = record_referral_signup(new_user, code)
    second = record_referral_signup(new_user, code)

    assert first.id == second.id
    assert Referral.query.filter_by(referred_user_id=new_user.id).count() == 1


# ---------------------------------------------------------------------------
# /r/<code> landing route
# ---------------------------------------------------------------------------

def test_referral_landing_personalizes_page_and_sets_session(db_session, client):
    referrer = _make_user(db_session, email="jane@example.com")
    referrer.first_name = "Jane"
    db_session.commit()
    code = get_or_create_referral_code(referrer)

    resp = client.get(f"/r/{code}")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Jane invited you to Ravlo" in body

    with client.session_transaction() as sess:
        assert sess["referral_code"] == code


def test_referral_landing_invalid_code_redirects_to_generic_page(client):
    resp = client.get("/r/DOESNOTEXIST")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/refer")


# ---------------------------------------------------------------------------
# Registration attribution
# ---------------------------------------------------------------------------

def test_register_attributes_referral_signup(db_session, client, app):
    referrer = _make_user(db_session, email="referrer4@example.com")
    code = get_or_create_referral_code(referrer)

    client.get(f"/r/{code}")

    app.config["WTF_CSRF_ENABLED"] = False
    resp = client.post("/auth/register", data={
        "full_name": "New Friend",
        "email": "newfriend@example.com",
        "password": "password123",
        "confirm_password": "password123",
        "role": "investor",
    }, follow_redirects=False)

    assert resp.status_code in (302, 200)
    new_user = User.query.filter_by(email="newfriend@example.com").first()
    assert new_user is not None

    referral = Referral.query.filter_by(referred_user_id=new_user.id).first()
    assert referral is not None
    assert referral.referrer_user_id == referrer.id


def test_register_borrower_attributes_referral_signup(db_session, client, app):
    referrer = _make_user(db_session, email="referrer5@example.com")
    code = get_or_create_referral_code(referrer)

    client.get(f"/r/{code}")

    app.config["WTF_CSRF_ENABLED"] = False
    resp = client.post("/auth/register_borrower", data={
        "full_name": "New Borrower Friend",
        "email": "borrowerfriend@example.com",
        "password": "password123",
        "confirm_password": "password123",
    }, follow_redirects=False)

    assert resp.status_code in (302, 200)
    new_user = User.query.filter_by(email="borrowerfriend@example.com").first()
    assert new_user is not None

    referral = Referral.query.filter_by(referred_user_id=new_user.id).first()
    assert referral is not None
    assert referral.referrer_user_id == referrer.id


def test_register_without_referral_code_creates_no_referral(db_session, client, app):
    # auth.register() treats an empty user table as "workspace recovery
    # mode" and forces role=admin/owner-email-only -- seed an unrelated
    # existing user first so this organic signup isn't caught by that.
    _make_user(db_session, email="existing-user@example.com")

    app.config["WTF_CSRF_ENABLED"] = False
    resp = client.post("/auth/register", data={
        "full_name": "Organic Signup",
        "email": "organic@example.com",
        "password": "password123",
        "confirm_password": "password123",
        "role": "investor",
    }, follow_redirects=False)

    assert resp.status_code in (302, 200)
    new_user = User.query.filter_by(email="organic@example.com").first()
    assert new_user is not None
    assert Referral.query.filter_by(referred_user_id=new_user.id).count() == 0


# ---------------------------------------------------------------------------
# account.profile shows the referral link
# ---------------------------------------------------------------------------

def test_account_profile_shows_referral_link(db_session, client):
    user = _make_user(db_session, email="profileuser@example.com")
    login_as(client, user)

    resp = client.get("/account/profile")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "/r/" in body
    assert user.referral_code is not None


# ---------------------------------------------------------------------------
# mobile_api.partner_referrals() IDOR regression
# ---------------------------------------------------------------------------

def test_partner_referrals_scoped_to_current_user_only(db_session, client):
    from LoanMVP.routes.mobile_api import _encode_token

    user_a = _make_user(db_session, email="partnera@example.com", role="partner")
    user_b = _make_user(db_session, email="partnerb@example.com", role="partner")

    friend_of_a = _make_user(db_session, email="friendofa@example.com")
    friend_of_b = _make_user(db_session, email="friendofb@example.com")

    db.session.add(Referral(
        referrer_user_id=user_a.id,
        referred_user_id=friend_of_a.id,
        referral_code=get_or_create_referral_code(user_a),
        referred_email=friend_of_a.email,
        status="signed_up",
    ))
    db.session.add(Referral(
        referrer_user_id=user_b.id,
        referred_user_id=friend_of_b.id,
        referral_code=get_or_create_referral_code(user_b),
        referred_email=friend_of_b.email,
        status="signed_up",
    ))
    db.session.commit()

    token_a = _encode_token(user_a.id)
    resp = client.get(
        "/mobile/partner/referrals",
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 1
    assert data["referrals"][0]["email"] == friend_of_a.email
