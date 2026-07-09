"""Processor Queue AI: aggregate summary across a processor's whole active
file queue — file counts, document/condition backlog, estimated pay, and
risk flags rolled up across every file.

Mirrors loan_officer_pipeline_ai_service.py's pattern: a real LLM call
(Claude) with a deterministic, non-LLM template fallback so the feature
never hard-fails.

Estimated pay uses the same rate and "funded" status definition already used
company-wide in LoanMVP/routes/admin.py (COMPENSATION_DEFAULTS
["processor_file_pay"] = $350/funded file, FUNDED_LOAN_STATUSES) — mirrored
here as constants rather than imported, for the same reason
loan_officer_pipeline_ai_service.py mirrors its own rate: importing a route
module into a service risks pulling in admin.py's much heavier import
chain. Keep these values in sync with admin.py by hand if they ever change.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from LoanMVP.models.processor_model import ProcessorProfile
from LoanMVP.models.loan_models import LoanApplication
from LoanMVP.models.document_models import LoanDocument
from LoanMVP.models.underwriter_model import UnderwritingCondition
from LoanMVP.services.llm_studio_service import claude_processor_queue_summary

_STALE_DAYS = 14
_CLOSED_STATUSES = {"approved", "declined", "closed"}

# Mirrors LoanMVP/routes/admin.py's COMPENSATION_DEFAULTS["processor_file_pay"]
# and FUNDED_LOAN_STATUSES — see module docstring.
_PER_FILE_PAY = 350
_FUNDED_STATUSES = {"closed", "funded", "completed", "paid"}

_DOC_PENDING_STATUSES = {"pending", "requested", "under review", "uploaded"}
_COND_OPEN_STATUSES = {"open", "pending", "requested"}


def _query_raw(user_id):
    """DB read scoped to this processor's own files. Untestable without an
    app/DB context, kept separate from the pure shaping logic in
    _shape_context."""
    profile = ProcessorProfile.query.filter_by(user_id=user_id).first()
    if not profile:
        return {"loans": []}

    loans = (
        LoanApplication.query
        .filter_by(processor_id=profile.id)
        .order_by(LoanApplication.updated_at.desc())
        .all()
    )
    return {"loans": loans}


def _file_label(loan):
    """Best-effort human label: borrower name + address -> address -> 'Loan #<id>'."""
    borrower = getattr(loan, "borrower_profile", None)
    name = getattr(borrower, "full_name", None) if borrower else None
    address = getattr(loan, "property_address", None)
    if name and address:
        return f"{name} — {address}"
    return name or address or f"Loan #{loan.id}"


def _file_counts(loan, doc_counter, cond_counter):
    """docs_pending/docs_total and cond_open/cond_total for one loan, via
    injected count functions so this stays testable without a DB."""
    docs_pending, docs_total = doc_counter(loan)
    cond_open, cond_total = cond_counter(loan)
    return docs_pending, docs_total, cond_open, cond_total


def _default_doc_counter(loan):
    docs = LoanDocument.query.filter_by(loan_id=loan.id).all()
    pending = [d for d in docs if (d.status or "").strip().lower() in _DOC_PENDING_STATUSES]
    return len(pending), len(docs)


def _default_cond_counter(loan):
    conditions = UnderwritingCondition.query.filter_by(loan_id=loan.id).all()
    open_ = [c for c in conditions if (c.status or "").strip().lower() in _COND_OPEN_STATUSES]
    return len(open_), len(conditions)


def _file_flags(loan, docs_pending, cond_open, now=None):
    """New risk-flag rules for a single file, grounded in real fields.
    Field access is duck-typed (works with SimpleNamespace in tests)."""
    now = now or datetime.utcnow()
    label = _file_label(loan)
    status = (loan.status or "").strip().lower()

    flags = []

    if status not in _CLOSED_STATUSES:
        last_activity = loan.updated_at or loan.created_at
        if last_activity:
            days_stale = (now - last_activity).days
            if days_stale > _STALE_DAYS:
                flags.append(f"{label}: no update in {days_stale} days.")

    if docs_pending >= 3:
        flags.append(f"{label}: {docs_pending} documents still pending.")

    if cond_open >= 3:
        flags.append(f"{label}: {cond_open} conditions still open.")

    return flags


def _shape_context(loans, now=None, doc_counter=None, cond_counter=None) -> dict:
    """Pure function: plain-primitive dict in/out, no DB/app context needed
    when doc_counter/cond_counter are injected (as tests do). Duck-typed on
    attributes so SimpleNamespace stand-ins work in tests."""
    loans = loans or []
    doc_counter = doc_counter or _default_doc_counter
    cond_counter = cond_counter or _default_cond_counter

    if not loans:
        return {
            "has_files": False,
            "total_files": 0,
        }

    funded_count = sum(
        1 for l in loans if (l.status or "").strip().lower() in _FUNDED_STATUSES
    )
    estimated_pay = funded_count * _PER_FILE_PAY

    file_flags = []
    total_docs_pending = 0
    total_cond_open = 0
    files_summary = []

    for l in loans:
        docs_pending, docs_total, cond_open, cond_total = _file_counts(l, doc_counter, cond_counter)
        total_docs_pending += docs_pending
        total_cond_open += cond_open
        file_flags.extend(_file_flags(l, docs_pending, cond_open, now=now))
        files_summary.append({
            "id": l.id,
            "label": _file_label(l),
            "status": l.status,
            "docs_pending": docs_pending,
            "docs_total": docs_total,
            "cond_open": cond_open,
            "cond_total": cond_total,
        })

    return {
        "has_files": True,
        "total_files": len(loans),
        "funded_count": funded_count,
        "estimated_pay": estimated_pay,
        "pay_rate_per_file": _PER_FILE_PAY,
        "total_docs_pending": total_docs_pending,
        "total_cond_open": total_cond_open,
        "file_flags": file_flags,
        "files": files_summary,
    }


def gather_processor_queue_context(user_id) -> dict:
    raw = _query_raw(user_id)
    return _shape_context(raw.get("loans"))


def _template_queue_explanation(context: dict) -> dict:
    """Deterministic, non-LLM fallback built directly from context — the
    feature must never hard-fail for the processor."""
    if not context.get("has_files"):
        return {
            "summary": "You don't have any files in your queue right now.",
            "next_steps": [],
            "flags": [],
            "highlight": "",
        }

    total_files = context["total_files"]
    summary = (
        f"You have {total_files} file{'s' if total_files != 1 else ''} in your "
        f"queue, with {context['total_docs_pending']} documents and "
        f"{context['total_cond_open']} conditions still open."
    )
    if context.get("funded_count"):
        summary += (
            f" {context['funded_count']} file{'s' if context['funded_count'] != 1 else ''} "
            f"funded so far, for an estimated pay of ${context['estimated_pay']:,.0f} "
            f"at ${context['pay_rate_per_file']:,.0f}/funded file."
        )

    next_steps = []
    if context["file_flags"]:
        next_steps.append("Resolve the flagged files below before moving the queue further along.")
    else:
        next_steps.append("Your queue has no outstanding flags right now — keep it moving.")

    busiest = max(
        context["files"],
        key=lambda f: f["docs_pending"] + f["cond_open"],
        default=None,
    )
    highlight = (
        f"{busiest['label']} has the most outstanding items ({busiest['docs_pending']} docs, {busiest['cond_open']} conditions)."
        if busiest and (busiest["docs_pending"] + busiest["cond_open"] > 0) else ""
    )

    return {
        "summary": summary,
        "next_steps": next_steps,
        "flags": context["file_flags"],
        "highlight": highlight,
    }


def explain_processor_queue(user_id, question: str | None = None) -> dict:
    context = gather_processor_queue_context(user_id)

    result = claude_processor_queue_summary({"context": context, "question": question})
    if result.get("error"):
        return {
            "result": _template_queue_explanation(context),
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
