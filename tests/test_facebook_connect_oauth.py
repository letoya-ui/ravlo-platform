"""Regression tests for the "Connect with Facebook" OAuth flow that
replaces manually pasting a Page ID + Page Access Token.

/integrations/facebook/connect/<company_id> -> facebook.com ->
/integrations/facebook/callback is a cross-site top-level navigation,
same shape as the Canva OAuth bug (see test_canva_oauth.py) -- the
callback recovers both the company_id and the initiating admin's user_id
from a signed `state` param instead of the session, and re-establishes
login via login_user() if the session did drop.
"""
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from LoanMVP.models.admin import Company
from LoanMVP.models.crm_models import FacebookPageConnection
from LoanMVP.models.user_model import User
from LoanMVP.services.facebook_oauth_service import OAUTH_SCOPES, build_oauth_url, decode_oauth_state

from tests.conftest import login_as


def _make_company_admin(db_session, email="admin@leadco.com", company_name="Lead Co"):
    company = Company(name=company_name, is_active=True)
    db_session.add(company)
    db_session.commit()
    user = User(email=email, role="admin", is_active=True, company_id=company.id, first_name="Ada")
    db_session.add(user)
    db_session.commit()
    return company, user


def _one_page():
    return [{"id": "page-1", "name": "Lead Co Page", "access_token": "page-token-1", "instagram_username": None}]


def _two_pages():
    return [
        {"id": "page-1", "name": "Lead Co Page", "access_token": "page-token-1", "instagram_username": None},
        {"id": "page-2", "name": "Lead Co Storefront", "access_token": "page-token-2", "instagram_username": "leadco"},
    ]


# ─── facebook_oauth_service: signed state round-trips correctly ────────────

def test_build_oauth_url_state_decodes_back_to_company_and_user(app):
    app.config["FACEBOOK_APP_ID"] = "app123"
    with app.test_request_context():
        auth_url = build_oauth_url(7, 42, "https://ravlohq.com/integrations/facebook/callback")

    state = parse_qs(urlparse(auth_url).query)["state"][0]

    with app.test_request_context():
        decoded = decode_oauth_state(state)

    assert decoded["company_id"] == 7
    assert decoded["uid"] == 42


def test_decode_oauth_state_rejects_tampered_state(app):
    with app.test_request_context():
        assert decode_oauth_state("not-a-real-signed-state") is None
        assert decode_oauth_state(None) is None


def test_oauth_scopes_omit_pages_manage_metadata():
    """Meta rejects pages_manage_metadata as an "Invalid Scope" for an
    app that hasn't had it added under App Review -> Permissions and
    Features -- and unlike a single bad scope being silently dropped,
    this blocks the whole OAuth dialog for anyone testing as an app
    admin/developer. Leave it out of the request until it's approved;
    subscribe_page_to_leadgen() already degrades gracefully without it."""
    assert "pages_manage_metadata" not in OAUTH_SCOPES
    assert "leads_retrieval" in OAUTH_SCOPES


# ─── /integrations/facebook/connect/<company_id> ───────────────────────────

def test_connect_requires_admin_of_that_company(db_session, client):
    company, admin = _make_company_admin(db_session)
    other_company, other_admin = _make_company_admin(db_session, email="admin@other.com", company_name="Other Co")
    login_as(client, other_admin)

    client.application.config["FACEBOOK_APP_ID"] = "app123"
    resp = client.get(f"/integrations/facebook/connect/{company.id}", follow_redirects=False)

    assert resp.status_code == 302
    assert "/integrations/facebook/callback" not in (resp.headers.get("Location") or "")


def test_connect_redirects_to_facebook_with_signed_state(db_session, client):
    company, admin = _make_company_admin(db_session)
    login_as(client, admin)
    client.application.config["FACEBOOK_APP_ID"] = "app123"

    resp = client.get(f"/integrations/facebook/connect/{company.id}", follow_redirects=False)

    assert resp.status_code == 302
    location = resp.headers["Location"]
    assert location.startswith("https://www.facebook.com/v19.0/dialog/oauth")
    query = parse_qs(urlparse(location).query)
    assert query["client_id"][0] == "app123"

    with client.application.test_request_context():
        decoded = decode_oauth_state(query["state"][0])
    assert decoded["company_id"] == company.id
    assert decoded["uid"] == admin.id


def test_connect_without_facebook_app_id_flashes_and_redirects_to_settings(db_session, client):
    company, admin = _make_company_admin(db_session)
    login_as(client, admin)
    client.application.config["FACEBOOK_APP_ID"] = ""

    resp = client.get(f"/integrations/facebook/connect/{company.id}", follow_redirects=True)

    assert resp.status_code == 200
    assert "not configured" in resp.get_data(as_text=True)


# ─── /integrations/facebook/callback ────────────────────────────────────────

def test_callback_completes_even_when_session_did_not_survive_the_round_trip(db_session, client, app):
    company, admin = _make_company_admin(db_session)

    with app.test_request_context():
        app.config["FACEBOOK_APP_ID"] = "app123"
        auth_url = build_oauth_url(company.id, admin.id, "https://ravlohq.com/integrations/facebook/callback")
    state = parse_qs(urlparse(auth_url).query)["state"][0]

    # No login_as() -- an anonymous client, exactly like a session that
    # got dropped on the way back from facebook.com.
    with patch("LoanMVP.routes.facebook_connect.exchange_code_for_user_token", return_value="short-tok"), \
         patch("LoanMVP.routes.facebook_connect.exchange_for_long_lived_token", return_value="long-tok"), \
         patch("LoanMVP.routes.facebook_connect.list_managed_pages", return_value=_one_page()), \
         patch("LoanMVP.routes.facebook_connect.subscribe_page_to_leadgen"):
        resp = client.get(f"/integrations/facebook/callback?code=abc123&state={state}", follow_redirects=False)

    assert resp.status_code == 302
    assert "/auth/login" not in resp.headers["Location"]

    connection = FacebookPageConnection.query.filter_by(company_id=company.id).first()
    assert connection is not None
    assert connection.page_id == "page-1"

    with client.session_transaction() as sess:
        assert sess.get("_user_id") == str(admin.id)


def test_callback_with_missing_state_redirects_to_login(client):
    resp = client.get("/integrations/facebook/callback?code=abc123", follow_redirects=False)

    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_callback_with_tampered_state_redirects_to_login(client):
    resp = client.get("/integrations/facebook/callback?code=abc123&state=garbage", follow_redirects=False)

    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_callback_single_page_auto_connects_and_subscribes(db_session, client, app):
    company, admin = _make_company_admin(db_session)
    login_as(client, admin)

    with app.test_request_context():
        app.config["FACEBOOK_APP_ID"] = "app123"
        auth_url = build_oauth_url(company.id, admin.id, "https://ravlohq.com/integrations/facebook/callback")
    state = parse_qs(urlparse(auth_url).query)["state"][0]

    with patch("LoanMVP.routes.facebook_connect.exchange_code_for_user_token", return_value="short-tok"), \
         patch("LoanMVP.routes.facebook_connect.exchange_for_long_lived_token", return_value="long-tok"), \
         patch("LoanMVP.routes.facebook_connect.list_managed_pages", return_value=_one_page()) as mock_list, \
         patch("LoanMVP.routes.facebook_connect.subscribe_page_to_leadgen") as mock_subscribe:
        resp = client.get(f"/integrations/facebook/callback?code=abc123&state={state}", follow_redirects=True)

    assert resp.status_code == 200
    mock_list.assert_called_once_with("long-tok")
    mock_subscribe.assert_called_once_with("page-1", "page-token-1")

    connection = FacebookPageConnection.query.filter_by(company_id=company.id).first()
    assert connection.page_id == "page-1"
    assert connection.page_name == "Lead Co Page"
    assert connection.platform == "facebook"


def test_callback_multiple_pages_renders_picker_without_connecting(db_session, client, app):
    company, admin = _make_company_admin(db_session)
    login_as(client, admin)

    with app.test_request_context():
        app.config["FACEBOOK_APP_ID"] = "app123"
        auth_url = build_oauth_url(company.id, admin.id, "https://ravlohq.com/integrations/facebook/callback")
    state = parse_qs(urlparse(auth_url).query)["state"][0]

    with patch("LoanMVP.routes.facebook_connect.exchange_code_for_user_token", return_value="short-tok"), \
         patch("LoanMVP.routes.facebook_connect.exchange_for_long_lived_token", return_value="long-tok"), \
         patch("LoanMVP.routes.facebook_connect.list_managed_pages", return_value=_two_pages()):
        resp = client.get(f"/integrations/facebook/callback?code=abc123&state={state}")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Lead Co Page" in body
    assert "Lead Co Storefront" in body
    assert "@leadco" in body
    assert FacebookPageConnection.query.filter_by(company_id=company.id).count() == 0


def test_callback_no_pages_flashes_warning(db_session, client, app):
    company, admin = _make_company_admin(db_session)
    login_as(client, admin)

    with app.test_request_context():
        app.config["FACEBOOK_APP_ID"] = "app123"
        auth_url = build_oauth_url(company.id, admin.id, "https://ravlohq.com/integrations/facebook/callback")
    state = parse_qs(urlparse(auth_url).query)["state"][0]

    with patch("LoanMVP.routes.facebook_connect.exchange_code_for_user_token", return_value="short-tok"), \
         patch("LoanMVP.routes.facebook_connect.exchange_for_long_lived_token", return_value="long-tok"), \
         patch("LoanMVP.routes.facebook_connect.list_managed_pages", return_value=[]):
        resp = client.get(f"/integrations/facebook/callback?code=abc123&state={state}", follow_redirects=True)

    assert resp.status_code == 200
    assert "No Facebook Pages found" in resp.get_data(as_text=True)


# ─── /integrations/facebook/connect/<company_id>/finish (picker submit) ───

def test_finish_creates_connection_for_chosen_page(db_session, client):
    company, admin = _make_company_admin(db_session)
    login_as(client, admin)

    with patch("LoanMVP.routes.facebook_connect.subscribe_page_to_leadgen") as mock_subscribe:
        resp = client.post(
            f"/integrations/facebook/connect/{company.id}/finish",
            data={
                "page_id": "page-2",
                "page_name": "Lead Co Storefront",
                "page_access_token": "page-token-2",
                "instagram_username": "leadco",
            },
            follow_redirects=False,
        )

    mock_subscribe.assert_called_once_with("page-2", "page-token-2")

    assert resp.status_code == 302
    connection = FacebookPageConnection.query.filter_by(company_id=company.id).first()
    assert connection.page_id == "page-2"
    assert connection.platform == "instagram"


def test_finish_rejects_another_companys_admin(db_session, client):
    company, admin = _make_company_admin(db_session)
    other_company, other_admin = _make_company_admin(db_session, email="admin@other2.com", company_name="Other Co 2")
    login_as(client, other_admin)

    resp = client.post(
        f"/integrations/facebook/connect/{company.id}/finish",
        data={"page_id": "page-1", "page_name": "x", "page_access_token": "tok"},
        follow_redirects=False,
    )

    assert resp.status_code == 302
    assert FacebookPageConnection.query.filter_by(company_id=company.id).count() == 0
