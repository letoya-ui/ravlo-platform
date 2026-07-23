"""Regression tests for the shared "want your own page" CTA included at
the bottom of every bespoke partner landing page. Submissions create a
BusinessInquiry the same way every other public lead-capture form in this
codebase does (marketing_routes.py's contact/lending_os_lead pattern),
tagged plan_interest="white_label" and inquiry_type="license_application"
so it lands directly in the existing Account Executive deal pipeline
(account_executive.py filters on inquiry_type == "license_application")
rather than inventing a new, disconnected inbox.
"""
from LoanMVP.models.admin import Company, BusinessInquiry
from LoanMVP.models.user_model import User
from LoanMVP.models.vip_models import VIPProfile
from LoanMVP.models.salon_models import StylistProfile

from tests.conftest import login_as


def _make_live_realtor(db_session, slug="generic-realtor-test", email="genericrealtor@example.com"):
    company = Company(name="Test Realty Co", is_active=True)
    db_session.add(company)
    db_session.commit()
    user = User(email=email, role="partner", is_active=True, company_id=company.id,
                first_name="Generic", last_name="Realtor")
    db_session.add(user)
    db_session.commit()
    profile = VIPProfile(user_id=user.id, display_name="Generic Realtor", role_type="realtor",
                          public_slug=slug, marketplace_enabled="yes")
    db_session.add(profile)
    db_session.commit()
    return profile


def _make_stylist_with_slug(db_session, slug="gotstyles-cta-test", email="stylist-cta@example.com"):
    company = Company(name="GotStyles CTA Test", is_active=True)
    db_session.add(company)
    db_session.commit()
    user = User(email=email, role="stylist", is_active=True, company_id=company.id,
                first_name="Stylist", last_name="Test")
    db_session.add(user)
    db_session.commit()
    profile = StylistProfile(user_id=user.id, company_id=company.id, full_name="GotStyles CTA Test",
                              email=email, public_slug=slug)
    db_session.add(profile)
    db_session.commit()
    return profile


def test_cta_renders_on_bonnie_landing_page(client):
    resp = client.get("/p/bonnie-sells-oc-homes")
    body = resp.get_data(as_text=True)
    assert "Want a page like this for your business?" in body
    assert 'action="/request-my-own-page"' in body


def test_cta_renders_on_john_headley_landing_page(client):
    resp = client.get("/p/john-headley")
    body = resp.get_data(as_text=True)
    assert "Want a page like this for your business?" in body


def test_cta_renders_on_key_signature_landing_page(client):
    resp = client.get("/p/key-signature-enterprise")
    body = resp.get_data(as_text=True)
    assert "Want a page like this for your business?" in body


def test_cta_renders_on_generic_realtor_landing_page(db_session, client):
    _make_live_realtor(db_session)
    resp = client.get("/p/generic-realtor-test")
    body = resp.get_data(as_text=True)
    assert "Want a page like this for your business?" in body


def test_cta_renders_on_gotstyles_landing_page(db_session, client):
    _make_stylist_with_slug(db_session)
    resp = client.get("/salon/gotstyles-cta-test")
    body = resp.get_data(as_text=True)
    assert "Want a page like this for your business?" in body


def test_submit_creates_business_inquiry_in_ae_pipeline(db_session, client):
    resp = client.post("/request-my-own-page", data={
        "name": "Jamie Prospect",
        "email": "jamie@example.com",
        "phone": "555-1212",
        "business_type": "Nail Salon",
        "source_page": "Generic Realtor",
    }, follow_redirects=True)

    assert resp.status_code == 200
    assert "We&#39;ll be in touch shortly." in resp.get_data(as_text=True) or "in touch shortly" in resp.get_data(as_text=True)

    row = BusinessInquiry.query.filter_by(email="jamie@example.com").first()
    assert row is not None
    assert row.inquiry_type == "license_application"
    assert row.plan_interest == "white_label"
    assert row.ae_stage == "prospect"
    assert row.assigned_ae_id is None
    assert row.contact_name == "Jamie Prospect"
    assert row.business_type == "Nail Salon"
    assert "Generic Realtor" in row.notes


def test_submit_requires_name_and_email(db_session, client):
    resp = client.post("/request-my-own-page", data={
        "name": "", "email": "", "business_type": "Salon",
    }, follow_redirects=True)

    assert resp.status_code == 200
    assert BusinessInquiry.query.filter_by(business_type="Salon").count() == 0


def test_submit_does_not_create_duplicate_for_same_email(db_session, client):
    for _ in range(2):
        client.post("/request-my-own-page", data={
            "name": "Dupe Prospect", "email": "dupe@example.com", "business_type": "Spa",
        }, follow_redirects=True)

    assert BusinessInquiry.query.filter_by(email="dupe@example.com").count() == 1


def test_white_label_request_shows_up_in_ae_prospect_pool(db_session, client):
    # An inquiry created with assigned_ae_id=None (exactly what
    # request_own_page() creates) lands in the unclaimed prospect pool
    # any AE can pick up (account_executive.py's /prospects route), not
    # the main /deals pipeline view -- that one only shows deals already
    # assigned to the logged-in AE. Created directly via the ORM here
    # (mirroring test_account_executive.py's _make_deal helper) rather
    # than through an anonymous POST to /request-my-own-page first -- an
    # anonymous request earlier in this same test function would cache
    # Flask-Login's per-request user resolution as anonymous on Flask's
    # `g` (bound to this test's nested app context, which persists for
    # the whole test function), so the later login_as() below would
    # appear to have no effect. See test_stylist.py's identical note for
    # the two-login variant of this same test-harness quirk.
    company = Company.query.filter_by(name="Ravlo").first()
    if not company:
        company = Company(name="Ravlo", is_active=True)
        db_session.add(company)
        db_session.commit()
    ae = User(email="ae-cta@ravlohq.com", role="account_executive", is_active=True, company_id=company.id,
              first_name="Alex", last_name="Exec")
    db_session.add(ae)
    db_session.commit()

    db_session.add(BusinessInquiry(
        inquiry_type="license_application",
        company_name="Barbershop",
        contact_name="New Prospect",
        email="newprospect@example.com",
        business_type="Barbershop",
        plan_interest="white_label",
        status="new",
        ae_stage="prospect",
        assigned_ae_id=None,
    ))
    db_session.commit()

    login_as(client, ae)
    resp = client.get("/account-executive/prospects")

    assert resp.status_code == 200
    assert "Barbershop" in resp.get_data(as_text=True) or "New Prospect" in resp.get_data(as_text=True)
