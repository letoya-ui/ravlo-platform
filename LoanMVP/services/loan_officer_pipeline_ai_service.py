"""Pipeline AI: aggregate summary across a loan officer's whole active loan
pipeline — total value, stage breakdown, and risk flags rolled up across
every loan.

Mirrors investor_portfolio_ai_service.py's pattern: a real LLM call (Claude)
with a deterministic, non-LLM template fallback so the feature never
hard-fails. No commission/dollar-comp math — no rate/commission model exists
for loan officers, so this only aggregates the real, already-modeled
LoanApplication.amount.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from LoanMVP.models.loan_officer_model import LoanOfficerProfile
from LoanMVP.models.loan_models import LoanApplication
from LoanMVP.services.llm_studio_service import claude_loan_pipeline_summary

_STALE_DAYS = 14
_HIGH_DTI_THRESHOLD = 43.0
_HIGH_LTV_THRESHOLD = 0.95
_CLOSED_STATUSES = {"approved", "declined", "closed"}


def _query_raw(user_id):
    """DB read scoped to this loan officer's own loans. Untestable without an
    app/DB context, kept separate from the pure shaping logic in
    _shape_context."""
    officer = LoanOfficerProfile.query.filter_by(user_id=user_id).first()
    if not officer:
        return {"loans": []}

    loans = (
        LoanApplication.query
        .filter_by(loan_officer_id=officer.id)
        .order_by(LoanApplication.updated_at.desc())
        .all()
    )
    return {"loans": loans}


def _loan_label(loan):
    """Best-effort human label: borrower name + address -> address -> 'Loan #<id>'."""
    borrower = getattr(loan, "borrower_profile", None)
    name = getattr(borrower, "full_name", None) if borrower else None
    address = getattr(loan, "property_address", None)
    if name and address:
        return f"{name} — {address}"
    return name or address or f"Loan #{loan.id}"


def _loan_flags(loan, now=None):
    """New risk-flag rules for a single loan, grounded in real fields.
    Field access is duck-typed (works with SimpleNamespace in tests)."""
    now = now or datetime.utcnow()
    label = _loan_label(loan)
    status = (loan.status or "").strip().lower()

    flags = []

    if status not in _CLOSED_STATUSES:
        last_activity = loan.updated_at or loan.created_at
        if last_activity:
            days_stale = (now - last_activity).days
            if days_stale > _STALE_DAYS:
                flags.append(f"{label}: no update in {days_stale} days.")

    back_end_dti = getattr(loan, "back_end_dti", None)
    if back_end_dti is not None and back_end_dti > _HIGH_DTI_THRESHOLD:
        flags.append(f"{label}: back-end DTI of {back_end_dti:.1f}% exceeds {_HIGH_DTI_THRESHOLD:.0f}%.")

    ltv_ratio = getattr(loan, "ltv_ratio", None)
    if ltv_ratio is not None and ltv_ratio > _HIGH_LTV_THRESHOLD:
        flags.append(f"{label}: LTV of {ltv_ratio * 100:.1f}% exceeds {_HIGH_LTV_THRESHOLD * 100:.0f}%.")

    return flags


def _shape_context(loans, now=None) -> dict:
    """Pure function: plain-primitive dict in/out, no DB/app context needed.
    Duck-typed on attributes so SimpleNamespace stand-ins work in tests."""
    loans = loans or []

    if not loans:
        return {
            "has_loans": False,
            "total_loans": 0,
        }

    total_pipeline_value = sum((l.amount or 0) for l in loans)

    stage_counts = {}
    for l in loans:
        stage = l.milestone_stage or "Unspecified"
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

    loan_flags = []
    for l in loans:
        loan_flags.extend(_loan_flags(l, now=now))

    loans_summary = [
        {
            "id": l.id,
            "label": _loan_label(l),
            "amount": l.amount or 0,
            "status": l.status,
            "milestone_stage": l.milestone_stage,
        }
        for l in loans
    ]

    return {
        "has_loans": True,
        "total_loans": len(loans),
        "total_pipeline_value": total_pipeline_value,
        "stage_counts": stage_counts,
        "loan_flags": loan_flags,
        "loans": loans_summary,
    }


def gather_loan_officer_pipeline_context(user_id) -> dict:
    raw = _query_raw(user_id)
    return _shape_context(raw.get("loans"))


def _template_pipeline_explanation(context: dict) -> dict:
    """Deterministic, non-LLM fallback built directly from context — the
    feature must never hard-fail for the loan officer."""
    if not context.get("has_loans"):
        return {
            "summary": "You don't have any loans in your pipeline yet.",
            "next_steps": [],
            "flags": [],
            "highlight": "",
        }

    total_loans = context["total_loans"]
    total_value = context["total_pipeline_value"]
    stage_counts = context["stage_counts"]
    stage_text = ", ".join(f"{count} {stage}" for stage, count in stage_counts.items())
    summary = (
        f"You're tracking {total_loans} loan{'s' if total_loans != 1 else ''} "
        f"worth ${total_value:,.0f} in total ({stage_text})."
    )

    next_steps = []
    if context["loan_flags"]:
        next_steps.append("Resolve the flagged risks below before moving these loans further along.")
    else:
        next_steps.append("Your pipeline has no outstanding flags right now — keep it moving.")

    largest = max(context["loans"], key=lambda l: l["amount"], default=None)
    highlight = (
        f"{largest['label']} is your largest active loan at ${largest['amount']:,.0f}."
        if largest else ""
    )

    return {
        "summary": summary,
        "next_steps": next_steps,
        "flags": context["loan_flags"],
        "highlight": highlight,
    }


def explain_loan_officer_pipeline(user_id, question: str | None = None) -> dict:
    context = gather_loan_officer_pipeline_context(user_id)

    result = claude_loan_pipeline_summary({"context": context, "question": question})
    if result.get("error"):
        return {
            "result": _template_pipeline_explanation(context),
            "provider": "template",
            "context": context,
        }

    return {
        "result": {
            "summary": result.get("summary", ""),
            "next_steps": result.get("next_steps", []),
            "flags": result.get("flags", []),
            "highlight": result.get("highlight", ""),
        },
        "provider": "anthropic/claude",
        "context": context,
    }
