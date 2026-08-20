# LoanMVP/services/renter_invite_service.py
"""Signed tenant portal invite links.

A property manager generates a link for a specific Tenant record and
sends it to the renter directly (text/email, outside the app). The link
itself carries a signed, time-limited token instead of a server-side
row, mirroring build_canva_auth_url()/decode_oauth_state() in
canva_service.py -- there's no session to depend on since the person
opening the link has never logged in yet.
"""
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from flask import current_app

# Renters may not open a text/email right away, so this is generous
# compared to the 900s Canva OAuth round trip -- 7 days.
INVITE_TOKEN_MAX_AGE_SECONDS = 7 * 24 * 60 * 60


def _serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt="renter-portal-invite")


def build_invite_token(tenant_id: int) -> str:
    return _serializer().dumps({"tenant_id": tenant_id})


def decode_invite_token(token: str):
    """Verify and decode an invite token. Returns the tenant_id, or None
    if the token is missing, tampered with, or expired -- callers should
    treat that as "ask the property manager to resend the invite."""
    if not token:
        return None
    try:
        payload = _serializer().loads(token, max_age=INVITE_TOKEN_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
    return payload.get("tenant_id")
