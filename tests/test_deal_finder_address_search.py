"""Regression tests for Deal Finder's address-only search.

Deal Finder's address field is a single free-text box. When a user typed
a full address there and left ZIP/city/state blank, the search silently
returned nothing: RentCast needs a ZIP or city+state to fetch a market's
listings from before it can even attempt to match an address, and
get_rentcast_sale_listings() returns [] immediately when neither is
present. Fixed by recovering a ZIP/state from the address text itself
before handing off to the search orchestrator.
"""
from unittest.mock import MagicMock, patch

from LoanMVP.models.admin import Company
from LoanMVP.models.investor_models import InvestorProfile
from LoanMVP.models.user_model import User
from LoanMVP.routes.investor_routes import _parse_market_from_address_text

from tests.conftest import login_as


def test_parses_zip_from_trailing_full_address():
    zip_code, state = _parse_market_from_address_text("123 Main St, Otisville, NY 10924")
    assert zip_code == "10924"
    assert state == "NY"


def test_parses_zip_only_when_no_state_present():
    zip_code, state = _parse_market_from_address_text("123 Main St 10924")
    assert zip_code == "10924"
    assert state == ""


def test_parses_state_only_when_no_zip_present():
    zip_code, state = _parse_market_from_address_text("123 Main St, Otisville, NY")
    assert zip_code == ""
    assert state == "NY"


def test_ignores_street_abbreviations_that_look_like_state_codes():
    # "St" and "Rd" are not real state abbreviations -- must not false-positive.
    zip_code, state = _parse_market_from_address_text("123 Main St")
    assert zip_code == ""
    assert state == ""


def test_returns_nothing_for_address_with_no_recoverable_market():
    zip_code, state = _parse_market_from_address_text("Unnamed Rural Route")
    assert zip_code == ""
    assert state == ""


def _make_investor(db_session, email="investor@example.com"):
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


def test_address_only_search_recovers_zip_before_calling_orchestrator(db_session, client):
    user, profile = _make_investor(db_session)
    login_as(client, user)

    mock_orchestrator_instance = MagicMock()
    mock_orchestrator_instance.run_search.return_value = ([], {})

    with patch(
        "LoanMVP.routes.investor_routes.PropertyIntelligenceOrchestrator",
        return_value=mock_orchestrator_instance,
    ) as mock_orchestrator_cls:
        resp = client.post(
            "/investor/api/property_tool_search",
            json={"address": "123 Main St, Otisville, NY 10924"},
        )

    assert resp.status_code == 200
    mock_orchestrator_cls.assert_called_once()
    mock_orchestrator_instance.run_search.assert_called_once()
    call_kwargs = mock_orchestrator_instance.run_search.call_args.kwargs
    assert call_kwargs["zip_code"] == "10924"
    assert call_kwargs["address"] == "123 Main St, Otisville, NY 10924"


def test_address_only_search_with_no_recoverable_zip_still_calls_orchestrator(db_session, client):
    # Even when nothing can be parsed out of the address text, the search
    # should still run (and return an empty/error result on its own terms)
    # rather than never reaching the orchestrator at all.
    user, profile = _make_investor(db_session, email="investor2@example.com")
    login_as(client, user)

    mock_orchestrator_instance = MagicMock()
    mock_orchestrator_instance.run_search.return_value = ([], {})

    with patch(
        "LoanMVP.routes.investor_routes.PropertyIntelligenceOrchestrator",
        return_value=mock_orchestrator_instance,
    ):
        resp = client.post(
            "/investor/api/property_tool_search",
            json={"address": "Unnamed Rural Route"},
        )

    assert resp.status_code == 200
    mock_orchestrator_instance.run_search.assert_called_once()


def test_explicit_zip_is_not_overridden_by_address_parsing(db_session, client):
    user, profile = _make_investor(db_session, email="investor3@example.com")
    login_as(client, user)

    mock_orchestrator_instance = MagicMock()
    mock_orchestrator_instance.run_search.return_value = ([], {})

    with patch(
        "LoanMVP.routes.investor_routes.PropertyIntelligenceOrchestrator",
        return_value=mock_orchestrator_instance,
    ):
        resp = client.post(
            "/investor/api/property_tool_search",
            json={"address": "123 Main St, Otisville, NY 10924", "zip_code": "99999"},
        )

    assert resp.status_code == 200
    call_kwargs = mock_orchestrator_instance.run_search.call_args.kwargs
    assert call_kwargs["zip_code"] == "99999"
