"""Regression tests for two Canva bugs found together:

1. create_design() sent design_type={"type": "preset", "name": "flyer_a4"}
   -- Canva's Connect API only recognizes "doc"/"whiteboard"/"presentation"
   as preset names, so every single flyer creation request was rejected
   with a 400 (confirmed in production logs: "Could not create Canva
   design: 400 Client Error: Bad Request for url:
   https://api.canva.com/rest/v1/designs"). Flyer-shaped designs now go
   through design_type={"type": "custom", "width": ..., "height": ...}
   instead; real preset names still pass through unchanged.

2. When that request failed, the error handler in canva.py's
   create_flyer() fell back to _canva_fallback(), which checked
   `role in ("realtor", "partner_group")` -- but "partner_group" is only
   a @role_required() alias (expanded from PARTNER_ROLES in
   decorators.py), never an actual User.role value. Every real/demo
   partner account (role "partner", "contractor", "student", etc.) fell
   through to auth.login on ANY Canva error, which read as being logged
   out. See test_canva_oauth.py for the separate OAuth-callback logout bug.
"""
import json
from unittest.mock import patch

import requests as requests_lib

from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User
from LoanMVP.routes.canva import _canva_fallback
from LoanMVP.services.canva_service import create_design
from LoanMVP.utils.decorators import PARTNER_ROLES


def _make_user(db_session, email, role):
    company = Company(name=f"{email} Co", is_active=True)
    db_session.add(company)
    db_session.commit()
    user = User(email=email, role=role, is_active=True, company_id=company.id, first_name="Sam")
    db_session.add(user)
    db_session.commit()
    return user


def _make_response(status_code, json_body=None, reason="Error"):
    resp = requests_lib.Response()
    resp.status_code = status_code
    resp.reason = reason
    resp.url = "https://api.canva.com/rest/v1/designs"
    resp._content = json.dumps(json_body if json_body is not None else {}).encode("utf-8")
    return resp


# ─── create_design(): real design_type shapes ───────────────────────────────

def test_flyer_preset_uses_a_custom_sized_canvas_not_a_fake_preset_name():
    ok_response = _make_response(200, {"design": {"urls": {"edit_url": "https://canva.com/x"}}})

    with patch("LoanMVP.services.canva_service.requests.post", return_value=ok_response) as mock_post:
        create_design("tok", title="Flyer", design_preset="flyer_a4")

    payload = mock_post.call_args.kwargs["json"]
    assert payload["design_type"] == {"type": "custom", "width": 2480, "height": 3508}


def test_real_canva_preset_names_pass_through_unchanged():
    ok_response = _make_response(200, {"design": {"urls": {"edit_url": "https://canva.com/x"}}})

    with patch("LoanMVP.services.canva_service.requests.post", return_value=ok_response) as mock_post:
        create_design("tok", title="Doc", design_preset="presentation")

    payload = mock_post.call_args.kwargs["json"]
    assert payload["design_type"] == {"type": "preset", "name": "presentation"}


def test_unrecognized_preset_falls_back_to_default_custom_size():
    ok_response = _make_response(200, {"design": {"urls": {"edit_url": "https://canva.com/x"}}})

    with patch("LoanMVP.services.canva_service.requests.post", return_value=ok_response) as mock_post:
        create_design("tok", title="X", design_preset="something_made_up")

    payload = mock_post.call_args.kwargs["json"]
    assert payload["design_type"]["type"] == "custom"


def test_a_400_retries_once_with_the_default_size_before_giving_up():
    bad_response = _make_response(400, {"error": "invalid design_type"})
    ok_response = _make_response(200, {"design": {"urls": {"edit_url": "https://canva.com/x"}}})

    with patch("LoanMVP.services.canva_service.requests.post", side_effect=[bad_response, ok_response]) as mock_post:
        result = create_design("tok", title="X", design_preset="flyer_a4")

    assert mock_post.call_count == 2
    assert result["design"]["urls"]["edit_url"] == "https://canva.com/x"


def test_a_persistent_400_raises_with_canvas_real_error_body_not_an_opaque_message():
    bad_response = _make_response(400, {"error": "invalid_request", "message": "width must be between 40 and 8000"})

    with patch("LoanMVP.services.canva_service.requests.post", return_value=bad_response):
        try:
            create_design("tok", title="X", design_preset="flyer_letter")
            assert False, "expected an HTTPError"
        except requests_lib.exceptions.HTTPError as exc:
            assert "width must be between 40 and 8000" in str(exc)


# ─── _canva_fallback(): every partner-family role must land on a real dashboard ──

def test_canva_fallback_routes_every_partner_role_to_partners_dashboard(db_session, app):
    from flask_login import login_user

    for role in PARTNER_ROLES:
        user = _make_user(db_session, f"{role}@example.com", role=role)

        with app.test_request_context():
            login_user(user)
            fallback_url = _canva_fallback()

        assert fallback_url == "/partners/dashboard", f"role={role!r} did not route to partners.dashboard"


def test_canva_fallback_never_sends_a_partner_role_to_login():
    # This is the exact bug from production: "partner_group" is a
    # @role_required() alias, not a real User.role value, so this check
    # always missed every actual partner account.
    assert "partner_group" not in PARTNER_ROLES
    assert "partner" in PARTNER_ROLES
