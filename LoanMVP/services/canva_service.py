import base64
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, quote

import requests
from flask import session

from LoanMVP.utils.safe_http import safe_call


CANVA_AUTH_BASE = "https://www.canva.com/api/oauth/authorize"
CANVA_TOKEN_URL = "https://api.canva.com/rest/v1/oauth/token"
CANVA_API_BASE = "https://api.canva.com/rest/v1"


def _utcnow():
    return datetime.now(timezone.utc)


def generate_pkce_pair():
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("utf-8")).digest()
    ).decode("utf-8").rstrip("=")
    return verifier, challenge


def build_canva_auth_url():
    client_id = os.environ.get("CANVA_CLIENT_ID")
    redirect_uri = os.environ.get("CANVA_REDIRECT_URI")
    scopes = os.environ.get(
        "CANVA_SCOPES",
        "app:read asset:read asset:write design:content:read design:content:write design:meta:read",
    )

    state = secrets.token_urlsafe(24)
    verifier, challenge = generate_pkce_pair()

    session["canva_oauth_state"] = state
    session["canva_code_verifier"] = verifier

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


def exchange_code_for_tokens(code: str):
    client_id = os.environ.get("CANVA_CLIENT_ID")
    client_secret = os.environ.get("CANVA_CLIENT_SECRET")
    redirect_uri = os.environ.get("CANVA_REDIRECT_URI")
    code_verifier = session.get("canva_code_verifier")

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


def create_design(access_token: str, title: str = "Ravlo Design",
                  design_preset: str = "flyer_a4"):
    """Create a new Canva design and return the full response including edit URL.

    design_preset options for real estate flyers:
      "flyer_a4"        — standard portrait flyer (8.27 × 11.69 in)
      "real_estate_flyer" — if Canva exposes it; falls back gracefully
      "presentation"    — 16:9 slide (fallback)

    The response includes ``design.urls.edit_url`` — redirect the user there
    so they open their own Canva editor immediately.
    """
    url = f"{CANVA_API_BASE}/designs"

    payload = {
        "design_type": {
            "type": "preset",
            "name": design_preset,
        },
        "title": title,
    }

    response = safe_call(
        requests.post,
        url,
        json=payload,
        headers=canva_headers(access_token),
        timeout=30,
    )

    # If the preset name isn't supported, fall back to a generic flyer
    if response.status_code == 400 and design_preset != "flyer_a4":
        payload["design_type"]["name"] = "flyer_a4"
        response = safe_call(
            requests.post,
            url, json=payload, headers=canva_headers(access_token), timeout=30,
        )

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