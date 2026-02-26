# =========================================================
# 🧮 LoanMVP Compliance Routes — 2025 Unified Final Version
# =========================================================

from flask import Blueprint, render_template, request, jsonify, flash
from flask_login import current_user
from datetime import datetime
from LoanMVP.extensions import db
from LoanMVP.ai.base_ai import AIAssistant
from LoanMVP.models.loan_models import LoanApplication
from LoanMVP.models.document_models import LoanDocument
from LoanMVP.models.system_models import AuditLog
from LoanMVP.utils.decorators import role_required  # ✅ Role-based access

# ---------------------------------------------------------
# Blueprint Setup
# ---------------------------------------------------------
compliance_bp = Blueprint("compliance", __name__, url_prefix="/compliance")
assistant = AIAssistant()

# ---------------------------------------------------------
# 🧭 Compliance Dashboard
# ---------------------------------------------------------
@compliance_bp.route("/dashboard")
@role_required("compliance")
def dashboard():
    """Main compliance hub — verifies loan files, document status, and audit events."""
    loans = LoanApplication.query.order_by(LoanApplication.created_at.desc()).limit(50).all()
    docs = LoanDocument.query.order_by(LoanDocument.created_at.desc()).limit(50).all()
    pending_docs = [d for d in docs if d.status not in ["approved", "verified"]]

    audits = []
    if hasattr(AuditLog, "timestamp"):
        audits = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(10).all()

    try:
        ai_summary = assistant.generate_reply(
            f"Summarize compliance status: {len(loans)} loans, {len(pending_docs)} pending documents.",
            "compliance_dashboard"
        )
    except Exception as e:
        print(" AI summary error:", e)
        ai_summary = "AI compliance summary unavailable."

    return render_template(
        "compliance/dashboard.html",
        loans=loans,
        docs=docs,
        pending_docs=pending_docs,
        audits=audits,
        ai_summary=ai_summary,
        title="Compliance Dashboard"
    )

# ---------------------------------------------------------
# 🧾 Document Verification
# ---------------------------------------------------------
@compliance_bp.route("/verify/<int:doc_id>", methods=["GET", "POST"])
@role_required("compliance")
def verify(doc_id):
    """Manual or AI-powered document verification."""
    doc = LoanDocument.query.get_or_404(doc_id)

    if request.method == "POST":
        try:
            ai_verdict = assistant.generate_reply(
                f"Verify authenticity and completeness of document {doc.filename} for loan {doc.loan_id}.",
                "admin_verification"
            )
        except Exception as e:
            print(" AI verification error:", e)
            ai_verdict = "AI verification unavailable. Please verify manually."

        doc.status = "verified" if "authentic" in ai_verdict.lower() else "flagged"
        doc.updated_at = datetime.utcnow()
        db.session.commit()

        flash(f"✅ Document '{doc.filename}' marked as {doc.status}.", "success")
        return render_template(
            "compliance/verify_result.html",
            doc=doc,
            ai_verdict=ai_verdict,
            title="Document Verification"
        )

    return render_template("compliance/verify.html", doc=doc, title="Verify Document")

# ---------------------------------------------------------
# 📊 Automated Pipeline Auditing
# ---------------------------------------------------------
@compliance_bp.route("/pipeline_audit")
@role_required("compliance")
def pipeline_audit():
    """Scans the loan pipeline for incomplete or at-risk records."""
    loans = LoanApplication.query.all()
    flagged = []

    for loan in loans:
        issues = []
        if not loan.borrower_id:
            issues.append("Missing borrower profile")
        if not loan.amount or loan.amount <= 0:
            issues.append("Invalid or missing loan amount")
        if loan.status not in ["approved", "closed"]:
            issues.append("Pending compliance review")
        if issues:
            flagged.append({"loan": loan, "issues": issues})

    try:
        ai_summary = assistant.generate_reply(
            f"Review {len(flagged)} flagged pipeline items for compliance issues.",
            "pipeline_auto"
        )
    except Exception:
        ai_summary = "AI pipeline audit unavailable."

    return render_template(
        "compliance/pipeline_audit.html",
        flagged=flagged,
        ai_summary=ai_summary,
        title="Pipeline Compliance Audit"
    )

# ---------------------------------------------------------
# 🧠 AI Compliance Review API
# ---------------------------------------------------------
@compliance_bp.route("/ai_review")
@role_required("compliance")
def ai_review():
    """Returns AI-generated analysis for a compliance query."""
    query = request.args.get("query", "")
    context = request.args.get("context", "compliance")

    if not query:
        return jsonify({"reply": "⚠️ Please provide a query."}), 400

    try:
        reply = assistant.generate_reply(query, context)
    except Exception as e:
        print(" AI compliance review error:", e)
        reply = "Error generating compliance analysis."

    return jsonify({"reply": reply})

# ---------------------------------------------------------
# 🪪 Audit Log Viewer
# ---------------------------------------------------------
@compliance_bp.route("/logs")
@role_required("compliance")
def logs():
    """Displays recent compliance and system audit logs."""
    logs = []
    if hasattr(AuditLog, "timestamp"):
        logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(100).all()

    return render_template(
        "compliance/logs.html",
        logs=logs,
        title="Audit Logs"
    )
