"""
Tests for the Loan Officer Pipeline AI assistant's pure logic.

Covers:
1. Empty pipeline (no loans)
2. Single healthy loan (no flags)
3. Stalled / high-DTI / high-LTV flags, individually and combined
4. Aggregate math (total value, stage counts, funded volume, estimated commission)
5. Template fallback when the Claude call fails
"""

import sys
import os
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

# Allow imports from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from LoanMVP.services.loan_officer_pipeline_ai_service import (
    _shape_context,
    _loan_flags,
    _template_pipeline_explanation,
    explain_loan_officer_pipeline,
)

NOW = datetime(2026, 7, 9, 12, 0, 0)


def _loan(**overrides):
    base = dict(
        id=1, property_address="123 Main St", borrower_profile=None,
        amount=300000.0, status="in_review", milestone_stage="Underwriting",
        created_at=NOW - timedelta(days=1), updated_at=NOW - timedelta(days=1),
        back_end_dti=None, ltv_ratio=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# ── _shape_context ──────────────────────────────────────

def test_shape_context_no_loans():
    context = _shape_context([])
    assert context == {"has_loans": False, "total_loans": 0}


def test_shape_context_single_healthy_loan():
    context = _shape_context([_loan()], now=NOW)
    assert context["has_loans"] is True
    assert context["total_loans"] == 1
    assert context["total_pipeline_value"] == 300000.0
    assert context["stage_counts"] == {"Underwriting": 1}
    assert context["loan_flags"] == []


def test_shape_context_stage_counts_and_total_value():
    loans = [
        _loan(id=1, amount=100000.0, milestone_stage="Underwriting"),
        _loan(id=2, amount=200000.0, milestone_stage="Underwriting"),
        _loan(id=3, amount=50000.0, milestone_stage="Clear to Close"),
    ]
    context = _shape_context(loans, now=NOW)
    assert context["total_pipeline_value"] == 350000.0
    assert context["stage_counts"] == {"Underwriting": 2, "Clear to Close": 1}


def test_shape_context_funded_volume_and_estimated_commission():
    loans = [
        _loan(id=1, amount=200000.0, status="in_review"),
        _loan(id=2, amount=300000.0, status="closed"),
        _loan(id=3, amount=100000.0, status="funded"),
    ]
    context = _shape_context(loans, now=NOW)
    # Only the closed + funded loans count toward funded volume
    assert context["funded_volume"] == 400000.0
    assert context["commission_rate"] == 0.01
    assert context["estimated_commission"] == round(400000.0 * 0.01, 2)


def test_shape_context_no_funded_loans_gives_zero_commission():
    context = _shape_context([_loan(status="in_review")], now=NOW)
    assert context["funded_volume"] == 0
    assert context["estimated_commission"] == 0


# ── _loan_flags ──────────────────────────────────────────

def test_loan_flags_all_healthy():
    assert _loan_flags(_loan(), now=NOW) == []


def test_loan_flags_stalled():
    loan = _loan(updated_at=NOW - timedelta(days=20), created_at=NOW - timedelta(days=20))
    flags = _loan_flags(loan, now=NOW)
    assert any("no update in 20 days" in f for f in flags)


def test_loan_flags_not_stalled_when_closed():
    loan = _loan(status="approved", updated_at=NOW - timedelta(days=30))
    assert _loan_flags(loan, now=NOW) == []


def test_loan_flags_high_dti():
    flags = _loan_flags(_loan(back_end_dti=48.0), now=NOW)
    assert any("back-end DTI" in f for f in flags)


def test_loan_flags_high_ltv():
    flags = _loan_flags(_loan(ltv_ratio=0.98), now=NOW)
    assert any("LTV" in f for f in flags)


def test_loan_flags_combined():
    loan = _loan(
        updated_at=NOW - timedelta(days=20), created_at=NOW - timedelta(days=20),
        back_end_dti=50.0, ltv_ratio=0.97,
    )
    flags = _loan_flags(loan, now=NOW)
    assert len(flags) == 3


# ── _template_pipeline_explanation ───────────────────────

def test_template_pipeline_explanation_no_loans():
    result = _template_pipeline_explanation({"has_loans": False})
    assert "don't have any loans" in result["summary"]
    assert result["flags"] == []
    assert result["highlight"] == ""


def test_template_pipeline_explanation_with_loans():
    context = _shape_context([_loan(id=1, amount=500000.0, property_address="123 Main St")], now=NOW)
    result = _template_pipeline_explanation(context)
    assert "1 loan" in result["summary"]
    assert "123 Main St" in result["highlight"]


def test_template_pipeline_explanation_mentions_commission_when_funded():
    context = _shape_context(
        [_loan(id=1, amount=500000.0, status="closed", property_address="123 Main St")],
        now=NOW,
    )
    result = _template_pipeline_explanation(context)
    assert "estimated commission" in result["summary"]
    assert "$5,000" in result["summary"]  # 500000 * 0.01


def test_template_pipeline_explanation_omits_commission_when_nothing_funded():
    context = _shape_context([_loan(id=1, status="in_review")], now=NOW)
    result = _template_pipeline_explanation(context)
    assert "estimated commission" not in result["summary"]


# ── explain_loan_officer_pipeline — template fallback on Claude failure ──

def test_explain_loan_officer_pipeline_falls_back_to_template_on_claude_error():
    with patch(
        "LoanMVP.services.loan_officer_pipeline_ai_service.gather_loan_officer_pipeline_context",
        return_value=_shape_context([_loan()], now=NOW),
    ), patch(
        "LoanMVP.services.loan_officer_pipeline_ai_service.claude_loan_pipeline_summary",
        return_value={"error": "ANTHROPIC_API_KEY is not set."},
    ):
        outcome = explain_loan_officer_pipeline(user_id=1)

    assert outcome["provider"] == "template"
    assert outcome["result"]["summary"]


def test_explain_loan_officer_pipeline_uses_claude_result_when_available():
    claude_result = {
        "summary": "Your pipeline is worth $500,000 across 1 loan.",
        "next_steps": ["Follow up with the borrower on outstanding docs."],
        "flags": [],
        "highlight": "123 Main St is your largest active loan.",
        "meta": {"provider": "anthropic/claude"},
    }
    with patch(
        "LoanMVP.services.loan_officer_pipeline_ai_service.gather_loan_officer_pipeline_context",
        return_value=_shape_context([_loan()], now=NOW),
    ), patch(
        "LoanMVP.services.loan_officer_pipeline_ai_service.claude_loan_pipeline_summary",
        return_value=claude_result,
    ):
        outcome = explain_loan_officer_pipeline(user_id=1)

    assert outcome["provider"] == "anthropic/claude"
    assert outcome["result"]["summary"] == claude_result["summary"]
