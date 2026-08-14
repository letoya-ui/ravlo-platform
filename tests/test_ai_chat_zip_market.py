"""Ravlo AI chat (/admin/ai/chat) previously answered "what's a fast-moving
market to flip/rent/develop in ZIP 33607" purely from the model's general
training knowledge -- no real data behind it. It now detects a 5-digit ZIP
in the user's message, pulls live RentCast market stats for it, and grounds
the system prompt with those numbers before calling the model.
"""
from unittest.mock import MagicMock, patch

from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User
from LoanMVP.routes.admin import _zip_market_context

from tests.conftest import login_as


def _make_user(db_session, email, role="investor"):
    company = Company(name=f"{email} Co", is_active=True)
    db_session.add(company)
    db_session.commit()
    user = User(email=email, role=role, is_active=True, company_id=company.id, first_name="Sam")
    db_session.add(user)
    db_session.commit()
    return user


def _fake_openai_response(text):
    completion = MagicMock()
    completion.choices = [MagicMock(message=MagicMock(content=text))]
    client = MagicMock()
    client.chat.completions.create.return_value = completion
    return client


# ─── _zip_market_context() unit tests ───────────────────────────────────────

def test_zip_market_context_empty_when_no_zip_in_message():
    assert _zip_market_context("what's a good market to flip in?") == ""


def test_zip_market_context_includes_real_numbers_for_a_zip():
    snapshot = {"median_price": 350000, "median_rent": 1950, "dom": 18, "trend": "Fast-moving", "inventory": 42}

    with patch("LoanMVP.services.market_service.get_market_snapshot", return_value=snapshot):
        context = _zip_market_context("is 33607 a fast-moving rental market?")

    assert "33607" in context
    assert "$350,000" in context
    assert "$1,950/mo" in context
    assert "Fast-moving" in context
    assert "42 active listings" in context


def test_zip_market_context_empty_when_rentcast_has_no_data():
    empty_snapshot = {"median_price": None, "median_rent": None, "dom": None, "trend": None, "inventory": None}

    with patch("LoanMVP.services.market_service.get_market_snapshot", return_value=empty_snapshot):
        context = _zip_market_context("what about 99999?")

    assert context == ""


def test_zip_market_context_degrades_gracefully_on_error():
    with patch("LoanMVP.services.market_service.get_market_snapshot", side_effect=Exception("rentcast down")):
        context = _zip_market_context("what about 33607?")

    assert context == ""


# ─── Full route: system prompt actually gets the market data ──────────────

def test_ai_chat_grounds_response_with_zip_market_data(db_session, client):
    user = _make_user(db_session, "investor-zip@example.com")
    login_as(client, user)

    snapshot = {"median_price": 350000, "median_rent": 1950, "dom": 18, "trend": "Fast-moving", "inventory": 42}
    fake_client = _fake_openai_response("33607 looks like a fast-moving rental market right now.")

    with patch("LoanMVP.services.market_service.get_market_snapshot", return_value=snapshot), \
         patch("openai.OpenAI", return_value=fake_client):
        resp = client.post(
            "/admin/ai/chat",
            json={"message": "Is 33607 a fast-moving market for rentals or fix and flip?", "history": []},
        )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True

    sent_messages = fake_client.chat.completions.create.call_args.kwargs["messages"]
    system_prompt = sent_messages[0]["content"]
    assert "33607" in system_prompt
    assert "$350,000" in system_prompt
    assert "Fast-moving" in system_prompt


def test_ai_chat_without_a_zip_does_not_call_rentcast(db_session, client):
    user = _make_user(db_session, "investor-nozip@example.com")
    login_as(client, user)

    fake_client = _fake_openai_response("Sure, tell me more about what you're looking for.")

    with patch("LoanMVP.services.market_service.get_market_snapshot") as mock_snapshot, \
         patch("openai.OpenAI", return_value=fake_client):
        resp = client.post("/admin/ai/chat", json={"message": "What markets are trending right now?", "history": []})

    assert resp.status_code == 200
    mock_snapshot.assert_not_called()
