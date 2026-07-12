# LoanMVP/routes/facebook_leads_webhook.py
"""Facebook / Instagram Lead Ads webhook receiver.

One shared Ravlo-owned Meta App handles the webhook subscription (App
Secret for signature verification, verify token for the one-time GET
handshake); each company connects its own Page separately (see
FacebookPageConnection, configured from the admin Workspace Settings page)
so an incoming event's page_id tells us which company's Lead pipeline to
drop the lead into.

Meta's leadgen webhook event only carries a leadgen_id reference, not the
actual field data -- we call back to the Graph API with the company's
stored Page Access Token to fetch name/email/phone.
"""
import hashlib
import hmac
import logging

import requests
from flask import Blueprint, current_app, jsonify, request

from LoanMVP.extensions import db, csrf
from LoanMVP.models.crm_models import FacebookPageConnection, Lead
from LoanMVP.routes.admin import _company_loan_officers
from LoanMVP.routes.crm_comm_routes import _choose_auto_assignee, _lead_source_record

facebook_leads_webhook_bp = Blueprint(
    "facebook_leads_webhook", __name__, url_prefix="/webhooks/facebook"
)

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


@facebook_leads_webhook_bp.get("/leads")
def verify_webhook():
    """Meta's one-time webhook subscription handshake."""
    verify_token = current_app.config.get("FACEBOOK_WEBHOOK_VERIFY_TOKEN", "")
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge", "")

    if mode == "subscribe" and verify_token and token == verify_token:
        return challenge, 200

    return "Verification failed", 403


def _valid_signature(app_secret: str, raw_body: bytes, signature_header: str) -> bool:
    if not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        key=app_secret.encode("utf-8"), msg=raw_body, digestmod=hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header[len("sha256=") :])


def _fetch_lead_fields(leadgen_id: str, page_access_token: str) -> dict:
    resp = requests.get(
        f"{GRAPH_API_BASE}/{leadgen_id}",
        params={"access_token": page_access_token},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    fields = {}
    for item in data.get("field_data") or []:
        name = (item.get("name") or "").strip().lower()
        values = item.get("values") or []
        if name and values:
            fields[name] = values[0]
    return fields


def _lead_name(fields: dict) -> str:
    if fields.get("full_name"):
        return fields["full_name"]
    first = fields.get("first_name", "")
    last = fields.get("last_name", "")
    combined = f"{first} {last}".strip()
    return combined or "Facebook Lead"


def _process_leadgen_change(page_id: str, leadgen_id: str, form_id: str | None) -> None:
    if Lead.query.filter_by(external_lead_id=leadgen_id).first():
        return

    connection = FacebookPageConnection.query.filter_by(
        page_id=page_id, is_active=True
    ).first()
    if not connection:
        logging.warning(
            "[facebook_leads_webhook] no active connection for page_id=%s", page_id
        )
        return

    fields = _fetch_lead_fields(leadgen_id, connection.page_access_token)

    source_label = "Instagram" if connection.platform == "instagram" else "Facebook"
    source = _lead_source_record(source_label)

    officers = _company_loan_officers(connection.company_id)
    officer = _choose_auto_assignee(officers)

    lead = Lead(
        name=_lead_name(fields),
        email=fields.get("email"),
        phone=fields.get("phone_number"),
        message=f"{source_label} Lead Ad" + (f" — form {form_id}" if form_id else ""),
        source_id=source.id,
        external_lead_id=leadgen_id,
        assigned_officer_id=getattr(officer, "id", None),
        assigned_to=getattr(officer, "user_id", None),
        status="New",
    )
    db.session.add(lead)
    db.session.commit()


@facebook_leads_webhook_bp.post("/leads")
@csrf.exempt
def receive_lead_event():
    app_secret = current_app.config.get("FACEBOOK_APP_SECRET", "")
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not app_secret:
        current_app.logger.error(
            "[facebook_leads_webhook] FACEBOOK_APP_SECRET is not set — webhook rejected"
        )
        return jsonify({"error": "Webhook secret not configured."}), 500

    if not _valid_signature(app_secret, request.get_data(), signature):
        current_app.logger.warning("[facebook_leads_webhook] invalid signature")
        return jsonify({"error": "Invalid signature."}), 403

    payload = request.get_json(silent=True) or {}

    for entry in payload.get("entry") or []:
        page_id = entry.get("id")
        for change in entry.get("changes") or []:
            if change.get("field") != "leadgen":
                continue
            value = change.get("value") or {}
            leadgen_id = value.get("leadgen_id")
            if not page_id or not leadgen_id:
                continue
            try:
                _process_leadgen_change(page_id, leadgen_id, value.get("form_id"))
            except Exception:
                db.session.rollback()
                current_app.logger.exception(
                    "[facebook_leads_webhook] failed to process leadgen_id=%s", leadgen_id
                )

    # Always ack 200 so Meta doesn't retry-storm us over application bugs
    # (same reasoning LoanMVP/routes/billing_webhook.py uses for Stripe).
    return "EVENT_RECEIVED", 200
