"""Regression tests for the "connecting Canva logs me out" bug.

/canva/connect -> canva.com -> /canva/callback is a cross-site
top-level navigation. The callback used to be @login_required and
compared the returned `state` against a copy stashed in the Flask
session (canva_oauth_state/canva_code_verifier/canva_next) -- if the
session cookie didn't survive that round trip (browser/proxy/webview
dependent, not something we control), @login_required bounced the user
straight to the login page mid-connection, which read as "Ravlo logged
me out."

The fix: everything the callback needs (who started this, the PKCE
verifier, where to return them) is now encoded in a signed `state`
param instead of the session, and the callback recovers the user from
that signed state -- re-establishing login via login_user() if the
session did drop, instead of redirecting to /auth/login.
"""
from unittest.mock import patch

from LoanMVP.models.admin import Company
from LoanMVP.models.canva_models import CanvaConnection
from LoanMVP.models.user_model import User
from LoanMVP.services.canva_service import build_canva_auth_url, decode_oauth_state

from tests.conftest import login_as


def _make_user(db_session, email, role="loan_officer", is_active=True, is_blocked=False):
    company = Company(name=f"{email} Co", is_active=True)
    db_session.add(company)
    db_session.commit()
    user = User(
        email=email, role=role, is_active=is_active, is_blocked=is_blocked,
        company_id=company.id, first_name="Sam",
    )
    db_session.add(user)
    db_session.commit()
    return user


def _fake_token_response():
    return {
        "access_token": "fake-access-token",
        "refresh_token": "fake-refresh-token",
        "scope": "app:read asset:read asset:write design:content:read design:content:write design:meta:read",
        "expires_in": 3600,
    }


# ─── canva_service: signed state round-trips correctly ─────────────────────

def test_build_canva_auth_url_state_decodes_back_to_the_same_user(app):
    with app.test_request_context(), \
         patch.dict("os.environ", {"CANVA_CLIENT_ID": "abc", "CANVA_REDIRECT_URI": "https://ravlohq.com/canva/callback"}):
        auth_url = build_canva_auth_url(42, next_url="/vip/realtor/dashboard")

    from urllib.parse import parse_qs, urlparse
    state = parse_qs(urlparse(auth_url).query)["state"][0]

    with app.test_request_context():
        decoded = decode_oauth_state(state)

    assert decoded["uid"] == 42
    assert decoded["next"] == "/vip/realtor/dashboard"
    assert decoded["verifier"]


def test_decode_oauth_state_rejects_tampered_state(app):
    with app.test_request_context():
        assert decode_oauth_state("not-a-real-signed-state") is None
        assert decode_oauth_state(None) is None
        assert decode_oauth_state("") is None


# ─── /canva/callback: the actual regression ─────────────────────────────────

def test_callback_completes_even_when_the_session_did_not_survive_the_round_trip(db_session, client, app):
    """The core bug: hit /canva/callback with a valid signed state but an
    ANONYMOUS client (simulating the session cookie not surviving the trip
    to canva.com and back). It must NOT bounce to the login page, and the
    Canva connection must still be created for the right user."""
    user = _make_user(db_session, "realtor-zip@example.com", role="realtor")

    with app.test_request_context():
        auth_url = build_canva_auth_url(user.id, next_url="/vip/realtor/dashboard")
    from urllib.parse import parse_qs, urlparse
    state = parse_qs(urlparse(auth_url).query)["state"][0]

    # No login_as() call here -- this client is anonymous, exactly like a
    # session that got dropped on the way back from canva.com.
    with patch("LoanMVP.routes.canva.exchange_code_for_tokens", return_value={
        "access_token": "fake-access-token",
        "refresh_token": "fake-refresh-token",
        "scope": _fake_token_response()["scope"],
        "expires_at": None,
    }):
        resp = client.get(f"/canva/callback?code=abc123&state={state}", follow_redirects=False)

    assert resp.status_code == 302
    assert "/auth/login" not in resp.headers["Location"]
    assert resp.headers["Location"] == "/vip/realtor/dashboard"

    connection = CanvaConnection.query.filter_by(user_id=user.id).first()
    assert connection is not None
    assert connection.access_token == "fake-access-token"


def test_callback_re_establishes_login_when_session_was_dropped(db_session, client, app):
    user = _make_user(db_session, "reestablish@example.com")

    with app.test_request_context():
        auth_url = build_canva_auth_url(user.id, next_url="/dashboard")
    from urllib.parse import parse_qs, urlparse
    state = parse_qs(urlparse(auth_url).query)["state"][0]

    with patch("LoanMVP.routes.canva.exchange_code_for_tokens", return_value={
        "access_token": "tok", "refresh_token": "ref", "scope": "app:read", "expires_at": None,
    }):
        client.get(f"/canva/callback?code=abc123&state={state}", follow_redirects=False)

    with client.session_transaction() as sess:
        assert sess.get("_user_id") == str(user.id)


def test_callback_with_missing_state_redirects_to_login_not_a_500(client):
    resp = client.get("/canva/callback?code=abc123", follow_redirects=False)

    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_callback_with_tampered_state_redirects_to_login(client):
    resp = client.get("/canva/callback?code=abc123&state=garbage", follow_redirects=False)

    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_callback_refuses_a_blocked_user_even_with_a_valid_state(db_session, client, app):
    user = _make_user(db_session, "blocked@example.com", is_blocked=True)

    with app.test_request_context():
        auth_url = build_canva_auth_url(user.id, next_url="/dashboard")
    from urllib.parse import parse_qs, urlparse
    state = parse_qs(urlparse(auth_url).query)["state"][0]

    resp = client.get(f"/canva/callback?code=abc123&state={state}", follow_redirects=False)

    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]
    assert CanvaConnection.query.filter_by(user_id=user.id).first() is None


def test_callback_with_canva_error_still_recovers_identity_and_routes_home(db_session, client, app):
    # Even if the user declined consent on Canva's side, we should still
    # recognize who they are (from the signed state) and send them to
    # their own dashboard, not to the login page.
    user = _make_user(db_session, "declined@example.com", role="investor")

    with app.test_request_context():
        auth_url = build_canva_auth_url(user.id, next_url="/investor/dashboard")
    from urllib.parse import parse_qs, urlparse
    state = parse_qs(urlparse(auth_url).query)["state"][0]

    resp = client.get(f"/canva/callback?error=access_denied&state={state}", follow_redirects=False)

    assert resp.status_code == 302
    assert "/auth/login" not in resp.headers["Location"]


# ─── /canva/connect: still requires an existing login (unaffected) ─────────

def test_connect_requires_login(client):
    resp = client.get("/canva/connect", follow_redirects=False)
    assert resp.status_code in (302, 401)


def test_connect_redirects_to_canva_with_a_signed_state(db_session, client):
    user = _make_user(db_session, "connector@example.com")
    login_as(client, user)

    with patch.dict("os.environ", {"CANVA_CLIENT_ID": "abc", "CANVA_REDIRECT_URI": "https://ravlohq.com/canva/callback"}):
        resp = client.get("/canva/connect?next=/vip/realtor/dashboard", follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("https://www.canva.com/api/oauth/authorize")
    assert "state=" in resp.headers["Location"]
