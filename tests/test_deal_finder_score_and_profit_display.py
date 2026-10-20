"""Regression tests for three Deal Finder / investor analytics fixes:

1. The score badge on each result card (property_tool.html) only ever
   showed a bare "95/99", with no indication of which exit strategy that
   score was tied to. It now appends " · {strategy}" (e.g. "95/99 ·
   Rental") using the per-result best_exit_strategy.
2. The exit-strategy cards formatted profit/cash-flow through money(),
   which collapses any value <= 0 to "-". That's correct for something
   like rent or last-sale price (0 means no data), but wrong for profit
   -- a negative profit is real, meaningful data, not missing data.
   signedMoney() renders a losing flip as -$526,000 instead of a blank
   dash, and negative profit/cash-flow values get a ".negative" class.
3. /investor/analysis summed loan.loan_amount, a column that doesn't
   exist on LoanApplication (only `amount` does) --
   getattr(loan, "loan_amount", 0) silently fell back to 0 for every
   loan, every time. Fixed to sum the real `amount` field.
"""
from unittest.mock import patch

from LoanMVP.extensions import db
from LoanMVP.models.admin import Company
from LoanMVP.models.investor_models import InvestorProfile
from LoanMVP.models.loan_models import LoanApplication
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_investor(db_session, email="investor-df@example.com"):
    company = Company(name="Deal Finder Co", is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role="investor", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    profile = InvestorProfile(user_id=user.id, full_name="Ivy Vestor")
    db_session.add(profile)
    db_session.commit()
    return user, profile


def test_score_badge_renders_strategy_label_next_to_the_score(db_session, client):
    user, profile = _make_investor(db_session)
    login_as(client, user)

    body = client.get("/investor/property_tool").get_data(as_text=True)

    assert "function signedMoney" in body
    # The badge template literal must include the strategy label, not a bare score.
    assert "${score}/99${bestExitLabel" in body
    assert "const bestExitLabel = r.best_exit_strategy" in body


def test_exit_strategy_cards_use_signed_money_for_profit_fields_not_money(db_session, client):
    user, profile = _make_investor(db_session, email="investor-df2@example.com")
    login_as(client, user)

    body = client.get("/investor/property_tool").get_data(as_text=True)

    assert "isSignedField ? signedMoney(card.headline_value) : prettyNumber(card.headline_value)" in body
    assert "isNegative ? \" negative\" : \"\"" in body
    assert ".dfv4-exit-value.negative{color:#f87171}" in body


def test_investor_analysis_sums_real_amount_field(db_session, client):
    user, profile = _make_investor(db_session, email="investor-df3@example.com")
    login_as(client, user)

    db_session.add(LoanApplication(investor_profile_id=profile.id, amount=250000, status="Submitted"))
    db_session.add(LoanApplication(investor_profile_id=profile.id, amount=175000, status="Submitted"))
    db_session.commit()

    with patch("LoanMVP.routes.investor_routes.AIAssistant") as mock_assistant_cls:
        mock_assistant_cls.return_value.generate_reply.return_value = "summary"
        resp = client.get("/investor/analysis")

    assert resp.status_code == 200
    prompt = mock_assistant_cls.return_value.generate_reply.call_args.args[0]
    assert "totaling $425000.0" in prompt or "totaling $425000" in prompt
