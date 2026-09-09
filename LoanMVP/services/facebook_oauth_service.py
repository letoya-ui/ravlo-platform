"""Facebook Login for Business OAuth flow, used to connect a company's
Facebook Page (and its linked Instagram professional account, if any)
without making an admin go dig a Page Access Token out of Meta Business
Suite by hand.

Mirrors LoanMVP.services.canva_service's signed-state pattern: the round
trip to facebook.com and back is a cross-site top-level navigation, and
whether the session cookie survives it varies by browser/proxy/webview.
Encoding who started the flow into a signed `state` param means the
callback never depends on the session having survived.
"""
import os
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

import requests
from flask import current_app

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"
FACEBOOK_OAUTH_DIALOG = "https://www.facebook.com/v19.0/dialog/oauth"

# Pages, leads, and the ability to subscribe a Page to this app's webhook.
OAUTH_SCOPES = "pages_show_list,pages_read_engagement,pages_manage_metadata,leads_retrieval"

# How long an admin has to complete the Facebook consent screen and be
# redirected back before their OAuth state expires.
OAUTH_STATE_MAX_AGE_SECONDS = 900


class FacebookOAuthError(Exception):
    pass


def _state_serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt="facebook-oauth-state")


def build_oauth_url(company_id: int, user_id: int, redirect_uri: str) -> str:
    client_id = current_app.config.get("FACEBOOK_APP_ID", "")
    if not client_id:
        raise FacebookOAuthError("FACEBOOK_APP_ID is not configured on this server.")

    state = _state_serializer().dumps({"company_id": company_id, "uid": user_id})

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": OAUTH_SCOPES,
        "response_type": "code",
    }
    query = "&".join(f"{key}={requests.utils.quote(str(value), safe='')}" for key, value in params.items())
    return f"{FACEBOOK_OAUTH_DIALOG}?{query}"


def decode_oauth_state(state: str):
    """Verify and decode a state param built by build_oauth_url(). Returns
    None if it's missing, tampered with, or older than
    OAUTH_STATE_MAX_AGE_SECONDS -- callers should treat that as "start the
    connection over," not silently continue."""
    if not state:
        return None
    try:
        return _state_serializer().loads(state, max_age=OAUTH_STATE_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None


def _graph_get(path: str, params: dict) -> dict:
    resp = requests.get(f"{GRAPH_API_BASE}/{path}", params=params, timeout=10)
    data = resp.json()
    if resp.status_code >= 400 or "error" in data:
        message = (data.get("error") or {}).get("message") or f"Graph API request failed ({resp.status_code})."
        raise FacebookOAuthError(message)
    return data


def exchange_code_for_user_token(code: str, redirect_uri: str) -> str:
    client_id = current_app.config.get("FACEBOOK_APP_ID", "")
    client_secret = current_app.config.get("FACEBOOK_APP_SECRET", "")
    data = _graph_get(
        "oauth/access_token",
        {"client_id": client_id, "client_secret": client_secret, "redirect_uri": redirect_uri, "code": code},
    )
    return data["access_token"]


def exchange_for_long_lived_token(short_lived_token: str) -> str:
    client_id = current_app.config.get("FACEBOOK_APP_ID", "")
    client_secret = current_app.config.get("FACEBOOK_APP_SECRET", "")
    data = _graph_get(
        "oauth/access_token",
        {
            "grant_type": "fb_exchange_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "fb_exchange_token": short_lived_token,
        },
    )
    return data["access_token"]


def list_managed_pages(user_access_token: str) -> list[dict]:
    """Returns [{id, name, access_token, instagram_username}] for every
    Page the authorizing admin manages. instagram_username is None when
    the Page has no linked Instagram professional account."""
    data = _graph_get(
        "me/accounts",
        {
            "fields": "id,name,access_token,instagram_business_account{username}",
            "access_token": user_access_token,
        },
    )

    pages = []
    for item in data.get("data") or []:
        ig_account = item.get("instagram_business_account") or {}
        pages.append({
            "id": item.get("id"),
            "name": item.get("name"),
            "access_token": item.get("access_token"),
            "instagram_username": ig_account.get("username"),
        })
    return pages


def subscribe_page_to_leadgen(page_id: str, page_access_token: str) -> None:
    """Tells Meta to actually deliver leadgen webhook events for this
    Page to Ravlo's app -- the app-level webhook subscription (Meta App
    Dashboard) is necessary but not sufficient; each Page also has to be
    subscribed individually via this call."""
    resp = requests.post(
        f"{GRAPH_API_BASE}/{page_id}/subscribed_apps",
        params={"subscribed_fields": "leadgen", "access_token": page_access_token},
        timeout=10,
    )
    data = resp.json() if resp.content else {}
    if resp.status_code >= 400 or not data.get("success", True):
        message = (data.get("error") or {}).get("message") or f"Could not subscribe the Page to lead events ({resp.status_code})."
        raise FacebookOAuthError(message)
