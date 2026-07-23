"""Regression tests for two fixes to the public insurance quote form
(/vip/insurance/<profile_id>/get-quote):

1. It was styled with a generic dark indigo theme with no connection to
   the VIP's own branding -- for Key Signature Enterprise (Keyona Hall,
   the only live "insurance" VIP), it looked nothing like her actual
   landing page's red/gold/black/white look. It's now themed off
   profile.brand_color, defaulting to Key Signature's red when unset
   (mirroring the profile.brand_color or <default> fallback pattern
   public_pages.py already uses for the bespoke landing pages).

2. Submitting the form only ever created a VIPNotification row (in-app),
   which is never read anywhere in the codebase -- so partners got no
   real signal that a quote request came in. This adds a best-effort
   email to the VIP (mirroring test_lead_capture_email_notification.py's
   pattern for the similar lead-capture gap) plus an optional client
   confirmation email.
"""
from LoanMVP.extensions import mail
from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User
from LoanMVP.models.vip_models import VIPProfile


def _make_insurance_vip(db_session, email="agent@example.com", brand_color=None,
                         company_name="Quote Form Test Co", public_slug="quote-form-test"):
    company = Company(name=company_name, is_active=True)
    db_session.add(company)
    db_session.commit()
    user = User(email=email, role="partner", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    profile = VIPProfile(
        user_id=user.id,
        display_name="Test Insurance Agency",
        business_name="Test Insurance Agency",
        role_type="insurance",
        public_slug=public_slug,
        marketplace_enabled="yes",
        brand_color=brand_color,
    )
    db_session.add(profile)
    db_session.commit()
    return user, profile


def test_quote_form_defaults_to_key_signature_red_when_no_brand_color_set(db_session, client):
    _, profile = _make_insurance_vip(db_session, email="nocolor@example.com")

    resp = client.get(f"/vip/insurance/{profile.id}/get-quote")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "--iq-accent: #B3122A" in body


def test_quote_form_uses_profiles_own_brand_color_when_set(db_session, client):
    _, profile = _make_insurance_vip(db_session, email="ownercolor@example.com",
                                      brand_color="#2563EB", public_slug="owner-color-test")

    resp = client.get(f"/vip/insurance/{profile.id}/get-quote")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "--iq-accent: #2563EB" in body


def test_submitting_quote_request_emails_the_vip(db_session, client):
    agent, profile = _make_insurance_vip(db_session, email="notifyme@example.com",
                                          public_slug="notify-me-test")

    with mail.record_messages() as outbox:
        resp = client.post(
            f"/vip/insurance/{profile.id}/get-quote",
            data={
                "client_name": "Quote Seeker",
                "client_email": "seeker@example.com",
                "client_phone": "615-555-0100",
                "line": "auto",
            },
        )

    assert resp.status_code == 200
    agent_emails = [m for m in outbox if m.recipients == ["notifyme@example.com"]]
    assert len(agent_emails) == 1
    assert "Quote Seeker" in agent_emails[0].body
    assert "seeker@example.com" in agent_emails[0].body
    assert "615-555-0100" in agent_emails[0].body


def test_submitting_quote_request_confirms_with_the_client_when_email_given(db_session, client):
    _, profile = _make_insurance_vip(db_session, email="agent2@example.com",
                                      public_slug="client-confirm-test")

    with mail.record_messages() as outbox:
        client.post(
            f"/vip/insurance/{profile.id}/get-quote",
            data={"client_name": "Confirm Me", "client_email": "confirmme@example.com", "line": "home"},
        )

    client_emails = [m for m in outbox if m.recipients == ["confirmme@example.com"]]
    assert len(client_emails) == 1
    assert "Confirm Me" in client_emails[0].body


def test_submitting_quote_request_without_client_email_only_notifies_the_vip(db_session, client):
    _, profile = _make_insurance_vip(db_session, email="agent3@example.com",
                                      public_slug="no-client-email-test")

    with mail.record_messages() as outbox:
        client.post(
            f"/vip/insurance/{profile.id}/get-quote",
            data={"client_name": "No Email Client", "line": "auto"},
        )

    assert len(outbox) == 1
    assert outbox[0].recipients == ["agent3@example.com"]
