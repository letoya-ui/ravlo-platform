from flask import Blueprint, render_template
from LoanMVP.models.loan_models import LoanApplication
from LoanMVP.models.document_models import LoanDocument
from LoanMVP.models.underwriter_model import UnderwritingCondition

processor_queue_bp = Blueprint("processor_queue", __name__, url_prefix="/processor")


@processor_queue_bp.route("/queue")
def queue():
    # Get all active loans
    loans = LoanApplication.query.filter(
        LoanApplication.status.in_(["Pending", "In Review", "Submitted"])
    ).order_by(LoanApplication.created_at.desc()).all()

    # Build summary totals
    total_loans = len(loans)
    docs_pending = LoanDocument.query.filter(
        LoanDocument.status.in_(["requested", "pending"])
    ).count()
    cond_open = UnderwritingCondition.query.filter_by(status="Open").count()

    # Prepare pipeline dataset
    pipeline = []
    for loan in loans:

        # Count docs
        doc_total = len(loan.loan_documents)
        doc_pending = len([
            d for d in loan.loan_documents 
            if d.status.lower() in ("pending", "requested")
        ])

        # Count conditions
        cond_total = len(loan.underwriting_conditions)
        cond_open_count = len([
            c for c in loan.underwriting_conditions 
            if c.status.lower() == "open"
        ])

        pipeline.append({
            "loan": loan,
            "borrower": loan.borrower_profile,
            "docs_total": doc_total,
            "docs_pending": doc_pending,
            "cond_total": cond_total,
            "cond_open": cond_open_count,
            "risk": loan.risk_level,
            "ltv": loan.ltv_ratio,
            "amount": loan.amount
        })

    return render_template(
        "processor/queue.html",
        pipeline=pipeline,
        total_loans=total_loans,
        docs_pending=docs_pending,
        cond_open=cond_open
    )

@processor_queue_bp.route("/loan/<int:loan_id>")
def loan_review(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    borrower = loan.borrower_profile

    docs = loan.loan_documents
    conditions = loan.underwriting_conditions
    payments = loan.payments  # PaymentRecord
    ai_summary = loan.ai_summary

    # Separate docs
    docs_pending = [d for d in docs if d.status.lower() in ("pending", "requested")]
    docs_verified = [d for d in docs if d.status.lower() == "verified"]

    # Separate conditions
    cond_open = [c for c in conditions if c.status.lower() == "open"]
    cond_cleared = [c for c in conditions if c.status.lower() == "cleared"]

    return render_template(
        "processor/loan_review.html",
        loan=loan,
        borrower=borrower,
        docs=docs,
        docs_pending=docs_pending,
        docs_verified=docs_verified,
        cond_open=cond_open,
        cond_cleared=cond_cleared,
        payments=payments,
        ai_summary=ai_summary
    )
