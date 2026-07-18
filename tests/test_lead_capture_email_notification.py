"""Regression tests for emailing VIP partners about new leads.

Before this change, /p/<slug>/contact only created Lead/ElenaClient rows
and (for live VIPProfile pages) an in-app VIPNotification -- there was no
email. Partners using the SLUG_STATIC_CONTEXT fallback (Bonnie, Keyona,
John Headley) got no notification of any kind, since the VIPNotification
is only created when profile_id is set, which static-context pages never
have. This adds a best-effort email to whoever owns the page so a new
lead is never silently missed.
"""
from LoanMVP.extensions import mail
from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User
from LoanMVP.models.vip_models import VIPProfile


def test_static_context_page_emails_the_owner(db_session, client):
    """Bonnie's page has no live VIPProfile, so it relies on
    SLUG_OWNER_EMAILS to find her account for the email recipient."""
    company = Company(name="Bonnie Email Co", is_active=True)
    db_session.add(company)
    db_session.commit()
    bonnie = User(email="Bonniesellsochomes@gmail.com", role="partner", is_active=True, company_id=company.id)
    db_session.add(bonnie)
    db_session.commit()

    with mail.record_messages() as outbox:
        resp = client.post(
            "/p/bonnie-sells-oc-homes/contact",
            data={
                "client_name": "Prospective Buyer",
                "client_email": "buyer@example.com",
                "client_phone": "555-000-1111",
                "interest": "buyer",
                "message": "Looking for a home in Orange County.",
            },
        )

    assert resp.status_code == 200
    assert len(outbox) == 1
    sent = outbox[0]
    assert sent.recipients == ["Bonniesellsochomes@gmail.com"]
    assert "Prospective Buyer" in sent.body
    assert "buyer@example.com" in sent.body
    assert "555-000-1111" in sent.body


def test_live_vip_profile_page_emails_its_owner(db_session, client):
    company = Company(name="Realtor Email Co", is_active=True)
    db_session.add(company)
    db_session.commit()
    realtor = User(email="livepage@example.com", role="partner", is_active=True, company_id=company.id)
    db_session.add(realtor)
    db_session.commit()

    profile = VIPProfile(
        user_id=realtor.id,
        display_name="Live Page Realtor",
        role_type="realtor",
        public_slug="live-page-realtor",
        marketplace_enabled="yes",
    )
    db_session.add(profile)
    db_session.commit()

    with mail.record_messages() as outbox:
        resp = client.post(
            "/p/live-page-realtor/contact",
            data={
                "client_name": "Another Buyer",
                "client_email": "another@example.com",
                "interest": "buyer",
            },
        )

    assert resp.status_code == 200
    assert len(outbox) == 1
    assert outbox[0].recipients == ["livepage@example.com"]


def test_missing_owner_does_not_break_lead_capture(client):
    """No matching User for the static-context owner email -- lead capture
    must still succeed even though there's no one to email."""
    resp = client.post(
        "/p/john-headley/contact",
        data={"client_name": "No Owner Yet", "client_email": "noowner@example.com"},
    )

    assert resp.status_code == 200
    assert "No Owner Yet" in resp.get_data(as_text=True)
