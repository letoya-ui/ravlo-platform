"""Regression tests for tying Design Studio's AI redesign to the deal's
actual dollar rehab budget instead of only a generic Finish Level label.

_design_budget_context_for_prompt() reads the room budget Design Studio's
"Generate Budget" action already computes and stores in
deal.results_json["design_budget"], and generate_build_interior() (the
route the Design Studio page's form actually submits to) now threads that
dollar figure into the AI prompt so finishes shown are realistically
achievable at the deal's real numbers.
"""
from unittest.mock import patch

from LoanMVP.models.admin import Company
from LoanMVP.models.borrowers import Deal
from LoanMVP.models.investor_models import InvestorProfile
from LoanMVP.models.user_model import User
from LoanMVP.routes.investor_routes import (
    _compose_photo_to_interior_prompt,
    _design_budget_context_for_prompt,
)

from tests.conftest import login_as


def test_no_context_when_no_design_budget_stored():
    assert _design_budget_context_for_prompt({}) == ""
    assert _design_budget_context_for_prompt({"design_budget": {}}) == ""
    assert _design_budget_context_for_prompt(
        {"design_budget": {"cost_low": 0, "cost_high": 0}}
    ) == ""


def test_context_includes_dollar_range():
    context = _design_budget_context_for_prompt(
        {"design_budget": {"cost_low": 12500, "cost_high": 18000}}
    )
    assert "$12,500" in context
    assert "$18,000" in context
    assert "achievable within this budget" in context


def test_context_uses_single_figure_when_low_equals_high():
    context = _design_budget_context_for_prompt(
        {"design_budget": {"cost_low": 15000, "cost_high": 15000}}
    )
    assert "$15,000" in context
    assert "-" not in context.split("budget")[0]


def test_compose_photo_to_interior_prompt_includes_budget_context():
    prompt = _compose_photo_to_interior_prompt(
        room_type="kitchen",
        finish_level="standard",
        budget_context="Renovation budget for this room: $12,500-$18,000.",
    )
    assert "$12,500-$18,000" in prompt


def _make_investor(db_session, email="investor@example.com"):
    company = Company(name="Design Studio Co", is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role="investor", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    profile = InvestorProfile(user_id=user.id, full_name="Ivy Vestor")
    db_session.add(profile)
    db_session.commit()
    return user, profile


def _make_deal_with_design_budget(db_session, user, cost_low=12500, cost_high=18000):
    deal = Deal(
        user_id=user.id,
        title="Test Deal",
        results_json={"design_budget": {"cost_low": cost_low, "cost_high": cost_high}},
    )
    db_session.add(deal)
    db_session.commit()
    return deal


def test_generate_build_interior_includes_real_budget_in_prompt(db_session, client):
    user, profile = _make_investor(db_session)
    deal = _make_deal_with_design_budget(db_session, user)
    login_as(client, user)

    with patch("LoanMVP.routes.investor_routes._engine_or_dalle") as mock_engine, \
         patch("LoanMVP.routes.investor_routes._upload_after_images_from_b64", return_value=["https://example.com/after.webp"]):
        mock_engine.return_value = {"images_base64": ["ZmFrZQ=="], "seed": 1, "job_id": "abc", "meta": {}}

        resp = client.post(
            "/investor/deal-studio/build-studio/generate-interior",
            data={
                "deal_id": str(deal.id),
                "room_type": "kitchen",
                "finish_level": "standard",
                "image_url": "https://example.com/kitchen-before.jpg",
                "generation_family": "design",
            },
        )

    assert resp.status_code == 200
    mock_engine.assert_called_once()
    call_payload = mock_engine.call_args.args[1]
    assert "$12,500" in call_payload["prompt"]
    assert "$18,000" in call_payload["prompt"]
    assert "$12,500" in call_payload["budget_context"]


def test_generate_build_interior_omits_budget_context_when_none_stored(db_session, client):
    user, profile = _make_investor(db_session, email="investor2@example.com")
    deal = Deal(user_id=user.id, title="No Budget Deal")
    db_session.add(deal)
    db_session.commit()
    login_as(client, user)

    with patch("LoanMVP.routes.investor_routes._engine_or_dalle") as mock_engine, \
         patch("LoanMVP.routes.investor_routes._upload_after_images_from_b64", return_value=["https://example.com/after.webp"]):
        mock_engine.return_value = {"images_base64": ["ZmFrZQ=="], "seed": 1, "job_id": "abc", "meta": {}}

        resp = client.post(
            "/investor/deal-studio/build-studio/generate-interior",
            data={
                "deal_id": str(deal.id),
                "room_type": "bathroom",
                "finish_level": "standard",
                "image_url": "https://example.com/bathroom-before.jpg",
                "generation_family": "design",
            },
        )

    assert resp.status_code == 200
    call_payload = mock_engine.call_args.args[1]
    assert call_payload["budget_context"] == ""
