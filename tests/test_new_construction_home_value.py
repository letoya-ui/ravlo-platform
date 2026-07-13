"""Regression tests for Budget Studio's "what's the finished home worth"
new-construction ARV helper.

Follows up on the ARV-for-new-construction fix: that made ARV editable,
but the investor still had to guess a dollar figure out of thin air for a
ground-up build. This reuses the deal's already-fetched ARV Engine comps
(cached in deal.results_json["ravlo_arv_report"], no new provider calls)
to compute a real weighted $/sqft, then prices out a few starter floor
plan sizes (3 bed/2 bath, 4 bed/3 bath, 5 bed/3 bath) so the investor can
pick a realistic ARV instead of typing in a guess.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.borrowers import Deal
from LoanMVP.models.investor_models import InvestorProfile
from LoanMVP.models.user_model import User
from LoanMVP.services.ravlo_arv_calculator import estimate_ppsf_from_comps

from tests.conftest import login_as


def test_estimate_ppsf_uses_sold_comps_weighted_by_score():
    comps = [
        {"status_normalized": "sold", "price_per_sqft": 180, "comp_score": 90},
        {"status_normalized": "sold", "price_per_sqft": 200, "comp_score": 10},
        {"status_normalized": "active", "price_per_sqft": 500, "comp_score": 100},  # excluded: not sold
    ]
    ppsf = estimate_ppsf_from_comps(comps)
    assert ppsf == 182.0  # (180*90 + 200*10) / 100


def test_estimate_ppsf_falls_back_to_all_comps_when_no_sold():
    comps = [
        {"status_normalized": "active", "price_per_sqft": 220, "comp_score": 50},
    ]
    ppsf = estimate_ppsf_from_comps(comps)
    assert ppsf == 220.0


def test_estimate_ppsf_returns_none_for_no_usable_data():
    assert estimate_ppsf_from_comps([]) is None
    assert estimate_ppsf_from_comps([{"status_normalized": "sold", "comp_score": 90}]) is None


def _make_investor(db_session, email="investor@example.com"):
    company = Company(name="Home Value Co", is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role="investor", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    profile = InvestorProfile(user_id=user.id, full_name="Ivy Vestor")
    db_session.add(profile)
    db_session.commit()
    return user, profile


def test_budget_studio_shows_home_value_configs(db_session, client):
    user, profile = _make_investor(db_session)
    deal = Deal(
        user_id=user.id,
        title="New Build Deal",
        purchase_price=150000,
        arv=205000,
        results_json={
            "ravlo_arv_report": {
                "comps": {
                    "included": [
                        {"status_normalized": "sold", "price_per_sqft": 180, "comp_score": 90},
                        {"status_normalized": "sold", "price_per_sqft": 190, "comp_score": 80},
                    ]
                }
            }
        },
    )
    db_session.add(deal)
    db_session.commit()

    login_as(client, user)
    resp = client.get(f"/investor/deal-studio/budget/{deal.id}")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "3 Bed / 2 Bath" in body
    assert "4 Bed / 3 Bath" in body
    assert "5 Bed / 3 Bath" in body
    assert "from comps near this deal" in body


def test_budget_studio_home_value_configs_blank_without_comps(db_session, client):
    user, profile = _make_investor(db_session, email="investor2@example.com")
    deal = Deal(user_id=user.id, title="No Comps Deal", purchase_price=150000, arv=205000)
    db_session.add(deal)
    db_session.commit()

    login_as(client, user)
    resp = client.get(f"/investor/deal-studio/budget/{deal.id}")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "3 Bed / 2 Bath" in body
    assert "enter your local $/sqft estimate" in body


def test_budget_studio_home_value_card_hidden_for_design_budget(db_session, client):
    user, profile = _make_investor(db_session, email="investor3@example.com")
    deal = Deal(
        user_id=user.id,
        title="Design Budget Deal",
        purchase_price=0,
        arv=0,
        results_json={"design_budget": {"cost_low": 5000, "cost_high": 8000}},
    )
    db_session.add(deal)
    db_session.commit()

    login_as(client, user)
    resp = client.get(f"/investor/deal-studio/budget/{deal.id}?source=design_studio")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'id="homeValueCard"' not in body
