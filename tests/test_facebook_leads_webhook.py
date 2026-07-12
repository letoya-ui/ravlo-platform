"""Regression tests for the Facebook/Instagram Lead Ads webhook.

Covers the GET verification handshake, POST signature verification, lead
creation from a mocked Graph API response, dedup on webhook redelivery,
an unconnected page_id being a safe no-op, and the admin settings page
that creates/updates a company's FacebookPageConnection.
"""
import hashlib
import hmac
import json
from unittest.mock import Mock, patch

from LoanMVP.models.admin import Company
from LoanMVP.models.crm_models import FacebookPageConnection, Lead
from LoanMVP.models.loan_officer_model import LoanOfficerProfile
from LoanMVP.models.user_model import User

from tests.conftest import login_as

APP_SECRET = "test-fb-app-secret"
VERIFY_TOKEN = "test-fb-verify-token"


def _sign(body: bytes) -> str:
    digest = hmac.new(APP_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _make_company_with_officer(db_session, company_name="Lead Co", email="lo@example.com"):
    company = Company(name=company_name, is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role="loan_officer", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    officer = LoanOfficerProfile(user_id=user.id, name="Lonnie Officer", email=email)
    db_session.add(officer)
    db_session.commit()
    return company, user, officer


def _make_connection(db_session, company, page_id="123456", platform="facebook"):
    connection = FacebookPageConnection(
        company_id=company.id,
        page_id=page_id,
        page_name="Test Page",
        platform=platform,
        page_access_token="test-page-token",
    )
    db_session.add(connection)
    db_session.commit()
    return connection


def _leadgen_payload(page_id, leadgen_id, form_id="form_1"):
    return {
        "object": "page",
        "entry": [
            {
                "id": page_id,
                "changes": [
                    {
                        "field": "leadgen",
                        "value": {
                            "leadgen_id": leadgen_id,
                            "form_id": form_id,
                            "page_id": page_id,
                        },
                    }
                ],
            }
        ],
    }


def _graph_api_response(name="Jane Doe", email="jane@example.com", phone="+15551234567"):
    mock_resp = Mock()
    mock_resp.raise_for_status = Mock()
    mock_resp.json.return_value = {
        "field_data": [
            {"name": "full_name", "values": [name]},
            {"name": "email", "values": [email]},
            {"name": "phone_number", "values": [phone]},
        ]
    }
    return mock_resp


def test_verify_webhook_correct_token_echoes_challenge(app, client):
    app.config["FACEBOOK_WEBHOOK_VERIFY_TOKEN"] = VERIFY_TOKEN
    resp = client.get(
        "/webhooks/facebook/leads",
        query_string={
            "hub.mode": "subscribe",
            "hub.verify_token": VERIFY_TOKEN,
            "hub.challenge": "12345",
        },
    )
    assert resp.status_code == 200
    assert resp.get_data(as_text=True) == "12345"


def test_verify_webhook_wrong_token_rejected(app, client):
    app.config["FACEBOOK_WEBHOOK_VERIFY_TOKEN"] = VERIFY_TOKEN
    resp = client.get(
        "/webhooks/facebook/leads",
        query_string={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong-token",
            "hub.challenge": "12345",
        },
    )
    assert resp.status_code == 403


def test_receive_lead_event_invalid_signature_rejected(app, client, db_session):
    app.config["FACEBOOK_APP_SECRET"] = APP_SECRET
    company, _, _ = _make_company_with_officer(db_session)
    _make_connection(db_session, company, page_id="page-bad-sig")

    body = json.dumps(_leadgen_payload("page-bad-sig", "lead-1")).encode()
    resp = client.post(
        "/webhooks/facebook/leads",
        data=body,
        content_type="application/json",
        headers={"X-Hub-Signature-256": "sha256=deadbeef"},
    )

    assert resp.status_code == 403
    assert Lead.query.filter_by(external_lead_id="lead-1").first() is None


def test_receive_lead_event_creates_lead_from_graph_api(app, client, db_session):
    app.config["FACEBOOK_APP_SECRET"] = APP_SECRET
    company, _, loaded_officer = _make_company_with_officer(db_session, email="busy@example.com")
    # A second, less-loaded officer at the same company -- should win auto-assign.
    quiet_user = User(email="quiet@example.com", role="loan_officer", is_active=True, company_id=company.id)
    db_session.add(quiet_user)
    db_session.commit()
    quiet_officer = LoanOfficerProfile(user_id=quiet_user.id, name="Quiet Officer", email="quiet@example.com")
    db_session.add(quiet_officer)
    db_session.commit()

    # Give the first officer an existing lead so they're "busier".
    existing = Lead(name="Existing", assigned_officer_id=loaded_officer.id, assigned_to=loaded_officer.user_id)
    db_session.add(existing)
    db_session.commit()

    _make_connection(db_session, company, page_id="page-create")

    body = json.dumps(_leadgen_payload("page-create", "lead-create-1")).encode()

    with patch(
        "LoanMVP.routes.facebook_leads_webhook.requests.get",
        return_value=_graph_api_response(),
    ):
        resp = client.post(
            "/webhooks/facebook/leads",
            data=body,
            content_type="application/json",
            headers={"X-Hub-Signature-256": _sign(body)},
        )

    assert resp.status_code == 200
    lead = Lead.query.filter_by(external_lead_id="lead-create-1").first()
    assert lead is not None
    assert lead.name == "Jane Doe"
    assert lead.email == "jane@example.com"
    assert lead.phone == "+15551234567"
    assert lead.source.source_name == "Facebook"
    assert lead.assigned_officer_id == quiet_officer.id


def test_receive_lead_event_dedupes_repeated_leadgen_id(app, client, db_session):
    app.config["FACEBOOK_APP_SECRET"] = APP_SECRET
    company, _, _ = _make_company_with_officer(db_session, email="dedupe@example.com")
    _make_connection(db_session, company, page_id="page-dedupe")

    body = json.dumps(_leadgen_payload("page-dedupe", "lead-dedupe-1")).encode()
    signature = _sign(body)

    with patch(
        "LoanMVP.routes.facebook_leads_webhook.requests.get",
        return_value=_graph_api_response(),
    ):
        client.post(
            "/webhooks/facebook/leads",
            data=body,
            content_type="application/json",
            headers={"X-Hub-Signature-256": signature},
        )
        client.post(
            "/webhooks/facebook/leads",
            data=body,
            content_type="application/json",
            headers={"X-Hub-Signature-256": signature},
        )

    assert Lead.query.filter_by(external_lead_id="lead-dedupe-1").count() == 1


def test_receive_lead_event_unknown_page_is_noop(app, client, db_session):
    app.config["FACEBOOK_APP_SECRET"] = APP_SECRET
    body = json.dumps(_leadgen_payload("no-such-page", "lead-orphan-1")).encode()

    resp = client.post(
        "/webhooks/facebook/leads",
        data=body,
        content_type="application/json",
        headers={"X-Hub-Signature-256": _sign(body)},
    )

    assert resp.status_code == 200
    assert Lead.query.filter_by(external_lead_id="lead-orphan-1").first() is None


def test_admin_company_settings_facebook_integration_creates_and_updates_connection(db_session, client):
    company = Company(name="Settings Co", is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()

    admin_user = User(email="admin@settingsco.com", role="admin", is_active=True, company_id=company.id)
    db_session.add(admin_user)
    db_session.commit()
    login_as(client, admin_user)

    resp = client.post(
        f"/admin/company/{company.id}/settings",
        data={
            "action_type": "facebook_integration",
            "fb_page_id": "page-999",
            "fb_page_name": "Settings Co Page",
            "fb_page_access_token": "token-abc",
            "fb_platform": "facebook",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    connections = FacebookPageConnection.query.filter_by(company_id=company.id).all()
    assert len(connections) == 1
    assert connections[0].page_id == "page-999"

    resp2 = client.post(
        f"/admin/company/{company.id}/settings",
        data={
            "action_type": "facebook_integration",
            "fb_page_id": "page-999-updated",
            "fb_page_name": "Settings Co Page",
            "fb_page_access_token": "token-xyz",
            "fb_platform": "instagram",
        },
        follow_redirects=False,
    )
    assert resp2.status_code == 302

    connections = FacebookPageConnection.query.filter_by(company_id=company.id).all()
    assert len(connections) == 1
    assert connections[0].page_id == "page-999-updated"
    assert connections[0].platform == "instagram"
