"""Regression test for the "Your Ravlo AI portfolio summary is ready"
notification's "Open" link landing on a blank dashboard panel.

portfolio_ai_summary() (investor_routes.py) sends a notification promising
"open it to see the highlights" with action_url=url_for("investor.command_center"),
but the actual analysis only ever lived in the DOM -- injected by
runPortfolioAi() at the moment someone clicked "Analyze My Portfolio", never
persisted anywhere the dashboard could read it back. Clicking "Open" later
(from the notification, possibly in a new page load) just landed on the
plain empty panel with no trace of what was "ready".

The result was already being logged to RavloAIMemoryLog via log_ai_exchange()
for training purposes -- command_center() now reads the most recent one back
and pre-renders it, so "Open" actually shows the promised highlights.
"""
import json
from datetime import datetime, timedelta

from LoanMVP.models.admin import Company
from LoanMVP.models.training_models import RavloAIMemoryLog
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_investor(db_session, email="investor-portfolio-ai@example.com"):
    company = Company(name="Portfolio AI Co", is_active=True)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role="investor", is_active=True, company_id=company.id, subscription="active")
    db_session.add(user)
    db_session.commit()
    return user


def test_dashboard_shows_the_last_portfolio_summary(db_session, client):
    user = _make_investor(db_session)

    log = RavloAIMemoryLog(
        user_id=user.id,
        module="investor_os",
        feature="portfolio_ai_summary",
        event_type="ai_exchange",
        response=json.dumps({
            "summary": "Your portfolio is weighted toward long-term rentals.",
            "highlight": "Cash flow across tracked deals is trending positive.",
            "next_steps": ["Review the Austin deal's rent estimate"],
            "flags": ["One deal has no recent activity"],
        }),
        created_at=datetime.utcnow() - timedelta(hours=2),
    )
    db_session.add(log)
    db_session.commit()

    login_as(client, user)
    body = client.get("/investor/dashboard").get_data(as_text=True)

    assert "Your portfolio is weighted toward long-term rentals." in body
    assert "Cash flow across tracked deals is trending positive." in body
    assert "Review the Austin deal&#39;s rent estimate" in body or "Review the Austin deal's rent estimate" in body
    assert "One deal has no recent activity" in body
    assert "Last analyzed" in body
    assert 'id="portfolioAiResult"' in body
    assert 'id="portfolioAiResult" hidden' not in body


def test_dashboard_panel_stays_hidden_with_no_prior_summary(db_session, client):
    user = _make_investor(db_session, email="investor-no-summary@example.com")

    login_as(client, user)
    body = client.get("/investor/dashboard").get_data(as_text=True)

    assert "Last analyzed" not in body


def test_dashboard_only_shows_this_users_own_summary(db_session, client):
    user_a = _make_investor(db_session, email="investor-a-portfolio@example.com")
    user_b = _make_investor(db_session, email="investor-b-portfolio@example.com")

    db_session.add(RavloAIMemoryLog(
        user_id=user_b.id,
        module="investor_os",
        feature="portfolio_ai_summary",
        event_type="ai_exchange",
        response=json.dumps({"summary": "User B's private portfolio insight."}),
    ))
    db_session.commit()

    login_as(client, user_a)
    body = client.get("/investor/dashboard").get_data(as_text=True)

    assert "User B's private portfolio insight." not in body
