import base64
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests
from flask import session


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
        "design:meta:read asset:read profile:read",
    )

    state = secrets.token_urlsafe(24)
    verifier, challenge = generate_pkce_pair()

    session["canva_oauth_state"] = state
    session["canva_code_verifier"] = verifier

    query = {
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "scope": scopes,
        "response_type": "code",
        "state": state,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
    }

    return f"{CANVA_AUTH_BASE}?{urlencode(query)}"


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

    response = requests.post(
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

    response = requests.post(
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


def create_design(access_token: str, title: str = "Ravlo Design"):
    url = f"{CANVA_API_BASE}/designs"

    payload = {
        "design_type": {
            "type": "preset",
            "name": "presentation"
        },
        "title": title,
    }

    response = requests.post(
        url,
        json=payload,
        headers=canva_headers(access_token),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_design(access_token: str, design_id: str):
    url = f"{CANVA_API_BASE}/designs/{design_id}"

    response = requests.get(
        url,
        headers=canva_headers(access_token),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def list_designs(access_token: str, ownership: str = "owned"):
    url = f"{CANVA_API_BASE}/designs"
    params = {"ownership": ownership}

    response = requests.get(
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

    response = requests.post(
        url,
        json=payload,
        headers=canva_headers(access_token),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_export_job(access_token: str, job_id: str):
    url = f"{CANVA_API_BASE}/exports/{job_id}"

    response = requests.get(
        url,
        headers=canva_headers(access_token),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()