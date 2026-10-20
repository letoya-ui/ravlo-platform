import base64
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, quote

import requests
from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from LoanMVP.utils.safe_http import safe_call


CANVA_AUTH_BASE = "https://www.canva.com/api/oauth/authorize"
CANVA_TOKEN_URL = "https://api.canva.com/rest/v1/oauth/token"
CANVA_API_BASE = "https://api.canva.com/rest/v1"

# How long a user has to complete the Canva consent screen and be
# redirected back before their OAuth state expires.
OAUTH_STATE_MAX_AGE_SECONDS = 900


def _utcnow():
    return datetime.now(timezone.utc)


def _state_serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt="canva-oauth-state")


def generate_pkce_pair():
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("utf-8")).digest()
    ).decode("utf-8").rstrip("=")
    return verifier, challenge


def build_canva_auth_url(user_id, next_url=None):
    """Build the Canva authorize URL, encoding everything the callback
    needs (who started this, the PKCE verifier, where to return them)
    into a signed `state` param instead of the Flask session.

    The round trip to canva.com and back is a cross-site top-level
    navigation -- browsers/proxies/mobile webviews vary in how reliably
    they carry a session cookie through that, and when they don't, a
    session-dependent callback bounces the user to the login page,
    which reads as "connecting Canva logged me out." Signing the state
    instead means the callback never needs the session to have survived.
    """
    client_id = os.environ.get("CANVA_CLIENT_ID")
    redirect_uri = os.environ.get("CANVA_REDIRECT_URI")
    scopes = os.environ.get(
        "CANVA_SCOPES",
        "app:read asset:read asset:write design:content:read design:content:write design:meta:read",
    )

    verifier, challenge = generate_pkce_pair()
    state = _state_serializer().dumps({"uid": user_id, "next": next_url, "verifier": verifier})

    # Build query string manually to match Canva's expected encoding:
    # - scope: colons must be literal (not %3A), spaces must be %20 (not +)
    # - other params: standard percent-encoding
    scope_encoded = scopes.replace(" ", "%20")   # spaces → %20, colons stay literal

    params = "&".join([
        f"client_id={quote(client_id or '', safe='')}",
        f"response_type=code",
        f"code_challenge_method=S256",
        f"code_challenge={quote(challenge, safe='')}",
        f"scope={scope_encoded}",
        f"state={quote(state, safe='')}",
        f"redirect_uri={quote(redirect_uri or '', safe='')}",
    ])

    return f"{CANVA_AUTH_BASE}?{params}"


def decode_oauth_state(state):
    """Verify and decode a state param built by build_canva_auth_url().
    Returns None if it's missing, tampered with, or older than
    OAUTH_STATE_MAX_AGE_SECONDS -- callers should treat that as "start
    the Canva connection over," not silently continue."""
    if not state:
        return None
    try:
        return _state_serializer().loads(state, max_age=OAUTH_STATE_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None


def exchange_code_for_tokens(code: str, code_verifier: str):
    client_id = os.environ.get("CANVA_CLIENT_ID")
    client_secret = os.environ.get("CANVA_CLIENT_SECRET")
    redirect_uri = os.environ.get("CANVA_REDIRECT_URI")

    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": code_verifier,
    }

    auth = (client_id, client_secret) if client_secret else None

    response = safe_call(
        requests.post,
        CANVA_TOKEN_URL,
        data=payload,
        auth=auth,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    expires_in = data.get("expires_in", 3600)
    expires_at = _utcnow() + timedelta(seconds=expires_in)

    return {
        "access_token": data.get("access_token"),
        "refresh_token": data.get("refresh_token"),
        "scope": data.get("scope"),
        "expires_at": expires_at,
        "raw": data,
    }


def refresh_access_token(refresh_token: str):
    client_id = os.environ.get("CANVA_CLIENT_ID")
    client_secret = os.environ.get("CANVA_CLIENT_SECRET")

    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }

    auth = (client_id, client_secret) if client_secret else None

    response = safe_call(
        requests.post,
        CANVA_TOKEN_URL,
        data=payload,
        auth=auth,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    expires_in = data.get("expires_in", 3600)
    expires_at = _utcnow() + timedelta(seconds=expires_in)

    return {
        "access_token": data.get("access_token"),
        "refresh_token": data.get("refresh_token", refresh_token),
        "scope": data.get("scope"),
        "expires_at": expires_at,
        "raw": data,
    }


def canva_headers(access_token: str):
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


# Canva's Connect API "Create a design" endpoint only recognizes
# "doc", "whiteboard", and "presentation" as design_type.preset names --
# there's no "flyer" preset. Anything else (including our own
# "flyer_a4"/"flyer_letter" shorthands) must go through design_type.custom
# with explicit pixel dimensions instead. Sizes below are 300dpi portrait.
_CANVA_PRESET_NAMES = {"doc", "whiteboard", "presentation"}
_CUSTOM_DESIGN_SIZES = {
    "flyer_a4": (2480, 3508),      # A4 portrait
    "flyer_letter": (2550, 3300),  # US Letter portrait
}
_DEFAULT_CUSTOM_SIZE = "flyer_letter"


def _design_type_payload(design_preset: str):
    if design_preset in _CANVA_PRESET_NAMES:
        return {"type": "preset", "name": design_preset}

    width, height = _CUSTOM_DESIGN_SIZES.get(design_preset, _CUSTOM_DESIGN_SIZES[_DEFAULT_CUSTOM_SIZE])
    return {"type": "custom", "width": width, "height": height}


def create_design(access_token: str, title: str = "Ravlo Design",
                  design_preset: str = "flyer_letter"):
    """Create a new Canva design and return the full response including edit URL.

    design_preset options:
      "flyer_letter"          — US Letter portrait flyer (custom size, default)
      "flyer_a4"              — A4 portrait flyer (custom size)
      "doc"/"whiteboard"/"presentation" — real Canva presets, passed through as-is

    The response includes ``design.urls.edit_url`` — redirect the user there
    so they open their own Canva editor immediately.
    """
    url = f"{CANVA_API_BASE}/designs"

    payload = {
        "design_type": _design_type_payload(design_preset),
        "title": title,
    }

    response = safe_call(
        requests.post,
        url,
        json=payload,
        headers=canva_headers(access_token),
        timeout=30,
    )

    # If that shape was rejected for some other reason, fall back to the
    # plain default custom size rather than repeating the same request.
    if response.status_code == 400 and design_preset != _DEFAULT_CUSTOM_SIZE:
        payload["design_type"] = _design_type_payload(_DEFAULT_CUSTOM_SIZE)
        response = safe_call(
            requests.post,
            url, json=payload, headers=canva_headers(access_token), timeout=30,
        )

    if response.status_code >= 400:
        # requests' default HTTPError message ("400 Client Error: Bad
        # Request for url: ...") drops Canva's actual reason -- surface it
        # so a real API rejection is diagnosable instead of opaque.
        detail = (response.text or "")[:500]
        response.reason = f"{response.reason} — {detail}" if detail else response.reason

    response.raise_for_status()
    return response.json()


def get_design(access_token: str, design_id: str):
    url = f"{CANVA_API_BASE}/designs/{design_id}"

    response = safe_call(
        requests.get,
        url,
        headers=canva_headers(access_token),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def list_designs(access_token: str, ownership: str = "owned"):
    url = f"{CANVA_API_BASE}/designs"
    params = {"ownership": ownership}

    response = safe_call(
        requests.get,
        url,
        params=params,
        headers=canva_headers(access_token),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def create_export_job(access_token: str, design_id: str, export_type: str = "pdf"):
    url = f"{CANVA_API_BASE}/exports"

    payload = {
        "design_id": design_id,
        "format": {
            "type": export_type
        }
    }

    response = safe_call(
        requests.post,
        url,
        json=payload,
        headers=canva_headers(access_token),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_export_job(access_token: str, job_id: str):
    url = f"{CANVA_API_BASE}/exports/{job_id}"

    response = safe_call(
        requests.get,
        url,
        headers=canva_headers(access_token),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()