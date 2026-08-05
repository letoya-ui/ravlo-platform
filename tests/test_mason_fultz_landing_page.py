"""Regression tests for Mason-Fultz Commercial Cleaning's public landing
page at /p/mason-fultz-cleaning.

Unlike Bonnie/John Headley/Key Signature Enterprise (which predate a live
VIPProfile and fall back to a hardcoded SLUG_STATIC_CONTEXT stub), Mason-
Fultz's account already exists, so this page is entirely DB-driven off a
real VIPProfile row -- which surfaced a real gap: _load_realtor_context()
only recognized role_type in (realtor, contractor_realtor,
insurance_realtor), so a plain "contractor" VIPProfile (cleaning,
handyman, etc.) had no live public-page path at all. These tests cover
both the gap fix and the new landing page itself.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.crm_models import Lead
from LoanMVP.models.user_model import User
from LoanMVP.models.vip_models import VIPProfile, VIPNotification


def _make_mason_fultz(db_session, email="MasonFultz45cleaningservice@gmail.com"):
    company = Company(name="Mason-Fultz Co", is_active=True)
    db_session.add(company)
    db_session.commit()
    user = User(email=email, role="partner", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    profile = VIPProfile(
        user_id=user.id,
        display_name="Mason-Fultz Commercial Cleaning",
        business_name="Mason-Fultz Commercial Cleaning",
        role_type="contractor",
        public_slug="mason-fultz-cleaning",
        marketplace_enabled="yes",
        brand_color="#1A4EA1",
        logo_url="/static/images/vip/mason_fultz_logo.png",
    )
    db_session.add(profile)
    db_session.commit()
    return user, profile


def test_plain_contractor_role_type_now_gets_a_live_public_page(db_session, client):
    """The regression this whole feature surfaced: before the fix, a
    role_type="contractor" VIPProfile fell through _load_realtor_context's
    role_type filter entirely and 404'd."""
    _make_mason_fultz(db_session)

    resp = client.get("/p/mason-fultz-cleaning")

    assert resp.status_code == 200


def test_landing_page_renders_flyer_content(db_session, client):
    _make_mason_fultz(db_session)

    resp = client.get("/p/mason-fultz-cleaning")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Mason-Fultz Commercial Cleaning" in body
    assert "A Cleaner Space." in body
    assert "A Better Impression." in body
    assert "Office &amp; Building Cleaning" in body
    assert "Restroom Sanitation" in body
    assert "Disinfecting High-Touch Surfaces" in body
    assert "Reliable &amp; Consistent" in body
    assert "High Standards" in body
    assert "Competitive Pricing" in body
    assert "Offices" in body and "Medical Facilities" in body and "Churches" in body


def test_landing_page_shows_her_logo(db_session, client):
    _make_mason_fultz(db_session)

    resp = client.get("/p/mason-fultz-cleaning")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'src="/static/images/vip/mason_fultz_logo.png"' in body
    assert "mf-nav-logo-img" in body
    assert "mf-hero-logo" in body


def test_unknown_slug_still_404s(client):
    resp = client.get("/p/not-a-real-cleaning-business")
    assert resp.status_code == 404


def test_landing_page_contact_form_creates_lead_for_owner(db_session, client):
    user, profile = _make_mason_fultz(db_session)

    resp = client.post(
        "/p/mason-fultz-cleaning/contact",
        data={
            "client_name": "Prospective Client",
            "client_email": "prospect@example.com",
            "client_phone": "615-555-9876",
            "interest": "office",
            "message": "Need weekly office cleaning for a 10-person suite.",
        },
    )

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Prospective Client" in body

    lead = Lead.query.filter_by(email="prospect@example.com").first()
    assert lead is not None
    assert lead.assigned_to == user.id

    notification = VIPNotification.query.filter_by(vip_profile_id=profile.id).first()
    assert notification is not None
    assert "Prospective Client" in notification.title


def test_landing_page_contact_form_requires_name(db_session, client):
    _make_mason_fultz(db_session)

    resp = client.post(
        "/p/mason-fultz-cleaning/contact",
        data={"client_email": "noname@example.com"},
    )

    assert resp.status_code == 200
    assert "Name is required" in resp.get_data(as_text=True)


def test_sitemap_recognizes_contractor_role_type(db_session, client):
    _make_mason_fultz(db_session)

    resp = client.get("/p/mason-fultz-cleaning/sitemap.xml")

    assert resp.status_code == 200
    assert b"mason-fultz-cleaning" in resp.data
