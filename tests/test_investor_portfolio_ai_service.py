"""
Tests for the Portfolio AI assistant's pure logic.

Covers:
1. Empty portfolio (no deals)
2. Single healthy deal (no flags)
3. Multiple deals, some flagged (ARV, rent, rehab-ratio rules)
4. Aggregate math (sums, portfolio ROI, average score, counts)
5. Template fallback when the Claude call fails
"""

import sys
import os
from types import SimpleNamespace
from unittest.mock import patch

# Allow imports from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from LoanMVP.services.investor_portfolio_ai_service import (
    _shape_context,
    _deal_risk_flags,
    _template_portfolio_explanation,
    explain_investor_portfolio,
)


def _deal(**overrides):
    base = dict(
        id=1, title="123 Main St", address="123 Main St",
        strategy="flip", recommended_strategy=None,
        purchase_price=100000.0, arv=160000.0, rehab_cost=20000.0,
        estimated_rent=0, deal_score=70, submitted_for_funding=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# ── _shape_context ──────────────────────────────────────

def test_shape_context_no_deals():
    context = _shape_context([])
    assert context == {"has_deals": False, "total_deals": 0}


def test_shape_context_single_healthy_deal():
    context = _shape_context([_deal()])
    assert context["has_deals"] is True
    assert context["total_deals"] == 1
    assert context["total_purchase_price"] == 100000.0
    assert context["total_arv"] == 160000.0
    assert context["total_rehab_cost"] == 20000.0
    assert context["total_project_cost"] == 120000.0
    assert context["total_profit"] == 40000.0
    assert context["portfolio_roi_percent"] == round(40000.0 / 120000.0 * 100, 2)
    assert context["average_deal_score"] == 70
    assert context["deal_flags"] == []  # ARV > price, rehab ratio 0.2, no rental w/o rent


def test_shape_context_multiple_deals_with_flags():
    healthy = _deal(id=1, title="123 Main St")
    bad_arv = _deal(id=2, title="456 Oak Ave", arv=90000.0, purchase_price=100000.0)
    rental_no_rent = _deal(id=3, title="789 Pine Rd", strategy="rental", estimated_rent=0)
    high_rehab = _deal(id=4, title="321 Elm St", purchase_price=100000.0, rehab_cost=60000.0)

    context = _shape_context([healthy, bad_arv, rental_no_rent, high_rehab])

    assert context["total_deals"] == 4
    flags = context["deal_flags"]
    assert any("456 Oak Ave" in f and "ARV" in f for f in flags)
    assert any("789 Pine Rd" in f and "rental" in f for f in flags)
    assert any("321 Elm St" in f and "rehab cost exceeds 50%" in f for f in flags)
    assert not any("123 Main St" in f for f in flags)


def test_shape_context_average_deal_score_ignores_none():
    context = _shape_context([_deal(id=1, deal_score=80), _deal(id=2, deal_score=None)])
    assert context["average_deal_score"] == 80


def test_shape_context_ready_for_funding_and_funding_requested_counts():
    d1 = _deal(id=1, submitted_for_funding=False, strategy="flip", purchase_price=100000.0)
    d2 = _deal(id=2, submitted_for_funding=True)
    context = _shape_context([d1, d2])
    assert context["ready_for_funding_count"] == 1
    assert context["funding_requested_count"] == 1


# ── _deal_risk_flags ─────────────────────────────────────

def test_deal_risk_flags_all_healthy():
    assert _deal_risk_flags(_deal()) == []


def test_deal_risk_flags_arv_not_above_price():
    flags = _deal_risk_flags(_deal(arv=90000.0, purchase_price=100000.0))
    assert any("ARV needs validation" in f for f in flags)


def test_deal_risk_flags_rental_without_rent():
    flags = _deal_risk_flags(_deal(strategy="rental", estimated_rent=0))
    assert any("rental strategy selected without rent support" in f for f in flags)


def test_deal_risk_flags_high_rehab_ratio():
    flags = _deal_risk_flags(_deal(purchase_price=100000.0, rehab_cost=60000.0))
    assert any("rehab cost exceeds 50%" in f for f in flags)


# ── _template_portfolio_explanation ──────────────────────

def test_template_portfolio_explanation_no_deals():
    result = _template_portfolio_explanation({"has_deals": False})
    assert "don't have any tracked deals" in result["summary"]
    assert result["flags"] == []
    assert result["highlight"] == ""


def test_template_portfolio_explanation_with_deals():
    context = _shape_context([_deal(id=1, title="123 Main St")])
    result = _template_portfolio_explanation(context)
    assert "1 deal" in result["summary"]
    assert "123 Main St" in result["highlight"]


# ── explain_investor_portfolio — template fallback on Claude failure ──

def test_explain_investor_portfolio_falls_back_to_template_on_claude_error():
    with patch(
        "LoanMVP.services.investor_portfolio_ai_service.gather_investor_portfolio_context",
        return_value=_shape_context([_deal()]),
    ), patch(
        "LoanMVP.services.investor_portfolio_ai_service.claude_portfolio_analysis",
        return_value={"error": "ANTHROPIC_API_KEY is not set."},
    ):
        outcome = explain_investor_portfolio(user_id=1)

    assert outcome["provider"] == "template"
    assert outcome["result"]["summary"]


def test_explain_investor_portfolio_uses_claude_result_when_available():
    claude_result = {
        "summary": "Your portfolio is worth $500,000 with 12% ROI.",
        "next_steps": ["Submit deal #2 for funding."],
        "flags": [],
        "highlight": "Deal #1 is your strongest performer.",
        "meta": {"provider": "anthropic/claude"},
    }
    with patch(
        "LoanMVP.services.investor_portfolio_ai_service.gather_investor_portfolio_context",
        return_value=_shape_context([_deal()]),
    ), patch(
        "LoanMVP.services.investor_portfolio_ai_service.claude_portfolio_analysis",
        return_value=claude_result,
    ):
        outcome = explain_investor_portfolio(user_id=1)

    assert outcome["provider"] == "anthropic/claude"
    assert outcome["result"]["summary"] == claude_result["summary"]
