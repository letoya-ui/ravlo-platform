"""Regression tests for the Borrower Dashboard redesign
(LoanMVP/routes/borrower_routes.py's dashboard(), templates/borrower/dashboard.html):
the hero photo banner and a real bug found while adding it -- the primary
button, progress bar, and checklist dot were hardcoded grays (#607487 etc.)
instead of var(--accent)/var(--accent-2), so a white-label company's own
brand colors never reached their borrowers' dashboard even though the
layout's :root override set those variables correctly.
"""
from LoanMVP.extensions import db
from LoanMVP.models.admin import Company
from LoanMVP.models.loan_models import BorrowerProfile
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_borrower(db_session, email="borrower-widgets@example.com", **company_kwargs):
    company = Company(name="Widgets Lending Co", is_active=True, **company_kwargs)
    db_session.add(company)
    db_session.commit()

    user = User(
        email=email, role="borrower", is_active=True, company_id=company.id,
        first_name="Danielle", onboarding_complete=True,
        ica_accepted=True, nda_accepted=True,
    )
    db_session.add(user)
    db_session.commit()

    borrower = BorrowerProfile(user_id=user.id, full_name="Danielle Carter", email=email)
    db_session.add(borrower)
    db_session.commit()
    return user, borrower, company


def test_hero_banner_shows_welcome_message(db_session, client):
    user, borrower, company = _make_borrower(db_session)
    login_as(client, user)

    resp = client.get("/borrower/dashboard")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Welcome back, Danielle" in body
    assert "rb-hero" in body
    assert "interior_luxury.jpg" in body


def test_dashboard_buttons_use_brand_variables_not_hardcoded_gray(db_session, client):
    user, borrower, company = _make_borrower(db_session, email="borrower-colors@example.com")
    login_as(client, user)

    body = client.get("/borrower/dashboard").get_data(as_text=True)

    assert "#607487" not in body
    assert "#45586B" not in body
    assert "#8DA7C2" not in body
    assert "var(--accent)" in body


def test_promo_card_hidden_for_ravlo_tier_company(db_session, client):
    user, borrower, company = _make_borrower(db_session, email="borrower-ravlo@example.com")
    login_as(client, user)

    body = client.get("/borrower/dashboard").get_data(as_text=True)

    assert 'class="rb-card rb-promo-card"' not in body


def test_promo_card_shows_real_brand_for_white_label_company(db_session, client):
    user, borrower, company = _make_borrower(
        db_session, email="borrower-whitelabel@example.com",
        subscription_tier="white_label", brand_name="Meridian Capital Lending",
        brand_primary_color="#0F2D52", brand_tagline="Guiding Capital. Building Futures.",
    )
    login_as(client, user)

    body = client.get("/borrower/dashboard").get_data(as_text=True)

    assert 'class="rb-card rb-promo-card"' in body
    assert "Meridian Capital Lending" in body
    assert "GUIDING CAPITAL. BUILDING FUTURES." in body
