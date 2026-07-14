"""Regression test: the Ravlo Academy portal's "back to dashboard" link
for a partner-role user pointed at a nonexistent endpoint (vip.dashboard),
which 500'd the whole page (BuildError) for any authenticated partner who
visited /academy/portal. The real smart-routing entry point is vip.index.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def test_partner_can_load_academy_portal(db_session, client):
    company = Company(name="Partner Co", is_active=True)
    db_session.add(company)
    db_session.commit()
    user = User(email="partner-academy@example.com", role="partner", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    login_as(client, user)
    resp = client.get("/academy/portal")

    assert resp.status_code == 200
    assert "vip.dashboard" not in resp.get_data(as_text=True)


# ---------------------------------------------------------------------------
# Account executives previously had no Academy access at all: "account_executive"
# was missing from both _ROLE_TIER and _ROLE_TRACK, so the portal fell through
# to the no-access landing screen (code entry / subscribe) for every AE.
# ---------------------------------------------------------------------------

def test_account_executive_gets_academy_access_and_ae_track(db_session, client):
    company = Company(name="AE Co", is_active=True)
    db_session.add(company)
    db_session.commit()
    user = User(email="ae-academy@example.com", role="account_executive", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    login_as(client, user)
    resp = client.get("/academy/portal")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'tier: "elite"' in body
    assert 'allowedTrack: "account_executive"' in body


def test_academy_link_appears_on_ae_sidebar(db_session, client):
    company = Company(name="AE Sidebar Co", is_active=True)
    db_session.add(company)
    db_session.commit()
    user = User(email="ae-sidebar-academy@example.com", role="account_executive", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    login_as(client, user)
    resp = client.get("/account-executive/dashboard")

    assert resp.status_code == 200
    assert "/academy/portal" in resp.get_data(as_text=True)
