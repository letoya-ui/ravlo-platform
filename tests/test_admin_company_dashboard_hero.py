"""Regression tests for the hero banner + brand promo card added to
admin/company_dashboard.html (LoanMVP/routes/admin.py's company_dashboard()):
the Broker-Owner/Admin dashboard already has real ApexCharts analytics,
so this only adds the consistent hero-photo treatment used across the
other role dashboards, plus a white-label brand promo card that should
only appear for companies actually on the white_label tier.
"""
from LoanMVP.extensions import db
from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_admin(db_session, email="admin-widgets@example.com", **company_kwargs):
    company = Company(name="Widgets Lending Co", is_active=True, **company_kwargs)
    db_session.add(company)
    db_session.commit()

    user = User(
        email=email, role="admin", is_active=True, company_id=company.id,
        first_name="Renata", onboarding_complete=True,
        ica_accepted=True, nda_accepted=True,
    )
    db_session.add(user)
    db_session.commit()
    return user, company


def test_hero_banner_shows_welcome_message(db_session, client):
    user, company = _make_admin(db_session)
    login_as(client, user)

    resp = client.get(f"/admin/company/{company.id}/dashboard")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Welcome back, Renata." in body
    assert "dash-hero" in body


def test_promo_card_hidden_for_ravlo_tier_company(db_session, client):
    user, company = _make_admin(db_session, email="admin-ravlo@example.com")
    login_as(client, user)

    body = client.get(f"/admin/company/{company.id}/dashboard").get_data(as_text=True)

    assert "Your Brand. Your Platform." not in body


def test_promo_card_shows_real_brand_for_white_label_company(db_session, client):
    user, company = _make_admin(
        db_session, email="admin-whitelabel@example.com",
        subscription_tier="white_label", brand_name="Meridian Capital Lending",
        brand_primary_color="#0F2D52", brand_tagline="Guiding Capital. Building Futures.",
    )
    login_as(client, user)

    body = client.get(f"/admin/company/{company.id}/dashboard").get_data(as_text=True)

    assert "Meridian Capital Lending" in body
    assert "GUIDING CAPITAL. BUILDING FUTURES." in body
    assert "Your Brand. Your Platform." in body
