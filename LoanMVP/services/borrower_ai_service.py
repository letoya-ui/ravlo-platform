"""Borrower AI assistant: status clarity, condition/document explanations,
and next-step guidance, grounded entirely in the borrower's own loan data.

Mirrors the ravlo_arv_explainer.py pattern: a real LLM call (Claude) with a
deterministic, non-LLM template fallback so the feature never hard-fails.
"""

from __future__ import annotations

from LoanMVP.models.loan_models import LoanStatusEvent
from LoanMVP.models.underwriter_model import UnderwritingCondition, ConditionRequest
from LoanMVP.models.document_models import DocumentRequest, DocumentNeed
from LoanMVP.services.llm_studio_service import claude_borrower_explainer

_CLEARED_CONDITION_STATUSES = {"cleared", "waived"}
_CLEARED_REQUEST_STATUSES = {"cleared", "waived"}
_CLEARED_NEED_STATUSES = {"waived", "uploaded"}


def _query_raw(borrower):
    """DB reads scoped to this borrower's active loan. Returns a dict of ORM
    rows/None; untestable without an app/DB context, kept separate from the
    pure shaping logic in _shape_context."""
    from LoanMVP.routes.borrower_routes import get_active_loan

    loan = get_active_loan(borrower)
    if not loan:
        return {"loan": None}

    open_conditions = [
        c for c in UnderwritingCondition.query.filter_by(
            borrower_profile_id=borrower.id, loan_id=loan.id
        ).all()
        if (c.status or "").lower() not in _CLEARED_CONDITION_STATUSES
    ]
    condition_requests = [
        r for r in ConditionRequest.query.filter_by(
            borrower_profile_id=borrower.id, loan_id=loan.id
        ).all()
        if (r.status or "").lower() not in _CLEARED_REQUEST_STATUSES
    ]
    document_requests = DocumentRequest.query.filter_by(
        borrower_id=borrower.id, loan_id=loan.id, is_resolved=False
    ).all()
    document_needs = [
        n for n in DocumentNeed.query.filter_by(
            borrower_id=borrower.id, loan_id=loan.id
        ).all()
        if (n.status or "").lower() not in _CLEARED_NEED_STATUSES
    ]
    status_events = (
        LoanStatusEvent.query.filter_by(loan_id=loan.id)
        .order_by(LoanStatusEvent.timestamp.desc())
        .limit(5)
        .all()
    )

    return {
        "loan": loan,
        "open_conditions": open_conditions,
        "condition_requests": condition_requests,
        "document_requests": document_requests,
        "document_needs": document_needs,
        "status_events": status_events,
    }


def _shape_context(
    loan,
    open_conditions=None,
    condition_requests=None,
    document_requests=None,
    document_needs=None,
    status_events=None,
) -> dict:
    """Pure function: plain-primitive dict in/out, no DB/app context needed.
    Duck-typed on attributes so plain objects (e.g. SimpleNamespace) work in
    tests as stand-ins for real ORM rows."""
    if loan is None:
        return {"has_active_loan": False}

    open_conditions = open_conditions or []
    condition_requests = condition_requests or []
    document_requests = document_requests or []
    document_needs = document_needs or []
    status_events = status_events or []

    return {
        "has_active_loan": True,
        "status": loan.status,
        "progress_percent": loan.progress_percent,
        "milestone_stage": loan.milestone_stage,
        "property_address": loan.property_address,
        "amount": loan.amount,
        "open_conditions": [
            {
                "condition_type": c.condition_type,
                "description": c.description,
                "severity": c.severity,
                "status": c.status,
            }
            for c in open_conditions
        ],
        "condition_requests": [
            {"document_name": r.document_name, "status": r.status}
            for r in condition_requests
        ],
        "document_requests": [
            {"document_name": d.document_name, "notes": d.notes, "status": d.status}
            for d in document_requests
        ],
        "document_needs": [
            {"name": n.name, "reason": n.reason, "status": n.status}
            for n in document_needs
        ],
        "recent_status_events": [
            {
                "event_name": e.event_name,
                "description": e.description,
                "status": e.status,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            }
            for e in status_events
        ],
    }


def gather_borrower_context(borrower) -> dict:
    raw = _query_raw(borrower)
    return _shape_context(
        raw.get("loan"),
        raw.get("open_conditions"),
        raw.get("condition_requests"),
        raw.get("document_requests"),
        raw.get("document_needs"),
        raw.get("status_events"),
    )


def _template_explanation(context: dict, question=None) -> dict:
    """Deterministic, non-LLM fallback built directly from context — the
    feature must never hard-fail for the borrower."""
    if not context.get("has_active_loan"):
        return {
            "summary": "You don't have an active loan application right now.",
            "next_steps": [],
            "documents_needed": [],
            "flags": [],
        }

    open_conditions = context.get("open_conditions", [])
    condition_requests = context.get("condition_requests", [])
    document_requests = context.get("document_requests", [])
    document_needs = context.get("document_needs", [])

    milestone = context.get("milestone_stage") or "your application"
    progress = context.get("progress_percent")
    progress_str = f" ({progress}% complete)" if progress is not None else ""
    summary = f"Your loan is currently at: {milestone}{progress_str}."

    next_steps = []
    for c in open_conditions:
        if c.get("description"):
            next_steps.append(c["description"])
    for r in condition_requests:
        if r.get("document_name"):
            next_steps.append(f"Provide: {r['document_name']}")
    if not next_steps:
        next_steps.append("No outstanding action items right now — we'll notify you when something is needed.")

    documents_needed = []
    for d in document_requests:
        if d.get("document_name"):
            documents_needed.append(d["document_name"])
    for n in document_needs:
        if n.get("name"):
            documents_needed.append(n["name"])

    flags = [
        f"{c['condition_type']}: {c['description']}"
        for c in open_conditions
        if (c.get("severity") or "").lower() == "high"
    ]

    return {
        "summary": summary,
        "next_steps": next_steps,
        "documents_needed": documents_needed,
        "flags": flags,
    }


def explain_borrower_status(borrower, question: str | None = None) -> dict:
    context = gather_borrower_context(borrower)

    result = claude_borrower_explainer({"context": context, "question": question})
    if result.get("error"):
        return {
            "result": _template_explanation(context, question),
            "provider": "template",
            "context": context,
        }

    return {
        "result": {
            "summary": result.get("summary", ""),
            "next_steps": result.get("next_steps", []),
            "documents_needed": result.get("documents_needed", []),
            "flags": result.get("flags", []),
        },
        "provider": "anthropic/claude",
        "context": context,
    }
