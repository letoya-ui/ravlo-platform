# LoanMVP/routes/borrower.py

import os
import base64
import uuid
import requests
import json
from datetime import datetime
from io import BytesIO
from PIL import Image

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    send_file,
    send_from_directory,
    current_app,
    session,
)
from flask_login import current_user
from werkzeug.utils import secure_filename
from werkzeug.datastructures import ImmutableMultiDict
from sqlalchemy.exc import SQLAlchemyError

from LoanMVP.extensions import db, stripe
from LoanMVP.utils.decorators import role_required

# --- Models ---
from LoanMVP.models.activity_models import BorrowerActivity
from LoanMVP.models.loan_models import LoanApplication, BorrowerProfile, LoanQuote
from LoanMVP.models.document_models import LoanDocument, DocumentRequest, ESignedDocument, ResourceDocument
from LoanMVP.models.crm_models import Message, Partner
from LoanMVP.models.payment_models import PaymentRecord
from LoanMVP.models.ai_models import AIAssistantInteraction
from LoanMVP.models.property import SavedProperty
from LoanMVP.models.underwriter_model import UnderwritingCondition
from LoanMVP.models.borrowers import PropertyAnalysis, ProjectBudget, SubscriptionPlan, ProjectExpense, BorrowerMessage, BorrowerInteraction, Deal, DealShare
from LoanMVP.models.loan_officer_model import LoanOfficerProfile
from LoanMVP.models.renovation_models import RenovationMockup
from LoanMVP.models.partner_models import PartnerConnectionRequest


# --- AI / Assistant ---
from LoanMVP.ai.master_ai import master_ai
from LoanMVP.ai.base_ai import AIAssistant

# --- Services ---
from LoanMVP.services.progress_engine import calculate_progress
from LoanMVP.services.market_service import get_market_snapshot
from LoanMVP.services.comps_service import get_saved_property_comps, build_comps
from LoanMVP.services.rehab_service import (
    estimate_rehab_cost,
    optimize_rehab_to_budget,
    optimize_rehab_for_roi,
    optimize_rehab_for_timeline,
    optimize_rehab_for_arv,
    generate_rehab_risk_flags,
    estimate_rehab_timeline,
    estimate_material_costs,
    generate_rehab_notes,
)
from LoanMVP.services.ai_insights import generate_ai_insights
from LoanMVP.services.property_intel_service import (
    unified_property_resolver,
    generate_property_ai_summary,
    get_property_comps,
)
from LoanMVP.services.notification_service import notify_team_on_conversion
from LoanMVP.services.deal_export_service import (
    generate_cashflow_chart,
    generate_roi_vs_rehab_chart,
    generate_amortization_chart,
)
from LoanMVP.services.unified_resolver import resolve_property_unified
from LoanMVP.services.property_tool import search_deals_for_zip
from LoanMVP.services.ai_image_service import generate_renovation_images
from LoanMVP.services.openai_client import get_openai_client

from LoanMVP.forms import BorrowerProfileForm
from openai import OpenAI


borrower_bp = Blueprint("borrower", __name__, url_prefix="/borrower")

# ============================
# TIMELINE STRUCTURE
# ============================
BORROWER_TIMELINE = [
    {"step": 1, "title": "Application Submitted", "key": "application_submitted"},
    {"step": 2, "title": "Documents Uploaded", "key": "documents_uploaded"},
    {"step": 3, "title": "Processing Review", "key": "processing_review"},
    {"step": 4, "title": "Underwriting", "key": "underwriting"},
    {"step": 5, "title": "Conditions Issued", "key": "conditions_issued"},
    {"step": 6, "title": "Conditions Cleared", "key": "conditions_cleared"},
    {"step": 7, "title": "Final Approval", "key": "final_approval"},
    {"step": 8, "title": "Closing Scheduled", "key": "closing_scheduled"},
    {"step": 9, "title": "Loan Closed", "key": "loan_closed"},
]

# =========================================================
# 🔧 Helpers
# =========================================================

def _openai_client():
    key = (os.getenv("OPENAI_API_KEY") or "").strip()  # ✅ IMPORTANT
    return OpenAI(api_key=key)

def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@borrower_bp.app_template_filter("comma")
def comma_filter(value):
    try:
        return f"{value:,}"
    except Exception:
        return value

def _safe_json_loads(s, default=None):
    """
    Safely parse JSON from a string.
    Returns default if invalid or empty.
    """
    if default is None:
        default = {}
    if not s:
        return default
    try:
        return json.loads(s)
    except Exception:
        return default
def _safe_int(val, default=1, min_v=1, max_v=4):
    try:
        n = int(val)
        return max(min_v, min(max_v, n))
    except Exception:
        return default

def _download_image_bytes(url: str, timeout=15) -> bytes:
    # basic allowlist could be added later (S3/CDN only), but MVP is fine
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.content

def _to_png_bytes(img_bytes: bytes, max_size=1024) -> bytes:
    im = Image.open(BytesIO(img_bytes)).convert("RGB")
    im.thumbnail((max_size, max_size))
    out = BytesIO()
    im.save(out, format="PNG", optimize=True)
    return out.getvalue()

def _save_to_static(png_bytes: bytes, subdir="visualizer") -> str:
    # Save to /static/uploads/visualizer/<uuid>.png
    static_dir = current_app.static_folder  # e.g. .../LoanMVP/static
    upload_dir = os.path.join(static_dir, "uploads", subdir)
    os.makedirs(upload_dir, exist_ok=True)

    filename = f"{uuid.uuid4().hex}.png"
    path = os.path.join(upload_dir, filename)
    with open(path, "wb") as f:
        f.write(png_bytes)

    # Return a public URL
    return f"/static/uploads/{subdir}/{filename}"
    
# =========================================================
# 🏠 Borrower Dashboard
# =========================================================
@borrower_bp.route("/dashboard")
@role_required("borrower")
def dashboard():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()

    # --- Always-safe defaults ---
    loans = []
    loan = None
    conditions = []
    doc_requests = []
    timeline = []
    progress_data = []
    primary_stage = None

    saved_props = []
    if borrower:
        # Saved Properties
        saved_props = SavedProperty.query.filter_by(
            borrower_profile_id=borrower.id
        ).order_by(SavedProperty.created_at.desc()).all()

        # Active loans (for counts + hero chips)
        loans = LoanApplication.query.filter_by(
            borrower_profile_id=borrower.id
        ).order_by(LoanApplication.created_at.desc()).all()

        # Primary active loan
        loan = LoanApplication.query.filter_by(
            borrower_profile_id=borrower.id,
            is_active=True
        ).first()

        # Documents (if you store borrower_profile_id on LoanDocument)
        doc_requests = LoanDocument.query.filter_by(
            borrower_profile_id=borrower.id
        ).order_by(LoanDocument.created_at.desc()).all()

        # Conditions (if active loan exists)
        if loan:
            conditions = UnderwritingCondition.query.filter_by(
                borrower_profile_id=borrower.id,
                loan_id=loan.id
            ).order_by(UnderwritingCondition.created_at.desc()).all()

            primary_stage = getattr(loan, "status", None) or "Application"

    # --------------------------
    # Next Step AI
    # --------------------------
    assistant = AIAssistant()
    next_step_ai = None

    if borrower:
        if loan:
            pending_conditions = [
                c for c in conditions
                if (c.status or "").lower() not in ["submitted", "cleared", "completed"]
            ]
            if pending_conditions:
                next_step_text = (
                    f"The borrower has {len(pending_conditions)} pending conditions. "
                    f"The next required item is: {pending_conditions[0].description}."
                )
            else:
                next_step_text = "All conditions are completed. They are waiting on lender review."
        else:
            next_step_text = "No active loan. Prompt them to start a new loan application."

        try:
            next_step_ai = assistant.generate_reply(
                f"Create a friendly, borrower-facing next-step message: {next_step_text}",
                "borrower_next_step"
            )
        except Exception:
            next_step_ai = "Next step guidance is unavailable right now."

    # --------------------------
    # Snapshot + Progress
    # --------------------------
    progress_percent = 0
    progress_stage = "Not Started"
    if loan:
        total_conditions = len(conditions)
        cleared_conditions = len([c for c in conditions if (c.status or "").lower() == "cleared"])
        if total_conditions > 0:
            progress_percent = int((cleared_conditions / total_conditions) * 100)

        if progress_percent == 0:
            progress_stage = "Started"
        elif progress_percent < 100:
            progress_stage = "In Progress"
        else:
            progress_stage = "Completed"

    snapshot = {
        "loan_type": getattr(loan, "loan_type", None) if loan else None,
        "amount": getattr(loan, "amount", None) if loan else None,
        "status": getattr(loan, "status", None) if loan else None,
        "address": getattr(loan, "property_address", None) if loan else None,
        "progress_percent": progress_percent,
        "progress_stage": progress_stage,
    }

    # --------------------------
    # Checklist
    # --------------------------
    checklist_items = []
    if loan:
        pending = [c for c in conditions if (c.status or "").lower() not in ["cleared", "completed"]]
        if pending:
            for c in pending[:6]:
                checklist_items.append({"label": f"Upload: {c.description}", "done": False})
        else:
            checklist_items.append({"label": "All required documents submitted", "done": True})

        checklist_items.append({"label": f"Loan is {progress_percent}% complete", "done": progress_percent >= 100})
    else:
        checklist_items.append({"label": "Start your first loan", "done": False})

    # --------------------------
    # Tour / Welcome back
    # --------------------------
    show_dashboard_tour = bool(borrower and not getattr(borrower, "has_seen_dashboard_tour", False))
    dashboard_welcome_ai = None
    show_welcome_back = bool(borrower and getattr(borrower, "has_seen_dashboard_tour", False))
    welcome_back_ai = None

    if show_dashboard_tour:
        try:
            dashboard_welcome_ai = assistant.generate_reply(
                "Write a warm, friendly welcome message for a borrower seeing their dashboard for the first time.",
                "borrower_dashboard_welcome"
            )
        except Exception:
            dashboard_welcome_ai = "Welcome to your dashboard!"

    if show_welcome_back:
        try:
            welcome_back_ai = assistant.generate_reply(
                "Write a short, friendly welcome-back message for a borrower returning to their dashboard.",
                "borrower_welcome_back"
            )
        except Exception:
            welcome_back_ai = "Welcome back!"

    whats_new = [
        "AI-powered Next Step guidance",
        "Saved Properties list with Deal Workspace links",
        "Loan Snapshot + Progress",
        "Document and Conditions tables",
    ]

    # for your hero date
    now_str = datetime.now().strftime("%b %d, %Y • %I:%M %p")

    return render_template(
        "borrower/dashboard.html",
        borrower=borrower,
        loans=loans,
        loan=loan,
        conditions=conditions,
        doc_requests=doc_requests,
        saved_props=saved_props,     # ✅ use ONE name everywhere
        snapshot=snapshot,
        next_step_ai=next_step_ai,
        checklist_items=checklist_items,
        show_dashboard_tour=show_dashboard_tour,
        dashboard_welcome_ai=dashboard_welcome_ai,
        show_welcome_back=show_welcome_back,
        welcome_back_ai=welcome_back_ai,
        whats_new=whats_new,
        primary_stage=primary_stage,
        now_str=now_str,
        active_tab="dashboard",
        title="Dashboard"
    )

@borrower_bp.route("/dismiss_dashboard_tour", methods=["POST"])
@role_required("borrower")
def dismiss_dashboard_tour():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    borrower.has_seen_dashboard_tour = True
    db.session.commit()
    return jsonify({"status": "ok"})


@borrower_bp.route("/onboarding")
@role_required("borrower")
def onboarding():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()

    # If borrower already has an active loan, skip onboarding
    active_loan = LoanApplication.query.filter_by(
        borrower_profile_id=borrower.id,
        is_active=True
    ).first()

    if active_loan:
        return redirect(url_for("borrower.dashboard"))

    # AI welcome message
    assistant = AIAssistant()
    welcome_ai = assistant.generate_reply(
        "Write a warm, friendly welcome message for a borrower starting their onboarding.",
        "borrower_onboarding"
    )

    return render_template(
        "borrower/onboarding.html",
        borrower=borrower,
        welcome_ai=welcome_ai,
        title="Welcome",
        active_tab=None
    )

@borrower_bp.route("/onboarding/start_loan", methods=["GET", "POST"])
@role_required("borrower")
def onboarding_start_loan():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()

    if request.method == "POST":
        loan_type = request.form.get("loan_type")
        amount = request.form.get("amount")

        # Deactivate old loans
        LoanApplication.query.filter_by(
            borrower_profile_id=borrower.id
        ).update({"is_active": False})

        new_loan = LoanApplication(
            borrower_profile_id=borrower.id,
            loan_type=loan_type,
            amount=float(amount),
            is_active=True,
            status="Started"
        )
        db.session.add(new_loan)
        db.session.commit()

        return redirect(url_for("borrower.dashboard"))

    return render_template(
        "borrower/onboarding_start_loan.html",
        borrower=borrower,
        title="Start Loan",
        active_tab=None
    )

# =========================================================
# 🧾 Borrower Profile
# =========================================================

@borrower_bp.route("/create_profile", methods=["GET", "POST"])
@role_required("borrower")
def create_profile():
    form = BorrowerProfileForm()

    if form.validate_on_submit():
        borrower = BorrowerProfile(
            user_id=current_user.id,
            full_name=form.full_name.data,
            email=form.email.data,
            phone=form.phone.data,
            address=form.address.data,
            city=form.city.data,
            state=form.state.data,
            zip=form.zip_code.data,
            employment_status=form.employment_status.data,
            annual_income=form.annual_income.data,
            credit_score=form.credit_score.data,
            created_at=datetime.utcnow(),
        )
        db.session.add(borrower)
        db.session.commit()

        flash("✅ Profile created successfully!", "success")
        return redirect(url_for("borrower.dashboard"))

    return render_template(
        "borrower/create_profile.html",
        form=form,
        title="Create Profile"
    )


@borrower_bp.route("/update_profile", methods=["POST"])
@role_required("borrower")
def update_profile():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if not borrower:
        return jsonify({"status": "error", "message": "Profile not found."}), 404

    for field, value in request.form.items():
        if hasattr(borrower, field) and value.strip():
            setattr(borrower, field, value)
    borrower.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({"status": "success", "message": "Profile updated successfully."})


# =========================================================
# 📝 Loan Application
# =========================================================

@borrower_bp.route("/apply", methods=["GET", "POST"])
@role_required("borrower")
def apply():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()

    if not borrower:
        flash("Please create your profile before applying for a loan.", "warning")
        return redirect(url_for("borrower.create_profile"))

    if request.method == "POST":
        loan_type = request.form.get("loan_type")
        amount = safe_float(request.form.get("amount"))
        property_address = request.form.get("property_address")

        ai_summary = assistant.generate_reply(
            f"Create loan application summary for borrower {borrower.full_name} "
            f"applying for a {loan_type} loan at {property_address}.",
            "borrower_apply",
        )

        loan = LoanApplication(
            borrower_profile_id=borrower.id,
            loan_type=loan_type,
            loan_amount=amount,
            property_address=property_address,
            ai_summary=ai_summary,
            created_at=datetime.datetime.utcnow(),
            status="Submitted",
        )
        db.session.add(loan)
        db.session.commit()
        flash("✅ Loan application submitted successfully!", "success")
        return redirect(url_for("borrower.status"))

    return render_template(
        "borrower/apply.html",
        borrower=borrower,
        title="Apply for Loan",
    )


@borrower_bp.route("/status")
@role_required("borrower")
def status():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()

    if not borrower:
        flash("Please complete your borrower profile first.", "warning")
        return redirect(url_for("borrower.create_profile"))

    loans = LoanApplication.query.filter_by(borrower_profile_id=borrower.id).all()
    documents = LoanDocument.query.filter_by(borrower_profile_id=borrower.id).all()

    stats = {
        "total_loans": len(loans),
        "pending_docs": len(
            [d for d in documents if d.status and d.status.lower() in ["pending", "uploaded"]]
        ),
        "verified_docs": len(
            [d for d in documents if d.status and d.status.lower() == "verified"]
        ),
        "active_loans": len(
            [l for l in loans if l.status and l.status.lower() in ["active", "processing"]]
        ),
        "completed_loans": len(
            [l for l in loans if l.status and l.status.lower() in ["closed", "funded"]]
        ),
    }

    try:
        ai_summary = assistant.generate_reply(
            f"Summarize borrower loan status for {borrower.full_name} with {stats}",
            "borrower_status",
        )
    except Exception:
        ai_summary = "⚠️ AI summary unavailable."

    return render_template(
        "borrower/status.html",
        borrower=borrower,
        loans=loans,
        documents=documents,
        stats=stats,
        ai_summary=ai_summary,
        title="Loan Status",
    )

@borrower_bp.route("/loan_summary/<int:loan_id>")
@role_required("borrower")
def loan_summary(loan_id):
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    loan = LoanApplication.query.get_or_404(loan_id)
    property = PropertyAnalysis.query.get(loan.property_id)

    documents_count = LoanDocument.query.filter_by(
        borrower_profile_id=borrower.id
    ).count()

    conditions_count = UnderwritingCondition.query.filter_by(
        borrower_profile_id=borrower.id
    ).count()

    ai_summary = master_ai.ask(
        f"""
        Provide a clear, friendly summary of this borrower's loan:

        Loan Type: {loan.loan_type}
        Amount: {loan.loan_amount}
        Rate: {loan.interest_rate}
        Term: {loan.term_months} months
        LTV: {loan.ltv}
        LTC: {loan.ltc}
        DSCR: {loan.dscr}

        Property: {property.address}, ARV {property.after_repair_value}, As‑Is {property.as_is_value}

        Documents: {documents_count}
        Conditions: {conditions_count}
        Status: {loan.status}

        Explain what the borrower should expect next.
        """,
        role="loan_officer",
    )

    return render_template(
        "borrower/loan_summary.html",
        borrower=borrower,
        loan=loan,
        property=property,
        documents_count=documents_count,
        conditions_count=conditions_count,
        ai_summary=ai_summary,
        title="Loan Summary",
    )
@borrower_bp.route("/loan_timeline/<int:loan_id>")
@role_required("borrower")
def loan_timeline(loan_id):
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    loan = LoanApplication.query.get_or_404(loan_id)

    documents_count = LoanDocument.query.filter_by(
        borrower_profile_id=borrower.id
    ).count()

    conditions_count = UnderwritingCondition.query.filter_by(
        borrower_profile_id=borrower.id
    ).count()

    ai_summary = master_ai.ask(
        f"""
        Provide a friendly, simple explanation of this borrower's loan timeline:

        Loan Status: {loan.status}
        Documents Uploaded: {documents_count}
        Conditions Outstanding: {conditions_count}
        Application Date: {loan.created_at}

        Explain what the borrower should expect next.
        """,
        role="loan_officer",
    )

    return render_template(
        "borrower/loan_timeline.html",
        borrower=borrower,
        loan=loan,
        documents_count=documents_count,
        conditions_count=conditions_count,
        ai_summary=ai_summary,
        title="Loan Timeline",
    )

@borrower_bp.route("/loan")
@role_required("borrower")
def loan_center():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()

    if not borrower:
        flash("Please complete your profile before accessing the Loan Center.", "warning")
        return redirect(url_for("borrower.create_profile"))

    loans = LoanApplication.query.filter_by(borrower_profile_id=borrower.id).all()

    return render_template(
        "borrower/loan_center.html",
        borrower=borrower,
        loans=loans,
        title="Loan Center"
    )


# =========================================================
# 💎 Subscription Management
# =========================================================

@borrower_bp.route("/subscription", methods=["GET", "POST"])
@role_required("borrower")
def subscription():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()

    if request.method == "POST":
        plan = request.form.get("plan")
        borrower.subscription_plan = plan
        borrower.updated_at = datetime.datetime.utcnow()
        db.session.commit()
        flash(f"🎉 Subscription upgraded to {plan}!", "success")

    return render_template(
        "borrower/subscription.html",
        borrower=borrower,
        title="Subscription Plans",
    )


@borrower_bp.route("/upgrade")
@role_required("borrower")
def upgrade_plan():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    borrower.subscription_plan = "Premium"
    db.session.commit()
    flash("✨ Upgraded to Premium plan.", "success")
    return redirect(url_for("borrower.subscription"))


@borrower_bp.route("/downgrade")
@role_required("borrower")
def downgrade_plan():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    borrower.subscription_plan = "Basic"
    db.session.commit()
    flash("⚙️ Downgraded to Basic plan.", "info")
    return redirect(url_for("borrower.subscription"))


# =========================================================
# 📁 Documents & Requests
# =========================================================
@borrower_bp.route("/documents")
@role_required("borrower")
def documents():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()

    documents = (
        LoanDocument.query.filter_by(borrower_profile_id=borrower.id).all()
        if borrower else []
    )

    assistant = AIAssistant()
    ai_summary = assistant.generate_reply(
        f"Summarize the borrower’s {len(documents)} uploaded documents and highlight any missing or recommended items.",
        "borrower_documents"
    )

    return render_template(
        "borrower/documents.html",
        borrower=borrower,
        documents=documents,
        ai_summary=ai_summary,
        title="My Documents",
        active_tab="documents"
    )

@borrower_bp.route("/document_requests")
@role_required("borrower")
def document_requests():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()

    # 1. Regular document requests
    doc_requests = DocumentRequest.query.filter_by(
        borrower_id=borrower.id
    ).all()

    # 2. Underwriting conditions (loan-specific)
    conditions = UnderwritingCondition.query.filter_by(
        borrower_profile_id=borrower.id,
        loan_id=borrower.active_loan_id
    ).all()

    # 3. Merge into unified list
    unified = []

    # Document Requests
    for req in doc_requests:
        unified.append({
            "id": req.id,
            "type": "document",
            "document_name": req.document_name,
            "requested_by": req.requested_by,
            "notes": req.notes,
            "status": req.status,
            "file_path": req.file_path
        })

    # Conditions
    for cond in conditions:
        unified.append({
            "id": cond.id,
            "type": "condition",
            "document_name": cond.description,  # maps to table column
            "requested_by": cond.requested_by or "Processor",
            "notes": cond.notes if hasattr(cond, "notes") else None,
            "status": cond.status,
            "file_path": cond.file_path
        })

    # AI summary
    assistant = AIAssistant()
    ai_summary = assistant.generate_reply(
        f"List {len(unified)} outstanding document requests and conditions for borrower {borrower.full_name}.",
        "document_requests",
    )

    return render_template(
        "borrower/document_requests.html",
        borrower=borrower,
        requests=unified,
        ai_summary=ai_summary,
        title="Document Requests",
    )

@borrower_bp.route("/upload_document", methods=["GET", "POST"])
@role_required("borrower")
def upload_document():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()

    if request.method == "POST":
        file = request.files.get("file")
        doc_type = request.form.get("doc_type")

        if file:
            filename = secure_filename(file.filename)
            save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
            file.save(save_path)

            new_doc = LoanDocument(
                borrower_profile_id=borrower.id,
                file_path=filename,
                doc_type=doc_type,
                status="uploaded"
            )
            db.session.add(new_doc)
            db.session.commit()

            return redirect(url_for("borrower.documents"))

    return render_template(
        "borrower/upload_document.html",
        borrower=borrower,
        title="Upload Document",
        active_tab="documents"
    )

@borrower_bp.route("/upload_request", methods=["GET", "POST"])
@role_required("borrower")
def upload_request():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()

    item_id = request.args.get("item_id")
    item_type = request.args.get("type")  # "request" or "condition"

    if item_type == "request":
        item = DocumentRequest.query.get(item_id)
    else:
        item = UnderwritingCondition.query.get(item_id)

    if request.method == "POST":
        file = request.files.get("file")

        if file:
            filename = secure_filename(file.filename)
            save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
            file.save(save_path)

            # Save document
            new_doc = LoanDocument(
                borrower_profile_id=borrower.id,
                file_path=filename,
                doc_type=item.description,
                status="submitted",
                request_id=item.id if item_type == "request" else None,
                condition_id=item.id if item_type == "condition" else None
            )
            db.session.add(new_doc)

            # Mark request/condition as submitted
            item.status = "submitted"
            db.session.commit()

            return redirect(url_for("borrower.document_requests"))

    return render_template(
        "borrower/upload_request.html",
        borrower=borrower,
        item=item,
        item_type=item_type,
        title="Upload Document",
        active_tab="documents"
    )

@borrower_bp.route("/delete_document/<int:doc_id>", methods=["POST"])
@role_required("borrower")
def delete_document(doc_id):
    doc = LoanDocument.query.get_or_404(doc_id)

    try:
        os.remove(os.path.join(current_app.config["UPLOAD_FOLDER"], doc.file_path))
    except Exception:
        pass

    db.session.delete(doc)
    db.session.commit()

    return redirect(url_for("borrower.documents"))

# ============================
# COMMAND CENTER MAIN ROUTE
# ============================
@borrower_bp.route('/command-center')
@role_required("borrower")
def borrower_command_center():
    borrower = current_user

    # ============================
    # 1. ACTIVE LOAN
    # ============================
    loan = LoanApplication.query.filter_by(
        borrower_profile_id=borrower.id,
        is_active=True
    ).first()

    # ============================
    # 2. LOAN OFFICER & PROCESSOR
    # ============================
    loan_officer = None
    processor = None

    if loan:
        loan_officer = User.query.filter_by(id=loan.loan_officer_id).first()
        processor = User.query.filter_by(id=loan.processor_id).first()

    # ============================
    # 3. PARTNER DIRECTORY
    # ============================
    partners = Partner.query.filter_by(active=True).order_by(Partner.category.asc()).all()

    # ============================
    # 4. DOCUMENT LIBRARY
    # ============================
    documents = {}
    docs = ResourceDocument.query.filter_by(active=True).order_by(ResourceDocument.category.asc()).all()
    for doc in docs:
        documents.setdefault(doc.category, []).append({
            "title": doc.title,
            "file": doc.filename
        })

    # ============================
    # 5. FAQs
    # ============================
    faqs = [
        {"q": "What is a loan condition?", "a": "A condition is a requirement your lender needs before approving your loan."},
        {"q": "How do I upload documents?", "a": "Use the Upload Document button or visit the Documents page."},
        {"q": "How long does underwriting take?", "a": "Typically 24–72 hours depending on your file."},
    ]

    # ============================
    # 6. TIMELINE
    # ============================
    current_status = borrower.timeline_status
    timeline = []
    status_reached = True

    for item in BORROWER_TIMELINE:
        if status_reached:
            item_status = "completed"
        else:
            item_status = "upcoming"

        if item["key"] == current_status:
            item_status = "current"
            status_reached = False

        timeline.append({
            "step": item["step"],
            "title": item["title"],
            "status": item_status
        })

    # ============================
    # 7. RENDER TEMPLATE
    # ============================
    return render_template(
        'borrower/command_center.html',
        borrower=borrower,
        loan=loan,
        loan_officer=loan_officer,
        processor=processor,
        partners=partners,
        documents=documents,
        faqs=faqs,
        timeline=timeline
    )


# ============================
# AI SUPPORT ENDPOINT
# ============================
@borrower_bp.route('/command-center/ai-support', methods=['POST'])
@role_required("borrower")
def borrower_ai_support():
    data = request.get_json()
    question = data.get('question', '').strip()

    if not question:
        return jsonify({"error": "Please enter a question."}), 400

    borrower = current_user

    try:
        ai = CMAIEngine()

        next_step = next((i for i in BORROWER_TIMELINE if i["key"] == borrower.timeline_status), None)

        ai_reply = ai.generate_reply(
            user_question=question,
            role="Borrower Support",
            tone="calm, clear, supportive, premium",
            borrower=borrower,
            next_step=next_step
        )

        return jsonify({"answer": ai_reply})

    except Exception:
        return jsonify({"error": "AI support is temporarily unavailable."}), 500


# ============================
# SEARCH ENGINE
# ============================
@borrower_bp.route('/search')
@role_required("borrower")
def borrower_search():
    q = request.args.get('q', '').strip().lower()
    borrower = current_user

    results = []

    if not q:
        return render_template('borrower/search_results.html', query=q, results=[])

    # Uploaded Documents
    for doc in borrower.documents:
        if q in doc.filename.lower():
            results.append({
                "type": "Uploaded Document",
                "title": doc.filename,
                "link": f"/borrower/documents/view/{doc.id}"
            })

    # Conditions
    for cond in borrower.conditions:
        if q in cond.description.lower() or q in cond.status.lower():
            results.append({
                "type": "Condition",
                "title": cond.description,
                "status": cond.status,
                "link": "/borrower/conditions"
            })

    # Partners
    partners = Partner.query.filter_by(active=True).all()
    for p in partners:
        if q in p.name.lower() or q in p.category.lower():
            results.append({
                "type": "Partner",
                "title": p.name,
                "category": p.category,
                "link": "/borrower/command-center#partners"
            })

    # FAQs
    faq_list = [
        {"q": "What is a loan condition?", "a": "A condition is a requirement your lender needs before approving your loan."},
        {"q": "How do I upload documents?", "a": "Use the Upload Document button or visit the Documents page."},
        {"q": "How long does underwriting take?", "a": "Typically 24–72 hours depending on your file."},
    ]

    for item in faq_list:
        if q in item["q"].lower() or q in item["a"].lower():
            results.append({
                "type": "FAQ",
                "title": item["q"],
                "link": "/borrower/command-center#faq"
            })

    return render_template('borrower/search_results.html', query=q, results=results)


# ============================
# BORROWER → PARTNERS (FILTER/LIST/REQUEST)
# ============================

@borrower_bp.route("/partners/filter")
@role_required("borrower")
def filter_partners():
    category = (request.args.get("category") or "All").strip()

    q = Partner.query.filter_by(active=True, approved=True)

    if category and category.lower() != "all":
        q = q.filter_by(category=category)

    partners = q.order_by(Partner.name.asc()).all()

    return render_template(
        "borrower/partner_list.html",
        partners=partners,
        category=category
    )


@borrower_bp.route("/partners/requests")
@role_required("borrower")
def my_partner_requests():
    borrower_profile = BorrowerProfile.query.filter_by(user_id=current_user.id).first()

    reqs = PartnerConnectionRequest.query.filter_by(borrower_user_id=current_user.id) \
        .order_by(PartnerConnectionRequest.created_at.desc()).all()

    return render_template(
        "borrower/partner_requests.html",
        borrower=borrower_profile,
        requests=reqs
    )


@borrower_bp.route("/partners/request/<int:partner_id>", methods=["POST"])
@role_required("borrower")
def request_partner_connection(partner_id):
    partner = Partner.query.get_or_404(partner_id)

    if not partner.approved or not partner.active:
        return jsonify({"success": False, "message": "This partner is not available."}), 403

    payload = request.get_json(silent=True) or {}
    category = (request.form.get("category") or payload.get("category") or partner.category or "").strip() or None
    message = (request.form.get("message") or payload.get("message") or "").strip() or None
    property_id = request.form.get("property_id") or payload.get("property_id")
    lead_id = request.form.get("lead_id") or payload.get("lead_id")

    borrower_profile = BorrowerProfile.query.filter_by(user_id=current_user.id).first()

    # ✅ prevent duplicate pending requests
    existing = PartnerConnectionRequest.query.filter_by(
        borrower_user_id=current_user.id,
        partner_id=partner.id,
        status="pending"
    ).first()
    if existing:
        return jsonify({"success": True, "message": "You already have a pending request."})

    req = PartnerConnectionRequest(
        borrower_user_id=current_user.id,
        borrower_profile_id=borrower_profile.id if borrower_profile else None,
        partner_id=partner.id,
        property_id=int(property_id) if property_id else None,
        lead_id=int(lead_id) if lead_id else None,
        category=category,
        message=message
    )

    db.session.add(req)
    db.session.commit()

    return jsonify({"success": True, "message": f"Connection request sent to {partner.name}.", "request_id": req.id})

@borrower_bp.route("/partners")
@role_required("borrower")
def borrower_partners():
    role_filter = request.args.get("role")
    q = Partner.query

    if role_filter:
        q = q.filter_by(role=role_filter)

    partners = q.order_by(Partner.company.asc()).all()
    return render_template("borrower/partners/center.html", partners=partners, role_filter=role_filter)

@borrower_bp.route("/partners/<int:partner_id>")
@role_required("borrower")
def borrower_partner_profile(partner_id):
    partner = Partner.query.get_or_404(partner_id)

    # show if borrower already requested them
    existing = PartnerRequest.query.filter_by(
        borrower_user_id=current_user.id,
        partner_id=partner.id
    ).order_by(PartnerRequest.created_at.desc()).first()

    return render_template("borrower/partners/profile.html", partner=partner, existing=existing)



@borrower_bp.route("/partners/requests")
@role_required("borrower")
def borrower_partner_requests():
    requests_q = PartnerRequest.query.filter_by(borrower_user_id=current_user.id)\
        .order_by(PartnerRequest.created_at.desc()).all()
    return render_template("borrower/partners/requests.html", requests=requests_q)


@borrower_bp.route("/partners/requests")
@role_required("borrower")
def my_partner_requests():
    borrower_profile = BorrowerProfile.query.filter_by(user_id=current_user.id).first()

    q = PartnerRequest.query.filter_by(borrower_user_id=current_user.id)\
        .order_by(PartnerRequest.created_at.desc()).all()

    return render_template("borrower/partner_requests.html", requests=q, borrower=borrower_profile)



    
# =========================================================
# 💬 Messages
# =========================================================

@borrower_bp.route("/messages", methods=["GET"])
@role_required("borrower")
def messages():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    from LoanMVP.models.user_model import User  # local import to avoid circular

    officers = User.query.filter(
        User.role.in_(["loan_officer", "processor", "underwriter"])
    ).all()

    receiver_id = request.args.get("receiver_id", type=int)
    if receiver_id:
        msgs = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == receiver_id))
            | ((Message.sender_id == receiver_id) & (Message.receiver_id == current_user.id))
        ).order_by(Message.created_at.asc()).all()
    else:
        msgs = []

    return render_template(
        "borrower/messages.html",
        borrower=borrower,
        officers=officers,
        messages=msgs,
        selected_receiver=receiver_id,
        title="Messages",
    )

@borrower_bp.route("/messages/send", methods=["POST"])
@role_required("borrower")
def send_message():
    content = request.form.get("content")
    receiver_id = request.form.get("receiver_id")

    if not receiver_id or not content.strip():
        flash("⚠️ Please select a recipient and enter a message.", "warning")
        return redirect(url_for("borrower.messages"))

    msg = Message(
        sender_id=current_user.id,
        receiver_id=int(receiver_id),
        content=content,
        created_at=datetime.datetime.utcnow(),
    )
    db.session.add(msg)
    db.session.commit()

    flash("📩 Message sent successfully!", "success")
    return redirect(url_for("borrower.messages", receiver_id=receiver_id))


# =========================================================
# 🤖 Ask AI + AI Hub
# =========================================================

@borrower_bp.route("/ask-ai", methods=["GET"])
@role_required("borrower")
def ask_ai_page():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    interactions = (
        AIAssistantInteraction.query.filter_by(user_id=current_user.id)
        .order_by(AIAssistantInteraction.timestamp.desc())
        .all()
    )

    prefill = request.args.get("prefill", "")

    class DummyForm:
        def hidden_tag(self): return ""

    dummy_question = type("obj", (), {"data": prefill})()
    form = DummyForm()
    form.question = dummy_question
    form.submit = None

    return render_template(
        "borrower/ask_ai.html",
        borrower=borrower,
        prefill=prefill,
        form=form,
        interactions=interactions,
        title="Ask AI Assistant",
    )


@borrower_bp.route("/ask-ai", methods=["POST"])
@role_required("borrower")
def ask_ai_post():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    interactions = (
        AIAssistantInteraction.query.filter_by(user_id=current_user.id)
        .order_by(AIAssistantInteraction.timestamp.desc())
        .all()
    )

    question = request.form.get("question")
    parent_id = request.form.get("parent_id")

    ai_reply = assistant.generate_reply(question, "borrower_ai")

    chat = AIAssistantInteraction(
        user_id=current_user.id,
        borrower_profile_id=borrower.id if borrower else None,
        question=question,
        response=ai_reply,
        parent_id=parent_id,
        timestamp=datetime.datetime.utcnow(),
    )
    db.session.add(chat)
    db.session.commit()

    next_steps = assistant.generate_reply(
        f"Suggest next steps after answering: {question}.",
        "borrower_next_steps",
    )
    upload_trigger = "document" in question.lower() or "upload" in question.lower()

    return render_template(
        "borrower/ai_response.html",
        form=request.form,
        response=ai_reply,
        steps=next_steps,
        upload_trigger=upload_trigger,
        interactions=interactions,
        chat=chat,
        borrower=borrower,
        title="AI Assistant Response",
    )


@borrower_bp.route("/ai_hub")
@role_required("borrower")
def ai_hub():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    interactions = (
        AIAssistantInteraction.query.filter_by(user_id=current_user.id)
        .order_by(AIAssistantInteraction.timestamp.desc())
        .limit(5)
        .all()
    )

    ai_summary = AIAssistant.generate_reply(
        f"Provide an overview of the borrower's AI activity and recent interactions ({len(interactions)} items).",
        "borrower_ai_hub",
    )

    return render_template(
        "borrower/ai_hub.html",
        borrower=borrower,
        interactions=interactions,
        ai_summary=ai_summary,
        title="AI Hub",
    )


@borrower_bp.route("/chat")
@role_required("borrower")
def chat():
    return render_template("borrower/chat.html")


@borrower_bp.route("/ask-ai/response/<int:chat_id>")
@role_required("borrower")
def ask_ai_response(chat_id):
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    chat = AIAssistantInteraction.query.get_or_404(chat_id)

    interactions = (
        AIAssistantInteraction.query.filter_by(user_id=current_user.id)
        .order_by(AIAssistantInteraction.timestamp.desc())
        .limit(10)
        .all()
    )

    class DummyForm:
        def hidden_tag(self): return ""

    form = DummyForm()
    form.question = type("obj", (), {"data": chat.question})()
    form.submit = None

    return render_template(
        "borrower/ai_response.html",
        borrower=borrower,
        response=chat.response,
        chat=chat,
        form=form,
        interactions=interactions,
        title="AI Assistant Response",
    )

# =========================================================
# 🧠 Deal Workspace (Flip / Rental / Airbnb) — FINAL CLEAN VERSION
# =========================================================

@borrower_bp.route("/deal_workspace", methods=["GET", "POST"])
@role_required("borrower")
def deal_workspace():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if not borrower:
        flash("Borrower profile not found.", "danger")
        return redirect(url_for("borrower.dashboard"))

    saved_props = (
        SavedProperty.query
        .filter_by(borrower_profile_id=borrower.id)
        .order_by(SavedProperty.created_at.desc())
        .all()
    )

    # ONE param everywhere: prop_id = SavedProperty.id
    prop_id = request.values.get("prop_id")
    selected_prop = None
    prop_id_int = None

    if prop_id:
        try:
            prop_id_int = int(prop_id)
            selected_prop = SavedProperty.query.filter_by(
                id=prop_id_int,
                borrower_profile_id=borrower.id
            ).first()
        except Exception:
            selected_prop = None

    mode = (request.values.get("mode") or "flip").lower()
    if mode not in ("flip", "rental", "airbnb"):
        mode = "flip"

    inputs = request.form if request.method == "POST" else ImmutableMultiDict()

    comps = {}
    resolved = None
    comparison = {}
    recommendation = None
    results = {}
    ai_summary = None
    risk_flags = []
    timeline = {}
    material_costs = {}
    rehab_notes = {}

    # If POST but no property selected: don't redirect (keeps UX smooth)
    if request.method == "POST" and not selected_prop:
        flash("Please select a saved property first.", "warning")
        return render_template(
            "borrower/deal_workspace.html",
            borrower=borrower,
            saved_props=saved_props,
            selected_prop=None,
            prop_id=None,
            mode=mode,
            comps=comps,
            resolved=resolved,
            comparison=comparison,
            recommendation=recommendation,
            results=results,
            ai_summary=ai_summary,
            risk_flags=risk_flags,
            timeline=timeline,
            material_costs=material_costs,
            rehab_notes=rehab_notes,
            active_page="deal_workspace",
        )

    # Load comps + resolved
    if selected_prop:
        # ✅ IMPORTANT: have this function accept saved_property_id
        comps = get_saved_property_comps(
            user_id=current_user.id,
            saved_property_id=selected_prop.id,
            rentometer_api_key=None,
        ) or {}

        if comps:
            try:
                from LoanMVP.services.unified_property_resolver import resolve_property_intelligence
                resolved = resolve_property_intelligence(selected_prop.id, comps)
            except Exception as e:
                print("Resolver error:", e)
                resolved = None

            from LoanMVP.services.deal_workspace_calcs import (
                calculate_flip_budget,
                calculate_rental_budget,
                calculate_airbnb_budget,
                recommend_strategy,
            )
            comparison = {
                "flip": calculate_flip_budget(inputs, comps),
                "rental": calculate_rental_budget(inputs, comps),
                "airbnb": calculate_airbnb_budget(inputs, comps),
            }
            recommendation = recommend_strategy(comparison)

    # POST run
    if request.method == "POST" and selected_prop and comps:
        results = comparison.get(mode) or comparison.get("flip") or {}

        try:
            ai_summary = generate_ai_insights(mode, results, comps)
        except Exception:
            ai_summary = "AI summary unavailable."

        rehab_items = {
            "kitchen": request.form.get("kitchen") or "",
            "bathroom": request.form.get("bathroom") or "",
            "flooring": request.form.get("flooring") or "",
            "paint": request.form.get("paint") or "",
            "roof": request.form.get("roof") or "",
            "hvac": request.form.get("hvac") or "",
        }
        rehab_scope = request.form.get("rehab_scope", "medium")

        sqft = (comps.get("property") or {}).get("sqft", 0)
        try:
            sqft = int(float(sqft or 0))
        except Exception:
            sqft = 0

        rehab = estimate_rehab_cost(property_sqft=sqft, scope=rehab_scope, items=rehab_items)

        action = request.form.get("action")
        target_budget = request.form.get("target_rehab_budget")

        if action == "optimize_rehab" and target_budget:
            rehab_items, rehab = optimize_rehab_to_budget(
                target_budget=float(target_budget),
                items=rehab_items,
                scope=rehab_scope,
                sqft=sqft,
            )
        elif action == "optimize_roi":
            rehab_items, rehab = optimize_rehab_for_roi(items=rehab_items, scope=rehab_scope, sqft=sqft, comps=comps)
        elif action == "optimize_timeline":
            rehab_items, rehab = optimize_rehab_for_timeline(items=rehab_items, scope=rehab_scope, sqft=sqft)
        elif action == "optimize_arv":
            rehab_items, rehab = optimize_rehab_for_arv(items=rehab_items, scope=rehab_scope, sqft=sqft)

        results["rehab_breakdown"] = rehab
        results["rehab_total"] = rehab.get("total")
        results["rehab_summary"] = {
            "total": rehab.get("total"),
            "cost_per_sqft": rehab.get("cost_per_sqft"),
            "scope": rehab.get("scope"),
            "items": {k: v for k, v in rehab_items.items() if v},
        }

        risk_flags = generate_rehab_risk_flags(results, comps) or []
        results["risk_flags"] = risk_flags

        timeline = estimate_rehab_timeline(rehab_items, rehab_scope) or {}
        results["rehab_timeline"] = timeline

        material_costs = estimate_material_costs(property_sqft=sqft, items=rehab_items) or {}
        results["material_costs"] = material_costs

        rehab_notes = generate_rehab_notes(results, comps, strategy=mode) or {}
        results["rehab_notes"] = rehab_notes

        session["latest_rehab_results"] = {
            "rehab_summary": results.get("rehab_summary"),
            "rehab_breakdown": results.get("rehab_breakdown"),
            "risk_flags": risk_flags,
            "rehab_timeline": timeline,
            "material_costs": material_costs,
            "rehab_notes": rehab_notes,
        }

    return render_template(
        "borrower/deal_workspace.html",
        borrower=borrower,
        saved_props=saved_props,
        selected_prop=selected_prop,
        prop_id=(selected_prop.id if selected_prop else None),
        mode=mode,
        comps=comps,
        resolved=resolved,
        comparison=comparison,
        recommendation=recommendation,
        results=results,
        ai_summary=ai_summary,
        risk_flags=risk_flags,
        timeline=timeline,
        material_costs=material_costs,
        rehab_notes=rehab_notes,
        active_page="deal_workspace",
    )

@borrower_bp.route("/deals", methods=["GET"])
@role_required("borrower")
def deals_list():
    status = request.args.get("status", "active")
    q = request.args.get("q", "").strip()

    query = Deal.query.filter_by(user_id=current_user.id)

    if status in ("active", "archived"):
        query = query.filter_by(status=status)

    if q:
        like = f"%{q}%"
        query = query.filter(
            (Deal.title.ilike(like)) |
            (Deal.property_id.ilike(like)) |
            (Deal.strategy.ilike(like))
        )

    deals = query.order_by(Deal.updated_at.desc()).all()
    return render_template("borrower/deals_list.html", deals=deals, status=status, q=q)

@borrower_bp.route("/deals/<int:deal_id>", methods=["GET"])
@role_required("borrower")
def deal_detail(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first_or_404()
    return render_template("borrower/deal_detail.html", deal=deal)

@borrower_bp.route("/deals/save", methods=["POST"])
@role_required("borrower")
def save_deal():
    property_id = request.form.get("property_id") or None
    strategy = request.form.get("mode") or request.form.get("strategy") or None
    title = request.form.get("title") or None

    results_json = _safe_json_loads(request.form.get("results_json"), default={})
    inputs_json  = _safe_json_loads(request.form.get("inputs_json"), default={})
    comps_json    = _safe_json_loads(request.form.get("comps_json"), default={})
    resolved_json = _safe_json_loads(request.form.get("resolved_json"), default={})

    # fallback title
    if not title:
        addr = None
        try:
            addr = resolved_json.get("property", {}).get("address")
        except Exception:
            addr = None
        title = addr or (property_id and f"Deal {property_id}") or "Saved Deal"

    deal = Deal(
        user_id=current_user.id,
        property_id=property_id,
        title=title,
        strategy=strategy,
        inputs_json=inputs_json or None,
        results_json=results_json or None,
        comps_json=comps_json or None,
        resolved_json=resolved_json or None,
        status="active",
    )

    db.session.add(deal)
    db.session.commit()

    flash("Deal saved.", "success")
    return redirect(url_for("borrower.deal_detail", deal_id=deal.id))

@borrower_bp.route("/deals/<int:deal_id>/edit", methods=["POST"])
@role_required("borrower")
def deal_edit(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first_or_404()

    deal.title = request.form.get("title", deal.title)
    deal.notes = request.form.get("notes", deal.notes)

    status = request.form.get("status")
    if status in ("active", "archived"):
        deal.status = status

    db.session.commit()
    flash("Deal updated.", "success")
    return redirect(url_for("borrower.deal_detail", deal_id=deal.id))

@borrower_bp.route("/deals/<int:deal_id>/delete", methods=["POST"])
@role_required("borrower")
def deal_delete(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first_or_404()
    db.session.delete(deal)
    db.session.commit()
    flash("Deal deleted.", "success")
    return redirect(url_for("borrower.deals_list"))

@borrower_bp.route("/deals/<int:deal_id>/open", methods=["GET"])
@role_required("borrower")
def deal_open(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first_or_404()

    # simplest: redirect with property_id + mode. Workspace can use those to refetch comps/resolved.
    return redirect(url_for("borrower.deal_workspace", property_id=deal.property_id, mode=deal.strategy))

@borrower_bp.route("/renovation_visualizer", methods=["POST"])
@role_required("borrower")
def renovation_visualizer():
    """
    Takes an existing property photo URL, applies a renovation style prompt,
    returns 1-4 generated images (as hosted static files).
    """

    image_url = (request.form.get("image_url") or "").strip()
    style_prompt = (request.form.get("style_prompt") or "").strip()
    style_preset = (request.form.get("style_preset") or "").strip()
    variations = _safe_int(request.form.get("variations"), default=2, min_v=1, max_v=4)
    save_to_deal = (request.form.get("save_to_deal") or "").lower() in ("1", "true", "yes", "on")
    property_id = (request.form.get("property_id") or "").strip()

    if not image_url:
        return jsonify({"status": "error", "message": "Missing image_url."}), 400

    # If user didn't type prompt, but selected preset, we still allow it.
    if not style_prompt and not style_preset:
        return jsonify({"status": "error", "message": "Add a style prompt or choose a preset."}), 400

    # Combine preset into the final prompt
    preset_map = {
        "luxury": "Luxury HGTV renovation: bright, high-end finishes, clean staging, premium lighting.",
        "modern": "Modern renovation: clean lines, minimal clutter, matte black fixtures, neutral palette.",
        "airbnb": "Airbnb-ready renovation: cozy, warm lighting, durable finishes, photogenic styling.",
        "flip": "Flip-ready renovation: resale-friendly neutrals, durable materials, bright and clean.",
        "budget": "Budget-friendly renovation: fresh paint, simple upgrades, clean and functional."
    }

    final_prompt = (
        f"{preset_map.get(style_preset, '')}\n"
        f"{style_prompt}\n"
        "Keep the same room layout. Produce an HGTV-style after image. No text overlays."
    ).strip()

    try:
        # 1) download and normalize the image
        raw = _download_image_bytes(image_url)
        png = _to_png_bytes(raw, max_size=1024)

        # 2) OpenAI image edit
        client = get_openai_client()

        # NOTE:
        # - This uses the OpenAI Images "edits" style flow.
        # - The SDK response typically contains base64 images.
        result = client.images.edits(
            model="gpt-image-1",
            image=("before.png", png, "image/png"),
            prompt=final_prompt,
            n=variations,
            size="1024x1024",
        )

        out_urls = []
        # OpenAI returns base64 in many cases:
        for item in (result.data or []):
            b64 = getattr(item, "b64_json", None)
            if not b64:
                # fallback if the SDK returns a URL field
                url = getattr(item, "url", None)
                if url:
                    out_urls.append(url)
                continue

            # decode and store locally
            import base64
            img_bytes = base64.b64decode(b64)
            out_urls.append(_save_to_static(img_bytes, subdir="visualizer"))

        if not out_urls:
            return jsonify({"status": "error", "message": "No images returned from generator."}), 500

        # Optional “save to deal” MVP: stash in session for now (DB table later)
        if save_to_deal:
            session["latest_renovation_visuals"] = {
                "property_id": property_id,
                "before": image_url,
                "after_images": out_urls,
                "preset": style_preset,
                "prompt": style_prompt,
            }

        return jsonify({
            "status": "ok",
            "images": out_urls,
            "cost_estimate": {
                "note": "AI design preview only (not a contractor bid)."
            }
        })

    except RuntimeError as e:
        # Missing OPENAI_API_KEY
        return jsonify({"status": "error", "message": str(e)}), 400
    except requests.RequestException as e:
        return jsonify({"status": "error", "message": f"Could not download image: {e}"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": f"Renovation generator failed: {e}"}), 500
    
@borrower_bp.route("/deal/<int:deal_id>/reveal")
@role_required("borrower")
def deal_reveal(deal_id):
    mockups = RenovationMockup.query.filter_by(deal_id=deal_id, user_id=current_user.id)\
                                   .order_by(RenovationMockup.created_at.desc()).all()
    return render_template("borrower/deal_reveal.html", deal_id=deal_id, mockups=mockups)

@borrower_bp.route("/renovation_upload", methods=["POST"])
@role_required("borrower")
def renovation_upload():
    f = request.files.get("photo")
    if not f:
        return jsonify({"status": "error", "message": "No file uploaded."}), 400

    filename = secure_filename(f.filename or "upload.png")
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".png", ".jpg", ".jpeg", ".webp"]:
        return jsonify({"status": "error", "message": "Upload png/jpg/webp only."}), 400

    raw = f.read()
    png = _to_png_bytes(raw, max_size=1400)
    url = _save_to_static(png, subdir="renovation_uploads")

    return jsonify({"status": "ok", "image_url": url})

@borrower_bp.route("/deals/send-to-lo", methods=["POST"])
@role_required("borrower")
def send_to_lo():
    property_id = request.form.get("property_id") or None
    strategy = request.form.get("mode") or request.form.get("strategy") or None
    title = request.form.get("title") or None
    note = (request.form.get("note") or "").strip() or None

    results_json = _safe_json_loads(request.form.get("results_json"), default={})
    comps_json = _safe_json_loads(request.form.get("comps_json"), default={})
    resolved_json = _safe_json_loads(request.form.get("resolved_json"), default={})

    # Fallback title
    if not title:
        addr = (resolved_json or {}).get("property", {}).get("address")
        title = addr or (property_id and f"Deal {property_id}") or "Deal Shared"

    # 🔎 Get borrower profile
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()

    lo_user_id = None

    if bp:
        # Priority 1 — assigned_officer_id (LoanOfficerProfile)
        if bp.assigned_officer_id:
            lo_profile = LoanOfficerProfile.query.get(bp.assigned_officer_id)
            if lo_profile:
                lo_user_id = lo_profile.user_id

        # Priority 2 — assigned_to (direct user id)
        if not lo_user_id and bp.assigned_to:
            lo_user_id = bp.assigned_to

    if not lo_user_id:
        flash("No assigned Loan Officer found on your profile.", "warning")
        return redirect(url_for("borrower.deal_workspace",
                                property_id=property_id,
                                mode=strategy))

    share = DealShare(
        borrower_user_id=current_user.id,
        loan_officer_user_id=lo_user_id,
        property_id=property_id,
        strategy=strategy,
        title=title,
        results_json=results_json or None,
        comps_json=comps_json or None,
        resolved_json=resolved_json or None,
        note=note,
        status="new",
    )

    db.session.add(share)
    db.session.commit()

    flash("Sent to your Loan Officer.", "success")

    return redirect(url_for("borrower.deal_workspace",
                            property_id=property_id,
                            mode=strategy))

@borrower_bp.route("/deals/<int:deal_id>/export-report", methods=["GET"])
@role_required("borrower")
def export_deal_report_pro(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first()
    if not deal:
        abort(404)

    r = deal.results_json or {}
    comps = deal.comps_json or {}
    resolved = deal.resolved_json or {}

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER

    y = height - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "Deal Report (Pro)")
    y -= 22

    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Title: {deal.title or '—'}")
    y -= 14
    c.drawString(50, y, f"Property ID: {deal.property_id or '—'}")
    y -= 14
    c.drawString(50, y, f"Strategy: {deal.strategy or '—'}")
    y -= 14
    c.drawString(50, y, f"Created: {deal.created_at.strftime('%Y-%m-%d %H:%M') if deal.created_at else '—'}")
    y -= 22

    # Property summary (best-effort)
    prop = (resolved.get("property") or {}) if isinstance(resolved, dict) else {}
    addr = prop.get("address")
    city = prop.get("city")
    state = prop.get("state")
    zipc = prop.get("zip")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Property Summary")
    y -= 16
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Address: {addr or '—'}")
    y -= 14
    c.drawString(50, y, f"City/State/Zip: {city or '—'}, {state or '—'} {zipc or ''}")
    y -= 18

    # Results summary
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Key Results")
    y -= 16
    c.setFont("Helvetica", 10)

    if "profit" in r:
        c.drawString(50, y, f"Flip Profit: {_fmt_money(r.get('profit'))}")
        y -= 14
    if "net_cashflow" in r:
        c.drawString(50, y, f"Rental Net Cashflow (mo): {_fmt_money(r.get('net_cashflow'))}")
        y -= 14
    if "net_monthly" in r:
        c.drawString(50, y, f"Airbnb Net Monthly: {_fmt_money(r.get('net_monthly'))}")
        y -= 14
    if r.get("roi") is not None:
        try:
            roi_pct = float(r.get("roi")) * 100
            c.drawString(50, y, f"ROI: {roi_pct:,.1f}%")
        except Exception:
            c.drawString(50, y, "ROI: —")
        y -= 14

    y -= 10

    # Rehab summary
    rehab = r.get("rehab_summary") if isinstance(r, dict) else None
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Rehab Summary")
    y -= 16
    c.setFont("Helvetica", 10)

    if isinstance(rehab, dict):
        c.drawString(50, y, f"Scope: {rehab.get('scope') or '—'}")
        y -= 14
        c.drawString(50, y, f"Total Rehab: {_fmt_money(rehab.get('total'))}")
        y -= 14
        c.drawString(50, y, f"Cost per Sqft: {_fmt_money(rehab.get('cost_per_sqft'))}")
        y -= 14
    else:
        c.drawString(50, y, "No rehab summary available.")
        y -= 14

    c.showPage()
    c.save()

    buffer.seek(0)
    filename = f"deal_report_{deal.id}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")

@borrower_bp.route("/deals/<int:deal_id>/export-rehab-scope", methods=["GET"])
@role_required("borrower")
def export_rehab_scope(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first()
    if not deal:
        abort(404)

    r = deal.results_json or {}
    rehab = r.get("rehab_summary") if isinstance(r, dict) else None

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER

    y = height - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "Rehab Scope")
    y -= 22

    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Deal: {deal.title or '—'}")
    y -= 14
    c.drawString(50, y, f"Property ID: {deal.property_id or '—'}")
    y -= 14
    c.drawString(50, y, f"Strategy: {deal.strategy or '—'}")
    y -= 22

    if not isinstance(rehab, dict):
        c.drawString(50, y, "No rehab summary available for this deal.")
        c.showPage()
        c.save()
        buffer.seek(0)
        filename = f"rehab_scope_{deal.id}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
        return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Summary")
    y -= 16
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Scope: {rehab.get('scope') or '—'}")
    y -= 14
    c.drawString(50, y, f"Total Rehab: {_fmt_money(rehab.get('total'))}")
    y -= 14
    c.drawString(50, y, f"Cost per Sqft: {_fmt_money(rehab.get('cost_per_sqft'))}")
    y -= 18

    items = rehab.get("items") or {}
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Selected Items")
    y -= 16
    c.setFont("Helvetica", 10)

    if isinstance(items, dict) and items:
        for k, v in items.items():
            if y < 80:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 10)

            level = v.get("level") if isinstance(v, dict) else None
            cost = v.get("cost") if isinstance(v, dict) else None
            c.drawString(50, y, f"- {str(k).capitalize()}: {str(level).capitalize() if level else '—'}  |  {_fmt_money(cost)}")
            y -= 14
    else:
        c.drawString(50, y, "No item selections found.")
        y -= 14

    c.showPage()
    c.save()

    buffer.seek(0)
    filename = f"rehab_scope_{deal.id}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")

# =========================================================
# 📄 Loan View / Edit
# =========================================================

@borrower_bp.route("/loan/<int:loan_id>", methods=["GET"])
@role_required("borrower")
def loan_view(loan_id):
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    loan = LoanApplication.query.get_or_404(loan_id)

    # Security check
    if loan.borrower_profile_id != borrower.id:
        return "Unauthorized", 403

    # Loan-specific conditions
    conditions = UnderwritingCondition.query.filter_by(
        borrower_profile_id=borrower.id,
        loan_id=loan.id
    ).all()

    assistant = AIAssistant()
    ai_summary = assistant.generate_reply(
        f"Summarize {len(conditions)} underwriting conditions for borrower {borrower.full_name}.",
        "loan_conditions",
    )

    return render_template(
        "borrower/view_loan.html",
        borrower=borrower,
        loan=loan,
        conditions=conditions,
        ai_summary=ai_summary,
        active_tab="loan",
        title=f"Loan #{loan.id}",
    )

   
@borrower_bp.route("/loan/<int:loan_id>/edit", methods=["GET", "POST"])
@role_required("borrower")
def edit_loan(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()

    if request.method == "POST":
        loan.loan_amount = safe_float(request.form.get("amount"))
        loan.status = request.form.get("status")
        loan.loan_type = request.form.get("loan_type")
        loan.property_address = request.form.get("property_address")
        loan.interest_rate = safe_float(request.form.get("interest_rate"))
        loan.term = request.form.get("term")

        db.session.commit()
        flash("✅ Loan application updated successfully!", "success")
        return redirect(url_for("borrower.loan_view", loan_id=loan.id))

    return render_template(
        "borrower/edit_loan.html",
        loan=loan,
        borrower=borrower,
        title="Edit Loan",
    )


# =========================================================
# 🔍 Property Search & Saved Properties
# =========================================================
@borrower_bp.route("/property_search", methods=["GET"])
@role_required("borrower")
def property_search():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()

    query = (request.args.get("query") or "").strip()

    property_data = None
    valuation = {}
    rent_estimate = {}
    comps = {}
    ai_summary = None
    error = None
    debug = None
    saved_id = None

    def normalize_property(p: dict) -> dict:
        if not isinstance(p, dict):
            return {}

        # normalize common aliases
        p.setdefault("zip", p.get("zipcode") or p.get("zipCode") or p.get("postalCode"))
        p.setdefault("city", p.get("city") or p.get("locality"))
        p.setdefault("state", p.get("state") or p.get("region") or p.get("stateCode"))
        p.setdefault("address", p.get("address") or p.get("formattedAddress") or query)

        # price normalize
        if p.get("price") is not None:
            try:
                p["price"] = float(p["price"])
            except Exception:
                pass

        # photos normalize
        if p.get("photos") in ({}, []):
            p["photos"] = None

        return p

    if query:
        from LoanMVP.services.unified_resolver import resolve_property_unified
        resolved = resolve_property_unified(query)

        print("PROPERTY SEARCH RESOLVED =>", resolved)

        if resolved.get("status") == "ok":
            raw_prop = resolved.get("property") or {}
            property_data = normalize_property(raw_prop)

            # ✅ Extract what template expects
            valuation = raw_prop.get("valuation") or {}
            rent_estimate = raw_prop.get("rent_estimate") or raw_prop.get("rentEstimate") or {}
            comps = raw_prop.get("comps") or {}

            # ai summary (your resolver returns this sometimes)
            ai_summary = resolved.get("ai_summary") or resolved.get("summary") or None

            # ✅ Find existing saved property
            if borrower and property_data.get("address"):
                try:
                    existing = SavedProperty.query.filter(
                        SavedProperty.borrower_profile_id == borrower.id,
                        db.func.lower(SavedProperty.address) == property_data["address"].lower()
                    ).first()
                    if existing:
                        saved_id = existing.id
                except Exception:
                    saved_id = None

        else:
            error = resolved.get("error") or "unknown_error"
            debug = {
                "provider": resolved.get("provider"),
                "stage": resolved.get("stage"),
            }

    return render_template(
        "borrower/property_search.html",
        borrower=borrower,
        title="Property Search",
        active_page="property_search",

        query=query,
        error=error,
        debug=debug,

        property=property_data,
        valuation=valuation,
        rent_estimate=rent_estimate,
        comps=comps,
        ai_summary=ai_summary,

        saved_id=saved_id,
    )
    
@borrower_bp.route("/save_property", methods=["POST"])
@role_required("borrower")
def save_property():
    print("SAVE_PROPERTY current_user.id =", current_user.id)

    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    print("SAVE_PROPERTY borrower_profile_id =", borrower.id if borrower else None)

    if not borrower:
        return jsonify({"status": "error", "message": "Borrower profile not found."}), 400

    # Raw inputs from form
    raw_property_id = (request.form.get("property_id") or "").strip()
    raw_address = (request.form.get("address") or "").strip()
    raw_price = request.form.get("price")
    raw_zipcode = (request.form.get("zipcode") or "").strip() or None
    sqft_raw = request.form.get("sqft")

    if not raw_address:
        return jsonify({"status": "error", "message": "Address required."}), 400

    # Normalize sqft from form
    sqft = None
    try:
        if sqft_raw not in (None, "", "None"):
            sqft = int(float(sqft_raw))
    except Exception:
        sqft = None

    # ---------------------------------------------------------
    # ✅ Resolve FIRST so we can save a normalized address + fill zip/sqft
    # ---------------------------------------------------------
    resolved = {}
    try:
        from LoanMVP.services.unified_resolver import resolve_property_unified
        resolved = resolve_property_unified(raw_address)
    except Exception as e:
        print("SAVE_PROPERTY resolver error:", e)
        resolved = {}

    normalized_address = raw_address
    resolved_property_id = None

    if resolved.get("status") == "ok":
        p = resolved.get("property") or {}

        # ✅ normalized address from provider (critical)
        normalized_address = (p.get("address") or raw_address).strip()

        # prefer provider property id if present
        resolved_property_id = (p.get("property_id") or p.get("id") or p.get("propertyId"))
        resolved_property_id = str(resolved_property_id).strip() if resolved_property_id else None

        # ✅ fill zipcode/sqft if missing
        raw_zipcode = raw_zipcode or p.get("zip") or p.get("zipCode") or p.get("postalCode")

        if sqft is None:
            try:
                sqft_val = p.get("sqft") or p.get("squareFootage")
                sqft = int(float(sqft_val)) if sqft_val not in (None, "", "None") else None
            except Exception:
                sqft = None

    # Choose the best property_id to store
    final_property_id = raw_property_id or resolved_property_id or None

    # ---------------------------------------------------------
    # ✅ Prevent duplicates (use property_id if we have it, else normalized address)
    # ---------------------------------------------------------
    existing = None

    if final_property_id:
        existing = SavedProperty.query.filter_by(
            borrower_profile_id=borrower.id,
            property_id=str(final_property_id)
        ).first()

    if not existing:
        # fallback: normalized address match (case-insensitive)
        existing = SavedProperty.query.filter(
            SavedProperty.borrower_profile_id == borrower.id,
            db.func.lower(SavedProperty.address) == normalized_address.lower()
        ).first()

    if existing:
        # update missing fields
        if not existing.address and normalized_address:
            existing.address = normalized_address

        if (not existing.zipcode) and raw_zipcode:
            existing.zipcode = raw_zipcode

        if (existing.sqft is None or existing.sqft == 0) and sqft:
            existing.sqft = sqft

        if (not existing.price) and raw_price is not None:
            existing.price = str(raw_price)

        if (not existing.property_id) and final_property_id:
            existing.property_id = str(final_property_id)

        # ✅ store snapshot if columns exist
        if hasattr(existing, "resolved_json"):
            existing.resolved_json = json.dumps(resolved) if resolved else None
            existing.resolved_at = datetime.utcnow() if resolved else None

        db.session.commit()
        return jsonify({
            "status": "success",
            "message": "✅ Property already saved (updated details).",
            "saved_id": existing.id
        })

    # ---------------------------------------------------------
    # ✅ Create new saved property using normalized address
    # ---------------------------------------------------------
    saved = SavedProperty(
        borrower_profile_id=borrower.id,
        property_id=str(final_property_id) if final_property_id else None,
        address=normalized_address,
        price=str(raw_price or ""),
        sqft=sqft,
        zipcode=raw_zipcode,
        saved_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )

    if hasattr(saved, "resolved_json"):
        saved.resolved_json = json.dumps(resolved) if resolved else None
        saved.resolved_at = datetime.utcnow() if resolved else None

    db.session.add(saved)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "🏠 Property saved!",
        "saved_id": saved.id
    })

@borrower_bp.route("/saved_properties")
@role_required("borrower")
def saved_properties():
    print("SAVED_PROPERTIES current_user.id =", current_user.id)
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    print("SAVED_PROPERTIES borrower_profile_id =", borrower.id if borrower else None)
    properties = (
        SavedProperty.query.filter_by(borrower_profile_id=borrower.id).all()
        if borrower else []
    )

    try:
        name = borrower.full_name if borrower else "this borrower"
        ai_summary = AIAssistant().generate_reply(
            f"Summarize {len(properties)} saved properties for {name}. Prioritize investment potential.",
            "saved_properties",
        )
    except Exception:
        ai_summary = "⚠️ AI summary unavailable."

    return render_template(
        "borrower/saved_properties.html",
        borrower=borrower,
        properties=properties,
        ai_summary=ai_summary,
        title="Saved Properties",
    )

@borrower_bp.route("/save_property_and_analyze", methods=["POST"])
@role_required("borrower")
def save_property_and_analyze():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if not borrower:
        flash("Borrower profile not found.", "danger")
        return redirect(url_for("borrower.property_search"))

    raw_address = (request.form.get("address") or "").strip()
    if not raw_address:
        flash("Address required.", "warning")
        return redirect(url_for("borrower.property_search"))

    zipcode = (request.form.get("zipcode") or "").strip() or None
    price = request.form.get("price")
    sqft_raw = request.form.get("sqft")

    # Normalize sqft
    sqft = None
    try:
        sqft = int(float(sqft_raw)) if sqft_raw not in (None, "", "None") else None
    except Exception:
        sqft = None

    # Resolve + normalize
    resolved = {}
    normalized_address = raw_address
    resolved_property_id = None

    try:
        from LoanMVP.services.unified_resolver import resolve_property_unified
        resolved = resolve_property_unified(raw_address)
    except Exception as e:
        print("SAVE_PROPERTY_AND_ANALYZE resolver error:", e)
        resolved = {}

    if resolved.get("status") == "ok":
        p = resolved.get("property") or {}
        normalized_address = (p.get("address") or raw_address).strip()

        resolved_property_id = (p.get("property_id") or p.get("id") or p.get("propertyId"))
        resolved_property_id = str(resolved_property_id).strip() if resolved_property_id else None

        zipcode = zipcode or p.get("zip") or p.get("zipCode") or p.get("postalCode")

        if sqft is None:
            try:
                sqft_val = p.get("sqft") or p.get("squareFootage")
                sqft = int(float(sqft_val)) if sqft_val not in (None, "", "None") else None
            except Exception:
                sqft = None

        # If no price passed in, optionally use provider value
        if (price in (None, "", "None")) and (p.get("price") is not None):
            try:
                price = str(p.get("price"))
            except Exception:
                pass

    # Best property_id to store
    form_pid = (request.form.get("property_id") or "").strip()
    final_property_id = form_pid or resolved_property_id or None
    final_property_id = str(final_property_id).strip() if final_property_id else None

    # Deduplicate: property_id first, else normalized address (case-insensitive)
    existing = None
    if final_property_id:
        existing = SavedProperty.query.filter_by(
            borrower_profile_id=borrower.id,
            property_id=final_property_id
        ).first()

    if not existing and normalized_address:
        existing = SavedProperty.query.filter(
            SavedProperty.borrower_profile_id == borrower.id,
            db.func.lower(SavedProperty.address) == normalized_address.lower()
        ).first()

    if existing:
        # Optional: update missing fields before redirect
        updated = False

        if (not existing.property_id) and final_property_id:
            existing.property_id = final_property_id
            updated = True

        if (not existing.zipcode) and zipcode:
            existing.zipcode = zipcode
            updated = True

        if (existing.sqft is None or existing.sqft == 0) and sqft:
            existing.sqft = sqft
            updated = True

        if (not existing.price) and price not in (None, "", "None"):
            existing.price = str(price)
            updated = True

        if hasattr(existing, "resolved_json"):
            existing.resolved_json = json.dumps(resolved) if resolved else None
            existing.resolved_at = datetime.utcnow() if resolved else None
            updated = True

        if updated:
            db.session.commit()

        flash("✅ Property already saved — opening Deal Workspace.", "info")
        return redirect(url_for("borrower.deal_workspace", prop_id=existing.id, mode="flip"))

    # Create new SavedProperty
    saved = SavedProperty(
        borrower_profile_id=borrower.id,
        property_id=final_property_id,
        address=normalized_address,
        price=str(price or ""),
        sqft=sqft,
        zipcode=zipcode,
        saved_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )

    if hasattr(saved, "resolved_json"):
        saved.resolved_json = json.dumps(resolved) if resolved else None
        saved.resolved_at = datetime.utcnow() if resolved else None

    db.session.add(saved)
    db.session.commit()

    flash("🏠 Property saved! Opening Deal Workspace…", "success")
    return redirect(url_for("borrower.deal_workspace", prop_id=saved.id, mode="flip"))

@borrower_bp.route("/saved_properties/manage", methods=["POST"])
@role_required("borrower")
def saved_properties_manage():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if not borrower:
        flash("Borrower profile not found.", "danger")
        return redirect(url_for("borrower.saved_properties"))

    prop_id = request.form.get("prop_id")
    action = request.form.get("action")
    notes = request.form.get("notes", "")

    try:
        prop_id = int(prop_id)
    except Exception:
        flash("Invalid property id.", "warning")
        return redirect(url_for("borrower.saved_properties"))

    prop = SavedProperty.query.filter_by(
        id=prop_id,
        borrower_profile_id=borrower.id
    ).first()

    if not prop:
        flash("Saved property not found.", "warning")
        return redirect(url_for("borrower.saved_properties"))

    if action == "edit":
        if hasattr(prop, "notes"):
            prop.notes = notes
            db.session.commit()
            flash("✅ Notes saved.", "success")
        else:
            flash("Notes column not added yet.", "info")

    elif action == "delete":
        db.session.delete(prop)
        db.session.commit()
        flash("🗑️ Saved property deleted.", "success")

    return redirect(url_for("borrower.saved_properties"))
    
@borrower_bp.route("/property_explore_plus/<int:prop_id>")
@role_required("borrower")
def property_explore_plus(prop_id):
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if not borrower:
        flash("Borrower profile not found.", "danger")
        return redirect(url_for("borrower.property_search"))

    prop = SavedProperty.query.filter_by(
        id=prop_id,
        borrower_profile_id=borrower.id
    ).first()

    if not prop:
        flash("Property not found.", "danger")
        return redirect(url_for("borrower.property_search"))

    # Resolve
    from LoanMVP.services.unified_resolver import resolve_property_unified
    resolved = resolve_property_unified(prop.address)

    resolved_property = (resolved.get("property") or {}) if resolved.get("status") == "ok" else {}
    photos = resolved_property.get("photos") or []

    # Comps + market
    from LoanMVP.services.comps_service import get_comps_for_property
    comps = get_comps_for_property(
        address=prop.address,
        zipcode=(prop.zipcode or ""),
        rentometer_api_key=None
    )

    from LoanMVP.services.market_service import get_market_snapshot
    market = get_market_snapshot(zipcode=(prop.zipcode or "")) if prop.zipcode else {}

    # AI summary (optional; keep it lightweight)
    ai_summary = resolved.get("ai_summary") or None

    return render_template(
        "borrower/property_explore_plus.html",
        borrower=borrower,
        prop=prop,
        resolved=resolved_property,
        ai_summary=ai_summary,
        comps=comps,
        market=market,
        photos=photos,
        active_page="property_search",
    )

@borrower_bp.route("/property_tool", methods=["GET"], endpoint="property_tool")
@role_required("borrower")
def property_tool():
    return render_template("borrower/property_tool.html", active_page="property_tool")
    
# -------------------------------
# ZIP SEARCH (NO ADDRESS REQUIRED)
# -------------------------------
@borrower_bp.route("/api/property_tool_search", methods=["POST"])
@role_required("borrower")
def api_property_tool_search():
    payload = request.get_json(force=True) or {}

    zip_code = (payload.get("zip") or "").strip()
    strategy = (payload.get("strategy") or "flip").strip().lower()

    if not zip_code:
        return jsonify({"status": "error", "message": "ZIP code is required."}), 400

    def _num(v):
        try:
            if v in (None, "", "None"):
                return None
            return float(v)
        except Exception:
            return None

    results = search_deals_for_zip(
        zip_code=zip_code,
        strategy=strategy,
        price_min=_num(payload.get("price_min")),
        price_max=_num(payload.get("price_max")),
        beds_min=_num(payload.get("beds_min")),
        baths_min=_num(payload.get("baths_min")),
        min_roi=_num(payload.get("min_roi")),
        min_cashflow=_num(payload.get("min_cashflow")),
        limit=int(payload.get("limit") or 20),
    )

    return jsonify({"status": "ok", "zip": zip_code, "strategy": strategy, "results": results})


# -------------------------------
# SAVE ONLY (NO REDIRECT)
# -------------------------------
@borrower_bp.route("/api/property_tool_save", methods=["POST"])
@role_required("borrower")
def api_property_tool_save():
    payload = request.get_json(force=True) or {}

    address = (payload.get("address") or "").strip()
    if not address:
        return jsonify({"status": "error", "message": "Address is required to save."}), 400

    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if not borrower:
        return jsonify({"status": "error", "message": "Borrower profile not found."}), 400

    # optional fields
    zipcode = (payload.get("zip") or "").strip() or None
    price = payload.get("price")
    sqft = payload.get("sqft")
    property_id = payload.get("property_id")

    # normalize types
    try:
        sqft = int(float(sqft)) if sqft not in (None, "", "None") else None
    except Exception:
        sqft = None

    # prevent duplicates by property_id OR address
    existing = None
    if property_id:
        existing = SavedProperty.query.filter_by(
            borrower_profile_id=borrower.id,
            property_id=str(property_id)
        ).first()

    if not existing:
        existing = SavedProperty.query.filter(
            SavedProperty.borrower_profile_id == borrower.id,
            db.func.lower(SavedProperty.address) == address.lower()
        ).first()

    if existing:
        return jsonify({
            "status": "ok",
            "message": "Already saved.",
            "saved_id": existing.id
        })

    saved = SavedProperty(
        borrower_profile_id=borrower.id,
        property_id=str(property_id) if property_id else None,
        address=address,
        price=str(price or ""),
        sqft=sqft,
        zipcode=zipcode,
        saved_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )
    db.session.add(saved)
    db.session.commit()

    return jsonify({
        "status": "ok",
        "message": "Saved.",
        "saved_id": saved.id
    })


# ----------------------------------------
# SAVE + REDIRECT TO DEAL WORKSPACE
# ----------------------------------------
@borrower_bp.route("/api/property_tool_save_and_analyze", methods=["POST"])
@role_required("borrower")
def api_property_tool_save_and_analyze():
    payload = request.get_json(force=True) or {}

    address = (payload.get("address") or "").strip()
    if not address:
        return jsonify({"status": "error", "message": "Address is required to analyze."}), 400

    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if not borrower:
        return jsonify({"status": "error", "message": "Borrower profile not found."}), 400

    zipcode = (payload.get("zip") or "").strip() or None
    price = payload.get("price")
    sqft = payload.get("sqft")
    property_id = payload.get("property_id")

    try:
        sqft = int(float(sqft)) if sqft not in (None, "", "None") else None
    except Exception:
        sqft = None

    # duplicate check
    existing = None
    if property_id:
        existing = SavedProperty.query.filter_by(
            borrower_profile_id=borrower.id,
            property_id=str(property_id)
        ).first()

    if not existing:
        existing = SavedProperty.query.filter(
            SavedProperty.borrower_profile_id == borrower.id,
            db.func.lower(SavedProperty.address) == address.lower()
        ).first()

    if not existing:
        existing = SavedProperty(
            borrower_profile_id=borrower.id,
            property_id=str(property_id) if property_id else None,
            address=address,
            price=str(price or ""),
            sqft=sqft,
            zipcode=zipcode,
            saved_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
        db.session.add(existing)
        db.session.commit()

    deal_url = url_for("borrower.deal_workspace", prop_id=existing.id, mode="flip")
    return jsonify({
        "status": "ok",
        "saved_id": existing.id,
        "deal_url": deal_url
    })
    
# =========================================================
# 💰 Quotes & Conversion
# =========================================================

@borrower_bp.route("/quote", methods=["GET", "POST"])
@role_required("borrower")
def quote():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()

    if not borrower:
        flash("Please complete your borrower profile before requesting a quote.", "warning")
        return redirect(url_for("borrower.create_profile"))

    if request.method == "POST":
        loan_amount = safe_float(request.form.get("loan_amount"))
        property_value = safe_float(request.form.get("property_value"))
        property_address = request.form.get("property_address", "")
        property_type = request.form.get("property_type", "")
        loan_type = request.form.get("loan_type", "Conventional")
        loan_category = request.form.get("loan_category", "Purchase")
        term_months = int(request.form.get("term_months", 360))
        fico_score = int(request.form.get("fico_score", 700))
        experience = request.form.get("experience", "New Investor")

        ltv = (loan_amount / property_value * 100) if property_value else 0

        try:
            prompt = (
                f"Generate up to 3 competitive loan quotes for a borrower requesting "
                f"${loan_amount:,.0f} on a property valued at ${property_value:,.0f} "
                f"({ltv:.1f}% LTV). Loan type: {loan_type}, category: {loan_category}, "
                f"credit score {fico_score}, experience: {experience}. "
                f"Suggest lenders, estimated rates, and short commentary."
            )
            ai_suggestion = assistant.generate_reply(prompt, role="borrower_quote")
        except Exception:
            ai_suggestion = "⚠️ AI system unavailable. Displaying mock results."

        mock_lenders = [
            {"lender_name": "Lime One Capital", "rate": 6.20, "loan_type": "30-Year Fixed", "deal_type": "Conventional"},
            {"lender_name": "Roc Funding", "rate": 6.05, "loan_type": "FHA 30-Year", "deal_type": "Residential"},
            {"lender_name": "Lev Bank", "rate": 5.90, "loan_type": "5/1 ARM", "deal_type": "Hybrid"},
        ]

        for lender in mock_lenders:
            new_quote = LoanQuote(
                borrower_profile_id=borrower.id,
                lender_name=lender["lender_name"],
                rate=lender["rate"],
                loan_type=lender["loan_type"],
                deal_type=lender["deal_type"],
                max_ltv=ltv,
                term_months=term_months,
                loan_amount=loan_amount,
                property_address=property_address,
                property_type=property_type,
                purchase_price=property_value,
                fico_score=fico_score,
                loan_category=loan_category,
                experience=experience,
                ai_suggestion=ai_suggestion,
                response_json=None,
                status="pending",
            )
            db.session.add(new_quote)
        db.session.commit()

        flash("✅ Loan quotes generated successfully!", "success")

        return render_template(
            "borrower/quote_results.html",
            borrower=borrower,
            lenders=mock_lenders,
            property_address=property_address,
            property_value=property_value,
            loan_amount=loan_amount,
            fico_score=fico_score,
            ltv=ltv,
            ai_response=ai_suggestion,
            title="Loan Quote Results",
        )

    return render_template(
        "borrower/quote.html",
        borrower=borrower,
        title="Get a Loan Quote",
    )


@borrower_bp.route("/quote/convert/<int:quote_id>", methods=["POST"])
@role_required("borrower")
def convert_quote_to_application(quote_id):
    quote = LoanQuote.query.get_or_404(quote_id)
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()

    if not borrower:
        flash("Please complete your borrower profile before applying.", "warning")
        return redirect(url_for("borrower.create_profile"))

    existing_app = LoanApplication.query.filter_by(
        borrower_profile_id=borrower.id,
        loan_amount=quote.loan_amount,
        property_address=quote.property_address,
    ).first()

    if existing_app:
        flash("This quote has already been converted to an application.", "info")
        return redirect(url_for("borrower.status"))

    new_app = LoanApplication(
        borrower_profile_id=borrower.id,
        loan_amount=quote.loan_amount,
        property_address=quote.property_address,
        loan_type=quote.loan_type,
        status="submitted",
        created_at=datetime.datetime.utcnow(),
    )
    db.session.add(new_app)
    db.session.flush()

    quote.loan_application_id = new_app.id
    quote.status = "converted"
    db.session.add(quote)

    activity = BorrowerActivity(
        borrower_profile_id=borrower.id,
        category="Loan Conversion",
        description=f"Converted quote #{quote.id} into loan application #{new_app.id}.",
        timestamp=datetime.datetime.utcnow(),
    )
    db.session.add(activity)

    message_body = (
        f"📢 Borrower {borrower.full_name} converted quote #{quote.id} into "
        f"Loan Application #{new_app.id} for {quote.property_address or 'a new property'}."
    )

    message = Message(
        sender_id=current_user.id,
        receiver_id=quote.assigned_officer_id or None,
        content=message_body,
        created_at=datetime.datetime.utcnow(),
        system_generated=True,
    )
    db.session.add(message)

    db.session.commit()

    try:
        notify_team_on_conversion(borrower, quote, new_app)
    except Exception as e:
        print("Notification error:", e)

    try:
        assistant.generate_reply(
            f"Borrower {borrower.full_name} converted a loan quote to a new application. "
            f"Property: {quote.property_address}, Loan Amount: ${quote.loan_amount:,.0f}. "
            f"Log this action and notify the assigned loan officer.",
            "system_event",
        )
    except Exception:
        pass

    flash("🎯 Quote converted and team notified successfully!", "success")
    return redirect(url_for("borrower.status"))


@borrower_bp.route("/get_quote_ai", methods=["POST"])
@role_required("borrower")
def get_quote_ai():
    from LoanMVP.ai.master_ai import CMAIEngine
    ai = CMAIEngine()

    data = request.json

    msg = f"""
    Borrower is requesting a loan quote.

    Loan Amount: {data['amount']}
    Property Value: {data['value']}
    Credit Score: {data['credit']}
    Purpose: {data['purpose']}
    Notes: {data.get('notes','')}
    """

    ai_reply = ai.generate(msg, role="borrower")

    return jsonify({"quote": ai_reply})


# =========================================================
# 📈 Analytics & Activity
# =========================================================

@borrower_bp.route("/analysis")
@role_required("borrower")
def analysis():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()

    loans = (
        LoanApplication.query.filter_by(borrower_profile_id=borrower.id).all()
        if borrower else []
    )
    total_loans = len(loans)
    total_loan_amount = sum([loan.loan_amount or 0 for loan in loans])
    verified_docs = LoanDocument.query.filter_by(
        borrower_profile_id=borrower.id, status="Verified"
    ).count()
    pending_docs = LoanDocument.query.filter_by(
        borrower_profile_id=borrower.id, status="Pending"
    ).count()

    ai_summary = assistant.generate_reply(
        f"Summarize borrower {borrower.full_name}'s analytics: {total_loans} loans totaling "
        f"${total_loan_amount}, {verified_docs} verified documents, {pending_docs} pending.",
        "borrower_analysis",
    )

    stats = {
        "total_loans": total_loans,
        "total_amount": f"${total_loan_amount:,.2f}",
        "verified_docs": verified_docs,
        "pending_docs": pending_docs,
    }

    return render_template(
        "borrower/analysis.html",
        borrower=borrower,
        loans=loans,
        stats=stats,
        ai_summary=ai_summary,
        title="Borrower Analytics",
    )


@borrower_bp.route("/activity/<int:borrower_id>")
@role_required("borrower")
def activity(borrower_id):
    borrower = BorrowerProfile.query.get_or_404(borrower_id)
    activities = (
        BorrowerActivity.query.filter_by(borrower_profile_id=borrower.id)
        .order_by(BorrowerActivity.timestamp.desc())
        .all()
    )

    ai_summary = assistant.generate_reply(
        f"Generate borrower {borrower.full_name}'s activity summary of {len(activities)} recent actions.",
        "borrower_activity",
    )

    return render_template(
        "borrower/activity.html",
        borrower=borrower,
        activities=activities,
        ai_summary=ai_summary,
        title="Borrower Activity",
    )


@borrower_bp.route("/ai_deal_insight", methods=["POST"])
@role_required("borrower")
def ai_deal_insight():
    data = request.get_json()
    name = data.get("name", "Unnamed Deal")
    roi = data.get("roi", 0)
    profit = data.get("profit", 0)
    total = data.get("total", 0)
    message = data.get("message", "")

    ai_reply = assistant.generate_reply(
        f"Evaluate deal '{name}' with ROI {roi}%, profit {profit}, total cost {total}. "
        f"Provide recommendations: {message}",
        "ai_deal_insight",
    )
    return jsonify({"reply": ai_reply})


# =========================================================
# 💸 Budget Planner
# =========================================================

@borrower_bp.route("/budget", methods=["GET", "POST"])
@role_required("borrower")
def budget():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()

    if request.method == "POST":
        expenses = request.form.to_dict()
        ai_tip = assistant.generate_reply(
            f"Analyze borrower {borrower.full_name}'s expenses: {expenses}",
            "borrower_budget",
        )
        return render_template(
            "borrower/budget_result.html",
            borrower=borrower,
            ai_tip=ai_tip,
            title="Budget Plan Results",
        )

    return render_template(
        "borrower/budget.html",
        borrower=borrower,
        title="Budget Planner",
    )


# =========================================================
# 📄 Conditions AI Helper
# =========================================================
@borrower_bp.route("/conditions")
@role_required("borrower")
def conditions():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()

    loan = LoanApplication.query.filter_by(
        borrower_profile_id=borrower.id,
        is_active=True
    ).first()

    conditions = []
    if loan:
        conditions = UnderwritingCondition.query.filter_by(
            borrower_profile_id=borrower.id,
            loan_id=loan.id
        ).all()

    # AI summary
    assistant = AIAssistant()
    ai_summary = assistant.generate_reply(
        f"Summarize the borrower’s {len(conditions)} underwriting conditions and highlight what is still required.",
        "borrower_conditions"
    )

    return render_template(
        "borrower/conditions.html",
        borrower=borrower,
        loan=loan,
        conditions=conditions,
        ai_summary=ai_summary,
        title="Conditions",
        active_tab="conditions"
    )

@borrower_bp.route("/condition/<int:cond_id>")
@role_required("borrower")
def view_condition(cond_id):
    cond = UnderwritingCondition.query.get_or_404(cond_id)
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()

    return render_template(
        "borrower/condition_view.html",
        condition=cond,
        borrower=borrower,
        title="Condition Detail",
        active_tab="conditions"
    )

@borrower_bp.route("/condition/<int:cond_id>/history")
@role_required("borrower")
def condition_history(cond_id):
    cond = UnderwritingCondition.query.get_or_404(cond_id)
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()

    history = []

    if cond.created_at:
        history.append({
            "timestamp": cond.created_at,
            "text": "Condition created"
        })

    if cond.file_path:
        history.append({
            "timestamp": cond.updated_at or cond.created_at,
            "text": "Document uploaded"
        })

    if cond.status.lower() == "submitted":
        history.append({
            "timestamp": cond.updated_at or cond.created_at,
            "text": "Document submitted"
        })

    if cond.status.lower() == "cleared":
        history.append({
            "timestamp": cond.updated_at or cond.created_at,
            "text": "Condition cleared"
        })

    history.sort(key=lambda x: x["timestamp"], reverse=True)

    return render_template(
        "borrower/condition_history.html",
        borrower=borrower,
        condition=cond,
        history=history,
        title="Condition History",
        active_tab="conditions"
    )

@borrower_bp.route("/conditions/ai/<int:condition_id>")
@role_required("borrower")
def borrower_condition_ai(condition_id):
    cond = UnderwritingCondition.query.get_or_404(condition_id)

    ai_msg = master_ai.ask(
        f"""
        Explain this underwriting condition to a borrower in simple terms:

        Condition: {cond.condition_type}
        Description: {cond.description}
        Severity: {cond.severity}
        """,
        role="underwriter",
    )

    return {"reply": ai_msg}

@borrower_bp.route("/conditions/upload/<int:cond_id>", methods=["POST"])
@role_required("borrower")
def upload_condition(cond_id):
    cond = UnderwritingCondition.query.get_or_404(cond_id)
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()

    # Security check
    if cond.borrower_profile_id != borrower.id:
        return "Unauthorized", 403

    file = request.files.get("file")
    if not file:
        return "No file uploaded", 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    cond.status = "submitted"
    cond.file_path = filename
    db.session.commit()

    # Redirect back to the loan-specific conditions page
    return redirect("/borrower/conditions")

# =========================================================
# ✍️ E‑Sign
# =========================================================

def add_signature_to_pdf(input_path, signature_image_path, output_path):
    # Placeholder: implement your PDF signing logic here
    # or move this into a dedicated PDF service.
    pass


@borrower_bp.route("/esign")
@role_required("borrower")
def borrower_esign():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    docs = ESignedDocument.query.filter_by(borrower_profile_id=borrower.id).all()

    return render_template(
        "borrower/esign.html",
        borrower=borrower,
        docs=docs,
    )


@borrower_bp.route("/esign/sign/<int:doc_id>", methods=["POST"])
@role_required("borrower")
def borrower_esign_sign(doc_id):
    doc = ESignedDocument.query.get_or_404(doc_id)

    signature_data = request.form.get("signature_data")
    signature_image_path = f"signatures/sign_{doc_id}.png"

    if signature_data:
        header, encoded = signature_data.split(",", 1)
        img_bytes = base64.b64decode(encoded)
        os.makedirs(os.path.dirname(signature_image_path), exist_ok=True)
        with open(signature_image_path, "wb") as f:
            f.write(img_bytes)

    signed_path = f"signed_docs/{doc_id}_signed.pdf"
    os.makedirs(os.path.dirname(signed_path), exist_ok=True)
    add_signature_to_pdf(doc.file_path, signature_image_path, signed_path)

    doc.file_path = signed_path
    doc.status = "Signed"
    db.session.commit()

    loan_doc = LoanDocument(
        borrower_profile_id=doc.borrower_profile_id,
        name=f"{doc.name} (Signed)",
        file_path=signed_path,
        status="Uploaded",
        uploaded_at=datetime.datetime.utcnow(),
    )
    db.session.add(loan_doc)
    db.session.commit()

    return redirect(url_for("borrower.borrower_esign"))


# =========================================================
# 💳 Payments
# =========================================================

@borrower_bp.route("/payments")
@role_required("borrower")
def payments():
    # Get the user
    user = current_user

    # Subscription info (if you store it on the user or borrower profile)
    subscription_plan = getattr(user, "subscription_plan", "Free")

    # Payment history (subscription payments only)
    payments = (
        PaymentRecord.query
        .filter_by(user_id=user.id)
        .order_by(PaymentRecord.timestamp.desc())
        .all()
    )


    return render_template(
        "borrower/payments.html",
        user=user,
        subscription_plan=subscription_plan,
        payments=payments
    )



@borrower_bp.route("/payments/checkout/<int:payment_id>")
@role_required("borrower")
def checkout(payment_id):
    payment = PaymentRecord.query.get_or_404(payment_id)
    borrower = payment.borrower

    checkout_session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": payment.payment_type},
                    "unit_amount": int(payment.amount * 100),
                },
                "quantity": 1,
            }
        ],
        mode="payment",
        success_url="http://localhost:5050/borrower/payments/success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="http://localhost:5050/borrower/payments",
        metadata={
            "payment_id": payment.id,
            "borrower_id": borrower.id,
        },
    )

    payment.stripe_payment_intent = checkout_session.payment_intent
    db.session.commit()

    return redirect(checkout_session.url, code=303)


@borrower_bp.route("/payments/success")
@role_required("borrower")
def payment_success():
    session_id = request.args.get("session_id")

    if not session_id:
        flash("Payment session missing.", "warning")
        return redirect(url_for("borrower.payments"))

    try:
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        payment_intent = checkout_session.get("payment_intent")
    except Exception as e:
        print("Stripe error:", e)
        flash("Unable to verify payment.", "danger")
        return redirect(url_for("borrower.payments"))

    payment = PaymentRecord.query.filter_by(
        stripe_payment_intent=payment_intent
    ).first()

    if not payment:
        flash("Payment record not found.", "warning")
        return redirect(url_for("borrower.payments"))

    payment.status = "Paid"
    payment.paid_at = datetime.datetime.utcnow()
    db.session.commit()

    receipt_dir = "stripe_receipts"
    os.makedirs(receipt_dir, exist_ok=True)

    receipt_path = os.path.join(receipt_dir, f"{payment.id}_receipt.txt")
    with open(receipt_path, "w") as f:
        f.write(f"Payment of ${payment.amount} received for {payment.payment_type}.")

    doc = LoanDocument(
        borrower_profile_id=payment.borrower_profile_id,
        loan_application_id=payment.loan_id,
        name=f"{payment.payment_type} Receipt",
        file_path=receipt_path,
        doc_type="Receipt",
        status="Uploaded",
        uploaded_at=datetime.datetime.utcnow(),
    )

    db.session.add(doc)
    db.session.commit()

    return render_template(
        "borrower/payment_success.html",
        payment=payment,
    )

@borrower_bp.route("/market")
@role_required("borrower")
def market_snapshot_page():
    borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if not borrower:
        return redirect(url_for("borrower.dashboard"))

    # If they have an active property, use its ZIP
    active_property = SavedProperty.query.filter_by(
        borrower_profile_id=borrower.id
    ).order_by(SavedProperty.created_at.desc()).first()

    zipcode = active_property.zipcode if active_property else None

    market_snapshot = None
    if zipcode:
        market_snapshot = get_market_snapshot(zipcode)

    return render_template(
        "borrower/market_snapshot.html",
        borrower=borrower,
        active_property=active_property,
        market_snapshot=market_snapshot,
    )
