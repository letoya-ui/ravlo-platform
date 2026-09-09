"""Regression tests for two sidebar-chrome bugs reported by the user:

1. Clicking "Network" from the public marketing site nav (marketing_base.html)
   dropped visitors into the full internal dashboard shell (ravlo_base.html)
   -- an admin saw the Admin sidebar, others saw whatever ravlo_base.html's
   blueprint-based fallback happened to guess. The Network feed/post pages
   should render on the same lightweight public layout as the rest of the
   marketing site, with no internal dashboard sidebar at all, for anyone.

2. Several shared-capability pages (Payments dashboard, Booking
   availability, Elena's Content Studio) never told ravlo_base.html which
   portal/sidebar to use. Its fallback only special-cases the 'vip',
   'elena', and 'partners' blueprints -- everything else (including these
   pages' own 'payments'/'booking'/'network' blueprints) silently fell
   through to the Investor sidebar, regardless of who was actually
   visiting. A stylist or a VIP/Partner clicking Payments/Booking, or a
   Loan Officer clicking "Create Content", would see themselves swapped
   into a different role's sidebar entirely.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.salon_models import StylistProfile
from LoanMVP.models.user_model import User
from LoanMVP.models.vip_models import VIPProfile
from LoanMVP.services.payments_service import get_or_create_payment_account

from tests.conftest import login_as


def _make_company(db_session, name):
    company = Company(name=name, is_active=True)
    db_session.add(company)
    db_session.commit()
    return company


def _make_admin(db_session, email="admin@example.com"):
    company = _make_company(db_session, "Admin Co")
    user = User(email=email, role="admin", is_active=True, company_id=None)
    db_session.add(user)
    db_session.commit()
    return user


def _make_partner(db_session, email="partner@example.com"):
    company = _make_company(db_session, "Partner Co")
    user = User(email=email, role="partner", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    profile = VIPProfile(user_id=user.id, display_name="Test Partner", business_name="Test Realty", role_type="realtor")
    db_session.add(profile)
    db_session.commit()
    return user


def _make_stylist(db_session, email="stylist@example.com"):
    company = _make_company(db_session, "Salon Co")
    user = User(email=email, role="stylist", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    profile = StylistProfile(user_id=user.id, company_id=company.id, full_name="Test Stylist")
    db_session.add(profile)
    db_session.commit()
    return user, profile


def _make_loan_officer(db_session, email="lo@example.com"):
    company = _make_company(db_session, "Lending Co")
    user = User(email=email, role="loan_officer", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user


_DASHBOARD_MARKERS = ["Admin OS", "Partner Workspace", "Investor Portal", 'class="ravlo-sidebar"']


def _assert_no_dashboard_chrome(body):
    for marker in _DASHBOARD_MARKERS:
        assert marker not in body, f"unexpected dashboard chrome marker {marker!r} on the public Network page"
    assert 'class="mk-nav"' in body


# ─── Network: public marketing chrome, no dashboard sidebar ────────────────

def test_network_feed_shows_marketing_chrome_for_anonymous_visitor(client):
    resp = client.get("/network/real-estate")
    assert resp.status_code == 200
    _assert_no_dashboard_chrome(resp.get_data(as_text=True))


def test_network_feed_shows_marketing_chrome_not_admin_sidebar_for_admin(db_session, client):
    admin = _make_admin(db_session)
    login_as(client, admin)

    resp = client.get("/network/real-estate")
    assert resp.status_code == 200
    _assert_no_dashboard_chrome(resp.get_data(as_text=True))


def test_network_feed_shows_marketing_chrome_not_vip_sidebar_for_partner(db_session, client):
    partner = _make_partner(db_session)
    login_as(client, partner)

    resp = client.get("/network/real-estate")
    assert resp.status_code == 200
    _assert_no_dashboard_chrome(resp.get_data(as_text=True))


def test_network_feed_shows_marketing_chrome_for_loan_officer(db_session, client):
    officer = _make_loan_officer(db_session)
    login_as(client, officer)

    resp = client.get("/network/real-estate")
    assert resp.status_code == 200
    _assert_no_dashboard_chrome(resp.get_data(as_text=True))


def test_network_post_detail_also_uses_marketing_chrome(db_session, client):
    from LoanMVP.models.network_models import NetworkPost
    from LoanMVP.services.network_service import get_or_create_group

    partner = _make_partner(db_session, email="poster@example.com")
    group = get_or_create_group("real-estate", name="Real Estate", description="desc")
    post = NetworkPost(group_id=group.id, author_user_id=partner.id, body="Hello network")
    db_session.add(post)
    db_session.commit()

    resp = client.get(f"/network/real-estate/posts/{post.id}")
    assert resp.status_code == 200
    _assert_no_dashboard_chrome(resp.get_data(as_text=True))


# ─── Payments dashboard: correct sidebar per owner type ─────────────────────

def test_payments_dashboard_shows_stylist_sidebar_for_stylist(db_session, client):
    stylist_user, profile = _make_stylist(db_session)
    get_or_create_payment_account("stylist_profile", profile.id)
    login_as(client, stylist_user)

    resp = client.get("/payments/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert '<div class="re-user-role">Stylist</div>' in body
    assert "Investor Portal" not in body


def test_payments_dashboard_shows_partner_sidebar_for_vip(db_session, client):
    partner = _make_partner(db_session, email="payments-partner@example.com")
    login_as(client, partner)

    resp = client.get("/payments/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Partner Workspace" in body
    assert "Investor Portal" not in body


# ─── Booking availability: correct sidebar per owner type ───────────────────

def test_booking_availability_shows_stylist_sidebar_for_stylist(db_session, client):
    stylist_user, _profile = _make_stylist(db_session, email="booking-stylist@example.com")
    login_as(client, stylist_user)

    resp = client.get("/booking/availability")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert '<div class="re-user-role">Stylist</div>' in body
    assert "Investor Portal" not in body


def test_booking_availability_shows_partner_sidebar_for_vip(db_session, client):
    partner = _make_partner(db_session, email="booking-partner@example.com")
    login_as(client, partner)

    resp = client.get("/booking/availability")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Partner Workspace" in body
    assert "Investor Portal" not in body


# ─── Elena Content Studio: Loan Officer keeps their own sidebar ────────────

def test_template_studio_shows_loan_officer_sidebar_for_internal_loan_officer(db_session, client):
    officer = _make_loan_officer(db_session, email="internal-lo@example.com")
    login_as(client, officer)

    resp = client.get("/elena/template-studio")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert '<div class="re-user-role">Loan Officer</div>' in body
    assert "Partner Workspace" not in body


def test_template_studio_shows_loan_officer_sidebar_even_for_full_access_email(db_session, client):
    """officer@caughmanmason.com (FULL_LOAN_OFFICER_ACCESS_EMAILS) gets
    extra VIP-side capabilities elsewhere in the app, but that flag isn't
    which sidebar they clicked "Create Content" from -- it must not swap
    their chrome to Partner Workspace when they're on their own Lending
    OS sidebar."""
    officer = _make_loan_officer(db_session, email="officer@caughmanmason.com")
    login_as(client, officer)

    resp = client.get("/elena/template-studio")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert '<div class="re-user-role">Loan Officer</div>' in body
    assert "Partner Workspace" not in body
    assert "/loan_officer/dashboard" in body


def test_template_studio_still_shows_partner_sidebar_for_real_vip(db_session, client):
    partner = _make_partner(db_session, email="content-partner@example.com")
    login_as(client, partner)

    resp = client.get("/elena/template-studio")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Partner Workspace" in body
