"""Regression test: the ARV tier picker's "Aggressive"/"Base"/"Conservative"
buttons always failed with a 404, surfaced in the browser as "Unexpected
token" (a JS parse error) rather than a clear message.

Both places that render the picker (the shared arv_tier_picker.html
component, and the inline copy in deal_workspace.html) posted to
"/deals/<id>/arv-tier", but set_deal_arv_tier() is registered under
investor_bp, which has url_prefix="/investor" -- so the real path is
"/investor/deals/<id>/arv-tier". Every click hit Flask's real 404 (the
un-prefixed path doesn't exist at all), and since the JS unconditionally
called resp.json() on the response, parsing the 404's HTML error page as
JSON threw "Unexpected token < in JSON at position 0".
"""
import os

from LoanMVP.models.admin import Company
from LoanMVP.models.borrowers import Deal
from LoanMVP.models.investor_models import InvestorProfile
from LoanMVP.models.user_model import User

from tests.conftest import login_as

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "LoanMVP", "templates", "investor")


def _make_investor(db_session, email="arv-tier-investor@example.com"):
    company = Company(name="ARV Tier Co", is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role="investor", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    profile = InvestorProfile(user_id=user.id, full_name="Ivy Investor")
    db_session.add(profile)
    db_session.commit()
    return user, profile


def test_arv_tier_picker_component_fetches_investor_prefixed_url():
    path = os.path.join(_TEMPLATES_DIR, "components", "arv_tier_picker.html")
    with open(path) as f:
        content = f.read()

    assert 'fetch("/investor/deals/" + dealId + "/arv-tier"' in content
    assert 'fetch("/deals/" + dealId + "/arv-tier"' not in content


def test_deal_workspace_arv_tier_picker_fetches_investor_prefixed_url():
    path = os.path.join(_TEMPLATES_DIR, "deal_workspace.html")
    with open(path) as f:
        content = f.read()

    assert 'fetch("/investor/deals/" + dealId + "/arv-tier"' in content
    assert 'fetch("/deals/" + dealId + "/arv-tier"' not in content


def test_unprefixed_arv_tier_url_really_is_a_404(client):
    """Documents the exact bug: the URL the JS used to call doesn't exist."""
    resp = client.post("/deals/1/arv-tier", json={"tier": "base"})
    assert resp.status_code == 404


def test_investor_prefixed_arv_tier_url_saves_the_tier(db_session, client):
    user, profile = _make_investor(db_session)
    deal = Deal(
        user_id=user.id,
        title="ARV Tier Deal",
        results_json={"ravlo_arv_report": {"arv": {
            "conservative": 300000, "base": 320000, "aggressive": 345000,
        }}},
    )
    db_session.add(deal)
    db_session.commit()
    login_as(client, user)

    resp = client.post(f"/investor/deals/{deal.id}/arv-tier", json={"tier": "aggressive"})

    assert resp.status_code == 200
    assert resp.get_json()["tier"] == "aggressive"

    updated = Deal.query.get(deal.id)
    assert updated.arv_tier == "aggressive"
    assert updated.arv == 345000
