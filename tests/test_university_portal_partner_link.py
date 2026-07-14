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
