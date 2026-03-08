from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required
from datetime import datetime

from LoanMVP.extensions import db
from LoanMVP.utils.decorators import role_required
from LoanMVP.ai.base_ai import AIAssistant
from LoanMVP.utils.engagement_engine import EngagementEngine
from LoanMVP.utils.pricing_engine import calculate_dti_ltv

from LoanMVP.models.loan_models import LoanApplication, BorrowerProfile, LoanIntakeSession
from LoanMVP.models.loan_officer_model import LoanOfficerProfile
from LoanMVP.models.crm_models import Lead, CRMNote, Task
from LoanMVP.models.document_models import LoanDocument
from LoanMVP.models.loan_models import CreditProfile

# Ravlo / investor-side models
from LoanMVP.models.deal_models import Deal, RenovationMockup
from LoanMVP.models.document_models import DocumentRequest
from LoanMVP.models.underwriting_models import UnderwritingCondition


loan_officer_bp = Blueprint("loan_officer", __name__, url_prefix="/loan_officer")
assistant = AIAssistant()


# =========================================================
# Helpers
# =========================================================

def _safe_status(value):
    return (value or "").strip().lower()


def _get_featured_rehab_for_deal(deal):
    if not deal:
        return {}

    try:
        rehab = (deal.resolved_json or {}).get("rehab", {}) or {}
    except Exception:
        rehab = {}

    return {
        "before_url": rehab.get("before_url") or "",
        "after_url": rehab.get("after_url") or rehab.get("featured_after_url") or "",
        "style_preset": rehab.get("style_preset") or "",
        "style_prompt": rehab.get("style_prompt") or "",
    }


def _get_recent_mockups_for_deal(deal, limit=4):
    if not deal:
        return []

    return (
        RenovationMockup.query
        .filter_by(deal_id=deal.id)
        .order_by(RenovationMockup.created_at.desc())
        .limit(limit)
        .all()
    )


def _derive_stage_from_status(status):
    status = _safe_status(status)

    if "pending" in status:
        return "Pre-Approval"
    if "submitted" in status:
        return "Submitted"
    if "review" in status:
        return "In Review"
    if "condition" in status:
        return "Conditions"
    if "processing" in status:
        return "Processing"
    if "approved" in status:
        return "Approved"
    if "declined" in status or "denied" in status:
        return "Declined"
    if "closed" in status or "funded" in status:
        return "Closed"

    return "Pipeline"


# =========================================================
# 1. DASHBOARD
# =========================================================
@loan_officer_bp.route("/dashboard")
@login_required
@role_required("loan_officer")
def dashboard():
    officer = LoanOfficerProfile.query.filter_by(user_id=current_user.id).first()

    if not officer:
        officer = LoanOfficerProfile(
            user_id=current_user.id,
            name=getattr(current_user, "username", None) or "Loan Officer"
        )
        db.session.add(officer)
        db.session.commit()
        flash("Temporary loan officer profile created.", "warning")

    leads = (
        Lead.query
        .filter_by(assigned_to=current_user.id)
        .order_by(Lead.created_at.desc())
        .all()
    )

    loans = (
        LoanApplication.query
        .filter_by(loan_officer_id=current_user.id)
        .order_by(LoanApplication.created_at.desc())
        .all()
    )

    pending_intakes = (
        LoanIntakeSession.query
        .filter(
            (LoanIntakeSession.assigned_officer_id == officer.id) |
            (LoanIntakeSession.status == "pending")
        )
        .order_by(LoanIntakeSession.created_at.desc())
        .all()
    )

    pipeline = {
        "submitted": [l for l in loans if _safe_status(l.status) == "submitted"],
        "in_review": [l for l in loans if _safe_status(l.status) in {"in_review", "review"}],
        "approved": [l for l in loans if _safe_status(l.status) == "approved"],
        "declined": [l for l in loans if _safe_status(l.status) in {"declined", "denied"}],
    }

    stats = {
        "total_leads": len(leads),
        "active_loans": len([l for l in loans if _safe_status(l.status) not in {"declined", "denied", "closed", "funded"}]),
        "approved": len([l for l in loans if _safe_status(l.status) == "approved"]),
        "declined": len([l for l in loans if _safe_status(l.status) in {"declined", "denied"}]),
        "pending_intakes": len(pending_intakes),
    }

    try:
        ai_summary = assistant.generate_reply(
            "Summarize loan officer performance across leads, loans, pipeline, and pending intakes.",
            "loan_officer_dashboard"
        )
    except Exception:
        ai_summary = "AI summary unavailable."

    return render_template(
        "loan_officer/dashboard.html",
        officer=officer,
        leads=leads,
        loans=loans,
        ai_intakes=pending_intakes,
        pipeline=pipeline,
        stats=stats,
        ai_summary=ai_summary,
        title="Loan Officer Dashboard",
    )


# =========================================================
# 2. LOAN QUEUE
# =========================================================
@loan_officer_bp.route("/loan_queue")
@login_required
@role_required("loan_officer")
def loan_queue():
    loans = (
        LoanApplication.query
        .filter_by(loan_officer_id=current_user.id)
        .order_by(LoanApplication.created_at.desc())
        .all()
    )

    total_loans = len(loans)
    active_loans = len([l for l in loans if _safe_status(l.status) in {"in_review", "submitted", "pending", "processing"}])
    approved_loans = len([l for l in loans if _safe_status(l.status) in {"approved", "cleared"}])
    declined_loans = len([l for l in loans if _safe_status(l.status) in {"declined", "denied"}])

    try:
        summary_prompt = (
            f"Summarize the current loan officer's queue activity. "
            f"Total loans: {total_loans}, Active: {active_loans}, "
            f"Approved: {approved_loans}, Declined: {declined_loans}. "
            f"Provide one prioritization insight."
        )
        ai_summary = assistant.generate_reply(summary_prompt, "loan_officer")
    except Exception:
        ai_summary = "Summary unavailable."

    return render_template(
        "loan_officer/loan_queue.html",
        loans=loans,
        total_loans=total_loans,
        active_loans=active_loans,
        approved_loans=approved_loans,
        declined_loans=declined_loans,
        ai_summary=ai_summary,
        title="Loan Queue",
    )


# =========================================================
# 3. PIPELINE
# =========================================================
@loan_officer_bp.route("/pipeline")
@login_required
@role_required("loan_officer")
def pipeline():
    status_filter = request.args.get("status", "").strip()
    stage_filter = request.args.get("stage", "").strip()
    name_filter = request.args.get("name", "").strip()

    q = LoanApplication.query.filter_by(loan_officer_id=current_user.id)

    if status_filter:
        q = q.filter(LoanApplication.status == status_filter)

    if name_filter:
        q = q.join(LoanApplication.borrower_profile).filter(
            BorrowerProfile.full_name.ilike(f"%{name_filter}%")
        )

    pipeline_loans = q.order_by(LoanApplication.created_at.desc()).limit(100).all()

    filtered_pipeline = []
    for loan in pipeline_loans:
        loan.milestone_stage = getattr(loan, "milestone_stage", None) or _derive_stage_from_status(loan.status)
        loan.updated_display = getattr(loan, "updated_at", None) or getattr(loan, "created_at", None)

        if stage_filter and loan.milestone_stage != stage_filter:
            continue

        if hasattr(loan, "loan_documents"):
            loan.missing_docs = len([
                d for d in loan.loan_documents
                if _safe_status(getattr(d, "status", "")) != "verified"
            ])
        else:
            loan.missing_docs = 0

        filtered_pipeline.append(loan)

    return render_template(
        "loan_officer/pipeline.html",
        pipeline=filtered_pipeline,
        title="Pipeline",
    )


# =========================================================
# 4. VIEW LOAN (Investor-aware)
# =========================================================
@loan_officer_bp.route("/loan/<int:loan_id>")
@login_required
@role_required("loan_officer")
def view_loan(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    borrower = getattr(loan, "borrower_profile", None)

    # Optional investor / deal linkage
    deal = None
    if hasattr(loan, "deal_id") and loan.deal_id:
        deal = Deal.query.get(loan.deal_id)

    featured_rehab = _get_featured_rehab_for_deal(deal)
    recent_mockups = _get_recent_mockups_for_deal(deal, limit=4)

    engagement_score = None
    credit = None
    ratios = {}

    if borrower:
        try:
            engine = EngagementEngine(borrower)
            engagement_score = engine.score()
        except Exception:
            engagement_score = None

        if hasattr(borrower, "credit_reports") and borrower.credit_reports:
            credit = borrower.credit_reports[-1]

        try:
            ratios = calculate_dti_ltv(borrower, loan, credit)
        except Exception:
            ratios = {}

    documents = getattr(loan, "loan_documents", []) or []
    conditions = getattr(loan, "underwriting_conditions", []) or []

    tasks = (
        Task.query
        .filter_by(loan_id=loan.id)
        .order_by(Task.due_date.asc())
        .all()
    )

    # Rehab / strategy summaries for Ravlo investor workflow
    rehab_scope = getattr(deal, "rehab_scope_json", None) if deal else None
    build_analysis = ((deal.results_json or {}).get("build_analysis", {})) if deal and getattr(deal, "results_json", None) else {}
    deal_strategy = ((deal.results_json or {}).get("strategy_analysis", {})) if deal and getattr(deal, "results_json", None) else {}

    try:
        ai_summary = assistant.generate_reply(
            f"Summarize loan file #{loan.id}. "
            f"Loan status: {loan.status}. "
            f"Borrower: {borrower.full_name if borrower else 'N/A'}. "
            f"Deal linked: {'yes' if deal else 'no'}. "
            f"Conditions: {len(conditions)}. Documents: {len(documents)}.",
            "loan_officer_loan_file"
        )
    except Exception:
        ai_summary = "AI summary unavailable."

    return render_template(
        "loan_officer/view_loan.html",
        loan=loan,
        borrower=borrower,
        credit=credit,
        documents=documents,
        tasks=tasks,
        conditions=conditions,
        engagement_score=engagement_score,
        ratios=ratios,
        ai_summary=ai_summary,

        # Ravlo investor context
        deal=deal,
        featured_rehab=featured_rehab,
        recent_mockups=recent_mockups,
        rehab_scope=rehab_scope,
        build_analysis=build_analysis,
        deal_strategy=deal_strategy,

        title=f"Loan #{loan.id}",
    )


# =========================================================
# 5. LEADS
# =========================================================
@loan_officer_bp.route("/leads")
@login_required
@role_required("loan_officer")
def leads():
    leads = (
        Lead.query
        .filter_by(assigned_to=current_user.id)
        .order_by(Lead.created_at.desc())
        .all()
    )
    return render_template(
        "loan_officer/leads.html",
        leads=leads,
        title="Leads",
    )


@loan_officer_bp.route("/lead/<int:lead_id>")
@login_required
@role_required("loan_officer")
def lead_detail(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    notes = CRMNote.query.filter_by(lead_id=lead.id).order_by(CRMNote.created_at.desc()).all()

    try:
        ai_summary = assistant.generate_reply(
            f"Summarize borrower insights for lead: {lead.name}, {lead.email}",
            "crm"
        )
    except Exception:
        ai_summary = "AI summary unavailable."

    return render_template(
        "loan_officer/lead_detail.html",
        lead=lead,
        notes=notes,
        ai_summary=ai_summary,
        title="Lead Details",
    )


# =========================================================
# 6. BORROWERS
# =========================================================
@loan_officer_bp.route("/borrowers")
@login_required
@role_required("loan_officer")
def borrowers():
    q = request.args.get("q", "").strip()

    qry = BorrowerProfile.query

    if q:
        qry = qry.filter(
            BorrowerProfile.full_name.ilike(f"%{q}%") |
            BorrowerProfile.email.ilike(f"%{q}%")
        )

    borrowers = qry.order_by(BorrowerProfile.created_at.desc()).all()

    for b in borrowers:
        b.has_loan = len(getattr(b, "loans", []) or []) > 0
        b.has_started_1003 = any(getattr(l, "amount", None) for l in (getattr(b, "loans", []) or []))

    return render_template(
        "loan_officer/borrowers.html",
        borrowers=borrowers,
        query=q,
        title="Borrowers",
    )


@loan_officer_bp.route("/borrower/<int:borrower_id>")
@login_required
@role_required("loan_officer")
def view_borrower(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)

    loans = (
        LoanApplication.query
        .filter_by(borrower_profile_id=borrower_id)
        .order_by(LoanApplication.created_at.desc())
        .all()
    )

    credit = borrower.credit_reports[-1] if hasattr(borrower, "credit_reports") and borrower.credit_reports else None

    tasks = (
        Task.query
        .filter_by(borrower_id=borrower_id)
        .order_by(Task.due_date.asc())
        .all()
    )

    documents = (
        LoanDocument.query
        .filter_by(borrower_profile_id=borrower_id)
        .all()
    )

    return render_template(
        "loan_officer/borrower_view.html",
        borrower=borrower,
        loans=loans,
        credit=credit,
        tasks=tasks,
        documents=documents,
        title="Borrower View",
    )