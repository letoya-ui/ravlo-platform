"""Regression tests for Keyona Hall's "Key Signature Enterprise" public
landing page and lead capture.

Two related fixes:
1. _PARTNER_DASHBOARD_PRESETS["keyonahall@icloud.com"] in auth.py had
   completely wrong business data ("Keyona Hall Insurance & Realty" in
   New York, insurance+realtor only) -- her real business is "Key
   Signature Enterprise" in Nashville, doing real estate, property
   management, and insurance.
2. She had no public marketing landing page at all. This adds one at
   /p/key-signature-enterprise following the same white-label
   SLUG_TEMPLATES/SLUG_OWNER_EMAILS/SLUG_STATIC_CONTEXT pattern already
   used for john-headley, so leads captured on the page are routed to
   her real account's CRM even without a live VIPProfile row.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.crm_models import Lead
from LoanMVP.models.user_model import User
from LoanMVP.routes.auth import _PARTNER_DASHBOARD_PRESETS


def test_keyona_preset_has_correct_business_info():
    preset = _PARTNER_DASHBOARD_PRESETS["keyonahall@icloud.com"]
    assert preset["company"] == "Key Signature Enterprise"
    assert "Nashville" in preset["service_area"]
    assert "real estate" in preset["type"].lower()
    assert "property management" in preset["type"].lower()
    assert "insurance" in preset["type"].lower()
    # category stays "insurance" so _default_vip_role_for_partner still
    # resolves the existing "insurance_realtor" combined dashboard role.
    assert preset["category"] == "insurance"


def test_landing_page_renders_flyer_content(client):
    resp = client.get("/p/key-signature-enterprise")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "KEY" in body and "SIGNATURE" in body
    assert "One Company. Multiple Solutions." in body
    assert "Real Estate" in body
    assert "Property Management" in body
    assert "Insurance Solutions" in body
    assert "Homebuyers" in body
    assert "Landlords" in body
    assert "Business Owners" in body
    assert "Tenants" in body
    assert "615-818-9438" in body
    assert "Keyona@keysignatureenterprise.com" in body


def test_landing_page_has_get_quote_button_wired_to_insurance_interest(client):
    resp = client.get("/p/key-signature-enterprise")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Get a Quote" in body
    assert "ksScrollToQuote" in body
    # Clicking it pre-selects the "insurance" option in the contact form.
    assert "interestField.value = 'insurance'" in body
    assert 'value="insurance"' in body


def test_landing_page_contact_form_creates_lead_for_keyona(db_session, client):
    company = Company(name="Key Signature Co", is_active=True)
    db_session.add(company)
    db_session.commit()
    keyona = User(email="keyonahall@icloud.com", role="partner", is_active=True, company_id=company.id)
    db_session.add(keyona)
    db_session.commit()

    resp = client.post(
        "/p/key-signature-enterprise/contact",
        data={
            "client_name": "Prospective Client",
            "client_email": "prospect@example.com",
            "client_phone": "615-555-1234",
            "interest": "property_management",
            "message": "Looking for a property manager for my rental.",
        },
    )

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Prospective Client" in body

    lead = Lead.query.filter_by(email="prospect@example.com").first()
    assert lead is not None
    assert lead.assigned_to == keyona.id


def test_landing_page_contact_form_requires_name(client):
    resp = client.post(
        "/p/key-signature-enterprise/contact",
        data={"client_email": "noname@example.com"},
    )

    assert resp.status_code == 200
    assert "Name is required" in resp.get_data(as_text=True)
