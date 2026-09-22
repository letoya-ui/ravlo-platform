"""ravlo_base.html's topbar had its own Logout form/button in addition to
the one every role-specific sidebar partial (e.g. _sidebar_investor.html)
already renders, so investor pages showed two Logout buttons. The topbar
copy was redundant chrome; the sidebar one is the persistent nav element."""
from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def test_investor_dashboard_renders_exactly_one_logout_button(db_session, client):
    company = Company(name="Logout Co", is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()

    user = User(email="logout-investor@example.com", role="investor", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    login_as(client, user)
    resp = client.get("/investor/dashboard")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert body.count('action="/auth/logout"') == 1
