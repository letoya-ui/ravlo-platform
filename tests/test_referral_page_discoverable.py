"""Regression test: the /refer marketing page existed and worked, but
nothing on the site actually linked to it -- no nav item, no footer
link, no button anywhere. Also updates its copy to reflect that logged-in
users get a self-serve personal link from account.profile rather than
needing to "reach out" for one."""
from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_user(db_session, email="referuser@example.com"):
    company = Company(name="Refer Discoverable Co", is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role="investor", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user


def test_marketing_footer_links_to_refer_page(client):
    resp = client.get("/lending-os")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'href="/refer"' in body


def test_refer_page_prompts_anonymous_visitors_to_log_in_for_their_link(client):
    resp = client.get("/refer")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Log In to Get Your Link" in body


def test_refer_page_sends_logged_in_users_to_their_profile(db_session, client):
    user = _make_user(db_session)
    login_as(client, user)

    resp = client.get("/refer")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Get My Referral Link" in body
    assert '/account/profile' in body
