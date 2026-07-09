"""
Tests for the Borrower AI assistant's pure logic.

Covers:
1. No active loan
2. Mixed-severity open conditions + outstanding documents
3. All conditions cleared, nothing outstanding
4. Template fallback when the Claude call fails
"""

import sys
import os
from types import SimpleNamespace
from datetime import datetime
from unittest.mock import patch

# Allow imports from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from LoanMVP.services.borrower_ai_service import (
    _shape_context,
    _template_explanation,
    explain_borrower_status,
    gather_borrower_context,
)


def _condition(**overrides):
    base = dict(condition_type="Income Verification", description="Provide last 2 paystubs",
                severity="Standard", status="Open")
    base.update(overrides)
    return SimpleNamespace(**base)


def _condition_request(**overrides):
    base = dict(document_name="Bank Statement", status="pending")
    base.update(overrides)
    return SimpleNamespace(**base)


def _document_request(**overrides):
    base = dict(document_name="W-2 Form", notes="Most recent year", status="Pending")
    base.update(overrides)
    return SimpleNamespace(**base)


def _document_need(**overrides):
    base = dict(name="Proof of Insurance", reason="Required for closing", status="required")
    base.update(overrides)
    return SimpleNamespace(**base)


def _status_event(**overrides):
    base = dict(event_name="Application Submitted", description="Initial application received",
                status="completed", timestamp=datetime(2026, 1, 1, 12, 0, 0))
    base.update(overrides)
    return SimpleNamespace(**base)


def _loan(**overrides):
    base = dict(status="Pending", progress_percent=40, milestone_stage="Underwriting Review",
                property_address="123 Main St", amount=250000)
    base.update(overrides)
    return SimpleNamespace(**base)


# ─────────────────────────────────────────────────
# _shape_context
# ─────────────────────────────────────────────────

def test_shape_context_no_active_loan():
    context = _shape_context(None)
    assert context == {"has_active_loan": False}


def test_shape_context_with_open_items():
    context = _shape_context(
        loan=_loan(),
        open_conditions=[_condition(severity="High")],
        condition_requests=[_condition_request()],
        document_requests=[_document_request()],
        document_needs=[_document_need()],
        status_events=[_status_event()],
    )
    assert context["has_active_loan"] is True
    assert context["milestone_stage"] == "Underwriting Review"
    assert context["progress_percent"] == 40
    assert len(context["open_conditions"]) == 1
    assert context["open_conditions"][0]["severity"] == "High"
    assert context["condition_requests"][0]["document_name"] == "Bank Statement"
    assert context["document_requests"][0]["document_name"] == "W-2 Form"
    assert context["document_needs"][0]["name"] == "Proof of Insurance"
    assert context["recent_status_events"][0]["event_name"] == "Application Submitted"
    assert context["recent_status_events"][0]["timestamp"] == "2026-01-01T12:00:00"


def test_shape_context_all_clear():
    context = _shape_context(loan=_loan(milestone_stage="Clear to Close", progress_percent=100))
    assert context["has_active_loan"] is True
    assert context["open_conditions"] == []
    assert context["document_requests"] == []
    assert context["document_needs"] == []


# ─────────────────────────────────────────────────
# _template_explanation (deterministic fallback)
# ─────────────────────────────────────────────────

def test_template_explanation_no_active_loan():
    result = _template_explanation({"has_active_loan": False})
    assert "don't have an active loan" in result["summary"]
    assert result["next_steps"] == []
    assert result["flags"] == []


def test_template_explanation_with_open_items_and_high_severity_flag():
    context = _shape_context(
        loan=_loan(),
        open_conditions=[_condition(severity="High", description="Explain large deposit")],
        condition_requests=[_condition_request(document_name="Gift Letter")],
        document_requests=[_document_request(document_name="Pay Stub")],
        document_needs=[_document_need(name="ID Copy")],
    )
    result = _template_explanation(context)
    assert "Underwriting Review" in result["summary"]
    assert "Explain large deposit" in result["next_steps"]
    assert "Provide: Gift Letter" in result["next_steps"]
    assert "Pay Stub" in result["documents_needed"]
    assert "ID Copy" in result["documents_needed"]
    assert any("Explain large deposit" in flag for flag in result["flags"])


def test_template_explanation_nothing_outstanding():
    context = _shape_context(loan=_loan(milestone_stage="Clear to Close", progress_percent=100))
    result = _template_explanation(context)
    assert result["next_steps"] == ["No outstanding action items right now — we'll notify you when something is needed."]
    assert result["documents_needed"] == []
    assert result["flags"] == []


# ─────────────────────────────────────────────────
# explain_borrower_status — template fallback on Claude failure
# ─────────────────────────────────────────────────

def test_explain_borrower_status_falls_back_to_template_on_claude_error():
    borrower = SimpleNamespace(id=1)

    with patch(
        "LoanMVP.services.borrower_ai_service.gather_borrower_context",
        return_value=_shape_context(loan=_loan()),
    ), patch(
        "LoanMVP.services.borrower_ai_service.claude_borrower_explainer",
        return_value={"error": "ANTHROPIC_API_KEY is not set."},
    ):
        outcome = explain_borrower_status(borrower, question="What's next?")

    assert outcome["provider"] == "template"
    assert outcome["result"]["summary"]
    assert isinstance(outcome["result"]["next_steps"], list)


def test_explain_borrower_status_uses_claude_result_when_available():
    borrower = SimpleNamespace(id=1)
    claude_result = {
        "summary": "You're in underwriting review.",
        "next_steps": ["Upload your latest pay stub."],
        "documents_needed": ["Pay stub"],
        "flags": [],
        "meta": {"provider": "anthropic/claude"},
    }

    with patch(
        "LoanMVP.services.borrower_ai_service.gather_borrower_context",
        return_value=_shape_context(loan=_loan()),
    ), patch(
        "LoanMVP.services.borrower_ai_service.claude_borrower_explainer",
        return_value=claude_result,
    ):
        outcome = explain_borrower_status(borrower)

    assert outcome["provider"] == "anthropic/claude"
    assert outcome["result"]["summary"] == "You're in underwriting review."
    assert outcome["result"]["next_steps"] == ["Upload your latest pay stub."]
