from LoanMVP.shared import generate_portfolio_summary, high_risk_loans
from LoanMVP.utils.ai import summarize_underwriter_context
from LoanMVP.models.ai_models import AIAuditLog

@underwriter_bp.route("/reports")
@role_required("underwriter")
def reports():
    # 🧮 Pull summarized metrics
    ai_portfolio = generate_portfolio_summary()
    risky_loans = high_risk_loans(threshold=0.85)

    # 🧠 Generate AI insight
    ai_summary = summarize_underwriter_context(
        f"Analyze portfolio: {ai_portfolio}. Found {len(risky_loans)} high-risk loans."
    )

    return render_template(
        "underwriter/reports.html",
        ai_summary=ai_summary,
        risky_loans=risky_loans,
        title="Reports & Insights"
    )

def log_ai_summary(borrower_id=None, lead_id=None, context=None, ai_summary=None, role_view=None, module="shared_ai"):
    """Logs shared AI insight (used across Borrower + CRM)."""
    entry = AIAuditLog(
        module=module,
        action="ai_summary_sync",
        details=ai_summary,
        borrower_id=borrower_id,
        lead_id=lead_id,
        context=context,
        role_view=role_view
    )
    db.session.add(entry)
    db.session.commit()

def get_latest_ai_summary(borrower_id=None, lead_id=None, context=None):
    """Fetches latest AI summary for a borrower or lead context."""
    q = AIAuditLog.query.filter_by(context=context)
    if borrower_id:
        q = q.filter_by(borrower_id=borrower_id)
    if lead_id:
        q = q.filter_by(lead_id=lead_id)
    return q.order_by(AIAuditLog.created_at.desc()).first()
