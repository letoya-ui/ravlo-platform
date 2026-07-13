"""Regression tests for fixing ARV in Budget Studio for new construction.

Budget Studio froze ARV at whatever Deal.arv was seeded with (an as-is /
light-rehab valuation) and never revisited it, regardless of which Quick
Start preset (New Construction, Rehab/Flip, Gut Rehab, Townhome Dev,
Design Only) the investor loaded. Loading "New Construction" (~$447K in
line items) against a deal whose ARV was computed for a $205,000 as-is
property produced a nonsensical negative "Projected Profit" -- spending
~$450K to build should not make the property worth less. Budget Studio's
ARV field is now editable client-side; this covers the server-side half:
create_budget_from_studio() persisting a corrected ARV back onto the deal
so it isn't lost and stays consistent everywhere else the deal is shown.
"""
import json

from LoanMVP.models.admin import Company
from LoanMVP.models.borrowers import Deal
from LoanMVP.models.investor_models import InvestorProfile
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_investor(db_session, email="investor@example.com"):
    company = Company(name="Budget Studio Co", is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role="investor", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    profile = InvestorProfile(user_id=user.id, full_name="Ivy Vestor")
    db_session.add(profile)
    db_session.commit()
    return user, profile


def _make_deal(db_session, user, purchase_price=150000, arv=205000):
    deal = Deal(user_id=user.id, title="New Construction Deal", purchase_price=purchase_price, arv=arv)
    db_session.add(deal)
    db_session.commit()
    return deal


def _post_budget_payload(client, deal_id, payload):
    return client.post(
        f"/investor/deals/{deal_id}/budget/create-from-studio",
        data={"budget_payload": json.dumps(payload)},
    )


def test_corrected_arv_is_persisted_to_deal(db_session, client):
    user, profile = _make_investor(db_session)
    deal = _make_deal(db_session, user, purchase_price=150000, arv=205000)
    login_as(client, user)

    _post_budget_payload(client, deal.id, {
        "budget_type": "build",
        "arv": 650000,
        "contingency": 45689,
        "items": [{"name": "Foundation & Concrete", "cost": 45000, "category": "Foundation"}],
    })

    updated = Deal.query.get(deal.id)
    assert updated.arv == 650000


def test_missing_arv_leaves_deal_unchanged(db_session, client):
    user, profile = _make_investor(db_session, email="investor2@example.com")
    deal = _make_deal(db_session, user, purchase_price=150000, arv=205000)
    login_as(client, user)

    _post_budget_payload(client, deal.id, {
        "budget_type": "rehab",
        "contingency": 5000,
        "items": [{"name": "Paint", "cost": 5000, "category": "Finishes"}],
    })

    updated = Deal.query.get(deal.id)
    assert updated.arv == 205000


def test_null_arv_leaves_deal_unchanged(db_session, client):
    """Design-only budgets deliberately send arv: null (see serializeBudgetPayload)."""
    user, profile = _make_investor(db_session, email="investor3@example.com")
    deal = _make_deal(db_session, user, purchase_price=150000, arv=205000)
    login_as(client, user)

    _post_budget_payload(client, deal.id, {
        "budget_type": "design",
        "arv": None,
        "contingency": 0,
        "items": [{"name": "Paint", "cost": 500, "category": "Finishes"}],
    })

    updated = Deal.query.get(deal.id)
    assert updated.arv == 205000


def test_invalid_arv_leaves_deal_unchanged(db_session, client):
    user, profile = _make_investor(db_session, email="investor4@example.com")
    deal = _make_deal(db_session, user, purchase_price=150000, arv=205000)
    login_as(client, user)

    _post_budget_payload(client, deal.id, {
        "budget_type": "build",
        "arv": -50000,
        "contingency": 0,
        "items": [{"name": "Site Work", "cost": 18000, "category": "Site"}],
    })

    updated = Deal.query.get(deal.id)
    assert updated.arv == 205000


def test_non_numeric_arv_leaves_deal_unchanged(db_session, client):
    user, profile = _make_investor(db_session, email="investor5@example.com")
    deal = _make_deal(db_session, user, purchase_price=150000, arv=205000)
    login_as(client, user)

    _post_budget_payload(client, deal.id, {
        "budget_type": "build",
        "arv": "not-a-number",
        "contingency": 0,
        "items": [{"name": "Site Work", "cost": 18000, "category": "Site"}],
    })

    updated = Deal.query.get(deal.id)
    assert updated.arv == 205000
