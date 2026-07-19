"""Regression tests for White Label branding + the Demo Center variant
toggle.

Covers: LoanMVP/utils/branding.py's effective_brand() gating logic, the
DEMO_VARIANTS-parameterized ensure_demo_environment() creating a fully
separate "Meridian Capital Lending" company for the white_label variant,
and the demo_center/demo_login routes threading the chosen variant all
the way through to which branding actually renders in the sidebar.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User
from LoanMVP.services.demo_environment_service import (
    DEMO_VARIANTS,
    ensure_demo_environment,
)
from LoanMVP.utils.branding import effective_brand

from tests.conftest import login_as


def _make_staff(db_session, email, role="executive"):
    company = Company.query.filter_by(name="Staff Co").first()
    if not company:
        company = Company(name="Staff Co", is_active=True)
        db_session.add(company)
        db_session.commit()
    user = User(email=email, role=role, company_id=company.id, is_active=True)
    db_session.add(user)
    db_session.commit()
    return user


# ---------------------------------------------------------------------------
# effective_brand()
# ---------------------------------------------------------------------------

def test_effective_brand_with_no_company_falls_back_to_ravlo():
    brand = effective_brand(None)
    assert (brand.name, brand.mark) == ("Ravlo", "RV")
    assert brand.tagline is None


def test_effective_brand_ignores_brand_fields_on_non_white_label_tier(db_session):
    company = Company(
        name="Some Lender",
        is_active=True,
        subscription_tier="enterprise",
        brand_name="Some Lender Co",
        brand_logo_initials="SL",
        brand_primary_color="#123456",
    )
    db_session.add(company)
    db_session.commit()

    brand = effective_brand(company)
    assert (brand.name, brand.mark) == ("Ravlo", "RV")
    assert brand.primary != "#123456"


def test_effective_brand_falls_back_when_tier_set_but_brand_name_never_configured(db_session):
    company = Company(name="Unbranded Lender", is_active=True, subscription_tier="white_label")
    db_session.add(company)
    db_session.commit()

    brand = effective_brand(company)
    assert (brand.name, brand.mark) == ("Ravlo", "RV")


def test_effective_brand_returns_company_branding_when_white_label_and_configured(db_session):
    company = Company(
        name="Meridian Capital Lending",
        is_active=True,
        subscription_tier="white_label",
        brand_name="Meridian Capital",
        brand_logo_initials="MC",
        brand_primary_color="#0F2D52",
        brand_secondary_color="#0E7C66",
        brand_accent_color="#C9A227",
        brand_tagline="Guiding Capital. Building Futures.",
    )
    db_session.add(company)
    db_session.commit()

    brand = effective_brand(company)
    assert brand.name == "Meridian Capital"
    assert brand.mark == "MC"
    assert brand.primary == "#0F2D52"
    assert brand.accent == "#C9A227"
    assert brand.tagline == "Guiding Capital. Building Futures."


def test_effective_brand_derives_mark_from_name_when_initials_not_set(db_session):
    company = Company(
        name="Acme Lending",
        is_active=True,
        subscription_tier="white_label",
        brand_name="Acme Capital Partners",
    )
    db_session.add(company)
    db_session.commit()

    brand = effective_brand(company)
    assert brand.name == "Acme Capital Partners"
    assert brand.mark == "AC"


def test_effective_brand_falls_back_to_ravlo_colors_when_white_label_colors_unset(db_session):
    company = Company(
        name="No Palette Lending",
        is_active=True,
        subscription_tier="white_label",
        brand_name="No Palette Lending Co",
    )
    db_session.add(company)
    db_session.commit()

    brand = effective_brand(company)
    from LoanMVP.utils.branding import RAVLO_BRAND_PRIMARY, RAVLO_BRAND_ACCENT
    assert brand.primary == RAVLO_BRAND_PRIMARY
    assert brand.accent == RAVLO_BRAND_ACCENT
    assert brand.tagline is None


# ---------------------------------------------------------------------------
# ensure_demo_environment() variants
# ---------------------------------------------------------------------------

def test_ensure_demo_environment_defaults_to_ravlo_variant(db_session):
    demo_users = ensure_demo_environment()

    company = demo_users["admin"].company
    assert company.name == DEMO_VARIANTS["ravlo"]["company_name"]
    assert company.subscription_tier == "enterprise"
    assert company.brand_name is None


def test_ensure_demo_environment_white_label_variant_creates_distinct_branded_company(db_session):
    demo_users = ensure_demo_environment("white_label")

    company = demo_users["loan_officer"].company
    assert company.name == "Meridian Capital Lending"
    assert company.subscription_tier == "white_label"
    assert company.brand_name == "Meridian Capital"
    assert company.brand_logo_initials == "MC"
    assert company.brand_primary_color == "#0F2D52"
    assert company.brand_secondary_color == "#0E7C66"
    assert company.brand_accent_color == "#C9A227"
    assert company.brand_tagline == "Guiding Capital. Building Futures."

    brand = effective_brand(company)
    assert (brand.name, brand.mark) == ("Meridian Capital", "MC")
    assert brand.primary == "#0F2D52"
    assert brand.accent == "#C9A227"
    assert brand.tagline == "Guiding Capital. Building Futures."
    assert brand.logo_url == "images/demo/meridian_capital_logo.png"


def test_ensure_demo_environment_variants_do_not_share_data(db_session):
    ravlo_users = ensure_demo_environment("ravlo")
    wl_users = ensure_demo_environment("white_label")

    assert ravlo_users["loan_officer"].company_id != wl_users["loan_officer"].company_id
    assert ravlo_users["loan_officer"].email != wl_users["loan_officer"].email
    assert Company.query.filter_by(name="Ravlo Demo Co").count() == 1
    assert Company.query.filter_by(name="Meridian Capital Lending").count() == 1


def test_ensure_demo_environment_unknown_variant_key_falls_back_to_ravlo(db_session):
    demo_users = ensure_demo_environment("not-a-real-variant")

    assert demo_users["admin"].company.name == DEMO_VARIANTS["ravlo"]["company_name"]


def test_ensure_demo_environment_self_heals_drifted_branding(db_session):
    ensure_demo_environment("white_label")
    company = Company.query.filter_by(name="Meridian Capital Lending").first()
    company.brand_name = "Wrong Name"
    company.subscription_tier = "enterprise"
    company.brand_primary_color = "#000000"
    company.brand_tagline = "Wrong tagline"
    company.brand_logo_url = "images/wrong.png"
    from LoanMVP.extensions import db
    db.session.commit()

    ensure_demo_environment("white_label")

    healed = Company.query.filter_by(name="Meridian Capital Lending").first()
    assert healed.subscription_tier == "white_label"
    assert healed.brand_name == "Meridian Capital"
    assert healed.brand_primary_color == "#0F2D52"
    assert healed.brand_tagline == "Guiding Capital. Building Futures."
    assert healed.brand_logo_url == "images/demo/meridian_capital_logo.png"


# ---------------------------------------------------------------------------
# Demo Center variant toggle (route + template)
# ---------------------------------------------------------------------------

def test_demo_center_defaults_to_ravlo_variant(db_session, client):
    staff = _make_staff(db_session, "letoya@ravlohq.com")
    login_as(client, staff)

    resp = client.get("/admin/demo-center")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "DEMO COMPANY" in body
    assert "Meridian Capital (White Label)" in body


def test_demo_center_shows_white_label_callout_when_selected(db_session, client):
    staff = _make_staff(db_session, "letoya@ravlohq.com")
    login_as(client, staff)

    resp = client.get("/admin/demo-center?variant=white_label")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "use this when a prospect is asking about White Label" in body


def test_demo_center_invalid_variant_falls_back_to_ravlo(db_session, client):
    staff = _make_staff(db_session, "letoya@ravlohq.com")
    login_as(client, staff)

    resp = client.get("/admin/demo-center?variant=not-a-real-variant")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "use this when a prospect is asking about White Label" not in body


# ---------------------------------------------------------------------------
# demo_login threads the chosen variant through to the actual dashboard
# ---------------------------------------------------------------------------

def test_demo_login_white_label_variant_logs_into_meridian_company(db_session, client):
    staff = _make_staff(db_session, "letoya@ravlohq.com")
    login_as(client, staff)

    resp = client.post(
        "/admin/demo-login/loan_officer",
        data={"variant": "white_label"},
        follow_redirects=False,
    )

    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert sess.get("demo_variant") == "white_label"

    demo_lo = User.query.filter_by(email="demo-loanofficer@demo.meridiancapital.com").first()
    assert demo_lo is not None
    assert demo_lo.company.brand_name == "Meridian Capital"
    with client.session_transaction() as sess:
        assert sess.get("_user_id") == str(demo_lo.id)


def test_demo_login_white_label_variant_renders_meridian_branding_in_sidebar(db_session, client):
    staff = _make_staff(db_session, "sandra@ravlohq.com")
    login_as(client, staff)

    login_resp = client.post(
        "/admin/demo-login/loan_officer",
        data={"variant": "white_label"},
        follow_redirects=False,
    )
    dashboard_resp = client.get(login_resp.headers["Location"])

    assert dashboard_resp.status_code == 200
    body = dashboard_resp.get_data(as_text=True)
    assert "images/demo/meridian_capital_logo.png" in body
    assert 'alt="Meridian Capital"' in body


def test_demo_login_missing_variant_defaults_to_ravlo_branding(db_session, client):
    staff = _make_staff(db_session, "jamaine.caughman@ravlohq.com")
    login_as(client, staff)

    login_resp = client.post(
        "/admin/demo-login/loan_officer",
        follow_redirects=False,
    )
    dashboard_resp = client.get(login_resp.headers["Location"])

    assert dashboard_resp.status_code == 200
    body = dashboard_resp.get_data(as_text=True)
    assert "RAVLO" in body
    assert ">RV<" in body
    with client.session_transaction() as sess:
        assert sess.get("demo_variant") == "ravlo"


# ---------------------------------------------------------------------------
# A real (non-demo) white-label company that hasn't uploaded a logo image
# yet still gets the text name/mark treatment, not a broken <img> tag --
# logo_url is optional, most self-serve companies won't have one.
# ---------------------------------------------------------------------------

def test_white_label_company_without_logo_url_falls_back_to_text_mark(db_session, client):
    from LoanMVP.models.loan_officer_model import LoanOfficerProfile

    company = Company(
        name="Textmark Lending",
        is_active=True,
        subscription_tier="white_label",
        brand_name="Textmark Capital",
        brand_logo_initials="TC",
        brand_primary_color="#112233",
        brand_accent_color="#445566",
        max_users=10,
    )
    db_session.add(company)
    db_session.commit()

    user = User(
        email="lo@textmark-lending.com",
        role="loan_officer",
        is_active=True,
        company_id=company.id,
        nda_accepted=True,
        ica_accepted=True,
        onboarding_complete=True,
        invite_accepted=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.add(LoanOfficerProfile(user_id=user.id, name="Lonnie Officer", email=user.email))
    db_session.commit()

    login_as(client, user)
    resp = client.get("/loan_officer/dashboard")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "TEXTMARK CAPITAL" in body
    assert ">TC<" in body


# ---------------------------------------------------------------------------
# Executive sidebar's "Demo Center" link hits a SEPARATE route
# (executive.demo_center in executive_new.py) that renders the same
# admin/demo_center.html template. That route originally never passed
# demo_variants/variant into the template context, so Jinja's
# "{% if can_use_demo_login and demo_variants %}" gate silently evaluated
# false and the whole toggle disappeared for executives -- even though the
# exact same feature worked fine on admin.demo_center. The toggle's own
# links were also hardcoded to admin.demo_center instead of following
# whichever namespace rendered the page.
# ---------------------------------------------------------------------------

def _make_ravlo_executive(db_session, email="letoya@ravlohq.com", role="executive"):
    company = Company.query.filter_by(name="Ravlo").first()
    if not company:
        company = Company(name="Ravlo", email_domain="ravlohq.com", is_active=True, subscription_tier="enterprise")
        db_session.add(company)
        db_session.commit()
    user = User(email=email, role=role, company_id=company.id, is_active=True)
    db_session.add(user)
    db_session.commit()
    return user


def test_executive_demo_center_shows_demo_company_toggle(db_session, client):
    exec_user = _make_ravlo_executive(db_session)
    login_as(client, exec_user)

    resp = client.get("/executive/demo-center")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "DEMO COMPANY" in body
    assert "Meridian Capital (White Label)" in body


def test_executive_demo_center_white_label_variant_shows_callout(db_session, client):
    exec_user = _make_ravlo_executive(db_session)
    login_as(client, exec_user)

    resp = client.get("/executive/demo-center?variant=white_label")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "use this when a prospect is asking about White Label" in body


def test_executive_demo_center_toggle_links_stay_in_executive_namespace(db_session, client):
    exec_user = _make_ravlo_executive(db_session)
    login_as(client, exec_user)

    resp = client.get("/executive/demo-center")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "/executive/demo-center?variant=white_label" in body
    assert "/admin/demo-center?variant=white_label" not in body


def test_executive_demo_center_login_form_respects_white_label_variant(db_session, client):
    exec_user = _make_ravlo_executive(db_session)
    login_as(client, exec_user)

    resp = client.get("/executive/demo-center?variant=white_label")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'name="variant" value="white_label"' in body
    assert "re-brand-logo-badge" not in body
