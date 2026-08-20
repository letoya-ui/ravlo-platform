"""Unit tests for the signed tenant portal invite token, mirroring the
coverage test_canva_service.py has for build_canva_auth_url()/
decode_oauth_state() -- same itsdangerous pattern, new salt/payload.
"""
from LoanMVP.services.renter_invite_service import build_invite_token, decode_invite_token


def test_round_trip_returns_the_tenant_id(app):
    with app.test_request_context():
        token = build_invite_token(42)
        assert decode_invite_token(token) == 42


def test_tampered_token_returns_none(app):
    with app.test_request_context():
        token = build_invite_token(42)
        tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
        assert decode_invite_token(tampered) is None


def test_empty_token_returns_none(app):
    with app.test_request_context():
        assert decode_invite_token("") is None
        assert decode_invite_token(None) is None


def test_garbage_token_returns_none(app):
    with app.test_request_context():
        assert decode_invite_token("not-a-real-token") is None
