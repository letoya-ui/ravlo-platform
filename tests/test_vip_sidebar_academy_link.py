"""Regression test: the Academy (property management course, realtor
track, etc.) was already free and auto-routed for every partner, but
the VIP partner sidebar had no persistent link to it -- the only way
in was a card on the dashboard homepage. Add a sidebar link so it's
reachable from every VIP page, not just the one landing screen.
"""
from LoanMVP.models.crm_models import Partner
from LoanMVP.models.user_model import User
from LoanMVP.models.vip_models import VIPProfile

from tests.conftest import login_as


def _make_realtor_partner(db_session, email="realtor@example.com"):
    user = User(email=email, role="partner", is_active=True, first_name="Pat", last_name="Partner")
    db_session.add(user)
    db_session.commit()
    partner = Partner(
        user_id=user.id, name="Test Realty", category="Realtor", type="Realtor",
    )
    db_session.add(partner)
    profile = VIPProfile(
        user_id=user.id, display_name="Test Realtor", business_name="Test Realty",
        role_type="realtor",
    )
    db_session.add(profile)
    db_session.commit()
    return user


def test_vip_sidebar_links_to_academy(db_session, client):
    user = _make_realtor_partner(db_session)
    login_as(client, user)

    resp = client.get("/vip/realtor")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "/academy/portal" in body
    assert "Academy" in body
