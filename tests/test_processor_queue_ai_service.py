"""
Tests for the Processor Queue AI assistant's pure logic.

Covers:
1. Empty queue (no files)
2. Single healthy file (no flags)
3. Stale / doc-backlog / condition-backlog flags, individually and combined
4. Aggregate math (file counts, doc/condition totals, estimated pay)
5. Template fallback when the Claude call fails
"""

import sys
import os
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

# Allow imports from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from LoanMVP.services.processor_queue_ai_service import (
    _shape_context,
    _file_flags,
    _template_queue_explanation,
    explain_processor_queue,
)

NOW = datetime(2026, 7, 9, 12, 0, 0)


def _loan(**overrides):
    base = dict(
        id=1, property_address="123 Main St", borrower_profile=None,
        status="in_review", created_at=NOW - timedelta(days=1),
        updated_at=NOW - timedelta(days=1),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _counter(pending, total):
    return lambda loan: (pending, total)


# ── _shape_context ──────────────────────────────────────

def test_shape_context_no_files():
    context = _shape_context([])
    assert context == {"has_files": False, "total_files": 0}


def test_shape_context_single_healthy_file():
    context = _shape_context(
        [_loan()], now=NOW,
        doc_counter=_counter(0, 2), cond_counter=_counter(0, 1),
    )
    assert context["has_files"] is True
    assert context["total_files"] == 1
    assert context["total_docs_pending"] == 0
    assert context["total_cond_open"] == 0
    assert context["file_flags"] == []
    assert context["funded_count"] == 0
    assert context["estimated_pay"] == 0


def test_shape_context_funded_count_and_estimated_pay():
    loans = [
        _loan(id=1, status="in_review"),
        _loan(id=2, status="closed"),
        _loan(id=3, status="funded"),
    ]
    context = _shape_context(
        loans, now=NOW,
        doc_counter=_counter(0, 1), cond_counter=_counter(0, 1),
    )
    assert context["funded_count"] == 2
    assert context["pay_rate_per_file"] == 350
    assert context["estimated_pay"] == 700


def test_shape_context_aggregates_docs_and_conditions():
    loans = [_loan(id=1), _loan(id=2)]
    context = _shape_context(
        loans, now=NOW,
        doc_counter=_counter(2, 5), cond_counter=_counter(1, 3),
    )
    assert context["total_docs_pending"] == 4
    assert context["total_cond_open"] == 2


# ── _file_flags ──────────────────────────────────────────

def test_file_flags_all_healthy():
    assert _file_flags(_loan(), docs_pending=0, cond_open=0, now=NOW) == []


def test_file_flags_stale():
    loan = _loan(updated_at=NOW - timedelta(days=20), created_at=NOW - timedelta(days=20))
    flags = _file_flags(loan, docs_pending=0, cond_open=0, now=NOW)
    assert any("no update in 20 days" in f for f in flags)


def test_file_flags_not_stale_when_closed():
    loan = _loan(status="approved", updated_at=NOW - timedelta(days=30))
    assert _file_flags(loan, docs_pending=0, cond_open=0, now=NOW) == []


def test_file_flags_doc_backlog():
    flags = _file_flags(_loan(), docs_pending=3, cond_open=0, now=NOW)
    assert any("documents still pending" in f for f in flags)


def test_file_flags_condition_backlog():
    flags = _file_flags(_loan(), docs_pending=0, cond_open=4, now=NOW)
    assert any("conditions still open" in f for f in flags)


def test_file_flags_combined():
    loan = _loan(updated_at=NOW - timedelta(days=20), created_at=NOW - timedelta(days=20))
    flags = _file_flags(loan, docs_pending=3, cond_open=3, now=NOW)
    assert len(flags) == 3


# ── _template_queue_explanation ──────────────────────────

def test_template_queue_explanation_no_files():
    result = _template_queue_explanation({"has_files": False})
    assert "don't have any files" in result["summary"]
    assert result["flags"] == []
    assert result["highlight"] == ""


def test_template_queue_explanation_with_files():
    context = _shape_context(
        [_loan(id=1, property_address="123 Main St")], now=NOW,
        doc_counter=_counter(2, 3), cond_counter=_counter(1, 2),
    )
    result = _template_queue_explanation(context)
    assert "1 file" in result["summary"]
    assert "123 Main St" in result["highlight"]


def test_template_queue_explanation_mentions_pay_when_funded():
    context = _shape_context(
        [_loan(id=1, status="closed")], now=NOW,
        doc_counter=_counter(0, 1), cond_counter=_counter(0, 1),
    )
    result = _template_queue_explanation(context)
    assert "estimated pay" in result["summary"]
    assert "$350" in result["summary"]


# ── explain_processor_queue — template fallback on Claude failure ──

def test_explain_processor_queue_falls_back_to_template_on_claude_error():
    with patch(
        "LoanMVP.services.processor_queue_ai_service.gather_processor_queue_context",
        return_value=_shape_context([_loan()], now=NOW, doc_counter=_counter(0, 1), cond_counter=_counter(0, 1)),
    ), patch(
        "LoanMVP.services.processor_queue_ai_service.claude_processor_queue_summary",
        return_value={"error": "ANTHROPIC_API_KEY is not set."},
    ):
        outcome = explain_processor_queue(user_id=1)

    assert outcome["provider"] == "template"
    assert outcome["result"]["summary"]


def test_explain_processor_queue_uses_claude_result_when_available():
    claude_result = {
        "summary": "You have 1 file in your queue.",
        "next_steps": ["Follow up on outstanding docs."],
        "flags": [],
        "highlight": "123 Main St needs attention.",
        "meta": {"provider": "anthropic/claude"},
    }
    with patch(
        "LoanMVP.services.processor_queue_ai_service.gather_processor_queue_context",
        return_value=_shape_context([_loan()], now=NOW, doc_counter=_counter(0, 1), cond_counter=_counter(0, 1)),
    ), patch(
        "LoanMVP.services.processor_queue_ai_service.claude_processor_queue_summary",
        return_value=claude_result,
    ):
        outcome = explain_processor_queue(user_id=1)

    assert outcome["provider"] == "anthropic/claude"
    assert outcome["result"]["summary"] == claude_result["summary"]
