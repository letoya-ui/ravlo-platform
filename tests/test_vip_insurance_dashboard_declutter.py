"""Regression tests for decluttering the VIP insurance/insurance_realtor
dashboard (LoanMVP/templates/vip/insurance/dashboard.html).

Keyona Hall (the real "Key Signature Enterprise" combined insurance +
realtor account) gave direct feedback that the dashboard felt cluttered.
Before this change, the same 5-7 action buttons appeared twice (topbar
and a duplicate hero-panel row), the same request/quote counts appeared
in three separate places (stat cards, a CRM summary card, and a full
list section), and the sidebar had two nearly-identical "add a listing"
panels (MLS Entry, Listing Feed). This test file locks in that the
duplication is gone while every distinct piece of functionality still
renders somewhere on the page.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.crm_models import Partner
from LoanMVP.models.user_model import User
from LoanMVP.models.vip_models import VIPProfile

from tests.conftest import login_as


def _make_combined_partner(db_session, email="keyonahall@icloud.com"):
    company = Company(name="Key Signature Enterprise Co", is_active=True)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role="partner", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    db_session.add(Partner(
        user_id=user.id,
        name="Keyona Hall",
        company="Key Signature Enterprise",
        category="insurance",
        type="Real Estate, Property Management & Insurance",
        subscription_tier="premium",
    ))
    db_session.commit()

    profile = VIPProfile(
        user_id=user.id,
        display_name="Key Signature Enterprise",
        role_type="insurance_realtor",
        public_slug="key-signature-enterprise-declutter",
        marketplace_enabled="yes",
    )
    db_session.add(profile)
    db_session.commit()
    return user, profile


def _make_plain_insurance_partner(db_session, email="insurance-only@example.com"):
    company = Company(name="Plain Insurance Co", is_active=True)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role="partner", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    db_session.add(Partner(
        user_id=user.id,
        name="Ida Insurance",
        company="Ida Insurance Agency",
        category="insurance",
        type="Insurance",
        subscription_tier="premium",
    ))
    db_session.commit()

    profile = VIPProfile(
        user_id=user.id,
        display_name="Ida Insurance Agency",
        role_type="insurance",
        public_slug="ida-insurance-agency",
        marketplace_enabled="yes",
    )
    db_session.add(profile)
    db_session.commit()
    return user, profile


def test_combined_dashboard_renders_without_duplicate_action_row(db_session, client):
    user, _profile = _make_combined_partner(db_session)
    login_as(client, user)

    resp = client.get("/vip/insurance")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # The old hero-panel action row is gone entirely.
    assert "combo-hero-actions" not in body
    # "New Quote Request" now appears exactly once (topbar only), not twice.
    assert body.count("New Quote Request") == 1


def test_combined_dashboard_has_no_separate_client_workspaces_row(db_session, client):
    user, _profile = _make_combined_partner(db_session)
    login_as(client, user)

    resp = client.get("/vip/insurance")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Separate Client Workspaces" not in body
    assert "Request Inbox" not in body
    # The consolidated recent-contacts panel is present instead.
    assert "Recent Contacts" in body


def test_combined_dashboard_merges_requests_into_one_tabbed_panel(db_session, client):
    user, _profile = _make_combined_partner(db_session)
    login_as(client, user)

    resp = client.get("/vip/insurance")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Lead and Quote Requests" not in body
    assert "Recent Quote Requests" not in body
    assert "combo-tabs" in body
    assert "Client &amp; Listing Requests" in body or "Client & Listing Requests" in body
    assert "Insurance Quotes" in body
    # Pending/Accepted/Completed summary appears exactly once, not duplicated
    # across two separate sections.
    assert body.count('<span>Pending</span>') == 1


def test_combined_dashboard_merges_listing_tools_sidebar_panels(db_session, client):
    user, _profile = _make_combined_partner(db_session)
    login_as(client, user)

    resp = client.get("/vip/insurance")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Listing Tools" in body
    assert "MLS Number" in body
    assert "Sync Token" in body
    # The old separate "MLS Entry" / "Listing Feed" section headers are gone.
    assert ">MLS Entry<" not in body
    assert ">Listing Feed<" not in body


def test_combined_dashboard_stat_cards_grouped_into_lanes(db_session, client):
    user, _profile = _make_combined_partner(db_session)
    login_as(client, user)

    resp = client.get("/vip/insurance")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "combo-stat-lane" in body
    assert "Realtor CRM" in body
    assert "Insurance CRM" in body
    # Insurance and Quote Requests stat cards link to their real pages.
    assert 'href="/vip/insurance/clients"' in body
    assert 'href="/vip/insurance/quote-requests"' in body
    # Realtor-lane cards link to the on-page anchors instead of a missing route.
    assert 'href="#pipeline-snapshot"' in body
    assert 'href="#property-desk"' in body


def test_property_management_badge_is_a_link_when_enabled(db_session, client, monkeypatch):
    from LoanMVP.routes import vip as vip_routes

    user, _profile = _make_combined_partner(db_session)
    monkeypatch.setattr(vip_routes, "partner_offers_property_management", lambda u: True)
    login_as(client, user)

    resp = client.get("/vip/insurance")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'href="/property/dashboard"' in body or 'href="/property"' in body


def test_plain_insurance_dashboard_still_renders_without_realtor_sections(db_session, client):
    user, _profile = _make_plain_insurance_partner(db_session)
    login_as(client, user)

    resp = client.get("/vip/insurance")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # No realtor-only sections leak into the plain insurance dashboard.
    assert "Pipeline Snapshot" not in body
    assert "Property Desk" not in body
    assert "Listing Tools" not in body
    assert "Recent Contacts" not in body
    # But the merged requests panel and insurance stat lane still render.
    assert "combo-tabs" in body
    assert "Insurance CRM" in body
