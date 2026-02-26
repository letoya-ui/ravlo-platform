# Unified Loan Officer Blueprint (Cleaned Structure)
# -------------------------------------------------
# =============================================================
#  Loan Officer Routes — Cleaned & Organized
# =============================================================

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload
from datetime import datetime
from LoanMVP.extensions import db
from LoanMVP.ai.base_ai import AIAssistant
from LoanMVP.ai.master_ai import master_ai
from LoanMVP.utils.decorators import role_required
from LoanMVP.utils.engagement_engine import EngagementEngine
from LoanMVP.utils.pricing_engine import calculate_dti_ltv
from LoanMVP.utils.pdf_generator import fill_1003_pdf
from LoanMVP.utils.needs_engine import generate_needs
from LoanMVP.utils.preapproval_engine import PreapprovalEngine
from LoanMVP.utils.preapproval_letter import generate_preapproval_pdf
from LoanMVP.utils.tracking import track_event
from LoanMVP.utils.payment_engine import calculate_monthly_payment, calculate_taxes, calculate_insurance, calculate_mortgage_insurance
from LoanMVP.utils.emailer import send_email_with_attachment

# Models
from LoanMVP.models.loan_models import (
    LoanApplication, BorrowerProfile, CreditProfile, LoanIntakeSession,
    LoanQuote, Upload, DocumentEvent, LoanStatusEvent 
)
from LoanMVP.models.loan_officer_model import LoanOfficerProfile, LenderQuote
from LoanMVP.models.crm_models import Lead, CRMNote, Message, Task, LeadSource, FollowUpItem
from LoanMVP.models.document_models import LoanDocument, DocumentRequest
from LoanMVP.models.system_models import SystemLog
from LoanMVP.models.ai_models import LoanAIConversation, AIAuditLog, LoanOfficerAISummary, AIIntakeSummary, AIAssistantInteraction
from LoanMVP.models.borrowers import BorrowerInteraction
from LoanMVP.models.payment_models import PaymentRecord

# Forms
from LoanMVP.forms.credit_forms import CreditCheckForm
from LoanMVP.forms.loan_officer_forms import (
    GenerateQuoteForm, BorrowerSearchForm, BorrowerIntakeForm,
    LoanEditForm, QuoteForm, QuotePlanForm, UploadForm,
    FollowUpForm, CRMNoteForm, CampaignForm, TaskForm
)
from LoanMVP.forms.ai_forms import AIIntakeForm, AIIntakeReviewForm

from LoanMVP.utils.ai import LoanMVPAI
from LoanMVP.models.campaign_model import Campaign

loan_officer_bp = Blueprint("loan_officer", __name__, url_prefix="/loan_officer")
assistant = AIAssistant()
ai = LoanMVPAI()

# =============================================================
# 1. DASHBOARD
# =============================================================
@loan_officer_bp.route("/dashboard")
@role_required("loan_officer")
def dashboard():
    officer = LoanOfficerProfile.query.filter_by(user_id=current_user.id).first()

    if not officer:
        officer = LoanOfficerProfile(
            user_id=current_user.id,
            name=current_user.username or "Unnamed Officer"
        )
        db.session.add(officer)
        db.session.commit()
        flash("Temporary profile created.", "warning")

    leads = Lead.query.filter_by(assigned_to=current_user.id).all()
    loans = LoanApplication.query.filter_by(loan_officer_id=current_user.id).all()
    
    pending_intakes = LoanIntakeSession.query.filter(
        (LoanIntakeSession.assigned_officer_id == officer.id) |
        (LoanIntakeSession.status == "pending")
    ).all()

    pipeline = {
        "submitted": [l for l in loans if l.status == "submitted"],
        "in_review": [l for l in loans if l.status == "in_review"],
        "approved": [l for l in loans if l.status == "approved"],
        "declined": [l for l in loans if l.status == "declined"]
    }

    stats = {
        "total_leads": len(leads),
        "active_loans": len([l for l in loans if l.status not in ["declined", "closed"]]),
        "approved": len([l for l in loans if l.status == "approved"]),
        "declined": len([l for l in loans if l.status == "declined"]),
        "pending_intakes": len(pending_intakes)
    }

    try:
        ai_summary = assistant.generate_reply(
            "Summarize loan officer performance across leads, loans, and pipeline.",
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
        ai_summary=ai_summary
    )

# =============================================================
#   AI Assistant — Loan Officer
# =============================================================
@loan_officer_bp.route("/ai", methods=["POST"])
@role_required("loan_officer")
def ai_assistant():
    data = request.get_json()
    message = data.get("message", "")

    reply = ai.ask(
        prompt=message,
        role="loan_officer"
    )

    return jsonify({"reply": reply})

@loan_officer_bp.route("/loan/<int:loan_id>")
@role_required("loan_officer")
def loan_file(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    borrower = loan.borrower_profile
    
    engine = EngagementEngine(borrower)
    engagement_score = engine.score()

    # Credit report
    credit = borrower.credit_reports[-1] if hasattr(borrower, "credit_reports") and borrower.credit_reports else None

    # Documents
    documents = loan.loan_documents

    # Tasks
    tasks = Task.query.filter_by(loan_id=loan.id).order_by(Task.due_date).all()

    # Underwriting Conditions
    conditions = loan.underwriting_conditions

    # DTI / LTV Helper
    dti_data = calculate_dti_ltv(borrower, loan, credit)

    return render_template(
        "loan_officer/loan_file.html",
        loan=loan,
        borrower=borrower,
        credit=credit,
        documents=documents,
        tasks=tasks,
        conditions=conditions,
        engagement_score=engagement_score,
        ratios=dti_data   # <-- changed from dti to ratios
    )

# ============================================
# Loan Search • Loan Officer Module
# ============================================
@loan_officer_bp.route("/loan_search", methods=["GET", "POST"])
@role_required("loan_officer")
def loan_search():
    """Search for loans by borrower name, loan ID, or status."""
    query = request.args.get("q", "").strip()
    loans = []

    if query:
        loans = LoanApplication.query.join(BorrowerProfile).filter(
            db.or_(
                BorrowerProfile.full_name.ilike(f"%{query}%"),
                LoanApplication.id.cast(db.String).ilike(f"%{query}%"),
                LoanApplication.status.ilike(f"%{query}%")
            )
        ).order_by(LoanApplication.created_at.desc()).all()

    stats = {
        "total_loans": LoanApplication.query.count(),
        "active_loans": LoanApplication.query.filter_by(status="Active").count(),
        "pending_loans": LoanApplication.query.filter_by(status="Pending").count(),
        "closed_loans": LoanApplication.query.filter_by(status="Closed").count(),
    }

    try:
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
        title="Loan Search"
    )

# =========================================================
# 📋 Lead Management
# =========================================================
@loan_officer_bp.route("/leads")
@role_required("loan_officer")
def leads():
    leads = Lead.query.filter_by(assigned_to=current_user.id).order_by(Lead.created_at.desc()).all()
    return render_template("loan_officer/leads.html", leads=leads, title="Lead List")

@loan_officer_bp.route("/lead/<int:lead_id>")
@role_required("loan_officer")
def lead_detail(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    notes = CRMNote.query.filter_by(lead_id=lead.id).all()
    try:
        ai_summary = assistant.generate_reply(
            f"Summarize borrower insights for lead: {lead.name}, {lead.email}", "crm"
        )
    except Exception:
        ai_summary = "AI summary unavailable."
    return render_template("loan_officer/lead_detail.html",
                           lead=lead, notes=notes, ai_summary=ai_summary, title="Lead Details")

@loan_officer_bp.route("/lead/new", methods=["GET", "POST"])
@role_required("loan_officer")
def new_lead():
    """Add a new CRM lead."""
    sources = LeadSource.query.order_by(LeadSource.source_name).all()
    if request.method == "POST":
        lead = Lead(
            name=request.form.get("name"),
            email=request.form.get("email"),
            phone=request.form.get("phone"),
            source_id=request.form.get("source_id"),
            status="new",
            assigned_to=current_user.id,
            created_at=datetime.utcnow(),
        )
        db.session.add(lead)
        db.session.commit()
        flash("✅ Lead created successfully!", "success")
        return redirect(url_for("loan_officer.leads"))
    return render_template("loan_officer/lead_form.html", sources=sources, title="Add New Lead")

@loan_officer_bp.route("/lead/<int:lead_id>/convert", methods=["POST"])
@role_required("loan_officer")
def convert_lead(lead_id):
    """Convert a lead into a borrower profile."""
    lead = Lead.query.get_or_404(lead_id)
    borrower = BorrowerProfile(full_name=lead.name, email=lead.email, phone=lead.phone, lead_id=lead.id)
    db.session.add(borrower)
    lead.status = "converted"
    db.session.commit()
    flash("✅ Lead converted to borrower successfully.", "success")
    return redirect(url_for("loan_officer.leads"))


@loan_officer_bp.route("/lead/update/<int:lead_id>", methods=["POST"])
def update_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)

    lead.status = request.form.get("status")
    lead.notes = request.form.get("notes")

    db.session.commit()

    return redirect(url_for("loan_officer.view_lead", lead_id=lead.id))
# =========================================================
# 💬 AI Generator & Bulk Messaging
# =========================================================
@loan_officer_bp.route("/ai_generator", methods=["GET", "POST"])
@role_required("loan_officer")
def ai_generator():
    """Generates text, summaries, or emails via AI."""
    ai_reply = None
    if request.method == "POST":
        prompt = request.form.get("prompt")
        if not prompt:
            flash("⚠️ Please enter a prompt.", "warning")
            return redirect(url_for("loan_officer.ai_generator"))
        try:
            ai_reply = assistant.generate_reply(prompt, "loan_officer_generator")
        except Exception:
            ai_reply = "AI engine unavailable."
        flash("✅ AI response generated.", "success")
    return render_template("loan_officer/ai_generator.html", ai_reply=ai_reply, title="AI Generator")

@loan_officer_bp.route("/lead_messages", methods=["GET", "POST"])
@role_required("loan_officer")
def lead_messages():
    leads = Lead.query.filter_by(assigned_to=current_user.id).all()
    if request.method == "POST":
        flash(f"📤 Message sent to {len(leads)} leads.", "info")
        return redirect(url_for("loan_officer.lead_messages"))
    return render_template("loan_officer/lead_messages.html", leads=leads, title="Bulk Messaging")

# =========================================================
# 💰 Loan Applications
# =========================================================
@loan_officer_bp.route("/new_application", methods=["GET", "POST"])
@role_required("loan_officer")
def new_application():
    """Create a new, detailed loan application."""
    borrowers = BorrowerProfile.query.order_by(BorrowerProfile.full_name.asc()).all()

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

        # Validate required fields
        if not borrower_id or not amount or not property_value:
            flash("Please fill in all required fields.", "warning")
            return redirect(url_for("loan_officer.new_application"))

        # 🏗 Create new Loan record
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
            loan_officer_id=current_user.id
        )

        db.session.add(new_loan)
        db.session.commit()

        # 🤖 Generate AI acknowledgment
        try:
            ai_message = assistant.generate_reply(
                f"A new {loan_type} loan of ${amount} was created for borrower ID {borrower_id} "
                f"at {rate}% for {term_months} months, property value ${property_value}.",
                "loan_application_summary"
            )
            flash(f"✅ Loan created successfully! AI Summary: {ai_message}", "success")
        except Exception:
            flash("✅ Loan created successfully (AI summary unavailable).", "info")

        return redirect(url_for("loan_officer.view_loan", loan_id=new_loan.id))

    return render_template(
        "loan_officer/new_application.html",
        borrowers=borrowers,
        title="New Loan Application"
    )

# ===============================================================
#   CREATE NEW LOAN
# ===============================================================
@loan_officer_bp.route("/create-loan", methods=["GET", "POST"])
def create_loan():
    officer_id = 1

    if request.method == "POST":
        borrower_id = request.form.get("borrower_id")
        amount = request.form.get("amount")
        loan_type = request.form.get("loan_type")
        property_value = request.form.get("property_value")

        loan = LoanApplication(
            borrower_profile_id=borrower_id,
            loan_officer_id=officer_id,
            amount=amount,
            loan_type=loan_type,
            property_value=property_value,
            status="Pending"
        )

        db.session.add(loan)
        db.session.commit()

        send_notification(loan.id, "processor", "New loan created by Loan Officer.")

        return redirect(f"/officer/dashboard")

    borrowers = BorrowerProfile.query.all()
    return render_template("loan_officer/create_loan.html", borrowers=borrowers)

@loan_officer_bp.route("/quick-1003", methods=["GET", "POST"])
def quick_1003():

    if request.method == "POST":

        # -----------------------------
        # 1 — Borrower Info
        # -----------------------------
        borrower = BorrowerProfile(
            full_name=request.form.get("full_name"),
            email=request.form.get("email"),
            phone=request.form.get("phone"),
            income=request.form.get("income") or 0,

            # Address block
            address=request.form.get("address"),
            city=request.form.get("city"),
            state=request.form.get("state"),
            zip=request.form.get("zip"),

            # Assign LO
            assigned_officer_id=current_user.id,
        )

        db.session.add(borrower)
        db.session.commit()  # ➜ borrower.id now exists


        # -----------------------------
        # 2 — Create Loan File
        # -----------------------------
        loan = LoanApplication(
            borrower_profile_id=borrower.id,
            amount=request.form.get("loan_amount"),
            loan_type=request.form.get("loan_type"),
            property_value=request.form.get("property_value"),
            property_address=request.form.get("property_address"),
            status="Application Submitted"
        )

        db.session.add(loan)
        db.session.commit()  # ➜ loan.id available


        # -----------------------------
        # 3 — Auto Fees
        # -----------------------------
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


        # -----------------------------
        # 4 — Auto Loan Status Timeline
        # -----------------------------
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


        # -----------------------------
        # 5 — Redirect LO to New Loan File
        # -----------------------------
        return redirect(url_for("loan_officer.loan_file", loan_id=loan.id))


    # GET request: Show Quick 1003 form
    return render_template("loan_officer/quick_1003.html")


# =========================================================
# ⚙️ Quote Engine
# =========================================================
@loan_officer_bp.route("/quote_engine", methods=["GET", "POST"])
@role_required("loan_officer")
def quote_engine():
    selected_loan = None
    quotes = []
    if request.method == "POST":
        loan_id = request.form.get("loan_id")
        selected_loan = LoanApplication.query.get(loan_id)
        if not selected_loan:
            flash("❌ Loan not found.", "danger")
            return redirect(url_for("loan_officer.quote_engine"))
        quotes = [
            {"lender": "Lima One", "rate": "7.25%", "ltv": "80%", "monthly_payment": round((selected_loan.amount * 0.0725) / 12, 2)},
            {"lender": "Roc Capital", "rate": "7.50%", "ltv": "78%", "monthly_payment": round((selected_loan.amount * 0.075) / 12, 2)},
            {"lender": "Lev Capital", "rate": "7.10%", "ltv": "82%", "monthly_payment": round((selected_loan.amount * 0.071) / 12, 2)},
        ]
    loans = LoanApplication.query.filter_by(loan_officer_id=current_user.id).all()
    return render_template("loan_officer/quote_engine.html", loans=loans, selected_loan=selected_loan, quotes=quotes, title="Quote Engine")


@loan_officer_bp.route("/quotes/new", methods=["GET", "POST"])
def new_quote():
    if request.method == "POST":
        
        borrower_id = request.form.get("borrower_id")
        loan_id = request.form.get("loan_id")

        # quote fields
        rate = request.form.get("rate")
        points = request.form.get("points")
        apr = request.form.get("apr")
        payment = request.form.get("payment")
        program = request.form.get("program")
        notes = request.form.get("notes")

        quote = LoanQuote(
            borrower_profile_id=borrower_id,
            loan_id=loan_id,
            program=program,
            rate=rate,
            points=points,
            apr=apr,
            payment=payment,
            notes=notes
        )

        db.session.add(quote)
        db.session.commit()

        return redirect(url_for("loan_officer.quotes_center"))

    borrowers = BorrowerProfile.query.all()
    loans = LoanApplication.query.all()

    return render_template("loan_officer/new_quote.html", borrowers=borrowers, loans=loans)

# =========================================================
# 📊 Pipeline & Reports
# =========================================================

# ===============================================================
#   PIPELINE VIEW
# ===============================================================
@loan_officer_bp.route("/pipeline")
def pipeline():

    # ------------------------------
    # Filters
    # ------------------------------
    status_filter = request.args.get("status", "").strip()
    stage_filter = request.args.get("stage", "").strip()
    name_filter = request.args.get("name", "").strip()

    # ------------------------------
    # Base query
    # ------------------------------
    q = LoanApplication.query

    # Filter by status
    if status_filter:
        q = q.filter(LoanApplication.status == status_filter)

    # Filter by stage (custom mapping)
    if stage_filter:
        q = q.filter(LoanApplication.stage == stage_filter)

    # Filter by borrower name
    if name_filter:
        q = q.join(LoanApplication.borrower_profile).filter(
            BorrowerProfile.full_name.ilike(f"%{name_filter}%")
        )

    # ------------------------------
    # Fetch full pipeline
    # ------------------------------
    pipeline = q.order_by(LoanApplication.created_at.desc()).limit(50).all()

    # ------------------------------
    # Add missing docs & stage mapping logic
    # ------------------------------
    for loan in pipeline:

        # Calculate missing docs
        loan.missing_docs = len([d for d in loan.loan_documents if d.status.lower() != "verified"])

        # If no milestone_stage set, derive from status
        if not loan.milestone_stage:
            loan.milestone_stage = derive_stage_from_status(loan.status)

        # Updated time for table
        loan.updated_at = loan.updated_at or loan.created_at


    return render_template(
        "loan_officer/pipeline.html",
        pipeline=pipeline
    )


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

@loan_officer_bp.route("/reports")
@role_required("loan_officer")
def reports():
    loans = LoanApplication.query.filter_by(loan_officer_id=current_user.id).all()
    total, approved, declined = len(loans), sum(l.status == "approved" for l in loans), sum(l.status == "declined" for l in loans)
    return render_template("loan_officer/reports.html", total=total, approved=approved, declined=declined, title="Reports")

# =========================================================
# 🧠 AI Summary (Quick API)
# =========================================================
@loan_officer_bp.route("/ai_summary")
@role_required("loan_officer")
def ai_summary():
    """Generates a short AI summary of performance metrics."""
    try:
        total_loans = LoanApplication.query.count()
        approved = LoanApplication.query.filter_by(status="approved").count()
        pending = LoanApplication.query.filter_by(status="pending").count()
        total_leads = Lead.query.count()

        prompt = (
            f"As a loan officer AI, summarize:\n"
            f"Total loans: {total_loans}, Approved: {approved}, Pending: {pending}, Leads: {total_leads}."
        )
        message = assistant.generate_reply(prompt, "loan_officer")
    except Exception:
        message = "⚠️ AI Summary currently unavailable."
    return jsonify({"message": message, "timestamp": datetime.now().strftime("%H:%M:%S")})

# =========================================================
# ✅ Task Manager
# =========================================================
@loan_officer_bp.route("/tasks", methods=["GET", "POST"])
@role_required("loan_officer")
def task():
    if request.method == "POST":
        title = request.form.get("title")
        if not title:
            flash("⚠️ Task title required.", "warning")
            return redirect(url_for("loan_officer.task"))
        new_task = Task(
            title=title,
            description=request.form.get("description"),
            due_date=datetime.strptime(request.form.get("due_date"), "%Y-%m-%d") if request.form.get("due_date") else None,
            priority=request.form.get("priority", "Normal"),
            assigned_to=current_user.id,
        )
        db.session.add(new_task)
        db.session.commit()
        flash("✅ Task added successfully!", "success")
        return redirect(url_for("loan_officer.task"))
    tasks = Task.query.filter_by(assigned_to=current_user.id).order_by(Task.due_date.asc()).all()
    return render_template("loan_officer/task.html", tasks=tasks, title="Tasks", role="loan_officer")

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
    flash("🗑️ Task deleted.", "info")
    return redirect(url_for("loan_officer.task"))

@loan_officer_bp.route("/tasks/complete/<int:task_id>", methods=["POST"])
def task_complete(task_id):
    task = Task.query.get(task_id)
    task.status = "Completed"
    db.session.commit()
    return redirect("/officer/tasks")

@loan_officer_bp.route("/tasks/new", methods=["GET", "POST"])
def new_task():
    borrowers = BorrowerProfile.query.all()
    loans = LoanApplication.query.all()

    if request.method == "POST":
        task = Task(
            title=request.form.get("title"),
            description=request.form.get("description"),
            assigned_to=current_user.id,
            borrower_id=request.form.get("borrower_id"),
            loan_id=request.form.get("loan_id"),
            due_date=request.form.get("due_date")
        )
        db.session.add(task)
        db.session.commit()

        return redirect(url_for("loan_officer.tasks_center"))

    return render_template("loan_officer/new_task.html", borrowers=borrowers, loans=loans)


@loan_officer_bp.route("/borrower-ai/<int:borrower_id>")
@role_required("loan_officer")
def borrower_ai_log(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)

    chats = BorrowerInteraction.query.filter_by(
        borrower_id=borrower.id,
        interaction_type="AI Chat"
    ).order_by(BorrowerInteraction.timestamp.desc()).all()

    return render_template("loan_officer/borrower_ai_log.html", borrower=borrower, chats=chats)

@loan_officer_bp.route("/credit-check", methods=["GET", "POST"])
@role_required("loan_officer")
def credit_check():
    borrowers = BorrowerProfile.query.all()
    credit_data = None

    if request.method == "POST":
        borrower_profile_id = request.form.get("borrower_profile_id")
        borrower = BorrowerProfile.query.get_or_404(borrower_profile_id)

        # 🔹 Replace this with your actual credit API integration
        credit_data = CreditProfile(
            borrower_profile_id=borrower.id,
            score=720,  # placeholder
            report_date=datetime.utcnow(),
            delinquencies=0,
            public_records=0,
            total_debt=5000
        )
        # If you want to persist:
        db.session.add(credit_data)
        db.session.commit()

    return render_template(
        "loan_officer/credit_check.html",
        borrowers=borrowers,
        credit_data=credit_data
    )

# ---------------------------------------------------------
# 📋 Loan Queue – View All Assigned Loans
# ---------------------------------------------------------
@loan_officer_bp.route("/loan_queue")
@role_required("loan_officer")
def loan_queue():
    """Display all loans assigned to the logged-in loan officer."""

    # Fetch loans where the current officer is assigned
    loans = (
        LoanApplication.query
        .filter_by(loan_officer_id=current_user.id)
        .order_by(LoanApplication.created_at.desc())
        .all()
    )

    # Basic counts for summary cards
    total_loans = len(loans)
    active_loans = len([l for l in loans if l.status.lower() in ["in_review", "submitted", "pending"]])
    approved_loans = len([l for l in loans if l.status.lower() in ["approved", "cleared"]])
    declined_loans = len([l for l in loans if l.status.lower() in ["declined", "denied"]])

    # AI Summary
    try:
        summary_prompt = (
            f"Summarize the current loan officer's queue activity:\n"
            f"- Total loans: {total_loans}\n"
            f"- Active: {active_loans}\n"
            f"- Approved: {approved_loans}\n"
            f"- Declined: {declined_loans}\n\n"
            "Provide a short operational insight with one suggestion for prioritization."
        )
        ai_summary = assistant.generate_reply(summary_prompt, "loan_officer")
    except Exception as e:
        print(f" AI summary error: {e}")
        ai_summary = "⚠️ Summary unavailable."

    return render_template(
        "loan_officer/loan_queue.html",
        loans=loans,
        total_loans=total_loans,
        active_loans=active_loans,
        approved_loans=approved_loans,
        declined_loans=declined_loans,
        ai_summary=ai_summary
    )

@loan_officer_bp.route("/crm-note/<int:lead_id>", methods=["GET", "POST"])
@role_required("loan_officer")
def crm_note(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    borrower = lead.borrower_profile
    form = CRMNoteForm()
    notes = CRMNote.query.filter_by(borrower_id=borrower.id).order_by(CRMNote.created_at.desc()).all()

    if form.validate_on_submit():
        note = CRMNote(
            borrower_id=borrower.id,
            author_id=current_user.id,
            content=form.content.data
        )
        db.session.add(note)
        db.session.commit()
        flash("Note saved.", "success")
        return redirect(url_for("loan_officer.crm_note", lead_id=lead_id))

    return render_template("loan_officer/crm_note.html", borrower=borrower, form=form, notes=notes)


# ===============================================================
#   AI ASSISTANT
# ===============================================================
@loan_officer_bp.route("/ai", methods=["POST"])
def ai():
    data = request.get_json()
    question = data.get("message")

    reply = ai_engine.ask(question, role="loan_officer")
    return jsonify({"reply": reply})

@loan_officer_bp.route("/ai/pricing", methods=["GET", "POST"])
def ai_pricing(): 
    if request.method == "GET":
        return "AI Pricing endpoint is POST-only. Use the UI button that sends JSON.", 200
    data = request.get_json()
    loan_id = data.get("loan_id")
    borrower_id = data.get("borrower_id")

    loan = LoanApplication.query.get(loan_id)
    borrower = BorrowerProfile.query.get(borrower_id)

    # credit
    credit = borrower.credit_reports[-1] if borrower.credit_reports else None
    score = credit.credit_score if credit else None

    # ratios
    ratios = calculate_dti_ltv(borrower, loan, credit)

    # Pack the pricing data for AI
    pricing_packet = f"""
    Loan Amount: {loan.amount}
    Property Value: {loan.property_value}
    Loan Type: {loan.loan_type}
    Credit Score: {score}
    Income: {borrower.income}
    Secondary Income: {getattr(borrower, "monthly_income_secondary", 0)}
    Total Monthly Income: {ratios['income_total']}
    Monthly Debts: {ratios['monthly_debts']}
    Front-End DTI: {ratios['front_end_dti']}
    Back-End DTI: {ratios['back_end_dti']}
    LTV: {ratios['ltv']}
    """

    # 📌 AI Signature Tone
    reply = master_ai.generate(
        f"""
        Provide a pricing recommendation for this borrower.

        Include:
        - Best program fit (Conventional, FHA, VA, DSCR, Bridge)
        - Estimated interest rate range
        - Max allowed LTV for program
        - Payment estimate
        - DTI + Risk flags
        - UW-level notes
        - List required conditions
        - Recommend next steps

        Data:
        {pricing_packet}
        """,
        role="loan_officer"
    )

   
    return jsonify({"reply": reply})

@loan_officer_bp.route("/ai/risk", methods=["GET", "POST"])
def ai_risk():

    # --- Handle GET requests safely ---
    if request.method == "GET":
        return jsonify({
            "status": "ready",
            "endpoint": "ai_risk",
            "message": "Send POST with JSON { loan_id } to evaluate loan risk."
        }), 200

    # --- Handle POST requests (real AI logic) ---
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

    # Credit report (safe)
    credit = borrower.credit_reports[-1] if borrower.credit_reports else None

    # Ratios (safe)
    ratios = calculate_dti_ltv(borrower, loan, credit)

    # Build packet
    packet = f"""
    Loan Amount: {loan.amount}
    Loan Type: {loan.loan_type}
    Property Value: {loan.property_value}
    LTV: {ratios['ltv']}

    DTI:
    Front-End: {ratios['front_end_dti']}
    Back-End: {ratios['back_end_dti']}

    Income: {borrower.income}
    Secondary Income: {getattr(borrower, "monthly_income_secondary", 0)}

    Credit Score: {credit.credit_score if credit else 'N/A'}
    Monthly Debts: {ratios['monthly_debts']}
    """

    # AI call
    reply = master_ai.generate(
        f"""
        Evaluate this loan's RISK.

        Provide:
        - Risk Category: Low / Moderate / High
        - Key Strengths
        - Key Weaknesses
        - DTI analysis
        - LTV analysis
        - Credit analysis
        - Loan Probability (funding likelihood)
        - Recommended program type
        - Required conditions
        - UW difficulty level (Easy / Moderate / Hard)

        Data:
        {packet}
        """,
        role="underwriter"
    )

    return jsonify({"reply": reply})

@loan_officer_bp.route("/ai/conditions", methods=["GET", "POST"])
def ai_conditions():

    # --- Handle GET requests safely ---
    if request.method == "GET":
        return jsonify({
            "status": "ready",
            "endpoint": "ai_conditions",
            "message": "Send POST with JSON { loan_id } to generate underwriting conditions."
        }), 200

    # --- Handle POST requests (real AI logic) ---
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

    credit = borrower.credit_reports[-1] if borrower.credit_reports else None
    ratios = calculate_dti_ltv(borrower, loan, credit)

    packet = f"""
    Loan Amount: {loan.amount}
    Loan Type: {loan.loan_type}
    Income: {borrower.income}
    Secondary Income: {getattr(borrower, "monthly_income_secondary", 0)}
    Credit Score: {credit.credit_score if credit else 'N/A'}
    LTV: {ratios['ltv']}
    DTI:
      FE: {ratios['front_end_dti']}
      BE: {ratios['back_end_dti']}
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
        - Property (appraisal, CO, lease, hazard)
        - Program-Specific (DSCR, FHA, VA, Bridge)
        - Final Approval Conditions

        Data:
        {packet}
        """,
        role="underwriter"
    )

    return jsonify({"reply": reply})

@loan_officer_bp.route("/intake-ai/<int:borrower_id>", methods=["GET", "POST"])
def intake_ai(borrower_id):

    borrower = BorrowerProfile.query.get_or_404(borrower_id)

    loan = LoanApplication.query.filter_by(
        borrower_profile_id=borrower.id
    ).order_by(LoanApplication.created_at.desc()).first()

    credit = borrower.credit_reports[-1] if getattr(borrower, "credit_reports", None) else None
    credit_score = credit.credit_score if credit else None
    credit_json = credit.credit_data if credit else {}

    ratios = calculate_dti_ltv(borrower, loan, credit)
    front = ratios["front_end_dti"]
    back = ratios["back_end_dti"]
    ltv = ratios["ltv"]

    missing_docs = [
        d.name for d in getattr(borrower, "document_requests", [])
        if d.status == "requested"
    ]

    # --- GET: Show intake page ---
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
        )

    # --- POST: AI question ---
    data = request.get_json() or {}
    user_message = data.get("message", "")

    underwriting_packet = f"""
Borrower: {borrower.full_name}
Email: {borrower.email}
Phone: {borrower.phone}

Income:
- Primary: {borrower.income}
- Secondary: {getattr(borrower, 'monthly_income_secondary', None)}
- Total Monthly Income: {ratios['income_total']}

Employment:
- Employer: {borrower.employer_name}
- Job Title: {getattr(borrower, 'job_title', None)}
- Years on Job: {getattr(borrower, 'years_at_job', None)}

Credit:
- Soft Credit Score: {credit_score}
- Monthly Debt Total: {ratios['monthly_debts']}
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
- Program Fit (FHA, Conv, DSCR, Non-QM, VA)
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
        AIIntakeSummary.query.order_by(AIIntakeSummary.created_at.desc())
        .limit(50)
        .all()
    )
    return render_template("loan_officer/ai_intake_queue.html", queue=queue)


# === Review View ===
@loan_officer_bp.route("/ai-intake-review/<int:intake_id>", methods=["GET", "POST"])
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
    )

@loan_officer_bp.route("/auto-create-loan/<int:borrower_id>", methods=["POST"])
def auto_create_loan(borrower_id):

    borrower = BorrowerProfile.query.get_or_404(borrower_id)

    data = request.get_json() or {}

    # AI may recommend defaults
    loan_amount = data.get("loan_amount", 0)
    loan_type = data.get("loan_type", borrower.loan_type)
    property_value = data.get("property_value", 0)
    property_address = data.get("property_address", None)

    # 1 — Create loan application
    loan = LoanApplication(
        borrower_profile_id=borrower.id,
        loan_type=loan_type,
        amount=loan_amount,
        property_value=property_value,
        property_address=property_address,
        status="Application Submitted"
    )

    db.session.add(loan)
    db.session.commit()

    # 2 — Auto fees
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

    # 3 — Loan Timeline Events
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
def followup_ai(borrower_id):

    borrower = BorrowerProfile.query.get_or_404(borrower_id)

    # Latest credit
    credit = borrower.credit_reports[-1] if borrower.credit_reports else None

    # Latest loan
    loan = LoanApplication.query.filter_by(
        borrower_profile_id=borrower.id
    ).order_by(LoanApplication.created_at.desc()).first()

    # Missing docs
    missing_docs = [
        d.name for d in getattr(borrower, "document_requests", [])
        if d.status == "requested"
    ]

    # Tasks
    tasks = FollowUpTask.query.filter_by(borrower_id=borrower.id).all()

    # Last contact
    last_contact = (
        borrower.last_contact_record[0].last_contact_at
        if getattr(borrower, "last_contact_record", None)
        else None
    )

    # Ratios
    ratios = calculate_dti_ltv(borrower, loan, credit)

    # --- GET: Safe response for button clicks ---
    if request.method == "GET":
        return jsonify({
            "status": "ready",
            "endpoint": "followup-ai",
            "message": "Send POST with JSON { message: '...' } to generate follow-up plan."
        }), 200

    # --- POST: Real AI follow-up logic ---
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
Front DTI: {ratios['front_end_dti']}
Back DTI: {ratios['back_end_dti']}
LTV: {ratios['ltv']}

Missing Documents:
{missing_docs}

Open Tasks:
{[t.title for t in tasks]}

Last Contact:
{last_contact}

User question:
{user_message}

Provide:
1. Urgency Level (High/Medium/Low)
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

    # Auto-create tasks
    created_tasks = extract_and_create_tasks(ai_reply, borrower, loan)

    return jsonify({
        "reply": ai_reply,
        "auto_tasks": created_tasks
    })
@loan_officer_bp.route("/communication-ai/<int:borrower_id>", methods=["GET", "POST"])
def communication_ai(borrower_id):

    borrower = BorrowerProfile.query.get_or_404(borrower_id)

    # Latest loan
    loan = LoanApplication.query.filter_by(
        borrower_profile_id=borrower.id
    ).order_by(LoanApplication.created_at.desc()).first()

    # Credit
    credit = borrower.credit_reports[-1] if borrower.credit_reports else None

    # Ratios
    ratios = calculate_dti_ltv(borrower, loan, credit)

    # --- GET: Safe response for button clicks ---
    if request.method == "GET":
        return jsonify({
            "status": "ready",
            "endpoint": "communication-ai",
            "message": "Send POST with JSON { message: '...' } to generate communication scripts."
        }), 200

    # --- POST: Real AI logic ---
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
Front DTI: {ratios['front_end_dti']}
Back DTI: {ratios['back_end_dti']}
LTV: {ratios['ltv']}

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

    # Auto-create tasks
    created_tasks = extract_and_create_tasks(ai_reply, borrower, loan)

    return jsonify({
        "reply": ai_reply,
        "auto_tasks": created_tasks
    })

@loan_officer_bp.route("/campaigns")
@role_required("loan_officer")
def campaigns():
    """Show active and archived campaigns for the loan officer."""
    active = (
        Campaign.query
        .filter(Campaign.status == "active")  # ✅ match the model’s status field
        .order_by(Campaign.created_at.desc())
        .all()
    )

    archived = (
        Campaign.query
        .filter(Campaign.status.in_(["completed", "paused", "draft"]))  # ✅ archived variants
        .order_by(Campaign.created_at.desc())
        .all()
    )

    return render_template(
        "loan_officer/campaign.html",
        active=active,
        archived=archived
    )

@loan_officer_bp.route("/call-center/<int:borrower_id>")
@role_required("loan_officer")
def call_center(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)

    # Latest credit report
    credit = borrower.credit_reports[-1] if borrower.credit_reports else None

    # Loan file
    loan = LoanApplication.query.filter_by(borrower_profile_id=borrower.id).first()

    return render_template(
        "loan_officer/call_center.html",
        borrower=borrower,
        loan=loan,
        credit=credit
    )

@loan_officer_bp.route("/save_call_notes", methods=["POST"])
@role_required("loan_officer")
def save_call_notes():
    data = request.get_json()

    borrower_id = data.get("borrower_id")
    transcript = data.get("transcript", "")
    summary = data.get("summary", "")
    tasks = data.get("tasks", [])
    missing_docs = data.get("missing_docs", [])

    borrower = BorrowerProfile.query.get_or_404(borrower_id)
    loan = LoanApplication.query.filter_by(borrower_profile_id=borrower_id).first()

    # 1) Save CRM Note
    note = BorrowerInteraction(
        borrower_id=borrower_id,
        interaction_type="Call Note",
        notes=summary or transcript
    )
    db.session.add(note)

    # 2) Create Tasks
    for t in tasks:
        task = Task(
            borrower_id=borrower_id,
            assigned_to=current_user.id,
            title=t,
            status="open"
        )
        db.session.add(task)

    # 3) Create Document Requests
    for doc in missing_docs:
        dr = DocumentRequest(
            borrower_id=borrower_id,
            loan_id=loan.id if loan else None,
            name=doc,
            status="requested"
        )
        db.session.add(dr)

    # 4) Create Loan Event
    if loan:
        event = LoanStatusEvent(
            loan_id=loan.id,
            event_name="Call Completed",
            description=f"AI auto-summarized call: {summary[:120]}..."
        )
        db.session.add(event)

    db.session.commit()

    return jsonify({"status": "success"})

@loan_officer_bp.route("/edit-loan/<int:loan_id>", methods=["GET", "POST"])
@role_required("loan_officer")
def edit_loan(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    form = LoanEditForm(obj=loan)

    if form.validate_on_submit():
        form.populate_obj(loan)
        db.session.commit()
        flash("Loan updated successfully.", "success")
        return redirect(url_for("loan_officer.loan_summary", loan_id=loan.id))

    return render_template("loan_officer/edit_loan.html", form=form, loan=loan)

@loan_officer_bp.route("/generate-quote/<int:loan_id>", methods=["GET", "POST"])
@role_required("loan_officer")
def generate_quote(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    form = GenerateQuoteForm()

    quote = None
    if form.validate_on_submit():
        principal = loan.loan_amount + (form.fees.data or 0)
        monthly_rate = float(form.rate.data) / 100 / 12
        months = form.term_months.data
        payment = principal * (monthly_rate * (1 + monthly_rate)**months) / ((1 + monthly_rate)**months - 1)

        quote = LoanQuote(
            loan_id=loan.id,
            rate=form.rate.data,
            term_months=months,
            fees=form.fees.data or 0,
            monthly_payment=round(payment, 2)
        )
        db.session.add(quote)
        db.session.commit()
        flash("Quote generated and saved.", "success")
        return redirect(url_for("loan_officer.quote_plan", loan_id=loan.id))

    return render_template("loan_officer/generate_quote.html", form=form, loan=loan, quote=quote)

@loan_officer_bp.route("/intake-review/<int:borrower_id>")
@role_required("loan_officer")
def intake_review(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)
    credit = borrower.credit_profile
    interactions = BorrowerInteraction.query.filter_by(borrower_id=borrower_id).order_by(BorrowerInteraction.timestamp.desc()).limit(10).all()
    ai_summary = AIIntakeSummary.query.filter_by(borrower_id=borrower_id).order_by(AIIntakeSummary.created_at.desc()).first()

    return render_template("loan_officer/intake_review.html", borrower=borrower, credit=credit, interactions=interactions, ai_summary=ai_summary)

@loan_officer_bp.route("/loan-summary/<int:loan_id>")
@role_required("loan_officer")
def loan_summary(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    borrower = loan.borrower
    quotes = LoanQuote.query.filter_by(loan_id=loan_id).order_by(LoanQuote.created_at.desc()).all()
    credit = borrower.credit_profile
    ai_summary = AIIntakeSummary.query.filter_by(borrower_id=borrower.id).order_by(AIIntakeSummary.created_at.desc()).first()

    return render_template("loan_officer/loan_summary.html", loan=loan, borrower=borrower, quotes=quotes, credit=credit, ai_summary=ai_summary)

@loan_officer_bp.route("/messages/<int:borrower_id>")
@role_required("loan_officer")
def messages(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)
    interactions = (
        BorrowerInteraction.query
        .filter_by(borrower_id=borrower_id)
        .order_by(BorrowerInteraction.timestamp.desc())
        .all()
    )
    uploads = Upload.query.filter_by(borrower_id=borrower_id).order_by(BorrowerUpload.uploaded_at.desc()).all()
    notes = CRMNote.query.filter_by(borrower_id=borrower_id).order_by(CRMNote.created_at.desc()).all()

    return render_template("loan_officer/messages.html", borrower=borrower, interactions=interactions, uploads=uploads, notes=notes)

@loan_officer_bp.route("/profile/<int:borrower_id>", methods=["GET", "POST"])
@role_required("loan_officer")
def profile(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)
    form = BorrowerProfileForm(obj=borrower)

    if form.validate_on_submit():
        form.populate_obj(borrower)
        db.session.commit()
        flash("Borrower profile updated.", "success")
        return redirect(url_for("loan_officer.intake_review", borrower_id=borrower.id))

    return render_template("loan_officer/profile.html", form=form, borrower=borrower)

@loan_officer_bp.route("/quote-plan/<int:loan_id>", methods=["GET", "POST"])
@role_required("loan_officer")
def quote_plan(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    form = QuotePlanForm()
    plan = QuotePlan.query.filter_by(loan_id=loan_id).order_by(QuotePlan.created_at.desc()).first()
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

    return render_template("loan_officer/quote_plan.html", loan=loan, form=form, plan=plan, options=options)
# =========================================================
# 💬 QUOTES VIEW BY BORROWER
# =========================================================
@loan_officer_bp.route("/quotes/<int:borrower_id>")
@role_required("loan_officer")
def quotes(borrower_id):
    from LoanMVP.models.loan_models import LoanApplication, LoanQuote, BorrowerProfile

    borrower = BorrowerProfile.query.get_or_404(borrower_id)
    loans = LoanApplication.query.filter_by(borrower_profile_id=borrower.id).all()
    quotes_by_loan = {
        loan_application.id: LoanQuote.query.filter_by(loan_application_id=loan_application.id)
        .order_by(LoanQuote.created_at.desc())
        .all()
        for loan in loans
    }

    return render_template(
        "loan_officer/quotes.html",
        borrower=borrower,
        loans=loans,
        quotes_by_loan=quotes_by_loan,
    )


# =========================================================
# ➕ NEW LOAN CREATION
# =========================================================

@loan_officer_bp.route("/loan/new", methods=["GET", "POST"])
@role_required("loan_officer")
def new_loan():
    """Create a new loan entry."""
    from LoanMVP.models.loan_models import LoanApplication, BorrowerProfile

    borrowers = BorrowerProfile.query.order_by(BorrowerProfile.full_name).all()

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
            )
            db.session.add(loan)
            db.session.commit()
            flash(f"Loan #{loan.id} created successfully.", "success")
            return redirect(url_for("loan_officer.loan_queue"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating loan: {e}", "danger")

    return render_template("loan_officer/new_loan.html", borrowers=borrowers)

@loan_officer_bp.route("/loan/<int:loan_id>")
@role_required("loan_officer")
def view_loan(loan_id):
    """Display a detailed loan page with borrower info, documents, and AI summary."""
    from LoanMVP.models.loan_models import LoanApplication, LoanQuote, BorrowerProfile
    from LoanMVP.models.document_models import LoanDocument

    loan = LoanApplication.query.get_or_404(loan_id)
    borrower = BorrowerProfile.query.get(loan.borrower_profile_id)

    # 📄 Fetch related docs and quotes if available
    documents = LoanDocument.query.filter_by(loan_id=loan.id).all() if hasattr(LoanDocument, "loan_id") else []
    quotes = LoanQuote.query.filter_by(loan_id=loan.id).all() if hasattr(LoanQuote, "loan_id") else []

    #  Placeholder for uploads if not linked to docs yet
    uploads_by_loan = {loan.id: [doc for doc in documents if getattr(doc, "status", "").lower() != "archived"]}

    # 🧠 AI summary auto-generation fallback
    if not getattr(loan, "ai_summary", None):
        try:
            loan.ai_summary = assistant.generate_reply(
                f"Summarize loan details for {borrower.full_name if borrower else 'Unknown Borrower'}: "
                f"{loan.loan_type} loan, ${loan.amount:,.0f} amount, property value ${loan.property_value or 0:,.0f}, "
                f"{loan.rate}% rate, {loan.term_months}-month term, status {loan.status}.",
                "loan_detail_summary"
            )
            db.session.commit()
        except Exception as e:
            print(" AI summary unavailable:", e)

    return render_template(
        "loan_officer/view_loan.html",
        loan=loan,
        borrower=borrower,
        documents=documents,
        quotes=quotes,
        uploads_by_loan=uploads_by_loan,
        title=f"Loan • {loan.loan_type or 'Details'}"
    )

@loan_officer_bp.route("/upload/<int:borrower_id>", methods=["GET", "POST"])
@role_required("loan_officer")
def upload(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)
    loans = LoanApplication.query.filter_by(borrower_profile_id=borrower_id).all()
    uploads = Upload.query.filter_by(borrower_profile_id=borrower_id).order_by(Upload.uploaded_at.desc()).all()
    requested_docs = RequestedDocument.query.join(LoanApplication).filter(LoanApplication.borrower_profile_id == borrower_id).all()

    form = UploadForm()
    form.loan_id.choices = [(loan.id, f"Loan #{loan.id} - {loan.loan_type}") for loan in loans]

    if form.validate_on_submit():
        file = request.files["file"]
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        upload = Upload(
            borrower_profile_id=borrower_id,
            loan_id=form.loan_id.data or None,
            filename=filename,
            description=form.description.data
        )
        db.session.add(upload)
        db.session.commit()
        flash("File uploaded successfully.", "success")
        return redirect(url_for("loan_officer.upload", borrower_id=borrower_id))

    return render_template("loan_officer/upload.html", borrower=borrower, form=form, uploads=uploads, requested_docs=requested_docs)

@loan_officer_bp.route("/follow-up/<int:borrower_id>", methods=["GET", "POST"])
@role_required("loan_officer")
def follow_up(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)
    form = FollowUpForm()
    items = FollowUpItem.query.filter_by(borrower_profile_id=borrower_id).order_by(FollowUpItem.created_at.desc()).all()

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

    return render_template("loan_officer/follow_up.html", borrower=borrower, form=form, items=items)

@loan_officer_bp.route("/timeline/<int:borrower_id>")
@role_required("loan_officer")
def timeline(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)

    interactions = BorrowerInteraction.query.filter_by(borrower_id=borrower_id).all()
    uploads = Upload.query.filter_by(borrower_profile_id=borrower_id).all()
    notes = CRMNote.query.filter_by(borrower_id=borrower_id).all()
    followups = FollowUpItem.query.filter_by(borrower_id=borrower_id).all()
    ai_summaries = AIIntakeSummary.query.filter_by(borrower_id=borrower_id).all()

    events = []

    for i in interactions:
        events.append({
            "type": "interaction",
            "timestamp": i.timestamp,
            "label": "AI Chat",
            "detail": f"Q: {i.question}<br>A: {i.answer}"
        })

    for u in uploads:
        events.append({
            "type": "upload",
            "timestamp": u.uploaded_at,
            "label": "Upload",
            "detail": f"{u.filename} ({u.description})"
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
            "timestamp": f.completed_at if f.is_done else f.created_at,
            "label": "Follow-Up",
            "detail": f.description + (" ✅ Completed" if f.is_done else "")
        })

    for a in ai_summaries:
        events.append({
            "type": "ai_summary",
            "timestamp": a.created_at,
            "label": "AI Intake Summary",
            "detail": a.summary[:300] + "..."  # truncate for display
        })

    events.sort(key=lambda e: e["timestamp"], reverse=True)

    return render_template("loan_officer/timeline.html", borrower=borrower, events=events)
# ===============================================================
#   BORROWERS
# ===============================================================
@loan_officer_bp.route("/borrowers")
@role_required("loan_officer")
def borrowers():

    q = request.args.get("q", "").strip()

    # Base query
    qry = BorrowerProfile.query

    # Search
    if q:
        qry = qry.filter(
            BorrowerProfile.full_name.ilike(f"%{q}%") |
            BorrowerProfile.email.ilike(f"%{q}%")
        )

    borrowers = qry.order_by(BorrowerProfile.created_at.desc()).all()

    # Add computed fields (1003 started, last activity, loan)
    for b in borrowers:
        b.has_loan = len(b.loans) > 0
        b.has_started_1003 = any(l.amount for l in b.loans)

        # find last interaction
        last = BorrowerInteraction.query.filter_by(borrower_id=b.id).order_by(
            BorrowerInteraction.timestamp.desc()
        ).first()

        b.last_activity = last.timestamp.strftime("%b %d, %Y") if last else None

    return render_template("loan_officer/borrowers.html", borrowers=borrowers)

@loan_officer_bp.route("/borrower/<int:borrower_id>")
@role_required("loan_officer")
def view_borrower(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)

    # All loans attached to this borrower
    loans = LoanApplication.query.filter_by(borrower_profile_id=borrower_id).all()

    # Soft credit report (latest)
    credit = borrower.credit_reports[-1] if hasattr(borrower, "credit_reports") and borrower.credit_reports else None

    # Borrower tasks
    tasks = Task.query.filter_by(borrower_id=borrower_id).order_by(Task.due_date).all()

    # Borrower documents
    documents = LoanDocument.query.filter_by(borrower_profile_id=borrower_id).all()

    return render_template(
        "loan_officer/borrower_view.html",
        borrower=borrower,
        loans=loans,
        credit=credit,
        tasks=tasks,
        documents=documents
    )


@loan_officer_bp.route("/borrower/<int:borrower_id>")
@role_required("loan_officer")
def borrower_dashboard(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)
    loan = LoanApplication.query.filter_by(borrower_profile_id=borrower_id).all()
    uploads = Upload.query.filter_by(borrower_profile_id=borrower_id).all()
    quotes = LoanQuote.query.join(LoanApplication).filter(LoanApplication.borrower_profile_id == borrower_id).all()
    followups = FollowUpItem.query.filter_by(borrower_profile_id=borrower_id, is_done=False).all()
    ai_summary = AIIntakeSummary.query.filter_by(borrower_profile_id=borrower_id).order_by(AIIntakeSummary.created_at.desc()).first()

    return render_template("loan_officer/borrower_dashboard.html", borrower=borrower, loan=loan, uploads=uploads, quotes=quotes, followups=followups, ai_summary=ai_summary)

@loan_officer_bp.route("/borrower-search", methods=["GET", "POST"])
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
                if any(l.status == form.loan_status.data for l in b.loans)
            ]

        results = borrowers

    return render_template("loan_officer/borrower_search.html", form=form, results=results)

@loan_officer_bp.route("/borrower-intake", methods=["GET", "POST"])
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
            employment_status=form.employment_status.data
        )
        db.session.add(borrower)
        db.session.commit()

        # Optional: trigger AI summary
        summary = ai.summarize_borrower(f"""
        Name: {borrower.full_name}
        Email: {borrower.email}
        Income: {borrower.annual_income}
        Credit Score: {borrower.credit_score}
        Employment: {borrower.employment_status}
        """)

        db.session.add(AIIntakeSummary(borrower_id=borrower.id, summary=summary))
        db.session.commit()

        flash("Borrower created and AI summary generated.", "success")
        return redirect(url_for("loan_officer.borrower_dashboard", borrower_id=borrower.id))

    return render_template("loan_officer/borrower_intake.html", form=form)

@loan_officer_bp.route("/resources", methods=["GET", "POST"])
@role_required("loan_officer")
def resources():
    """AI-driven Resource Center for Loan Officers."""
    resources = [
        {"title": "Underwriting Guidelines", "link": "#"},
        {"title": "Marketing Templates", "link": "#"},
        {"title": "Compliance Checklist", "link": "#"},
        {"title": "Bridge Loan DSCR Worksheet", "link": "#"},
    ]

    ai_reply = None
    query = None

    if request.method == "POST":
        query = request.form.get("query")
        if query:
            ai_reply = assistant.generate_reply(
                f"Loan officer resource request: {query}. Provide a clear, professional response with bullet points or steps where useful.",
                "loan_officer"
            )

    return render_template(
        "loan_officer/resources.html",
        resources=resources,
        ai_reply=ai_reply,
        query=query,
    )


# Optional AJAX endpoint for live chat (if you want it)
@loan_officer_bp.route("/resources/chat", methods=["POST"])
@role_required("loan_officer")
def resources_chat():
    """AJAX endpoint for real-time AI chat."""
    data = request.get_json()
    query = data.get("query", "")
    reply = assistant.generate_reply(
        f"Loan officer resource inquiry: {query}. Be concise, accurate, and instructional.",
        "loan_officer"
    )
    return jsonify({"reply": reply})

@loan_officer_bp.route("/campaigns/create", methods=["GET", "POST"])
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
        flash("✅ Campaign created successfully.", "success")
        return redirect(url_for("loan_officer.campaigns"))

    return render_template("loan_officer/create_campaign.html")


@loan_officer_bp.route("/upload-call/<int:borrower_id>", methods=["POST"])
@role_required("loan_officer")
def upload_call(borrower_id):
    file = request.files.get("file")

    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    filename = secure_filename(file.filename)
    saved_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(saved_path)

    # Whisper Transcription
    with open(saved_path, "rb") as audio:
        transcript_response = client.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=audio
        )

    transcript_text = transcript_response.text

    # Detect sentiment + missing docs
    sentiment = analyze_sentiment(transcript_text)
    docs = detect_documents(transcript_text)

    borrower = BorrowerProfile.query.get_or_404(borrower_id)
    loan = LoanApplication.query.filter_by(borrower_profile_id=borrower_id).first()

    # AI — Full Call Summary
    ai_summary = master_ai.generate(f"""
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
""", role="loan_officer")

    # Extract tasks and docs from AI summary
    tasks = extract_tasks(ai_summary)
    auto_docs = detect_documents(ai_summary)

    # Save call note
    note = BorrowerInteraction(
        borrower_id=borrower.id,
        interaction_type="Call Recording",
        notes=ai_summary
    )
    db.session.add(note)

    # Create tasks
    for t in tasks:
        task = Task(
            borrower_id=borrower.id,
            assigned_to=current_user.id,
            title=t,
            status="open"
        )
        db.session.add(task)

    # Create doc requests
    for doc in auto_docs:
        dr = DocumentRequest(
            borrower_id=borrower.id,
            loan_id=loan.id,
            name=doc,
            status="requested"
        )
        db.session.add(dr)

    # Loan Event
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
    credit = borrower.credit_reports[-1] if borrower.credit_reports else None

    # Values
    loan_amount = float(loan.amount or 0)
    property_value = float(loan.property_value or 0)
    credit_score = credit.credit_score if credit else 680

    ltv = loan_amount / property_value if property_value else None

    est_rate = estimate_rate(credit_score, ltv, loan.loan_type.lower())
    est_payment = calc_payment(loan_amount, est_rate, term=30)

    dscr = None
    if loan.loan_type.lower() == "dscr":
        dscr = calc_dscr(loan.monthly_rent or 0, est_payment)

    # AI Pricing Summary
    pricing_summary = master_ai.generate(f"""
Loan Type: {loan.loan_type}
Loan Amount: {loan.amount}
Property Value: {loan.property_value}
Credit Score: {credit_score}
LTV: {ltv:.2f if ltv else 'N/A'}
Estimated Rate: {est_rate}
Estimated Payment: {est_payment}
DSCR: {dscr}

Generate a luxury-finance explanation with:
- Program eligibility
- Risk factors
- Score impact
- DSCR commentary (if DSCR loan)
- Next steps for borrower
""", role="loan_officer")

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
    loan = LoanApplication.query.filter_by(
        borrower_profile_id=borrower.id
    ).first()

    credit = borrower.credit_reports[-1] if borrower.credit_reports else None

    engine = PreapprovalEngine(borrower, loan, credit)

    front_dti, back_dti = engine.calc_dti()
    ltv = engine.calc_ltv()
    fits = engine.program_fit()
    flags = engine.red_flags()
    conds = engine.required_conditions()

    # ------------------------------------------------------
    # AI Summary
    # ------------------------------------------------------
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
- Red flags (softened professional tone)
- Conditions needed
- Clear next steps
""",
        role="underwriter"
    )

    # ------------------------------------------------------
    # Tracking Event
    # ------------------------------------------------------
    track_event(
        loan_id=loan.id,
        borrower_id=borrower.id,
        document_name="Pre-Approval Letter",
        event_type="emailed"
    )

    # ------------------------------------------------------
    # JSON Response
    # ------------------------------------------------------
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
    # -----------------------------------------
    # 1) Load loan + borrower + credit
    # -----------------------------------------
    loan = LoanApplication.query.get_or_404(loan_id)
    borrower = loan.borrower_profile
    credit = borrower.credit_reports[-1] if borrower.credit_reports else None

    # -----------------------------------------
    # 2) Calculate ratios (DTI + LTV)
    # -----------------------------------------
    engine = PreapprovalEngine(borrower, loan, credit)
    front_dti, back_dti = engine.calc_dti()
    ltv = engine.calc_ltv()

    # -----------------------------------------
    # 3) Payment breakdown
    # -----------------------------------------
    p_and_i = calculate_monthly_payment(
        loan_amount=loan.amount,
        annual_rate=loan.rate or 6.99,       # fallback rate
        term_months=loan.term_months or 360  # fallback 30-yr
    )

    taxes = calculate_taxes(loan.property_value)
    insurance = calculate_insurance(loan.property_value)
    pmi = calculate_mortgage_insurance(loan.amount, loan.property_value)

    total_payment = p_and_i + taxes + insurance + (pmi or 0)

    # -----------------------------------------
    # 4) AI Summary (luxury pre-approval narrative)
    # -----------------------------------------
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
- Red flags (softened professional tone)
- Conditions needed
- Clear next steps
""",
        role="underwriter",
    )

    # -----------------------------------------
    # 5) Generate PDF using shared utility
    # -----------------------------------------
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

    # -----------------------------------------
    # 6) Save LoanDocument record
    # -----------------------------------------
    doc = LoanDocument(
        loan_id=loan.id,
        borrower_profile_id=borrower.id,
        document_name="Pre-Approval Letter",
        file_path=pdf_path,
        document_type="Preapproval",
        status="sent",
    )
    db.session.add(doc)
    db.session.commit()

    # -----------------------------------------
    # 7) Email to borrower
    # -----------------------------------------
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
@role_required("loan_officer")
def ai_chat():
    data = request.get_json()
    message = data.get("message", "")
    borrower_id = data.get("borrower_id")
    loan_id = data.get("loan_id")
    parent_id = data.get("parent_id")

    # Build context packet
    context = ""

    if borrower_id:
        borrower = BorrowerProfile.query.get(borrower_id)
        context += f"Borrower: {borrower.full_name}, Email: {borrower.email}, Phone: {borrower.phone}\n"

    if loan_id:
        loan = LoanApplication.query.get(loan_id)
        context += f"Loan: {loan.loan_type}, Amount: {loan.amount}, Status: {loan.status}\n"

    # AI call
    reply = master_ai.generate(
        f"Context:\n{context}\n\nUser Message:\n{message}",
        role="loan_officer"
    )

    # Save chat
    chat = AIAssistantInteraction(
        user_id=current_user.id,
        loan_officer_id=current_user.id,
        borrower_profile_id=borrower_id,
        loan_id=loan_id,
        parent_id=parent_id,
        question=message,
        response=reply,
        context_tag="loan_officer_chat"
    )
    db.session.add(chat)
    db.session.commit()

    return jsonify({"reply": reply, "chat_id": chat.id})

@loan_officer_bp.route("/ai_chat/history")
@role_required("loan_officer")
def ai_chat_history():
    borrower_id = request.args.get("borrower_id")
    loan_id = request.args.get("loan_id")

    q = AIAssistantInteraction.query.filter_by(
        loan_officer_id=current_user.id
    )

    if borrower_id:
        q = q.filter_by(borrower_profile_id=borrower_id)

    if loan_id:
        q = q.filter_by(loan_id=loan_id)

    history = q.order_by(AIAssistantInteraction.timestamp.asc()).all()

    return render_template(
        "loan_officer/ai_chat.html",
        history=history,
        borrower_id=borrower_id,
        loan_id=loan_id
    )

@loan_officer_bp.route("/loan/<int:loan_id>/scenarios", methods=["GET", "POST"])
@role_required("loan_officer")
def loan_scenarios(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)

    # Empty list for GET request
    scenarios = []

    if request.method == "POST":

        # -------------------------------------------------------
        # Gather form data
        # -------------------------------------------------------
        titles = request.form.getlist("title")
        amounts = request.form.getlist("loan_amount")
        rates = request.form.getlist("rate")
        terms = request.form.getlist("term")

        # -------------------------------------------------------
        # Build scenario objects
        # -------------------------------------------------------
        for i in range(len(titles)):
            sc = LoanScenario(
                title=titles[i],
                loan_amount=float(amounts[i]),
                rate=float(rates[i]),
                term=int(terms[i]),
                property_value=loan.property_value
            )
            scenarios.append(sc)

        # -------------------------------------------------------
        # AI Scenario Comparison
        # -------------------------------------------------------
        ai_summary = master_ai.generate(
            f"""
Compare these mortgage scenarios:

Scenario 1:
{scenarios[0].to_dict()}

Scenario 2:
{scenarios[1].to_dict()}

Scenario 3:
{scenarios[2].to_dict()}

Provide:
- Best program choice
- Payment sensitivity analysis
- Risk differences
- Which borrower profile each fits
- Scenario ranking (Best → Good → Avoid)
- Final recommendation
""",
            role="loan_officer"
        )

        return render_template(
            "loan_officer/scenarios_compare.html",
            loan=loan,
            scenarios=scenarios,
            ai_summary=ai_summary
        )

    # -------------------------------------------------------
    # GET request → Show input form
    # -------------------------------------------------------
    return render_template(
        "loan_officer/scenarios_form.html",
        loan=loan
    )

@loan_officer_bp.route("/loan/<int:loan_id>/scenario/add", methods=["POST"])
@role_required("loan_officer")
def add_scenario(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)

    s = LoanScenario(
        loan_id=loan.id,
        title=request.form.get("title"),
        amount=request.form.get("amount"),
        rate=request.form.get("rate"),
        term_months=request.form.get("term_months"),
        loan_type=request.form.get("loan_type"),
        down_payment=request.form.get("down_payment"),
        closing_costs=request.form.get("closing_costs"),
        monthly_payment=request.form.get("monthly_payment"),
        dti=request.form.get("dti"),
        ltv=request.form.get("ltv"),
        apr=request.form.get("apr")
    )

    db.session.add(s)
    db.session.commit()

    flash("Scenario saved.", "success")
    return redirect(url_for("loan_officer.loan_file", loan_id=loan.id))

@loan_officer_bp.route("/loan/<int:loan_id>/scenario/<int:id>/delete", methods=["POST"])
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

    # --------------------------------------------------
    # Generate the PDF via your fill_1003_pdf function
    # --------------------------------------------------
    pdf_path = fill_1003_pdf(borrower, loan)

    # --------------------------------------------------
    # Save document record
    # --------------------------------------------------
    doc = LoanDocument(
        borrower_profile_id=borrower.id,
        loan_id=loan.id,
        document_name="1003 Loan Application",
        file_path=pdf_path,
        status="generated"
    )
    db.session.add(doc)
    db.session.commit()

    # --------------------------------------------------
    # Return the PDF to download
    # --------------------------------------------------
    return send_file(pdf_path, as_attachment=True)

@loan_officer_bp.route("/borrower/<int:borrower_id>/request-docs", methods=["GET", "POST"])
@role_required("loan_officer")
def request_documents(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)

    if request.method == "POST":
        # Create a new DocumentRequest record
        doc_request = DocumentRequest(
            borrower_id=borrower.id,
            officer_id=current_user.id,
            status="Pending",
            requested_at=datetime.utcnow(),
            notes=request.form.get("notes")
        )
        db.session.add(doc_request)
        db.session.commit()

        flash("📄 Document request sent successfully!", "success")
        return redirect(url_for("loan_officer.view_borrower", borrower_id=borrower.id))

    return render_template(
        "loan_officer/request_docs.html",
        borrower=borrower
    )

@loan_officer_bp.route("/loan/<int:loan_id>/generate_needs", methods=["POST"])
@role_required("loan_officer")
def generate_doc_needs(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    borrower = loan.borrower_profile
    credit = borrower.credit_reports[-1] if borrower.credit_reports else None

    # FIX: call the AI engine, not the route
    needs = generate_needs(borrower, loan, credit)

    flash(f"{len(needs)} document needs generated.", "success")
    return redirect(url_for("loan_officer.loan_file", loan_id=loan_id))

@loan_officer_bp.route("/save_preapproval_snapshot/<int:loan_id>", methods=["POST"])
@role_required("loan_officer")
def save_preapproval_snapshot(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    borrower = loan.borrower

    engine = PreapprovalEngine(borrower, loan, borrower.credit_reports[-1] if borrower.credit_reports else None)

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
