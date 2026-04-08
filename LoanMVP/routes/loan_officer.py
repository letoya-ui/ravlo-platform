# Unified Loan Officer Blueprint (Cleaned Structure)
# -------------------------------------------------
# =============================================================
#  Loan Officer Routes — Cleaned & Organized
# =============================================================

import os
import json
from datetime import datetime
from collections import defaultdict

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    send_file,
    current_app,
)
from flask_login import current_user
from werkzeug.utils import secure_filename

from LoanMVP.extensions import db, csrf
from LoanMVP.utils.decorators import role_required, loan_officer_onboarding_required

# AI
from LoanMVP.ai.base_ai import AIAssistant
from LoanMVP.ai.master_ai import master_ai

# Utils / engines
from LoanMVP.utils.engagement_engine import EngagementEngine
from LoanMVP.utils.pricing_engine import calculate_dti_ltv
from LoanMVP.utils.pdf_generator import fill_1003_pdf
from LoanMVP.utils.needs_engine import generate_needs
from LoanMVP.utils.preapproval_engine import PreapprovalEngine
from LoanMVP.utils.preapproval_letter import generate_preapproval_pdf
from LoanMVP.utils.tracking import track_event
from LoanMVP.utils.payment_engine import (
    calculate_monthly_payment,
    calculate_taxes,
    calculate_insurance,
    calculate_mortgage_insurance,
)
from LoanMVP.utils.emailer import send_email_with_attachment

from LoanMVP.services.equifax_api import EquifaxAPI

# Optional AI helper / custom engine
from LoanMVP.utils.ai import LoanMVPAI

# Models
from LoanMVP.models.loan_models import (
    LoanApplication,
    BorrowerProfile,
    CreditProfile,
    LoanIntakeSession,
    LoanQuote,
    Upload,
    LoanStatusEvent,
    LoanScenario,
    BorrowerConsent,  
)
from LoanMVP.models.loan_officer_model import LoanOfficerProfile
from LoanMVP.models.crm_models import (
    Lead,
    CRMNote,
    Message,
    Task,
    LeadSource,
    FollowUpItem,
    MessageThread,
)
from LoanMVP.models.document_models import (
    LoanDocument,
    DocumentRequest,
)
from LoanMVP.models.ai_models import (
    AIIntakeSummary,
    AIAssistantInteraction,
)
from LoanMVP.models.borrowers import BorrowerInteraction
from LoanMVP.models.payment_models import PaymentRecord
from LoanMVP.models.campaign_model import Campaign
from LoanMVP.models.user_model import User
# Forms
from LoanMVP.forms import BorrowerProfileForm
from LoanMVP.forms.loan_officer_forms import (
    GenerateQuoteForm,
    BorrowerSearchForm,
    BorrowerIntakeForm,
    LoanEditForm,
    QuotePlanForm,
    UploadForm,
    FollowUpForm,
    CRMNoteForm,
)
from LoanMVP.forms.ai_forms import AIIntakeReviewForm

loan_officer_bp = Blueprint("loan_officer", __name__, url_prefix="/loan_officer")


equifax = EquifaxAPI()

assistant = AIAssistant()
ai = LoanMVPAI()

def _resolve_recipient_name(recipient_type, recipient_id):
    """
    Best-effort display name resolver for inbox UI.
    Safe fallback if a model is missing or record not found.
    """
    try:
        if recipient_type == "borrower" and BorrowerProfile:
            borrower = BorrowerProfile.query.get(recipient_id)
            if borrower:
                return getattr(borrower, "full_name", None) or getattr(borrower, "name", None) or f"Borrower #{recipient_id}"

        if recipient_type == "lead" and Lead:
            lead = Lead.query.get(recipient_id)
            if lead:
                return getattr(lead, "full_name", None) or getattr(lead, "name", None) or f"Lead #{recipient_id}"

        if recipient_type == "realtor" and Realtor:
            realtor = Realtor.query.get(recipient_id)
            if realtor:
                return getattr(realtor, "full_name", None) or getattr(realtor, "name", None) or f"Realtor #{recipient_id}"
    except Exception:
        pass

    return f"{recipient_type.title()} #{recipient_id}"

def enforce_onboarding_flow():
    if not current_user.ica_accepted:
        return redirect(url_for("loan_officer.agreement"))

    if not current_user.nda_accepted:
        return redirect(url_for("loan_officer.nda"))

    if not current_user.onboarding_complete:
        return redirect(url_for("loan_officer.onboarding"))

    return None

# =============================================================
# 1. DASHBOARD
# =============================================================
@loan_officer_bp.route("/dashboard")
@role_required("loan_officer")
@loan_officer_onboarding_required
def dashboard():
    redirect_response = enforce_onboarding_flow()
    if redirect_response:
        return redirect_response

    officer = LoanOfficerProfile.query.filter_by(user_id=current_user.id).first()

    if not officer:
        officer = LoanOfficerProfile(
            user_id=current_user.id,
            name=f"{current_user.first_name} {current_user.last_name}",
            email=getattr(current_user, "email", None),
        )
        db.session.add(officer)
        db.session.commit()
        flash("Temporary loan officer profile created.", "warning")

    leads = Lead.query.filter_by(
        assigned_to=current_user.id
    ).order_by(Lead.created_at.desc()).all()

    # IMPORTANT: loan_officer_id on LoanApplication points to LoanOfficerProfile.id
    loans = LoanApplication.query.filter_by(
        loan_officer_id=officer.id
    ).order_by(LoanApplication.created_at.desc()).all()

    pending_intakes = LoanIntakeSession.query.filter(
        (LoanIntakeSession.assigned_officer_id == officer.id) |
        (LoanIntakeSession.status == "pending")
    ).order_by(LoanIntakeSession.created_at.desc()).all()

    def _norm_status(val):
        return (val or "").strip().lower()

    def _norm_type(val):
        return (val or "").strip().lower()

    capital_loan_types = {
        "investor capital",
        "fix & flip",
        "new construction",
        "rental / dscr",
        "bridge loan",
        "land acquisition",
        "development capital",
    }

    capital_loans = [
        l for l in loans
        if _norm_type(getattr(l, "loan_type", None)) in capital_loan_types
        or _norm_status(getattr(l, "status", None)) == "capital submitted"
    ]

    pipeline = {
        "submitted": [
            l for l in loans
            if _norm_status(l.status) in ["submitted", "capital submitted"]
        ],
        "in_review": [
            l for l in loans
            if _norm_status(l.status) in ["in_review", "in review", "processing", "under review"]
        ],
        "approved": [
            l for l in loans
            if _norm_status(l.status) == "approved"
        ],
        "declined": [
            l for l in loans
            if _norm_status(l.status) == "declined"
        ],
        "capital_requests": capital_loans,
    }

    stats = {
        "total_leads": len(leads),
        "active_loans": len([
            l for l in loans
            if _norm_status(l.status) not in ["declined", "closed"]
        ]),
        "approved": len([
            l for l in loans
            if _norm_status(l.status) == "approved"
        ]),
        "declined": len([
            l for l in loans
            if _norm_status(l.status) == "declined"
        ]),
        "pending_intakes": len(pending_intakes),
        "capital_requests": len(capital_loans),
    }

    try:
        assistant = AIAssistant()
        ai_summary = assistant.generate_reply(
            "Summarize loan officer performance across leads, loans, pipeline, and capital applications.",
            "loan_officer_dashboard"
        )
    except Exception:
        ai_summary = "AI summary unavailable."

    return render_template(
        "loan_officer/dashboard.html",
        officer=officer,
        leads=leads,
        loans=loans,
        capital_loans=capital_loans,
        pending_intakes=pending_intakes,
        pipeline=pipeline,
        stats=stats,
        ai_summary=ai_summary,
        active_tab="dashboard",
        title="Loan Officer Dashboard",
    )



@loan_officer_bp.route("/onboarding", methods=["GET"])
@role_required("loan_officer")
def onboarding():
    if not getattr(current_user, "ica_accepted", False):
        return redirect(url_for("loan_officer.agreement"))

    if not getattr(current_user, "nda_accepted", False):
        return redirect(url_for("loan_officer.nda"))

    if getattr(current_user, "onboarding_complete", False):
        return redirect(url_for("loan_officer.dashboard"))

    return render_template(
        "loan_officer/onboarding.html",
        assigned_role="Loan Officer",
        onboarding_progress="15%",
        resource_count=6,
        required_steps=6,
    )


@loan_officer_bp.route("/onboarding/complete", methods=["POST"])
@role_required("loan_officer")
def complete_onboarding():
    acknowledged = request.form.get("acknowledged")
    agreement = request.form.get("agreement")

    if not acknowledged or not agreement:
        flash("You must confirm all acknowledgment items before continuing.", "danger")
        return redirect(url_for("loan_officer.onboarding"))

    current_user.onboarding_complete = True
    db.session.commit()

    flash("Onboarding completed. Welcome to your dashboard.", "success")
    return redirect(url_for("loan_officer.dashboard"))

@loan_officer_bp.route("/nda", methods=["GET"])
@role_required("loan_officer")
def nda():
    if getattr(current_user, "nda_accepted", False):
        if getattr(current_user, "onboarding_complete", False):
            return redirect(url_for("loan_officer.dashboard"))
        return redirect(url_for("loan_officer.onboarding"))

    return render_template("loan_officer/nda.html")

@loan_officer_bp.route("/nda/accept", methods=["POST"])
@role_required("loan_officer")
def accept_nda():
    nda_ack = request.form.get("nda_ack")
    nda_agree = request.form.get("nda_agree")

    if not nda_ack or not nda_agree:
        flash("You must accept the NDA to continue.", "danger")
        return redirect(url_for("loan_officer.nda"))

    current_user.nda_accepted = True
    db.session.commit()

    flash("NDA accepted successfully.", "success")
    return redirect(url_for("loan_officer.onboarding"))

@loan_officer_bp.route("/agreement", methods=["GET"])
@role_required("loan_officer")
def agreement():
    if getattr(current_user, "ica_accepted", False):
        if not getattr(current_user, "nda_accepted", False):
            return redirect(url_for("loan_officer.nda"))
        if getattr(current_user, "onboarding_complete", False):
            return redirect(url_for("loan_officer.dashboard"))
        return redirect(url_for("loan_officer.onboarding"))

    return render_template("loan_officer/agreement.html")

@loan_officer_bp.route("/agreement/accept", methods=["POST"])
@role_required("loan_officer")
def accept_ica():
    if not all([
        request.form.get("status_ack"),
        request.form.get("comp_ack"),
        request.form.get("no_guarantee"),
        request.form.get("agree_terms")
    ]):
        flash("You must accept all terms before continuing.", "danger")
        return redirect(url_for("loan_officer.agreement"))

    current_user.ica_accepted = True
    db.session.commit()

    flash("Agreement accepted successfully.", "success")
    return redirect(url_for("loan_officer.nda"))

# =============================================================
# AI Assistant — Loan Officer
# =============================================================

@loan_officer_bp.route("/ai/assistant", methods=["GET", "POST"])
@csrf.exempt
@role_required("loan_officer", "admin")
def ai_assistant():
    """
    Loan Officer AI endpoint
    GET  -> health check / usage instructions
    POST -> generate AI summary, next steps, or conditions
    """

    if request.method == "GET":
        return jsonify({
            "status": "ready",
            "endpoint": "loan_officer.ai_assistant",
            "message": "Send POST with JSON: { loan_id, prompt(optional), mode(optional) }"
        }), 200

    data = request.get_json(silent=True) or {}

    loan_id = data.get("loan_id")
    prompt = (data.get("prompt") or "").strip()
    mode = (data.get("mode") or "summary").strip().lower()

    if not loan_id:
        return jsonify({"success": False, "error": "loan_id is required"}), 400

    loan = LoanApplication.query.get(loan_id)
    if not loan:
        return jsonify({"success": False, "error": f"Loan {loan_id} not found"}), 404

    borrower = getattr(loan, "borrower_profile", None)
    if not borrower:
        return jsonify({"success": False, "error": "Borrower profile missing for this loan"}), 400

    officer = LoanOfficerProfile.query.filter_by(user_id=current_user.id).first()

    borrower_name = getattr(borrower, "full_name", None) or getattr(borrower, "name", None) or "Unknown Borrower"
    borrower_email = getattr(borrower, "email", None) or "N/A"
    loan_amount = getattr(loan, "amount", None) or 0
    loan_type = getattr(loan, "loan_type", None) or "Unknown"
    loan_status = getattr(loan, "status", None) or "Unknown"
    property_address = (
        getattr(loan, "property_address", None)
        or getattr(borrower, "property_address", None)
        or getattr(borrower, "address", None)
        or "No property address provided"
    )

    officer_name = officer.name if officer else f"{current_user.first_name or ''} {current_user.last_name or ''}".strip()

    context_packet = f"""
    Loan Officer: {officer_name}
    Borrower Name: {borrower_name}
    Borrower Email: {borrower_email}
    Loan ID: {loan.id}
    Loan Type: {loan_type}
    Loan Amount: {loan_amount}
    Loan Status: {loan_status}
    Property Address: {property_address}
    """

    if mode == "conditions":
        system_prompt = f"""
        You are an expert private lending loan officer assistant.

        Based on the following loan context, generate:
        1. A concise risk summary
        2. Recommended underwriting or processing conditions
        3. Clear next steps for the loan officer

        Keep the response practical, lender-focused, and easy to read.

        Context:
        {context_packet}
        """
    elif mode == "next_steps":
        system_prompt = f"""
        You are an expert loan officer assistant.

        Based on the loan context below, provide:
        1. Current file status assessment
        2. Recommended next actions
        3. Potential borrower outreach message points

        Keep it concise and actionable.

        Context:
        {context_packet}
        """
    else:
        system_prompt = f"""
        You are an expert loan officer AI assistant for Ravlo Lending OS.

        Review the loan file context below and provide:
        1. Executive summary
        2. Key risks or missing items
        3. Recommended next steps
        4. Borrower communication guidance

        Keep the answer polished, practical, and lender-friendly.

        Context:
        {context_packet}

        Additional user prompt:
        {prompt or "Provide a standard loan officer file summary."}
        """

    try:
        ai_response = assistant.generate_reply(system_prompt, "loan_officer_ai")
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"AI generation failed: {str(e)}"
        }), 500

    return jsonify({
        "success": True,
        "loan_id": loan.id,
        "mode": mode,
        "borrower": borrower_name,
        "loan_status": loan_status,
        "ai_response": ai_response
    }), 200


@loan_officer_bp.route("/messages", methods=["GET", "POST"])
@role_required("loan_officer")
@loan_officer_onboarding_required
def messages():
    if request.method == "POST":
        receiver_id = request.form.get("receiver_id", type=int)
        subject = (request.form.get("subject") or "").strip()
        content = (request.form.get("content") or "").strip()

        if not receiver_id or not content:
            flash("Receiver and message content are required.", "danger")
            return redirect(url_for("loan_officer.messages"))

        receiver = User.query.get(receiver_id)
        if not receiver:
            flash("Receiver not found.", "danger")
            return redirect(url_for("loan_officer.messages"))

        message = Message(
            sender_id=current_user.id,
            receiver_id=receiver.id,
            subject=subject,
            content=content,
        )

        db.session.add(message)
        db.session.commit()

        flash("Message sent successfully.", "success")
        return redirect(url_for("loan_officer.messages"))

    active_users = (
        User.query
        .filter(User.id != current_user.id)
        .filter_by(is_active=True)
        .order_by(User.first_name.asc(), User.last_name.asc())
        .all()
    )

    inbox = (
        Message.query
        .filter_by(receiver_id=current_user.id)
        .order_by(Message.created_at.desc())
        .all()
    )

    sent = (
        Message.query
        .filter_by(sender_id=current_user.id)
        .order_by(Message.created_at.desc())
        .all()
    )

    return render_template(
        "loan_officer/messages.html",
        active_users=active_users,
        inbox=inbox,
        sent=sent,
        active_tab="messages",
    )

@loan_officer_bp.route("/messages/send", methods=["POST"])
@csrf.exempt
@role_required("loan_officer")
def send_message():
    receiver_id = request.form.get("receiver_id", type=int)
    subject = (request.form.get("subject") or "internal").strip().lower()
    content = (request.form.get("content") or "").strip()

    

    if not receiver_id:
        flash("Please select a receiver.", "danger")
        return redirect(url_for("loan_officer.messages"))

    if not content:
        flash("Message content cannot be empty.", "danger")
        return redirect(url_for("loan_officer.messages"))

    msg = MessageThread(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content=content,
        sent_at=datetime.utcnow(),
        direction="outbound",
        status="sent",
    )
    db.session.add(msg)
    db.session.commit()

    flash("Message sent successfully.", "success")
    return redirect(
        url_for(
            "loan_officer.messages",
            receiver_id=receiver_id,
        )
    )
 
@loan_officer_bp.route("/loan/<int:loan_id>")
@role_required("loan_officer")
def loan_file(loan_id):
    officer = LoanOfficerProfile.query.filter_by(user_id=current_user.id).first()
    loan = LoanApplication.query.get_or_404(loan_id)

    # Optional ownership check
    if officer and loan.loan_officer_id and loan.loan_officer_id != officer.id:
        flash("You do not have access to that loan file.", "warning")
        return redirect(url_for("loan_officer.dashboard"))

    borrower = loan.borrower_profile

    credit = None
    if borrower and getattr(borrower, "credit_profiles", None):
        credit = borrower.credit_profiles[-1] if borrower.credit_profiles else None

    documents = loan.loan_documents or []

    tasks = Task.query.filter_by(loan_id=loan.id).order_by(Task.due_date.asc()).all()

    conditions = loan.underwriting_conditions or []

    dti_data = calculate_dti_ltv(borrower, loan, credit) if borrower else None

    engagement_score = None
    try:
        engine = EngagementEngine(borrower)
        engagement_score = engine.score()
    except Exception:
        engagement_score = None

    return render_template(
        "loan_officer/loan_file.html",
        loan=loan,
        borrower=borrower,
        credit=credit,
        documents=documents,
        tasks=tasks,
        conditions=conditions,
        engagement_score=engagement_score,
        ratios=dti_data,
        active_tab="pipeline",
        title=f"Loan #{loan.id}",
    )


# ============================================
# Loan Search • Loan Officer Module
# ============================================
@loan_officer_bp.route("/loan_search", methods=["GET"])
@role_required("loan_officer")
def loan_search():
    query = (request.args.get("q") or "").strip()
    loans = []

    if query:
        loans = (
            LoanApplication.query
            .join(BorrowerProfile)
            .filter(
                db.or_(
                    BorrowerProfile.full_name.ilike(f"%{query}%"),
                    LoanApplication.id.cast(db.String).ilike(f"%{query}%"),
                    LoanApplication.status.ilike(f"%{query}%")
                )
            )
            .order_by(LoanApplication.created_at.desc())
            .all()
        )

    stats = {
        "total_loans": LoanApplication.query.count(),
        "active_loans": LoanApplication.query.filter(
            LoanApplication.status.in_(["Active", "Submitted", "Pending", "Processing"])
        ).count(),
        "pending_loans": LoanApplication.query.filter_by(status="Pending").count(),
        "closed_loans": LoanApplication.query.filter_by(status="Closed").count(),
    }

    try:
        assistant = AIAssistant()
        ai_summary = assistant.generate_reply(
            f"Summarize search results for '{query}'. Found {len(loans)} loans.",
            "loan_search_summary"
        )
    except Exception:
        ai_summary = "AI summary unavailable."

    return render_template(
        "loan_officer/loan_search.html",
        loans=loans,
        query=query,
        stats=stats,
        ai_summary=ai_summary,
        active_tab="pipeline",
        title="Loan Search",
    )




# =========================================================
# AI Generator & Bulk Messaging
# =========================================================
@loan_officer_bp.route("/ai_generator", methods=["GET", "POST"])
@csrf.exempt
@role_required("loan_officer")
def ai_generator():
    ai_reply = None

    if request.method == "POST":
        prompt = (request.form.get("prompt") or "").strip()
        if not prompt:
            flash("Please enter a prompt.", "warning")
            return redirect(url_for("loan_officer.ai_generator"))

        try:
            assistant = AIAssistant()
            ai_reply = assistant.generate_reply(prompt, "loan_officer_generator")
        except Exception:
            ai_reply = "AI engine unavailable."

        flash("AI response generated.", "success")

    return render_template(
        "loan_officer/ai_generator.html",
        ai_reply=ai_reply,
        active_tab="tools",
        title="AI Generator"
    )




# =========================================================
# Loan Applications
# =========================================================
@loan_officer_bp.route("/new_application", methods=["GET", "POST"])
@csrf.exempt
@role_required("loan_officer")
def new_application():
    borrowers = BorrowerProfile.query.order_by(BorrowerProfile.full_name.asc()).all()
    officer = LoanOfficerProfile.query.filter_by(user_id=current_user.id).first()

    if request.method == "POST":
        borrower_id = request.form.get("borrower_profile_id")
        loan_type = request.form.get("loan_type")
        amount = request.form.get("amount")
        property_value = request.form.get("property_value")
        rate = request.form.get("rate")
        term_months = request.form.get("term_months")
        property_address = request.form.get("property_address")
        lender_name = request.form.get("lender_name")
        ai_summary = request.form.get("ai_summary")

        if not borrower_id or not amount or not property_value:
            flash("Please fill in all required fields.", "warning")
            return redirect(url_for("loan_officer.new_application"))

        new_loan = LoanApplication(
            borrower_profile_id=borrower_id,
            loan_type=loan_type,
            amount=float(amount),
            property_value=float(property_value),
            rate=float(rate or 0),
            term_months=int(term_months or 0),
            property_address=property_address,
            lender_name=lender_name,
            ai_summary=ai_summary,
            status="Pending",
            created_at=datetime.utcnow(),
            loan_officer_id=officer.id if officer else None
        )

        db.session.add(new_loan)
        db.session.commit()

        try:
            assistant = AIAssistant()
            ai_message = assistant.generate_reply(
                f"A new {loan_type} loan of ${amount} was created for borrower ID {borrower_id} "
                f"at {rate}% for {term_months} months, property value ${property_value}.",
                "loan_application_summary"
            )
            flash(f"Loan created successfully. AI Summary: {ai_message}", "success")
        except Exception:
            flash("Loan created successfully.", "success")

        return redirect(url_for("loan_officer.loan_file", loan_id=new_loan.id))

    return render_template(
        "loan_officer/new_application.html",
        borrowers=borrowers,
        active_tab="pipeline",
        title="New Loan Application"
    )


# ===============================================================
# CREATE NEW LOAN
# ===============================================================
@loan_officer_bp.route("/create-loan", methods=["GET", "POST"])
@csrf.exempt
@role_required("loan_officer")
def create_loan():
    borrowers = BorrowerProfile.query.order_by(BorrowerProfile.full_name.asc()).all()
    officer = LoanOfficerProfile.query.filter_by(user_id=current_user.id).first()

    if request.method == "POST":
        borrower_id = request.form.get("borrower_id")
        amount = request.form.get("amount")
        loan_type = request.form.get("loan_type")
        property_value = request.form.get("property_value")

        loan = LoanApplication(
            borrower_profile_id=borrower_id,
            loan_officer_id=officer.id if officer else None,
            amount=float(amount or 0),
            loan_type=loan_type,
            property_value=float(property_value or 0),
            status="Pending"
        )

        db.session.add(loan)
        db.session.commit()

        try:
            send_notification(loan.id, "processor", "New loan created by Loan Officer.")
        except Exception:
            pass

        return redirect(url_for("loan_officer.dashboard"))

    return render_template(
        "loan_officer/create_loan.html",
        borrowers=borrowers,
        active_tab="pipeline",
        title="Create Loan"
    )


@loan_officer_bp.route("/quick-1003", methods=["GET", "POST"])
@csrf.exempt
@role_required("loan_officer")
def quick_1003():
    officer = LoanOfficerProfile.query.filter_by(user_id=current_user.id).first()

    if request.method == "POST":
        borrower = BorrowerProfile(
            full_name=request.form.get("full_name"),
            email=request.form.get("email"),
            phone=request.form.get("phone"),
            income=request.form.get("income") or 0,
            address=request.form.get("address"),
            city=request.form.get("city"),
            state=request.form.get("state"),
            zip=request.form.get("zip"),
            assigned_officer_id=officer.id if officer else None,
        )
        db.session.add(borrower)
        db.session.commit()

        loan = LoanApplication(
            borrower_profile_id=borrower.id,
            amount=float(request.form.get("loan_amount") or 0),
            loan_type=request.form.get("loan_type"),
            property_value=float(request.form.get("property_value") or 0),
            property_address=request.form.get("property_address"),
            status="Application Submitted",
            loan_officer_id=officer.id if officer else None,
            created_at=datetime.utcnow(),
        )
        db.session.add(loan)
        db.session.commit()

        default_fees = [
            ("Credit Pull Fee", 40),
            ("Application Fee", 95),
        ]

        for name, amount in default_fees:
            db.session.add(PaymentRecord(
                borrower_profile_id=borrower.id,
                loan_id=loan.id,
                payment_type=name,
                amount=amount
            ))

        db.session.commit()

        default_events = [
            ("Application Submitted", "Loan Officer submitted the application."),
            ("Processor Review", "Processor will begin reviewing the file."),
            ("Document Review", "Borrower documents pending review."),
        ]

        for name, desc in default_events:
            db.session.add(LoanStatusEvent(
                loan_id=loan.id,
                event_name=name,
                description=desc
            ))

        db.session.commit()

        return redirect(url_for("loan_officer.loan_file", loan_id=loan.id))

    return render_template(
        "loan_officer/quick_1003.html",
        active_tab="pipeline",
        title="Quick 1003"
    )

# =========================================================
# Quote Engine
# =========================================================
@loan_officer_bp.route("/quote_engine", methods=["GET", "POST"])
@csrf.exempt
@role_required("loan_officer")
def quote_engine():
    officer = LoanOfficerProfile.query.filter_by(user_id=current_user.id).first()

    selected_loan = None
    quotes = []
    borrower_name = None
    loan_type = None
    amount = 0

    # Load all loans assigned to this loan officer
    loans = []
    if officer:
        loans = (
            LoanApplication.query
            .filter_by(loan_officer_id=officer.id)
            .order_by(LoanApplication.created_at.desc())
            .all()
        )

    # Support both POST form submit and GET query param
    loan_id = None
    if request.method == "POST":
        loan_id = request.form.get("loan_id")
    else:
        loan_id = request.args.get("loan_id")

    if loan_id:
        selected_loan = LoanApplication.query.get(loan_id)

        if not selected_loan:
            flash("Loan not found.", "danger")
            return redirect(url_for("loan_officer.quote_engine"))

        amount = float(selected_loan.amount or 0)
        loan_type = getattr(selected_loan, "loan_type", None) or "Unknown"

        borrower = None
        if getattr(selected_loan, "borrower_profile_id", None):
            borrower = BorrowerProfile.query.get(selected_loan.borrower_profile_id)

        borrower_name = (
            getattr(borrower, "full_name", None)
            if borrower else None
        ) or "N/A"

        # Basic sample quote engine
        quotes = [
            {
                "lender": "Lima One",
                "rate": "7.25%",
                "ltv": "80%",
                "term": "30 years",
                "monthly_payment": f"{round((amount * 0.0725) / 12, 2):,.2f}",
            },
            {
                "lender": "ROC Capital",
                "rate": "7.50%",
                "ltv": "78%",
                "term": "30 years",
                "monthly_payment": f"{round((amount * 0.0750) / 12, 2):,.2f}",
            },
            {
                "lender": "Lev Capital",
                "rate": "7.10%",
                "ltv": "82%",
                "term": "30 years",
                "monthly_payment": f"{round((amount * 0.0710) / 12, 2):,.2f}",
            },
        ]

        # Sort by lowest rate so best option appears first
        def parse_rate(q):
            try:
                return float(str(q.get("rate", "0")).replace("%", "").strip())
            except Exception:
                return 999.0

        quotes = sorted(quotes, key=parse_rate)

    return render_template(
        "loan_officer/quote_engine.html",
        loans=loans,
        selected_loan=selected_loan,
        borrower_name=borrower_name,
        loan_type=loan_type,
        amount=amount,
        quotes=quotes,
        active_tab="tools",
        title="Quote Engine"
    )

@loan_officer_bp.route("/quotes/new", methods=["GET", "POST"])
@csrf.exempt
@role_required("loan_officer")
def new_quote():
    borrowers = BorrowerProfile.query.order_by(BorrowerProfile.full_name.asc()).all()
    loans = LoanApplication.query.order_by(LoanApplication.created_at.desc()).all()

    if request.method == "POST":
        borrower_id = request.form.get("borrower_id")
        loan_id = request.form.get("loan_id")
        rate = request.form.get("rate")
        program = request.form.get("program")
        notes = request.form.get("notes")

        # IMPORTANT: build only with fields that exist on your LoanQuote model
        quote = LoanQuote(
            borrower_profile_id=borrower_id,
            loan_application_id=loan_id,
            rate=float(rate or 0),
            loan_type=program,
            requested_terms=notes,
            status="pending",
            created_at=datetime.utcnow(),
        )

        db.session.add(quote)
        db.session.commit()

        flash("Quote created successfully.", "success")
        return redirect(url_for("loan_officer.quote_engine"))

    return render_template(
        "loan_officer/new_quote.html",
        borrowers=borrowers,
        loans=loans,
        active_tab="tools",
        title="New Quote"
    )


# =========================================================
# Pipeline & Reports
# =========================================================

# ------------------------------------------------------------
# Helper: Derive logical loan stage from loan status
# ------------------------------------------------------------
def derive_stage_from_status(status):
    status = (status or "").lower()

    if "pending" in status:
        return "Pre-Approval"
    if "submitted" in status:
        return "Processing"
    if "review" in status:
        return "UW Review"
    if "condition" in status:
        return "Clearing Conditions"
    if "docs" in status:
        return "Docs Out"
    if "approved" in status:
        return "Approved"

    return "Pipeline"


# ===============================================================
# PIPELINE VIEW
# ===============================================================
@loan_officer_bp.route("/pipeline")
@role_required("loan_officer")
def pipeline():
    officer = LoanOfficerProfile.query.filter_by(user_id=current_user.id).first()

    status_filter = (request.args.get("status") or "").strip()
    stage_filter = (request.args.get("stage") or "").strip()
    name_filter = (request.args.get("name") or "").strip()

    q = LoanApplication.query

    # LoanApplication.loan_officer_id points to LoanOfficerProfile.id
    if officer:
        q = q.filter(LoanApplication.loan_officer_id == officer.id)

    if status_filter:
        q = q.filter(LoanApplication.status == status_filter)

    # Your model uses milestone_stage, not stage
    if stage_filter:
        q = q.filter(LoanApplication.milestone_stage == stage_filter)

    if name_filter:
        q = q.join(LoanApplication.borrower_profile).filter(
            BorrowerProfile.full_name.ilike(f"%{name_filter}%")
        )

    pipeline = q.order_by(LoanApplication.created_at.desc()).limit(50).all()

    for loan in pipeline:
        verified_statuses = ["verified", "reviewed", "cleared"]
        loan.missing_docs = len([
            d for d in (loan.loan_documents or [])
            if (d.status or "").lower() not in verified_statuses
        ])

        if not loan.milestone_stage:
            loan.milestone_stage = derive_stage_from_status(loan.status)

        loan.updated_at = loan.updated_at or loan.created_at

    return render_template(
        "loan_officer/pipeline.html",
        pipeline=pipeline,
        selected_status=status_filter,
        selected_stage=stage_filter,
        name_filter=name_filter,
        active_tab="pipeline",
        title="Pipeline"
    )


@loan_officer_bp.route("/reports")
@role_required("loan_officer")
def reports():
    officer = LoanOfficerProfile.query.filter_by(user_id=current_user.id).first()

    loans = []
    if officer:
        loans = LoanApplication.query.filter_by(loan_officer_id=officer.id).all()

    total = len(loans)
    approved = sum((l.status or "").lower() == "approved" for l in loans)
    declined = sum((l.status or "").lower() == "declined" for l in loans)

    return render_template(
        "loan_officer/reports.html",
        total=total,
        approved=approved,
        declined=declined,
        active_tab="reports",
        title="Reports"
    )


# =========================================================
# AI Summary (Quick API)
# =========================================================
@loan_officer_bp.route("/ai_summary")
@role_required("loan_officer")
def ai_summary():
    try:
        total_loans = LoanApplication.query.count()
        approved = LoanApplication.query.filter_by(status="approved").count()
        pending = LoanApplication.query.filter_by(status="pending").count()
        total_leads = Lead.query.count()

        prompt = (
            f"As a loan officer AI, summarize: "
            f"Total loans: {total_loans}, Approved: {approved}, Pending: {pending}, Leads: {total_leads}."
        )

        assistant = AIAssistant()
        message = assistant.generate_reply(prompt, "loan_officer")
    except Exception:
        message = "AI Summary currently unavailable."

    return jsonify({
        "message": message,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })


# =========================================================
# Task Manager
# =========================================================
@loan_officer_bp.route("/tasks", methods=["GET", "POST"])
@role_required("loan_officer")
def task():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        if not title:
            flash("Task title required.", "warning")
            return redirect(url_for("loan_officer.task"))

        due_date_raw = request.form.get("due_date")
        due_date = datetime.strptime(due_date_raw, "%Y-%m-%d") if due_date_raw else None

        new_task = Task(
            title=title,
            description=request.form.get("description"),
            due_date=due_date,
            priority=request.form.get("priority", "Normal"),
            assigned_to=current_user.id,
        )
        db.session.add(new_task)
        db.session.commit()

        flash("Task added successfully.", "success")
        return redirect(url_for("loan_officer.task"))

    tasks = Task.query.filter_by(assigned_to=current_user.id).order_by(Task.due_date.asc()).all()

    return render_template(
        "loan_officer/task.html",
        tasks=tasks,
        role="loan_officer",
        active_tab="tasks",
        title="Tasks"
    )


@loan_officer_bp.route("/tasks/<int:task_id>/toggle", methods=["POST"])
@role_required("loan_officer")
def toggle_task(task_id):
    task = Task.query.get_or_404(task_id)
    task.status = "Completed" if task.status != "Completed" else "Pending"
    db.session.commit()
    return jsonify({"status": task.status})


@loan_officer_bp.route("/tasks/<int:task_id>/delete", methods=["POST"])
@role_required("loan_officer")
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()

    flash("Task deleted.", "info")
    return redirect(url_for("loan_officer.task"))


@loan_officer_bp.route("/tasks/complete/<int:task_id>", methods=["POST"])
@role_required("loan_officer")
def task_complete(task_id):
    task = Task.query.get_or_404(task_id)
    task.status = "Completed"
    task.completed = True
    db.session.commit()
    return redirect(url_for("loan_officer.task"))


@loan_officer_bp.route("/tasks/new", methods=["GET", "POST"])
@role_required("loan_officer")
def new_task():
    borrowers = BorrowerProfile.query.order_by(BorrowerProfile.full_name.asc()).all()
    loans = LoanApplication.query.order_by(LoanApplication.created_at.desc()).all()
    selected_borrower_id = request.args.get("borrower_id", type=int)

    if request.method == "POST":
        due_date_raw = request.form.get("due_date")
        due_date = datetime.strptime(due_date_raw, "%Y-%m-%d") if due_date_raw else None

        task = Task(
            title=request.form.get("title"),
            description=request.form.get("description"),
            assigned_to=current_user.id,
            borrower_id=request.form.get("borrower_id"),
            loan_id=request.form.get("loan_id"),
            due_date=due_date
        )
        db.session.add(task)
        db.session.commit()

        flash("Task created successfully.", "success")
        return redirect(url_for("loan_officer.task"))

    return render_template(
        "loan_officer/new_task.html",
        borrowers=borrowers,
        loans=loans,
        selected_borrower_id=selected_borrower_id,
        active_tab="tasks",
        title="New Task"
    )


@loan_officer_bp.route("/borrower-ai/<int:borrower_id>")
@role_required("loan_officer")
def borrower_ai_log(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)

    chats = (
        BorrowerInteraction.query.filter_by(
            borrower_id=borrower.id,
            interaction_type="AI Chat"
        )
        .order_by(BorrowerInteraction.timestamp.desc())
        .all()
    )

    return render_template(
        "loan_officer/borrower_ai_log.html",
        borrower=borrower,
        chats=chats,
        active_tab="tools",
        title="Borrower AI Log"
    )



@loan_officer_bp.route("/credit-check", methods=["GET", "POST"])
@csrf.exempt
@role_required("loan_officer")
def credit_check():
    borrowers = BorrowerProfile.query.all()
    borrower_id = request.args.get("borrower_id")

    credit_data = None
    credit_history = None

    # POST → Run real Equifax pull
    if request.method == "POST":
        borrower_profile_id = request.form.get("borrower_profile_id")
        borrower = BorrowerProfile.query.get(borrower_profile_id)

        if not borrower:
            flash("Borrower not found.", "danger")
            return redirect(url_for("loan_officer.credit_check"))

        # 1. Check consent
        consent = BorrowerConsent.query.filter_by(
            borrower_id=borrower.id,
            consent_type="credit_pull"
        ).first()

        if not consent:
            flash("Borrower has not provided credit pull consent.", "danger")
            return redirect(url_for("loan_officer.credit_check"))

        # 2. Call Equifax
        result = equifax.pull_credit(borrower)

        # 3. Log audit
        audit = CreditPullAudit(
            borrower_id=borrower.id,
            loan_officer_id=current_user.id,
            permissible_purpose="loan_underwriting",
            result_status="success" if "error" not in result else "error",
            raw_response=result
        )
        db.session.add(audit)

        # 4. Handle error
        if "error" in result:
            db.session.commit()
            flash("Equifax Error: " + result["error"], "danger")
            return redirect(url_for("loan_officer.credit_check"))

        # 5. Map Equifax → DB
        report = result.get("creditReport", {})
        score = report.get("score", {}).get("ficoScore", 0)
        summary = report.get("summary", {})

        new_report = CreditReport(
            borrower_id=borrower.id,
            credit_score=score,
            delinquencies=summary.get("delinquencies", 0),
            public_records=summary.get("publicRecords", 0),
            total_debt=summary.get("totalDebt", 0),
            report_date=datetime.utcnow()
        )

        db.session.add(new_report)
        db.session.commit()

        return redirect(url_for("loan_officer.credit_check", borrower_id=borrower.id))

    # GET → Show latest + history
    if borrower_id:
        credit_data = CreditReport.query.filter_by(borrower_id=borrower_id)\
                                        .order_by(CreditReport.report_date.desc())\
                                        .first()

        credit_history = CreditReport.query.filter_by(borrower_id=borrower_id)\
                                           .order_by(CreditReport.report_date.desc())\
                                           .all()

    return render_template(
        "loan_officer/credit_check.html",
        borrowers=borrowers,
        credit_data=credit_data,
        credit_history=credit_history
    )


# ---------------------------------------------------------
# Loan Queue – View All Assigned Loans
# ---------------------------------------------------------
@loan_officer_bp.route("/loan_queue")
@role_required("loan_officer")
def loan_queue():
    officer = LoanOfficerProfile.query.filter_by(user_id=current_user.id).first()

    loans = []
    if officer:
        loans = (
            LoanApplication.query
            .filter_by(loan_officer_id=officer.id)
            .order_by(LoanApplication.created_at.desc())
            .all()
        )

    total_loans = len(loans)
    active_loans = len([
        l for l in loans
        if (l.status or "").lower() in ["in_review", "submitted", "pending", "processing"]
    ])
    approved_loans = len([
        l for l in loans
        if (l.status or "").lower() in ["approved", "cleared"]
    ])
    declined_loans = len([
        l for l in loans
        if (l.status or "").lower() in ["declined", "denied"]
    ])

    try:
        summary_prompt = (
            f"Summarize the current loan officer's queue activity: "
            f"Total loans: {total_loans}, Active: {active_loans}, "
            f"Approved: {approved_loans}, Declined: {declined_loans}. "
            f"Provide one prioritization suggestion."
        )
        assistant = AIAssistant()
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
        active_tab="pipeline",
        title="Loan Queue"
    )



# ===============================================================
# AI PRICING
# ===============================================================
@loan_officer_bp.route("/ai/pricing", methods=["GET", "POST"])
@csrf.exempt
@role_required("loan_officer")
def ai_pricing():
    if request.method == "GET":
        return "AI Pricing endpoint is POST-only. Use the UI button that sends JSON.", 200

    data = request.get_json() or {}
    loan_id = data.get("loan_id")
    borrower_id = data.get("borrower_id")

    loan = LoanApplication.query.get(loan_id)
    borrower = BorrowerProfile.query.get(borrower_id)

    if not loan or not borrower:
        return jsonify({"reply": "Loan or borrower not found."}), 404

    credit = borrower.credit_profiles[-1] if borrower.credit_profiles else None
    score = credit.credit_score if credit else None

    ratios = calculate_dti_ltv(borrower, loan, credit)

    pricing_packet = f"""
    Loan Amount: {loan.amount}
    Property Value: {loan.property_value}
    Loan Type: {loan.loan_type}
    Credit Score: {score}
    Income: {borrower.income}
    Secondary Income: {getattr(borrower, "monthly_income_secondary", 0)}
    Total Monthly Income: {ratios.get('income_total')}
    Monthly Debts: {ratios.get('monthly_debts')}
    Front-End DTI: {ratios.get('front_end_dti')}
    Back-End DTI: {ratios.get('back_end_dti')}
    LTV: {ratios.get('ltv')}
    """

    reply = master_ai.generate(
        f"""
        Provide a pricing recommendation for this borrower.

        Include:
        - Best program fit
        - Estimated interest rate range
        - Max allowed LTV
        - Payment estimate
        - DTI + Risk flags
        - UW-level notes
        - Required conditions
        - Recommended next steps

        Data:
        {pricing_packet}
        """,
        role="loan_officer"
    )

    return jsonify({"reply": reply})


@loan_officer_bp.route("/ai/risk", methods=["GET", "POST"])
@csrf.exempt
@role_required("loan_officer")
def ai_risk():
    if request.method == "GET":
        return jsonify({
            "status": "ready",
            "endpoint": "ai_risk",
            "message": "Send POST with JSON { loan_id } to evaluate loan risk."
        }), 200

    data = request.get_json() or {}
    loan_id = data.get("loan_id")

    if not loan_id:
        return jsonify({"error": "loan_id is required"}), 400

    loan = LoanApplication.query.get(loan_id)
    if not loan:
        return jsonify({"error": f"Loan {loan_id} not found"}), 404

    borrower = loan.borrower_profile
    if not borrower:
        return jsonify({"error": "Borrower profile missing for this loan"}), 400

    credit = borrower.credit_profiles[-1] if borrower.credit_profiles else None
    ratios = calculate_dti_ltv(borrower, loan, credit)

    packet = f"""
    Loan Amount: {loan.amount}
    Loan Type: {loan.loan_type}
    Property Value: {loan.property_value}
    LTV: {ratios.get('ltv')}

    DTI:
    Front-End: {ratios.get('front_end_dti')}
    Back-End: {ratios.get('back_end_dti')}

    Income: {borrower.income}
    Secondary Income: {getattr(borrower, "monthly_income_secondary", 0)}

    Credit Score: {credit.credit_score if credit else 'N/A'}
    Monthly Debts: {ratios.get('monthly_debts')}
    """

    reply = master_ai.generate(
        f"""
        Evaluate this loan's risk.

        Provide:
        - Risk Category
        - Key Strengths
        - Key Weaknesses
        - DTI analysis
        - LTV analysis
        - Credit analysis
        - Funding likelihood
        - Recommended program type
        - Required conditions
        - UW difficulty level

        Data:
        {packet}
        """,
        role="underwriter"
    )

    return jsonify({"reply": reply})

@loan_officer_bp.route("/ai/conditions", methods=["GET", "POST"])
@csrf.exempt
@role_required("loan_officer")
def ai_conditions():
    if request.method == "GET":
        return jsonify({
            "status": "ready",
            "endpoint": "ai_conditions",
            "message": "Send POST with JSON { loan_id } to generate underwriting conditions."
        }), 200

    data = request.get_json() or {}
    loan_id = data.get("loan_id")

    if not loan_id:
        return jsonify({"error": "loan_id is required"}), 400

    loan = LoanApplication.query.get(loan_id)
    if not loan:
        return jsonify({"error": f"Loan {loan_id} not found"}), 404

    borrower = loan.borrower_profile
    if not borrower:
        return jsonify({"error": "Borrower profile missing for this loan"}), 400

    credit = borrower.credit_profiles[-1] if borrower.credit_profiles else None
    ratios = calculate_dti_ltv(borrower, loan, credit)

    packet = f"""
    Loan Amount: {loan.amount}
    Loan Type: {loan.loan_type}
    Income: {borrower.income}
    Secondary Income: {getattr(borrower, "monthly_income_secondary", 0)}
    Credit Score: {credit.credit_score if credit else 'N/A'}
    LTV: {ratios.get('ltv')}
    DTI:
      FE: {ratios.get('front_end_dti')}
      BE: {ratios.get('back_end_dti')}
    """

    reply = master_ai.generate(
        f"""
        Produce underwriting conditions for this loan.

        Include grouped sections:
        - Identity & Compliance
        - Income
        - Employment
        - Assets
        - Credit
        - Liabilities
        - Property
        - Program-Specific
        - Final Approval Conditions

        Data:
        {packet}
        """,
        role="underwriter"
    )

    return jsonify({"reply": reply})


@loan_officer_bp.route("/intake-ai/<int:borrower_id>", methods=["GET", "POST"])
@csrf.exempt
@role_required("loan_officer")
def intake_ai(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)

    loan = (
        LoanApplication.query.filter_by(borrower_profile_id=borrower.id)
        .order_by(LoanApplication.created_at.desc())
        .first()
    )

    credit = borrower.credit_profiles[-1] if borrower.credit_profiles else None
    credit_score = credit.credit_score if credit else None
    credit_json = getattr(credit, "report_json", {}) if credit else {}

    ratios = calculate_dti_ltv(borrower, loan, credit) if loan else {
        "front_end_dti": None,
        "back_end_dti": None,
        "ltv": None,
        "income_total": None,
        "monthly_debts": None,
    }

    front = ratios.get("front_end_dti")
    back = ratios.get("back_end_dti")
    ltv = ratios.get("ltv")

    missing_docs = [
        d.document_name for d in getattr(borrower, "document_requests", [])
        if (d.status or "").lower() == "requested"
    ]

    if request.method == "GET":
        return render_template(
            "loan_officer/intake_ai.html",
            borrower=borrower,
            loan=loan,
            credit=credit,
            front_dti=front,
            back_dti=back,
            ltv=ltv,
            missing_docs=missing_docs,
            active_tab="tools",
            title="AI Intake",
        )

    data = request.get_json() or {}
    user_message = data.get("message", "")

    underwriting_packet = f"""
Borrower: {borrower.full_name}
Email: {borrower.email}
Phone: {borrower.phone}

Income:
- Primary: {borrower.income}
- Secondary: {getattr(borrower, 'monthly_income_secondary', None)}
- Total Monthly Income: {ratios.get('income_total')}

Employment:
- Employer: {borrower.employer_name}
- Job Title: {getattr(borrower, 'job_title', None)}
- Years on Job: {getattr(borrower, 'years_at_job', None)}

Credit:
- Soft Credit Score: {credit_score}
- Monthly Debt Total: {ratios.get('monthly_debts')}
- Full Credit JSON: {credit_json}

Loan:
- Loan Amount: {loan.amount if loan else 'N/A'}
- Property Value: {loan.property_value if loan else 'N/A'}
- Property Address: {loan.property_address if loan else 'N/A'}
- Loan Type: {loan.loan_type if loan else borrower.loan_type}
- LTV: {ltv}

Debt-to-Income:
- Front-End DTI: {front}
- Back-End DTI: {back}

Missing Documents:
{missing_docs}
"""

    ai_reply = master_ai.generate(
        f"""
Perform AI Smart Intake Analysis.

Here is the complete data:

{underwriting_packet}

User Question:
{user_message}

Provide:
- Missing Info We Still Need
- Program Fit
- Risk Flags
- Income Guidance
- Required Underwriting Documents
- Recommended Next Steps
- If the borrower is pre-approvable
""",
        role="loan_officer"
    )

    return jsonify({"reply": ai_reply})


# === Queue View ===
@loan_officer_bp.route("/ai-intake-queue")
@role_required("loan_officer")
def ai_intake_queue():
    queue = (
        AIIntakeSummary.query
        .order_by(AIIntakeSummary.created_at.desc())
        .limit(50)
        .all()
    )
    return render_template(
        "loan_officer/ai_intake_queue.html",
        queue=queue,
        active_tab="tools",
        title="AI Intake Queue"
    )


# === Review View ===
@loan_officer_bp.route("/ai-intake-review/<int:intake_id>", methods=["GET", "POST"])
@csrf.exempt
@role_required("loan_officer")
def ai_intake_review(intake_id):
    intake = AIIntakeSummary.query.get_or_404(intake_id)
    form = AIIntakeReviewForm(obj=intake)

    if form.validate_on_submit():
        intake.reviewer_notes = form.reviewer_notes.data
        intake.status = form.status.data
        intake.reviewer_id = current_user.id
        intake.reviewed_at = datetime.utcnow()
        db.session.commit()

        flash("Review saved successfully.", "success")
        return redirect(url_for("loan_officer.ai_intake_queue"))

    return render_template(
        "loan_officer/ai_intake_review.html",
        intake=intake,
        form=form,
        active_tab="tools",
        title="AI Intake Review"
    )


@loan_officer_bp.route("/auto-create-loan/<int:borrower_id>", methods=["POST"])
@csrf.exempt
@role_required("loan_officer")
def auto_create_loan(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)
    officer = LoanOfficerProfile.query.filter_by(user_id=current_user.id).first()

    data = request.get_json() or {}

    loan_amount = data.get("loan_amount", 0)
    loan_type = data.get("loan_type", borrower.loan_type)
    property_value = data.get("property_value", 0)
    property_address = data.get("property_address")

    loan = LoanApplication(
        borrower_profile_id=borrower.id,
        loan_type=loan_type,
        amount=float(loan_amount or 0),
        property_value=float(property_value or 0),
        property_address=property_address,
        status="Application Submitted",
        loan_officer_id=officer.id if officer else None,
        created_at=datetime.utcnow(),
    )

    db.session.add(loan)
    db.session.commit()

    fees = [
        ("Credit Pull Fee", 40),
        ("Application Fee", 95),
    ]
    for name, amount in fees:
        db.session.add(
            PaymentRecord(
                borrower_profile_id=borrower.id,
                loan_id=loan.id,
                payment_type=name,
                amount=amount
            )
        )

    db.session.commit()

    events = [
        ("File Created", "Loan file created automatically after AI intake review."),
        ("Processing Queue", "Waiting for processor assignment."),
        ("Document Review", "Pending borrower documents."),
    ]
    for name, desc in events:
        db.session.add(LoanStatusEvent(loan_id=loan.id, event_name=name, description=desc))

    db.session.commit()

    return jsonify({
        "status": "success",
        "loan_id": loan.id,
        "redirect_url": url_for("loan_officer.loan_file", loan_id=loan.id)
    })


@loan_officer_bp.route("/followup-ai/<int:borrower_id>", methods=["GET", "POST"])
@csrf.exempt
@role_required("loan_officer")
def followup_ai(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)

    credit = borrower.credit_profiles[-1] if borrower.credit_profiles else None

    loan = (
        LoanApplication.query.filter_by(borrower_profile_id=borrower.id)
        .order_by(LoanApplication.created_at.desc())
        .first()
    )

    missing_docs = [
        d.document_name for d in getattr(borrower, "document_requests", [])
        if (d.status or "").lower() == "requested"
    ]

    tasks = FollowUpTask.query.filter_by(borrower_id=borrower.id).all()

    last_contact = (
        borrower.last_contact_record[0].last_contact_at
        if getattr(borrower, "last_contact_record", None)
        else None
    )

    ratios = calculate_dti_ltv(borrower, loan, credit) if loan else {
        "front_end_dti": None,
        "back_end_dti": None,
        "ltv": None,
    }

    if request.method == "GET":
        return jsonify({
            "status": "ready",
            "endpoint": "followup-ai",
            "message": "Send POST with JSON { message: '...' } to generate follow-up plan."
        }), 200

    data = request.get_json() or {}
    user_message = data.get("message", "")

    ai_reply = master_ai.generate(
        f"""
You are CM Follow-Up Intelligence.

Generate a follow-up plan for the Loan Officer.

Borrower:
{borrower.full_name}
Phone: {borrower.phone}
Email: {borrower.email}

Loan:
Type: {loan.loan_type if loan else 'N/A'}
Amount: {loan.amount if loan else 'N/A'}
Property Value: {loan.property_value if loan else 'N/A'}

Credit Score: {credit.credit_score if credit else 'N/A'}
Front DTI: {ratios.get('front_end_dti')}
Back DTI: {ratios.get('back_end_dti')}
LTV: {ratios.get('ltv')}

Missing Documents:
{missing_docs}

Open Tasks:
{[t.title for t in tasks]}

Last Contact:
{last_contact}

User question:
{user_message}

Provide:
1. Urgency Level
2. Risk Flags
3. Document follow-up items beginning with "TASK:"
4. Phone call reminders beginning with "TASK:"
5. Action items for the loan officer beginning with "TASK:"
6. Short call script
7. Short text message
8. Short email message
""",
        role="loan_officer"
    )

    created_tasks = extract_and_create_tasks(ai_reply, borrower, loan)

    return jsonify({
        "reply": ai_reply,
        "auto_tasks": created_tasks
    })


@loan_officer_bp.route("/communication-ai/<int:borrower_id>", methods=["GET", "POST"])
@csrf.exempt
@role_required("loan_officer")
def communication_ai(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)

    loan = (
        LoanApplication.query.filter_by(borrower_profile_id=borrower.id)
        .order_by(LoanApplication.created_at.desc())
        .first()
    )

    credit = borrower.credit_profiles[-1] if borrower.credit_profiles else None
    ratios = calculate_dti_ltv(borrower, loan, credit) if loan else {
        "front_end_dti": None,
        "back_end_dti": None,
        "ltv": None,
    }

    if request.method == "GET":
        return jsonify({
            "status": "ready",
            "endpoint": "communication-ai",
            "message": "Send POST with JSON { message: '...' } to generate communication scripts."
        }), 200

    data = request.get_json() or {}
    user_message = data.get("message", "")

    ai_reply = master_ai.generate(
        f"""
Generate communication scripts for borrower follow-up.

Borrower:
{borrower.full_name}
Phone: {borrower.phone}
Email: {borrower.email}

Loan:
Type: {loan.loan_type if loan else 'N/A'}
Amount: {loan.amount if loan else 'N/A'}
Property Value: {loan.property_value if loan else 'N/A'}

Credit Score: {credit.credit_score if credit else 'N/A'}
Front DTI: {ratios.get('front_end_dti')}
Back DTI: {ratios.get('back_end_dti')}
LTV: {ratios.get('ltv')}

User question:
{user_message}

Your response MUST include:

CALL SCRIPT:
(Phone script)

SMS:
(Text message)

EMAIL SUBJECT:
(Email subject)

EMAIL BODY:
(Email message)

TASK:
(Any action item the LO must follow up on)
""",
        role="loan_officer"
    )

    created_tasks = extract_and_create_tasks(ai_reply, borrower, loan)

    return jsonify({
        "reply": ai_reply,
        "auto_tasks": created_tasks
    })


@loan_officer_bp.route("/campaigns")
@role_required("loan_officer")
def campaigns():
    active = (
        Campaign.query
        .filter(Campaign.status == "active")
        .order_by(Campaign.created_at.desc())
        .all()
    )

    archived = (
        Campaign.query
        .filter(Campaign.status.in_(["completed", "paused", "draft"]))
        .order_by(Campaign.created_at.desc())
        .all()
    )

    return render_template(
        "loan_officer/campaign.html",
        active=active,
        archived=archived,
        active_tab="campaigns",
        title="Campaigns"
    )


@loan_officer_bp.route("/call-center/<int:borrower_id>")
@role_required("loan_officer")
def call_center(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)

    credit = borrower.credit_profiles[-1] if borrower.credit_profiles else None

    loan = LoanApplication.query.filter_by(borrower_profile_id=borrower.id).first()

    return render_template(
        "loan_officer/call_center.html",
        borrower=borrower,
        loan=loan,
        credit=credit,
        active_tab="tools",
        title="Call Center"
    )


@loan_officer_bp.route("/save_call_notes", methods=["POST"])
@csrf.exempt
@role_required("loan_officer")
def save_call_notes():
    data = request.get_json() or {}

    borrower_id = data.get("borrower_id")
    transcript = data.get("transcript", "")
    summary = data.get("summary", "")
    tasks = data.get("tasks", [])
    missing_docs = data.get("missing_docs", [])

    borrower = BorrowerProfile.query.get_or_404(borrower_id)
    loan = LoanApplication.query.filter_by(borrower_profile_id=borrower_id).first()

    note = BorrowerInteraction(
        borrower_id=borrower_id,
        interaction_type="Call Note",
        notes=summary or transcript
    )
    db.session.add(note)

    for t in tasks:
        task = Task(
            borrower_id=borrower_id,
            assigned_to=current_user.id,
            title=t,
            status="open"
        )
        db.session.add(task)

    for doc in missing_docs:
        dr = DocumentRequest(
            borrower_id=borrower_id,
            loan_id=loan.id if loan else None,
            document_name=doc,
            status="requested"
        )
        db.session.add(dr)

    if loan:
        event = LoanStatusEvent(
            loan_id=loan.id,
            event_name="Call Completed",
            description=f"AI auto-summarized call: {(summary or transcript)[:120]}..."
        )
        db.session.add(event)

    db.session.commit()

    return jsonify({"status": "success"})


@loan_officer_bp.route("/edit-loan/<int:loan_id>", methods=["GET", "POST"])
@csrf.exempt
@role_required("loan_officer")
def edit_loan(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    form = LoanEditForm(obj=loan)

    if form.validate_on_submit():
        form.populate_obj(loan)
        db.session.commit()
        flash("Loan updated successfully.", "success")
        return redirect(url_for("loan_officer.loan_file", loan_id=loan.id))

    return render_template(
        "loan_officer/edit_loan.html",
        form=form,
        loan=loan,
        active_tab="pipeline",
        title="Edit Loan"
    )


@loan_officer_bp.route("/generate-quote/<int:loan_id>", methods=["GET", "POST"])
@csrf.exempt
@role_required("loan_officer")
def generate_quote(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    form = GenerateQuoteForm()
    quote = None

    if form.validate_on_submit():
        principal = float(loan.amount or 0)
        monthly_rate = float(form.rate.data) / 100 / 12
        months = form.term_months.data

        if monthly_rate > 0 and months > 0:
            payment = principal * (monthly_rate * (1 + monthly_rate) ** months) / ((1 + monthly_rate) ** months - 1)
        else:
            payment = 0

        # Keep this aligned to your actual LoanQuote model
        quote = LoanQuote(
            loan_application_id=loan.id,
            borrower_profile_id=loan.borrower_profile_id,
            rate=float(form.rate.data or 0),
            term_months=months,
            loan_amount=principal,
            loan_type=loan.loan_type,
            property_address=loan.property_address,
            purchase_price=loan.property_value,
            status="pending",
            ai_suggestion=f"Estimated monthly payment: {round(payment, 2)}"
        )
        db.session.add(quote)
        db.session.commit()

        flash("Quote generated and saved.", "success")
        return redirect(url_for("loan_officer.quote_engine"))

    return render_template(
        "loan_officer/generate_quote.html",
        form=form,
        loan=loan,
        quote=quote,
        active_tab="tools",
        title="Generate Quote"
    )

@loan_officer_bp.route("/intake-review/<int:borrower_id>")
@role_required("loan_officer")
def intake_review(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)
    credit = borrower.credit_profiles[-1] if borrower.credit_profiles else None

    interactions = (
        BorrowerInteraction.query
        .filter_by(borrower_id=borrower_id)
        .order_by(BorrowerInteraction.timestamp.desc())
        .limit(10)
        .all()
    )

    ai_summary = (
        AIIntakeSummary.query
        .filter_by(borrower_id=borrower_id)
        .order_by(AIIntakeSummary.created_at.desc())
        .first()
    )

    return render_template(
        "loan_officer/intake_review.html",
        borrower=borrower,
        credit=credit,
        interactions=interactions,
        ai_summary=ai_summary,
        active_tab="borrowers",
        title="Intake Review"
    )


@loan_officer_bp.route("/loan-summary/<int:loan_id>")
@role_required("loan_officer")
def loan_summary(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    borrower = loan.borrower_profile

    quotes = (
        LoanQuote.query
        .filter_by(loan_application_id=loan_id)
        .order_by(LoanQuote.created_at.desc())
        .all()
    )

    credit = borrower.credit_profiles[-1] if borrower and borrower.credit_profiles else None

    ai_summary = None
    if borrower:
        ai_summary = (
            AIIntakeSummary.query
            .filter_by(borrower_id=borrower.id)
            .order_by(AIIntakeSummary.created_at.desc())
            .first()
        )

    return render_template(
        "loan_officer/loan_summary.html",
        loan=loan,
        borrower=borrower,
        quotes=quotes,
        credit=credit,
        ai_summary=ai_summary,
        active_tab="pipeline",
        title=f"Loan Summary #{loan.id}"
    )


@loan_officer_bp.route("/messages/<int:borrower_id>")
@role_required("loan_officer")
def borrower_messages(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)

    interactions = (
        BorrowerInteraction.query
        .filter_by(borrower_id=borrower_id)
        .order_by(BorrowerInteraction.timestamp.desc())
        .all()
    )

    uploads = (
        Upload.query
        .filter_by(borrower_profile_id=borrower_id)
        .order_by(Upload.uploaded_at.desc())
        .all()
    )

    notes = (
        CRMNote.query
        .filter_by(borrower_id=borrower_id)
        .order_by(CRMNote.created_at.desc())
        .all()
    )

    return render_template(
        "loan_officer/messages.html",
        borrower=borrower,
        interactions=interactions,
        uploads=uploads,
        notes=notes,
        active_tab="messages",
        title="Borrower Messages"
    )


@loan_officer_bp.route("/profile/<int:borrower_id>", methods=["GET", "POST"])
@csrf.exempt
@role_required("loan_officer")
def profile(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)
    form = BorrowerProfileForm(obj=borrower)

    if form.validate_on_submit():
        form.populate_obj(borrower)
        db.session.commit()

        flash("Borrower profile updated.", "success")
        return redirect(url_for("loan_officer.intake_review", borrower_id=borrower.id))

    return render_template(
        "loan_officer/profile.html",
        form=form,
        borrower=borrower,
        active_tab="borrowers",
        title="Borrower Profile"
    )


@loan_officer_bp.route("/quote-plan/<int:loan_id>", methods=["GET", "POST"])
@csrf.exempt
@role_required("loan_officer")
def quote_plan(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    form = QuotePlanForm()

    plan = (
        QuotePlan.query
        .filter_by(loan_id=loan_id)
        .order_by(QuotePlan.created_at.desc())
        .first()
    )

    options = plan.options if plan else []

    if form.validate_on_submit():
        plan = QuotePlan(
            loan_id=loan.id,
            title=form.title.data,
            notes=form.notes.data,
            created_by=current_user.id
        )
        db.session.add(plan)
        db.session.commit()

        flash("Quote plan saved.", "success")
        return redirect(url_for("loan_officer.quote_plan", loan_id=loan.id))

    return render_template(
        "loan_officer/quote_plan.html",
        loan=loan,
        form=form,
        plan=plan,
        options=options,
        active_tab="tools",
        title="Quote Plan"
    )


# =========================================================
# QUOTES VIEW BY BORROWER
# =========================================================
@loan_officer_bp.route("/quotes/<int:borrower_id>")
@role_required("loan_officer")
def quotes(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)
    loans = LoanApplication.query.filter_by(borrower_profile_id=borrower.id).all()

    quotes_by_loan = {
        loan.id: (
            LoanQuote.query
            .filter_by(loan_application_id=loan.id)
            .order_by(LoanQuote.created_at.desc())
            .all()
        )
        for loan in loans
    }

    return render_template(
        "loan_officer/quotes.html",
        borrower=borrower,
        loans=loans,
        quotes_by_loan=quotes_by_loan,
        active_tab="tools",
        title="Quotes"
    )


# =========================================================
# NEW LOAN CREATION
# =========================================================
@loan_officer_bp.route("/loan/new", methods=["GET", "POST"])
@csrf.exempt
@role_required("loan_officer")
def new_loan():
    borrowers = BorrowerProfile.query.order_by(BorrowerProfile.full_name.asc()).all()
    officer = LoanOfficerProfile.query.filter_by(user_id=current_user.id).first()

    if request.method == "POST":
        borrower_id = request.form.get("borrower_id")
        loan_type = request.form.get("loan_type")
        amount = request.form.get("amount")
        status = request.form.get("status", "pending")

        if not borrower_id or not loan_type or not amount:
            flash("Please complete all required fields.", "warning")
            return redirect(url_for("loan_officer.new_loan"))

        try:
            loan = LoanApplication(
                borrower_profile_id=int(borrower_id),
                loan_type=loan_type,
                amount=float(amount),
                status=status,
                loan_officer_id=officer.id if officer else None,
                created_at=datetime.utcnow(),
            )
            db.session.add(loan)
            db.session.commit()

            flash(f"Loan #{loan.id} created successfully.", "success")
            return redirect(url_for("loan_officer.loan_queue"))

        except Exception as e:
            db.session.rollback()
            flash(f"Error creating loan: {e}", "danger")

    return render_template(
        "loan_officer/new_loan.html",
        borrowers=borrowers,
        active_tab="pipeline",
        title="New Loan"
    )


@loan_officer_bp.route("/loan/<int:loan_id>")
@loan_officer_bp.route("/capital-funds/<int:loan_id>")
@role_required("loan_officer")
def capital_funds(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)

    borrower = loan.borrower_profile
    investor = getattr(loan, "investor_profile", None)

    documents = LoanDocument.query.filter_by(loan_id=loan.id).all()
    quotes = LoanQuote.query.filter_by(loan_application_id=loan.id).all()
    tasks = Task.query.filter_by(loan_id=loan.id).order_by(Task.due_date.asc()).all()
    conditions = UnderwritingCondition.query.filter_by(loan_id=loan.id).all()

    credit = None
    if borrower and getattr(borrower, "credit_profiles", None):
        credit = borrower.credit_profiles[-1] if borrower.credit_profiles else None

    ratios = {}
    if borrower:
        try:
            ratios = calculate_dti_ltv(borrower, loan, credit) or {}
        except Exception:
            ratios = {}

    uploads_by_loan = {
        loan.id: [
            doc for doc in documents
            if (getattr(doc, "status", "") or "").lower() != "archived"
        ]
    }

    # Optional Ravlo deal context placeholders
    deal = None
    featured_rehab = {}
    rehab_scope = {}
    build_analysis = {}

    if not getattr(loan, "ai_summary", None):
        try:
            assistant = AIAssistant()
            client_name = (
                getattr(investor, "full_name", None)
                or getattr(borrower, "full_name", None)
                or "Unknown Client"
            )

            loan.ai_summary = assistant.generate_reply(
                f"Summarize this capital request for {client_name}: "
                f"{loan.loan_type or 'Capital Request'}, "
                f"${loan.amount or 0:,.0f} requested, "
                f"property value ${loan.property_value or 0:,.0f}, "
                f"rate {loan.rate or 0}%, "
                f"term {loan.term_months or 0} months, "
                f"status {loan.status or 'Pending'}.",
                "loan_detail_summary"
            )
            db.session.commit()
        except Exception as e:
            print("AI summary unavailable:", e)

    return render_template(
        "loan_officer/capital_funds.html",
        loan=loan,
        borrower=borrower,
        investor=investor,
        credit=credit,
        ratios=ratios,
        documents=documents,
        quotes=quotes,
        tasks=tasks,
        conditions=conditions,
        uploads_by_loan=uploads_by_loan,
        deal=deal,
        featured_rehab=featured_rehab,
        rehab_scope=rehab_scope,
        build_analysis=build_analysis,
        ai_summary=loan.ai_summary,
        active_tab="pipeline",
        title=f"Capital Funds • {loan.loan_type or 'Request'}"
    )

@loan_officer_bp.route("/upload/<int:borrower_id>", methods=["GET", "POST"])
@csrf.exempt
@role_required("loan_officer")
def upload(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)
    loans = LoanApplication.query.filter_by(borrower_profile_id=borrower_id).all()

    uploads = (
        Upload.query
        .filter_by(borrower_profile_id=borrower_id)
        .order_by(Upload.uploaded_at.desc())
        .all()
    )

    requested_docs = (
        DocumentRequest.query
        .join(LoanApplication)
        .filter(LoanApplication.borrower_profile_id == borrower_id)
        .all()
    )

    form = UploadForm()
    form.loan_id.choices = [(loan.id, f"Loan #{loan.id} - {loan.loan_type}") for loan in loans]

    if form.validate_on_submit():
        file = request.files.get("file")
        if not file or not file.filename:
            flash("Please choose a file.", "warning")
            return redirect(url_for("loan_officer.upload", borrower_id=borrower_id))

        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        upload = Upload(
            borrower_profile_id=borrower_id,
            loan_id=form.loan_id.data or None,
            file_name=filename,
            file_path=filepath,
            uploaded_by_id=current_user.id,
            category=form.description.data if hasattr(form, "description") else None,
        )
        db.session.add(upload)
        db.session.commit()

        flash("File uploaded successfully.", "success")
        return redirect(url_for("loan_officer.upload", borrower_id=borrower_id))

    return render_template(
        "loan_officer/upload.html",
        borrower=borrower,
        form=form,
        uploads=uploads,
        requested_docs=requested_docs,
        active_tab="borrowers",
        title="Uploads"
    )


@loan_officer_bp.route("/follow-up/<int:borrower_id>", methods=["GET", "POST"])
@csrf.exempt
@role_required("loan_officer")
def follow_up(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)
    form = FollowUpForm()

    items = (
        FollowUpItem.query
        .filter_by(borrower_profile_id=borrower_id)
        .order_by(FollowUpItem.created_at.desc())
        .all()
    )

    if form.validate_on_submit():
        item = FollowUpItem(
            borrower_profile_id=borrower_id,
            description=form.description.data,
            created_by=current_user.id
        )
        db.session.add(item)
        db.session.commit()

        flash("Follow-up item added.", "success")
        return redirect(url_for("loan_officer.follow_up", borrower_id=borrower_id))

    return render_template(
        "loan_officer/follow_up.html",
        borrower=borrower,
        form=form,
        items=items,
        active_tab="borrowers",
        title="Follow Up"
    )


@loan_officer_bp.route("/timeline/<int:borrower_id>")
@role_required("loan_officer")
def timeline(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)

    interactions = BorrowerInteraction.query.filter_by(borrower_id=borrower_id).all()
    uploads = Upload.query.filter_by(borrower_profile_id=borrower_id).all()
    notes = CRMNote.query.filter_by(borrower_id=borrower_id).all()
    followups = FollowUpItem.query.filter_by(borrower_profile_id=borrower_id).all()
    ai_summaries = AIIntakeSummary.query.filter_by(borrower_id=borrower_id).all()

    events = []

    for i in interactions:
        events.append({
            "type": "interaction",
            "timestamp": i.timestamp,
            "label": "AI Chat",
            "detail": f"Q: {getattr(i, 'question', '')}<br>A: {getattr(i, 'answer', '')}"
        })

    for u in uploads:
        events.append({
            "type": "upload",
            "timestamp": u.uploaded_at,
            "label": "Upload",
            "detail": f"{u.file_name} ({getattr(u, 'category', '')})"
        })

    for n in notes:
        events.append({
            "type": "note",
            "timestamp": n.created_at,
            "label": "CRM Note",
            "detail": n.content
        })

    for f in followups:
        events.append({
            "type": "followup",
            "timestamp": f.completed_at if getattr(f, "is_done", False) else f.created_at,
            "label": "Follow-Up",
            "detail": f.description + (" ✅ Completed" if getattr(f, "is_done", False) else "")
        })

    for a in ai_summaries:
        events.append({
            "type": "ai_summary",
            "timestamp": a.created_at,
            "label": "AI Intake Summary",
            "detail": (a.summary[:300] + "...") if getattr(a, "summary", None) else "AI Summary"
        })

    events.sort(key=lambda e: e["timestamp"], reverse=True)

    return render_template(
        "loan_officer/timeline.html",
        borrower=borrower,
        events=events,
        active_tab="borrowers",
        title="Timeline"
    )


# ===============================================================
# BORROWERS
# ===============================================================
@loan_officer_bp.route("/borrowers")
@role_required("loan_officer")
def borrowers():
    q = (request.args.get("q") or "").strip()

    qry = BorrowerProfile.query

    if q:
        qry = qry.filter(
            BorrowerProfile.full_name.ilike(f"%{q}%") |
            BorrowerProfile.email.ilike(f"%{q}%")
        )

    borrowers = qry.order_by(BorrowerProfile.created_at.desc()).all()

    for b in borrowers:
        b.has_loan = len(b.loans) > 0
        b.has_started_1003 = any(l.amount for l in b.loans)

        last = (
            BorrowerInteraction.query
            .filter_by(borrower_id=b.id)
            .order_by(BorrowerInteraction.timestamp.desc())
            .first()
        )

        b.last_activity = last.timestamp.strftime("%b %d, %Y") if last else None

    return render_template(
        "loan_officer/borrowers.html",
        borrowers=borrowers,
        active_tab="borrowers",
        title="Borrowers"
    )


@loan_officer_bp.route("/borrower/<int:borrower_id>")
@role_required("loan_officer")
def view_borrower(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)

    loans = LoanApplication.query.filter_by(borrower_profile_id=borrower_id).all()
    credit = borrower.credit_profiles[-1] if borrower.credit_profiles else None
    tasks = Task.query.filter_by(borrower_id=borrower_id).order_by(Task.due_date.asc()).all()
    documents = LoanDocument.query.filter_by(borrower_profile_id=borrower_id).all()

    safe_credit_data = None
    if credit and getattr(credit, "credit_data", None):
        try:
            safe_credit_data = json.dumps(credit.credit_data, indent=2, default=str)
        except Exception:
            safe_credit_data = str(credit.credit_data)

    return render_template(
        "loan_officer/borrower_view.html",
        borrower=borrower,
        loans=loans,
        credit=credit,
        tasks=tasks,
        documents=documents,
        safe_credit_data=safe_credit_data,
        active_tab="borrowers",
        title="Borrower View"
    )

@loan_officer_bp.route("/borrower-dashboard/<int:borrower_id>")
@role_required("loan_officer")
def borrower_dashboard(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)

    loans = LoanApplication.query.filter_by(borrower_profile_id=borrower_id).all()
    uploads = Upload.query.filter_by(borrower_profile_id=borrower_id).all()

    quotes = (
        LoanQuote.query
        .join(LoanApplication, LoanQuote.loan_application_id == LoanApplication.id)
        .filter(LoanApplication.borrower_profile_id == borrower_id)
        .all()
    )

    followups = FollowUpItem.query.filter_by(borrower_profile_id=borrower_id, is_done=False).all()

    ai_summary = (
        AIIntakeSummary.query
        .filter_by(borrower_id=borrower_id)
        .order_by(AIIntakeSummary.created_at.desc())
        .first()
    )

    return render_template(
        "loan_officer/borrower_dashboard.html",
        borrower=borrower,
        loans=loans,
        uploads=uploads,
        quotes=quotes,
        followups=followups,
        ai_summary=ai_summary,
        active_tab="borrowers",
        title="Borrower Dashboard"
    )


@loan_officer_bp.route("/borrower-search", methods=["GET", "POST"])
@csrf.exempt
@role_required("loan_officer")
def borrower_search():
    form = BorrowerSearchForm()
    results = []

    if form.validate_on_submit():
        query = BorrowerProfile.query

        if form.name.data:
            query = query.filter(BorrowerProfile.full_name.ilike(f"%{form.name.data}%"))
        if form.email.data:
            query = query.filter(BorrowerProfile.email.ilike(f"%{form.email.data}%"))
        if form.phone.data:
            query = query.filter(BorrowerProfile.phone.ilike(f"%{form.phone.data}%"))

        borrowers = query.all()

        if form.loan_status.data:
            borrowers = [
                b for b in borrowers
                if any((l.status or "") == form.loan_status.data for l in b.loans)
            ]

        results = borrowers

    return render_template(
        "loan_officer/borrower_search.html",
        form=form,
        results=results,
        active_tab="borrowers",
        title="Borrower Search"
    )

@loan_officer_bp.route("/borrower-intake", methods=["GET", "POST"])
@csrf.exempt
@role_required("loan_officer")
def borrower_intake():
    form = BorrowerIntakeForm()

    if form.validate_on_submit():
        borrower = BorrowerProfile(
            full_name=form.full_name.data,
            email=form.email.data,
            phone=form.phone.data,
            annual_income=form.annual_income.data,
            credit_score=form.credit_score.data,
            employment_status=form.employment_status.data,
            assigned_to=current_user.id,
            created_at=datetime.utcnow(),
        )
        db.session.add(borrower)
        db.session.commit()

        try:
            summary = master_ai.generate(
                f"""
                Summarize this new borrower intake:

                Name: {borrower.full_name}
                Email: {borrower.email}
                Income: {borrower.annual_income}
                Credit Score: {borrower.credit_score}
                Employment: {borrower.employment_status}
                """,
                role="loan_officer"
            )

            db.session.add(
                AIIntakeSummary(
                    borrower_id=borrower.id,
                    summary=summary,
                    created_at=datetime.utcnow(),
                )
            )
            db.session.commit()
        except Exception:
            pass

        flash("Borrower created and AI summary generated.", "success")
        return redirect(url_for("loan_officer.borrower_dashboard", borrower_id=borrower.id))

    return render_template(
        "loan_officer/borrower_intake.html",
        form=form,
        active_tab="borrowers",
        title="Borrower Intake"
    )


@loan_officer_bp.route("/resources")
@role_required("loan_officer")
def resources():
    resources = {
        "scripts": [
            {
                "title": "Borrower Welcome Script",
                "body": "Hello [Name], we received your loan request and I’ll be your main point of contact. I’ll help guide your file and next steps."
            },
            {
                "title": "Missing Documents Script",
                "body": "Hello [Name], to continue moving forward we still need the following items: [Docs]. Please upload them at your earliest convenience."
            },
            {
                "title": "Follow-Up Script",
                "body": "Hello [Name], just checking in on the remaining items for your file. Once received, we can continue processing immediately."
            },
            {
                "title": "Preapproval Update Script",
                "body": "Good news — your file has been reviewed and we’re preparing the next phase. I’ll send your official update shortly."
            },
        ],
        "products": [
            {
                "name": "DSCR Loan",
                "summary": "Investor loan based on rental cash flow rather than personal income."
            },
            {
                "name": "Fix & Flip",
                "summary": "Short-term financing for acquisition and renovation of investment properties."
            },
            {
                "name": "Bridge Loan",
                "summary": "Fast capital for transitional properties or time-sensitive opportunities."
            },
            {
                "name": "Construction Loan",
                "summary": "Funding for ground-up construction or major rebuild projects."
            },
        ],
        "checklists": [
            {
                "title": "Initial Intake Checklist",
                "items": [
                    "Borrower contact information",
                    "Entity / ownership details",
                    "Purchase contract or scenario details",
                    "Property address",
                    "Exit strategy",
                    "Income or rent support",
                ],
            },
            {
                "title": "Common Document Checklist",
                "items": [
                    "ID / entity docs",
                    "Bank statements",
                    "Purchase contract",
                    "Scope of work",
                    "Insurance",
                    "Credit authorization if needed",
                ],
            },
        ],
        "workflow": [
            "Review new lead activity",
            "Follow up on incomplete files",
            "Check document uploads",
            "Update CRM notes",
            "Move loans to next stage daily",
            "Flag files needing processor or underwriting attention",
        ],
    }

    return render_template(
        "loan_officer/resources.html",
        resources=resources,
        active_tab="resource_center",
        title="Resource Center",
    )

@loan_officer_bp.route("/resources/chat", methods=["POST"])
@csrf.exempt
@role_required("loan_officer")
def resources_chat():
    data = request.get_json() or {}
    query = data.get("query", "")

    try:
        assistant = AIAssistant()
        reply = assistant.generate_reply(
            f"Loan officer resource inquiry: {query}. Be concise, accurate, and instructional.",
            "loan_officer"
        )
    except Exception:
        reply = "AI chat is temporarily unavailable."

    return jsonify({"reply": reply})


@loan_officer_bp.route("/campaigns/create", methods=["GET", "POST"])
@csrf.exempt
@role_required("loan_officer")
def create_campaign():
    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description")
        channel = request.form.get("channel")
        status = request.form.get("status", "draft")

        new_campaign = Campaign(
            name=name,
            description=description,
            channel=channel,
            status=status,
            created_by_id=current_user.id
        )
        db.session.add(new_campaign)
        db.session.commit()

        flash("Campaign created successfully.", "success")
        return redirect(url_for("loan_officer.campaigns"))

    return render_template(
        "loan_officer/create_campaign.html",
        active_tab="campaigns",
        title="Create Campaign"
    )


@loan_officer_bp.route("/upload-call/<int:borrower_id>", methods=["POST"])
@csrf.exempt
@role_required("loan_officer")
def upload_call(borrower_id):
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    filename = secure_filename(file.filename)
    saved_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    file.save(saved_path)

    # Whisper / transcription service
    with open(saved_path, "rb") as audio:
        transcript_response = client.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=audio
        )

    transcript_text = transcript_response.text

    sentiment = analyze_sentiment(transcript_text)
    docs = detect_documents(transcript_text)

    borrower = BorrowerProfile.query.get_or_404(borrower_id)
    loan = LoanApplication.query.filter_by(borrower_profile_id=borrower_id).first()

    ai_summary = master_ai.generate(
        f"""
TRANSCRIPT:
{transcript_text}

BORROWER:
{borrower.full_name}
Income: {borrower.income}
Loan Type: {loan.loan_type if loan else 'N/A'}
Loan Amount: {loan.amount if loan else 'N/A'}

Provide:
1. FULL SUMMARY
2. BORROWER INTENT
3. QUALIFICATION OVERVIEW
4. RED FLAGS
5. RECOMMENDED NEXT STEPS
6. REQUIRED DOCUMENTS
7. FOLLOW-UP TASKS
8. CALL RATING (1-10)
""",
        role="loan_officer"
    )

    tasks = extract_tasks(ai_summary)
    auto_docs = detect_documents(ai_summary)

    note = BorrowerInteraction(
        borrower_id=borrower.id,
        interaction_type="Call Recording",
        notes=ai_summary
    )
    db.session.add(note)

    for t in tasks:
        task = Task(
            borrower_id=borrower.id,
            assigned_to=current_user.id,
            title=t,
            status="open"
        )
        db.session.add(task)

    for doc in auto_docs:
        dr = DocumentRequest(
            borrower_id=borrower.id,
            loan_id=loan.id if loan else None,
            document_name=doc,
            status="requested",
            requested_by=getattr(current_user, "email", None) or str(current_user.id),
        )
        db.session.add(dr)

    if loan:
        event = LoanStatusEvent(
            loan_id=loan.id,
            event_name="Call Recording Uploaded",
            description="AI has analyzed the call recording."
        )
        db.session.add(event)

    db.session.commit()

    return jsonify({
        "status": "success",
        "summary": ai_summary,
        "sentiment": sentiment,
        "auto_docs": auto_docs,
        "auto_tasks": tasks
    })


@loan_officer_bp.route("/auto-price/<int:borrower_id>")
@role_required("loan_officer")
def auto_price(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)
    loan = LoanApplication.query.filter_by(borrower_profile_id=borrower.id).first()
    credit = borrower.credit_profiles[-1] if borrower.credit_profiles else None

    if not loan:
        return jsonify({"error": "No loan found for this borrower."}), 404

    loan_amount = float(loan.amount or 0)
    property_value = float(loan.property_value or 0)
    credit_score = credit.credit_score if credit else 680

    ltv = (loan_amount / property_value) if property_value else None

    est_rate = estimate_rate(credit_score, ltv, (loan.loan_type or "").lower())
    est_payment = calc_payment(loan_amount, est_rate, term=30)

    dscr = None
    if (loan.loan_type or "").lower() == "dscr":
        dscr = calc_dscr(getattr(loan, "monthly_rent", 0) or 0, est_payment)

    ltv_display = f"{ltv:.2f}" if ltv is not None else "N/A"

    pricing_summary = master_ai.generate(
        f"""
Loan Type: {loan.loan_type}
Loan Amount: {loan.amount}
Property Value: {loan.property_value}
Credit Score: {credit_score}
LTV: {ltv_display}
Estimated Rate: {est_rate}
Estimated Payment: {est_payment}
DSCR: {dscr}

Generate a luxury-finance explanation with:
- Program eligibility
- Risk factors
- Score impact
- DSCR commentary (if DSCR loan)
- Next steps for borrower
""",
        role="loan_officer"
    )

    return jsonify({
        "rate": est_rate,
        "payment": est_payment,
        "ltv": ltv,
        "dscr": dscr,
        "summary": pricing_summary
    })


@loan_officer_bp.route("/preapprove/<int:borrower_id>")
@role_required("loan_officer")
def preapprove(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)
    loan = LoanApplication.query.filter_by(borrower_profile_id=borrower.id).first()
    credit = borrower.credit_profiles[-1] if borrower.credit_profiles else None

    if not loan:
        return jsonify({"error": "No loan found for this borrower."}), 404

    engine = PreapprovalEngine(borrower, loan, credit)

    front_dti, back_dti = engine.calc_dti()
    ltv = engine.calc_ltv()
    fits = engine.program_fit()
    flags = engine.red_flags()
    conds = engine.required_conditions()

    ai_summary = master_ai.generate(
        f"""
Borrower: {borrower.full_name}
Income: {borrower.income}
Loan Type: {loan.loan_type}
Loan Amount: {loan.amount}
Property Value: {loan.property_value}
Credit Score: {credit.credit_score if credit else 'N/A'}

DTI Front: {front_dti}
DTI Back: {back_dti}
LTV: {ltv}
Program Fit: {fits}
Red Flags: {flags}
Conditions: {conds}

Write a luxury-finance preapproval summary including:
- Borrower strength profile
- Eligibility assessment
- Recommended program(s)
- Risk commentary
- Red flags
- Conditions needed
- Clear next steps
""",
        role="underwriter"
    )

    track_event(
        loan_id=loan.id,
        borrower_id=borrower.id,
        document_name="Pre-Approval Letter",
        event_type="emailed"
    )

    return jsonify({
        "front_dti": front_dti,
        "back_dti": back_dti,
        "ltv": ltv,
        "fits": fits,
        "flags": flags,
        "conditions": conds,
        "ai_summary": ai_summary
    })


@loan_officer_bp.route("/preapproval_letter/<int:loan_id>")
@role_required("loan_officer")
def preapproval_letter(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    borrower = loan.borrower_profile
    credit = borrower.credit_profiles[-1] if borrower.credit_profiles else None

    engine = PreapprovalEngine(borrower, loan, credit)
    front_dti, back_dti = engine.calc_dti()
    ltv = engine.calc_ltv()

    p_and_i = calculate_monthly_payment(
        loan_amount=loan.amount,
        annual_rate=loan.rate or 6.99,
        term_months=loan.term_months or 360
    )

    taxes = calculate_taxes(loan.property_value)
    insurance = calculate_insurance(loan.property_value)
    pmi = calculate_mortgage_insurance(loan.amount, loan.property_value)

    total_payment = p_and_i + taxes + insurance + (pmi or 0)

    summary = master_ai.generate(
        f"""
Borrower: {borrower.full_name}
Loan Amount: {loan.amount}
Loan Type: {loan.loan_type}
DTI Front: {front_dti}
DTI Back: {back_dti}
LTV: {ltv}

Estimated Payment Breakdown:
- Principal & Interest: {p_and_i}
- Taxes: {taxes}
- Insurance: {insurance}
- Mortgage Insurance (PMI): {pmi}
- Total Payment: {total_payment}

Write a professional pre-approval narrative including:
- Borrower strength profile
- Eligibility assessment
- Recommended program(s)
- Risk commentary
- Conditions needed
- Clear next steps
""",
        role="underwriter",
    )

    pdf_path = generate_preapproval_pdf(
        borrower=borrower,
        loan=loan,
        summary=summary,
        front_dti=front_dti,
        back_dti=back_dti,
        ltv=ltv,
        p_and_i=p_and_i,
        taxes=taxes,
        insurance=insurance,
        pmi=pmi,
        total_payment=total_payment,
    )

    doc = LoanDocument(
        loan_id=loan.id,
        borrower_profile_id=borrower.id,
        document_name="Pre-Approval Letter",
        file_path=pdf_path,
        document_type="Preapproval",
        status="sent",
        created_at=datetime.utcnow(),
    )
    db.session.add(doc)
    db.session.commit()

    html_body = render_template(
        "email/preapproval_email.html",
        borrower=borrower,
        loan=loan,
    )

    send_email_with_attachment(
        borrower.email,
        "Your Pre-Approval Letter — Caughman Mason Loan Services",
        html_body,
        pdf_path,
    )

    flash("Pre-approval letter generated and emailed to borrower.", "success")
    return send_file(pdf_path, as_attachment=True)


@loan_officer_bp.route("/ai_chat", methods=["POST"])
@csrf.exempt
@role_required("loan_officer")
def ai_chat():
    data = request.get_json() or {}
    message = data.get("message", "")
    borrower_id = data.get("borrower_id")
    loan_id = data.get("loan_id")
    parent_id = data.get("parent_id")

    context = ""

    if borrower_id:
        borrower = BorrowerProfile.query.get(borrower_id)
        if borrower:
            context += f"Borrower: {borrower.full_name}, Email: {borrower.email}, Phone: {borrower.phone}\n"

    if loan_id:
        loan = LoanApplication.query.get(loan_id)
        if loan:
            context += f"Loan: {loan.loan_type}, Amount: {loan.amount}, Status: {loan.status}\n"

    reply = master_ai.generate(
        f"Context:\n{context}\n\nUser Message:\n{message}",
        role="loan_officer"
    )

    chat = AIAssistantInteraction(
        user_id=current_user.id,
        borrower_profile_id=borrower_id,
        parent_id=parent_id,
        question=message,
        response=reply,
        timestamp=datetime.utcnow(),
    )

    # only set optional attrs if your model supports them
    if hasattr(chat, "loan_id"):
        chat.loan_id = loan_id
    if hasattr(chat, "context_tag"):
        chat.context_tag = "loan_officer_chat"
    if hasattr(chat, "loan_officer_id"):
        chat.loan_officer_id = current_user.id

    db.session.add(chat)
    db.session.commit()

    return jsonify({"reply": reply, "chat_id": chat.id})


@loan_officer_bp.route("/ai_chat/history")
@role_required("loan_officer")
def ai_chat_history():
    borrower_id = request.args.get("borrower_id")
    loan_id = request.args.get("loan_id")

    q = AIAssistantInteraction.query.filter_by(user_id=current_user.id)

    if borrower_id:
        q = q.filter_by(borrower_profile_id=borrower_id)

    if loan_id and hasattr(AIAssistantInteraction, "loan_id"):
        q = q.filter_by(loan_id=loan_id)

    history = q.order_by(AIAssistantInteraction.timestamp.asc()).all()

    return render_template(
        "loan_officer/ai_chat.html",
        history=history,
        borrower_id=borrower_id,
        loan_id=loan_id,
        active_tab="tools",
        title="AI Chat"
    )


@loan_officer_bp.route("/loan/<int:loan_id>/scenarios", methods=["GET", "POST"])
@csrf.exempt
@role_required("loan_officer")
def loan_scenarios(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    scenarios = []

    if request.method == "POST":
        titles = request.form.getlist("title")
        amounts = request.form.getlist("loan_amount")
        rates = request.form.getlist("rate")
        terms = request.form.getlist("term")

        for i in range(len(titles)):
            sc = LoanScenario(
                loan_id=loan.id,
                title=titles[i],
                amount=float(amounts[i] or 0),
                rate=float(rates[i] or 0),
                term_months=int(terms[i] or 0),
                loan_type=loan.loan_type,
                ltv=(float(amounts[i] or 0) / float(loan.property_value or 1)) if loan.property_value else None,
            )
            scenarios.append(sc)

        scenario_text = "\n\n".join(
            [
                f"Scenario {idx + 1}: Title={s.title}, Amount={s.amount}, Rate={s.rate}, Term={s.term_months}"
                for idx, s in enumerate(scenarios)
            ]
        )

        ai_summary = master_ai.generate(
            f"""
Compare these mortgage scenarios:

{scenario_text}

Provide:
- Best program choice
- Payment sensitivity analysis
- Risk differences
- Which borrower profile each fits
- Scenario ranking
- Final recommendation
""",
            role="loan_officer"
        )

        return render_template(
            "loan_officer/scenarios_compare.html",
            loan=loan,
            scenarios=scenarios,
            ai_summary=ai_summary,
            active_tab="tools",
            title="Scenario Comparison"
        )

    return render_template(
        "loan_officer/scenarios_form.html",
        loan=loan,
        active_tab="tools",
        title="Scenario Builder"
    )


@loan_officer_bp.route("/loan/<int:loan_id>/scenario/add", methods=["POST"])
@role_required("loan_officer")
def add_scenario(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)

    s = LoanScenario(
        loan_id=loan.id,
        title=request.form.get("title"),
        amount=float(request.form.get("amount") or 0),
        rate=float(request.form.get("rate") or 0),
        term_months=int(request.form.get("term_months") or 0),
        loan_type=request.form.get("loan_type"),
        down_payment=float(request.form.get("down_payment") or 0),
        closing_costs=float(request.form.get("closing_costs") or 0),
        monthly_payment=float(request.form.get("monthly_payment") or 0),
        dti=float(request.form.get("dti") or 0),
        ltv=float(request.form.get("ltv") or 0),
        apr=float(request.form.get("apr") or 0),
    )

    db.session.add(s)
    db.session.commit()

    flash("Scenario saved.", "success")
    return redirect(url_for("loan_officer.loan_file", loan_id=loan.id))


@loan_officer_bp.route("/loan/<int:loan_id>/scenario/<int:id>/delete", methods=["POST"])
@csrf.exempt
@role_required("loan_officer")
def delete_scenario(loan_id, id):
    s = LoanScenario.query.get_or_404(id)
    db.session.delete(s)
    db.session.commit()
    return redirect(url_for("loan_officer.loan_file", loan_id=loan_id))


@loan_officer_bp.route("/loan/<int:loan_id>/generate_1003")
@role_required("loan_officer")
def generate_1003(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    borrower = loan.borrower_profile

    pdf_path = fill_1003_pdf(borrower, loan)

    doc = LoanDocument(
        borrower_profile_id=borrower.id,
        loan_id=loan.id,
        document_name="1003 Loan Application",
        file_path=pdf_path,
        document_type="1003",
        status="generated",
        created_at=datetime.utcnow(),
    )
    db.session.add(doc)
    db.session.commit()

    return send_file(pdf_path, as_attachment=True)


@loan_officer_bp.route("/borrower/<int:borrower_id>/request-docs", methods=["GET", "POST"])
@csrf.exempt
@role_required("loan_officer")
def request_documents(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)
    loan = LoanApplication.query.filter_by(borrower_profile_id=borrower.id).first()

    if request.method == "POST":
        doc_request = DocumentRequest(
            borrower_id=borrower.id,
            loan_id=loan.id if loan else None,
            document_name=request.form.get("document_name") or "Requested Document",
            notes=request.form.get("notes"),
            status="Pending",
            requested_by=getattr(current_user, "email", None) or str(current_user.id),
            created_at=datetime.utcnow(),
        )
        db.session.add(doc_request)
        db.session.commit()

        flash("Document request sent successfully.", "success")
        return redirect(url_for("loan_officer.view_borrower", borrower_id=borrower.id))

    return render_template(
        "loan_officer/request_docs.html",
        borrower=borrower,
        loan=loan,
        active_tab="borrowers",
        title="Request Documents"
    )


@loan_officer_bp.route("/loan/<int:loan_id>/generate_needs", methods=["POST"])
@csrf.exempt
@role_required("loan_officer")
def generate_doc_needs(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    borrower = loan.borrower_profile
    credit = borrower.credit_profiles[-1] if borrower.credit_profiles else None

    # renamed helper call to avoid route/helper confusion
    needs = generate_document_needs(borrower, loan, credit)

    flash(f"{len(needs)} document needs generated.", "success")
    return redirect(url_for("loan_officer.loan_file", loan_id=loan_id))


@loan_officer_bp.route("/save_preapproval_snapshot/<int:loan_id>", methods=["POST"])
@csrf.exempt
@role_required("loan_officer")
def save_preapproval_snapshot(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    borrower = loan.borrower_profile
    credit = borrower.credit_profiles[-1] if borrower.credit_profiles else None

    engine = PreapprovalEngine(borrower, loan, credit)

    fe, be = engine.calc_dti()
    ltv = engine.calc_ltv()
    fits = engine.program_fit()
    flags = engine.red_flags()
    conditions = engine.required_conditions()

    snapshot = PreapprovalSnapshot(
        loan_id=loan_id,
        front_dti=fe,
        back_dti=be,
        ltv=ltv,
        program_fit=", ".join(fits),
        red_flags=", ".join(flags),
        conditions=", ".join(conditions)
    )

    db.session.add(snapshot)
    db.session.commit()

    return jsonify({"message": "Preapproval snapshot saved successfully!"})


@loan_officer_bp.route("/loan/<int:loan_id>")
@role_required("loan_officer", "admin", "master_admin", "lending_admin")
def loan_detail(loan_id):
    """
    Detailed loan view for the loan officer.
    Shows borrower profile, loan summary, docs, and underwriting conditions.
    """

    loan = (
        db.session.query(LoanApplication)
        .options(
            joinedload(LoanApplication.borrower),
            joinedload(LoanApplication.documents),
            joinedload(LoanApplication.conditions),
        )
        .filter(LoanApplication.id == loan_id)
        .first()
    )

    if not loan:
        abort(404)

    borrower = getattr(loan, "borrower", None)

    # Safe fallbacks so template does not break
    documents = getattr(loan, "documents", []) or []
    conditions = getattr(loan, "conditions", []) or []

    # Optional progress calculations
    total_conditions = len(conditions)
    cleared_conditions = len(
        [c for c in conditions if (getattr(c, "status", "") or "").lower() in ["cleared", "complete", "completed", "satisfied"]]
    )
    pending_conditions = total_conditions - cleared_conditions

    condition_progress = 0
    if total_conditions > 0:
        condition_progress = round((cleared_conditions / total_conditions) * 100)

    # Optional document grouping
    docs_by_type = {}
    for doc in documents:
        doc_type = getattr(doc, "document_type", None) or getattr(doc, "doc_type", None) or "Other"
        docs_by_type.setdefault(doc_type, []).append(doc)

    return render_template(
        "loan_officer/loan_detail.html",
        loan=loan,
        borrower=borrower,
        documents=documents,
        docs_by_type=docs_by_type,
        conditions=conditions,
        total_conditions=total_conditions,
        cleared_conditions=cleared_conditions,
        pending_conditions=pending_conditions,
        condition_progress=condition_progress,
    )
