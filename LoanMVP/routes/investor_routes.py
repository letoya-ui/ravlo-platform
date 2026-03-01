# =========================================================
# 🏛 RAVLO — INVESTOR OPERATING SYSTEM (Unified Routes)
# - New: /investor/*
# - Legacy compatible: /borrower/*
# =========================================================

import os
import io
import json
import uuid
import base64
import requests
from datetime import datetime
from io import BytesIO

from PIL import Image
from werkzeug.utils import secure_filename
from werkzeug.datastructures import ImmutableMultiDict
from sqlalchemy.exc import SQLAlchemyError

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
    session,
    abort,
)

from flask_login import current_user

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import LETTER

from LoanMVP.extensions import db, stripe
from LoanMVP.utils.decorators import role_required

# -------------------------
# Models (as you have them)
# -------------------------
from LoanMVP.models.activity_models import BorrowerActivity
from LoanMVP.models.loan_models import LoanApplication, BorrowerProfile, LoanQuote
from LoanMVP.models.document_models import (
    LoanDocument,
    DocumentRequest,
    ESignedDocument,
    ResourceDocument
)
from LoanMVP.models.crm_models import Message, Partner
from LoanMVP.models.payment_models import PaymentRecord
from LoanMVP.models.ai_models import AIAssistantInteraction
from LoanMVP.models.property import SavedProperty
from LoanMVP.models.underwriter_model import UnderwritingCondition
from LoanMVP.models.borrowers import (
    PropertyAnalysis,
    ProjectBudget,
    SubscriptionPlan,
    ProjectExpense,
    BorrowerMessage,
    BorrowerInteraction,
    Deal,
    DealShare,
)
from LoanMVP.models.loan_officer_model import LoanOfficerProfile
from LoanMVP.models.renovation_models import RenovationMockup
from LoanMVP.models.partner_models import PartnerConnectionRequest

# -------------------------
# AI / Assistants
# -------------------------
from LoanMVP.ai.master_ai import master_ai
from LoanMVP.ai.base_ai import AIAssistant
from LoanMVP.ai.master_ai import CMAIEngine  # if you use it

# -------------------------
# Services (as in your code)
# -------------------------
from LoanMVP.services.market_service import get_market_snapshot
from LoanMVP.services.comps_service import get_saved_property_comps
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
from LoanMVP.services.unified_resolver import resolve_property_unified
from LoanMVP.services.property_tool import search_deals_for_zip
from LoanMVP.services.notification_service import notify_team_on_conversion
from LoanMVP.utils.r2_storage import r2_put_bytes

# ---------------------------------------------------------
# Blueprints
# ---------------------------------------------------------
investor_bp = Blueprint("investor", __name__, url_prefix="/investor")

# legacy prefix stays alive for testers + old templates
borrower_bp = Blueprint("borrower", __name__, url_prefix="/borrower")


# ---------------------------------------------------------
# Route helper: register same handler on both blueprints
# ---------------------------------------------------------
def dual_route(rule, **options):
    """
    Decorator to register one function on both:
      /investor/<rule> and /borrower/<rule>
    """
    def decorator(fn):
        investor_bp.route(rule, **options)(fn)
        borrower_bp.route(rule, **options)(fn)
        return fn
    return decorator


# =========================================================
# Helpers
# =========================================================
def safe_float(v, default=0.0):
    try:
        if v in (None, "", "None"):
            return default
        return float(v)
    except Exception:
        return default

def _safe_json_loads(s, default=None):
    if default is None:
        default = {}
    if not s:
        return default
    try:
        if isinstance(s, (dict, list)):
            return s
        return json.loads(s)
    except Exception:
        return default

def _fmt_money(v):
    try:
        if v in (None, "", "None"):
            return "—"
        return f"${float(v):,.2f}"
    except Exception:
        return "—"

def _safe_int(v, default=2, min_v=1, max_v=4):
    try:
        x = int(v)
        return max(min_v, min(max_v, x))
    except Exception:
        return default

def _split_ids(csv: str):
    out = []
    for p in (csv or "").replace(";", ",").split(","):
        p = p.strip()
        if not p:
            continue
        try:
            out.append(int(p))
        except Exception:
            pass
    seen = set()
    final = []
    for i in out:
        if i not in seen:
            seen.add(i)
            final.append(i)
    return final

def _download_image_bytes(url: str, timeout=15) -> bytes:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.content

def _to_png_bytes(img_bytes: bytes, max_size=1024) -> bytes:
    im = Image.open(BytesIO(img_bytes)).convert("RGB")
    im.thumbnail((max_size, max_size))
    out = BytesIO()
    im.save(out, format="PNG", optimize=True)
    return out.getvalue()

def _to_webp_bytes(img_bytes: bytes, max_size=1400, quality=86) -> bytes:
    im = Image.open(BytesIO(img_bytes)).convert("RGB")
    im.thumbnail((max_size, max_size))
    out = BytesIO()
    im.save(out, format="WEBP", quality=int(quality), method=6)
    return out.getvalue()


# =========================================================
# Timeline (your original)
# =========================================================
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
# 🏛 COMMAND CENTER + DASHBOARD
# =========================================================
@dual_route("/command", methods=["GET"])
@dual_route("/dashboard", methods=["GET"])  # legacy
@role_required("borrower")
def command_center():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()

    loans = []
    loan = None
    conditions = []
    doc_requests = []
    saved_props = []

    primary_stage = None
    assistant = AIAssistant()
    next_step_ai = None

    if bp:
        saved_props = SavedProperty.query.filter_by(
            borrower_profile_id=bp.id
        ).order_by(SavedProperty.created_at.desc()).all()

        loans = LoanApplication.query.filter_by(
            borrower_profile_id=bp.id
        ).order_by(LoanApplication.created_at.desc()).all()

        loan = LoanApplication.query.filter_by(
            borrower_profile_id=bp.id,
            is_active=True
        ).first()

        doc_requests = LoanDocument.query.filter_by(
            borrower_profile_id=bp.id
        ).order_by(LoanDocument.created_at.desc()).all()

        if loan:
            conditions = UnderwritingCondition.query.filter_by(
                borrower_profile_id=bp.id,
                loan_id=loan.id
            ).order_by(UnderwritingCondition.created_at.desc()).all()

            primary_stage = getattr(loan, "status", None) or "Application"

            pending_conditions = [
                c for c in conditions
                if (c.status or "").lower() not in ["submitted", "cleared", "completed"]
            ]
            if pending_conditions:
                next_step_text = (
                    f"You have {len(pending_conditions)} pending conditions. "
                    f"Next item: {pending_conditions[0].description}."
                )
            else:
                next_step_text = "All conditions are in. Waiting on lender review."
        else:
            next_step_text = "No active capital request. Start a new loan application when ready."

        try:
            next_step_ai = assistant.generate_reply(
                f"Create a calm, professional investor-facing next step message: {next_step_text}",
                "borrower_next_step"
            )
        except Exception:
            next_step_ai = "Next step guidance is unavailable right now."

    progress_percent = 0
    if loan:
        total_conditions = len(conditions)
        cleared_conditions = len([c for c in conditions if (c.status or "").lower() == "cleared"])
        if total_conditions > 0:
            progress_percent = int((cleared_conditions / total_conditions) * 100)

    snapshot = {
        "loan_type": getattr(loan, "loan_type", None) if loan else None,
        "amount": getattr(loan, "amount", None) if loan else None,
        "status": getattr(loan, "status", None) if loan else None,
        "address": getattr(loan, "property_address", None) if loan else None,
        "progress_percent": progress_percent,
    }

    now_str = datetime.now().strftime("%b %d, %Y • %I:%M %p")

    return render_template(
        "borrower/dashboard.html",  # keep path until you migrate to investor/
        borrower=bp,
        loans=loans,
        loan=loan,
        conditions=conditions,
        doc_requests=doc_requests,
        saved_props=saved_props,
        snapshot=snapshot,
        next_step_ai=next_step_ai,
        primary_stage=primary_stage,
        now_str=now_str,
        active_tab="command",
        title="RAVLO Command Center"
    )

@dual_route("/dismiss_dashboard_tour", methods=["POST"])
@role_required("borrower")
def dismiss_dashboard_tour():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if bp:
        bp.has_seen_dashboard_tour = True
        db.session.commit()
    return jsonify({"status": "ok"})


# =========================================================
# 👤 ACCOUNT (profile/settings/privacy/notifications)
# =========================================================
@dual_route("/profile", methods=["GET"])
@role_required("borrower")
def profile():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    return render_template("borrower/profile.html", borrower=bp)

@dual_route("/settings", methods=["GET", "POST"])
@role_required("borrower")
def settings():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if request.method == "POST":
        current_user.first_name = request.form.get("first_name")
        current_user.last_name = request.form.get("last_name")
        current_user.email = request.form.get("email")
        db.session.commit()
        flash("Settings updated successfully.", "success")
        return redirect(url_for("borrower.settings"))
    return render_template("borrower/settings.html", borrower=bp)

@dual_route("/privacy", methods=["GET", "POST"])
@role_required("borrower")
def privacy():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if bp and request.method == "POST":
        bp.subscription_plan = request.form.get("subscription_plan")
        db.session.commit()
        flash("Privacy preferences updated.", "success")
        return redirect(url_for("borrower.privacy"))
    return render_template("borrower/privacy.html", borrower=bp)

@dual_route("/notifications-settings", methods=["GET", "POST"])
@role_required("borrower")
def notifications_settings():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if bp and request.method == "POST":
        bp.email_notifications = True if request.form.get("email_notifications") else False
        bp.sms_notifications = True if request.form.get("sms_notifications") else False
        db.session.commit()
        flash("Notification settings updated.", "success")
        return redirect(url_for("borrower.notifications_settings"))
    return render_template("borrower/notifications_settings.html", borrower=bp)


# =========================================================
# 🧾 PROFILE CREATE/UPDATE
# =========================================================
@dual_route("/create_profile", methods=["GET", "POST"])
@role_required("borrower")
def create_profile():
    from LoanMVP.forms import BorrowerProfileForm
    form = BorrowerProfileForm()

    if form.validate_on_submit():
        bp = BorrowerProfile(
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
        db.session.add(bp)
        db.session.commit()
        flash("✅ Profile created successfully!", "success")
        return redirect(url_for("borrower.command_center"))
    return render_template("borrower/create_profile.html", form=form, title="Create Profile")

@dual_route("/update_profile", methods=["POST"])
@role_required("borrower")
def update_profile():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if not bp:
        return jsonify({"status": "error", "message": "Profile not found."}), 404

    for field, value in request.form.items():
        if hasattr(bp, field) and value.strip():
            setattr(bp, field, value)
    bp.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"status": "success", "message": "Profile updated successfully."})


# =========================================================
# 📝 LOAN APPLICATION + STATUS
# =========================================================
@dual_route("/capital/apply", methods=["GET", "POST"])
@dual_route("/apply", methods=["GET", "POST"])
@role_required("borrower")
def apply():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if not bp:
        flash("Please create your profile before applying for capital.", "warning")
        return redirect(url_for("borrower.create_profile"))

    assistant = AIAssistant()

    if request.method == "POST":
        loan_type = request.form.get("loan_type")
        amount = safe_float(request.form.get("amount"))
        property_address = request.form.get("property_address")

        try:
            ai_summary = assistant.generate_reply(
                f"Create a short investor-facing loan application summary for {bp.full_name} "
                f"for a {loan_type} at {property_address}.",
                "borrower_apply",
            )
        except Exception:
            ai_summary = None

        loan = LoanApplication(
            borrower_profile_id=bp.id,
            loan_type=loan_type,
            loan_amount=amount,
            property_address=property_address,
            ai_summary=ai_summary,
            created_at=datetime.utcnow(),
            status="Submitted",
            is_active=True
        )
        db.session.add(loan)
        db.session.commit()
        flash("✅ Application submitted successfully!", "success")
        return redirect(url_for("borrower.status"))

    return render_template("borrower/apply.html", borrower=bp, title="Apply for Capital")

@dual_route("/capital/status", methods=["GET"])
@dual_route("/status", methods=["GET"])
@role_required("borrower")
def status():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if not bp:
        flash("Please complete your profile first.", "warning")
        return redirect(url_for("borrower.create_profile"))

    loans = LoanApplication.query.filter_by(borrower_profile_id=bp.id).all()
    documents = LoanDocument.query.filter_by(borrower_profile_id=bp.id).all()

    stats = {
        "total_loans": len(loans),
        "pending_docs": len([d for d in documents if (d.status or "").lower() in ["pending", "uploaded"]]),
        "verified_docs": len([d for d in documents if (d.status or "").lower() == "verified"]),
        "active_loans": len([l for l in loans if (l.status or "").lower() in ["active", "processing"]]),
        "completed_loans": len([l for l in loans if (l.status or "").lower() in ["closed", "funded"]]),
    }

    assistant = AIAssistant()
    try:
        ai_summary = assistant.generate_reply(
            f"Summarize investor capital status for {bp.full_name} with: {stats}",
            "borrower_status",
        )
    except Exception:
        ai_summary = "⚠️ AI summary unavailable."

    return render_template(
        "borrower/status.html",
        borrower=bp,
        loans=loans,
        documents=documents,
        stats=stats,
        ai_summary=ai_summary,
        title="Capital Status",
    )


# =========================================================
# 📄 LOAN VIEW / EDIT (security-safe)
# =========================================================
@dual_route("/capital/loan/<int:loan_id>", methods=["GET"])
@dual_route("/loan/<int:loan_id>", methods=["GET"])
@role_required("borrower")
def loan_view(loan_id):
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    loan = LoanApplication.query.get_or_404(loan_id)

    if not bp or loan.borrower_profile_id != bp.id:
        return "Unauthorized", 403

    conditions = UnderwritingCondition.query.filter_by(
        borrower_profile_id=bp.id,
        loan_id=loan.id
    ).all()

    assistant = AIAssistant()
    try:
        ai_summary = assistant.generate_reply(
            f"Summarize {len(conditions)} underwriting conditions for investor {bp.full_name}.",
            "loan_conditions",
        )
    except Exception:
        ai_summary = None

    return render_template(
        "borrower/view_loan.html",
        borrower=bp,
        loan=loan,
        conditions=conditions,
        ai_summary=ai_summary,
        active_tab="capital",
        title=f"Loan #{loan.id}",
    )

@dual_route("/capital/loan/<int:loan_id>/edit", methods=["GET", "POST"])
@dual_route("/loan/<int:loan_id>/edit", methods=["GET", "POST"])
@role_required("borrower")
def edit_loan(loan_id):
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    loan = LoanApplication.query.get_or_404(loan_id)

    if not bp or loan.borrower_profile_id != bp.id:
        return "Unauthorized", 403

    if request.method == "POST":
        loan.loan_amount = safe_float(request.form.get("amount"))
        loan.status = request.form.get("status")
        loan.loan_type = request.form.get("loan_type")
        loan.property_address = request.form.get("property_address")
        loan.interest_rate = safe_float(request.form.get("interest_rate"))
        loan.term = request.form.get("term")
        db.session.commit()
        flash("✅ Loan updated successfully!", "success")
        return redirect(url_for("borrower.loan_view", loan_id=loan.id))

    return render_template("borrower/edit_loan.html", loan=loan, borrower=bp, title="Edit Loan")


# =========================================================
# 💰 QUOTES + CONVERSION
# =========================================================
@dual_route("/capital/quote", methods=["GET", "POST"])
@dual_route("/quote", methods=["GET", "POST"])
@role_required("borrower")
def quote():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if not bp:
        flash("Please complete your profile before requesting a quote.", "warning")
        return redirect(url_for("borrower.create_profile"))

    assistant = AIAssistant()

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
                f"Generate up to 3 competitive loan quotes for an investor requesting "
                f"${loan_amount:,.0f} on a property valued at ${property_value:,.0f} "
                f"({ltv:.1f}% LTV). Loan type: {loan_type}, category: {loan_category}, "
                f"credit score {fico_score}, experience: {experience}. "
                f"Suggest lenders, estimated rates, and short commentary."
            )
            ai_suggestion = assistant.generate_reply(prompt, "borrower_quote")
        except Exception:
            ai_suggestion = "⚠️ AI system unavailable. Displaying mock results."

        mock_lenders = [
            {"lender_name": "Lima One Capital", "rate": 6.20, "loan_type": "30-Year Fixed", "deal_type": "Conventional"},
            {"lender_name": "RCN Capital", "rate": 6.05, "loan_type": "FHA 30-Year", "deal_type": "Residential"},
            {"lender_name": "LendingOne", "rate": 5.90, "loan_type": "5/1 ARM", "deal_type": "Hybrid"},
        ]

        for lender in mock_lenders:
            db.session.add(LoanQuote(
                borrower_profile_id=bp.id,
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
            ))
        db.session.commit()

        flash("✅ Loan quotes generated successfully!", "success")

        return render_template(
            "borrower/quote_results.html",
            borrower=bp,
            lenders=mock_lenders,
            property_address=property_address,
            property_value=property_value,
            loan_amount=loan_amount,
            fico_score=fico_score,
            ltv=ltv,
            ai_response=ai_suggestion,
            title="Loan Quote Results",
        )

    return render_template("borrower/quote.html", borrower=bp, title="Get a Loan Quote")


@dual_route("/capital/quote/convert/<int:quote_id>", methods=["POST"])
@dual_route("/quote/convert/<int:quote_id>", methods=["POST"])
@role_required("borrower")
def convert_quote_to_application(quote_id):
    quote = LoanQuote.query.get_or_404(quote_id)
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if not bp:
        flash("Please complete your profile before applying.", "warning")
        return redirect(url_for("borrower.create_profile"))

    existing_app = LoanApplication.query.filter_by(
        borrower_profile_id=bp.id,
        loan_amount=quote.loan_amount,
        property_address=quote.property_address,
    ).first()

    if existing_app:
        flash("This quote has already been converted.", "info")
        return redirect(url_for("borrower.status"))

    new_app = LoanApplication(
        borrower_profile_id=bp.id,
        loan_amount=quote.loan_amount,
        property_address=quote.property_address,
        loan_type=quote.loan_type,
        status="submitted",
        created_at=datetime.utcnow(),
        is_active=True
    )
    db.session.add(new_app)
    db.session.flush()

    quote.loan_application_id = new_app.id
    quote.status = "converted"
    db.session.add(quote)

    db.session.add(BorrowerActivity(
        borrower_profile_id=bp.id,
        category="Loan Conversion",
        description=f"Converted quote #{quote.id} into loan application #{new_app.id}.",
        timestamp=datetime.utcnow(),
    ))

    msg = (
        f"📢 Investor {bp.full_name} converted quote #{quote.id} into "
        f"Loan Application #{new_app.id} for {quote.property_address or 'a new property'}."
    )

    db.session.add(Message(
        sender_id=current_user.id,
        receiver_id=getattr(quote, "assigned_officer_id", None),
        content=msg,
        created_at=datetime.utcnow(),
        system_generated=True,
    ))

    db.session.commit()

    try:
        notify_team_on_conversion(bp, quote, new_app)
    except Exception as e:
        print("Notification error:", e)

    flash("🎯 Quote converted and team notified!", "success")
    return redirect(url_for("borrower.status"))


@dual_route("/ai/quote", methods=["POST"])
@dual_route("/get_quote_ai", methods=["POST"])
@role_required("borrower")
def get_quote_ai():
    ai = CMAIEngine()
    data = request.json or {}

    msg = f"""
    Investor is requesting a loan quote.

    Loan Amount: {data.get('amount')}
    Property Value: {data.get('value')}
    Credit Score: {data.get('credit')}
    Purpose: {data.get('purpose')}
    Notes: {data.get('notes','')}
    """

    # If your engine uses generate_reply instead, swap here.
    ai_reply = getattr(ai, "generate", None)(msg, role="borrower") if getattr(ai, "generate", None) else ai.generate_reply(msg, role="borrower")

    return jsonify({"quote": ai_reply})


# =========================================================
# 📁 DOCUMENTS + REQUESTS
# =========================================================
@dual_route("/documents", methods=["GET"])
@role_required("borrower")
def documents():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    docs = LoanDocument.query.filter_by(borrower_profile_id=bp.id).all() if bp else []
    assistant = AIAssistant()
    ai_summary = assistant.generate_reply(
        f"Summarize the investor’s {len(docs)} uploaded documents and highlight missing items.",
        "borrower_documents"
    )
    return render_template("borrower/documents.html", borrower=bp, documents=docs, ai_summary=ai_summary, title="Documents", active_tab="documents")

@dual_route("/document_requests", methods=["GET"])
@role_required("borrower")
def document_requests():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if not bp:
        return redirect(url_for("borrower.create_profile"))

    doc_requests = DocumentRequest.query.filter_by(borrower_id=bp.id).all()

    conditions = UnderwritingCondition.query.filter_by(
        borrower_profile_id=bp.id,
        loan_id=getattr(bp, "active_loan_id", None)
    ).all()

    unified = []
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

    for cond in conditions:
        unified.append({
            "id": cond.id,
            "type": "condition",
            "document_name": cond.description,
            "requested_by": cond.requested_by or "Processor",
            "notes": getattr(cond, "notes", None),
            "status": cond.status,
            "file_path": cond.file_path
        })

    assistant = AIAssistant()
    ai_summary = assistant.generate_reply(
        f"List {len(unified)} outstanding document requests/conditions for investor {bp.full_name}.",
        "document_requests",
    )

    return render_template("borrower/document_requests.html", borrower=bp, requests=unified, ai_summary=ai_summary, title="Document Requests")


@dual_route("/upload_document", methods=["GET", "POST"])
@role_required("borrower")
def upload_document():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if request.method == "POST":
        file = request.files.get("file")
        doc_type = request.form.get("doc_type")
        if file and bp:
            filename = secure_filename(file.filename)
            save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
            file.save(save_path)

            db.session.add(LoanDocument(
                borrower_profile_id=bp.id,
                file_path=filename,
                doc_type=doc_type,
                status="uploaded"
            ))
            db.session.commit()
            return redirect(url_for("borrower.documents"))

    return render_template("borrower/upload_document.html", borrower=bp, title="Upload Document", active_tab="documents")


@dual_route("/upload_request", methods=["GET", "POST"])
@role_required("borrower")
def upload_request():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    item_id = request.args.get("item_id")
    item_type = request.args.get("type")  # request|condition

    item = DocumentRequest.query.get(item_id) if item_type == "request" else UnderwritingCondition.query.get(item_id)

    if request.method == "POST":
        file = request.files.get("file")
        if file and bp:
            filename = secure_filename(file.filename)
            save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
            file.save(save_path)

            db.session.add(LoanDocument(
                borrower_profile_id=bp.id,
                file_path=filename,
                doc_type=getattr(item, "description", None) or getattr(item, "document_name", "Document"),
                status="submitted",
                request_id=item.id if item_type == "request" else None,
                condition_id=item.id if item_type == "condition" else None
            ))

            item.status = "submitted"
            db.session.commit()
            return redirect(url_for("borrower.document_requests"))

    return render_template("borrower/upload_request.html", borrower=bp, item=item, item_type=item_type, title="Upload Document", active_tab="documents")


@dual_route("/delete_document/<int:doc_id>", methods=["POST"])
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


# =========================================================
# ✅ CONDITIONS (capital requirements)
# =========================================================
@dual_route("/capital/conditions", methods=["GET"])
@dual_route("/conditions", methods=["GET"])
@role_required("borrower")
def conditions():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    loan = LoanApplication.query.filter_by(borrower_profile_id=bp.id, is_active=True).first() if bp else None

    conds = []
    if loan and bp:
        conds = UnderwritingCondition.query.filter_by(borrower_profile_id=bp.id, loan_id=loan.id).all()

    assistant = AIAssistant()
    ai_summary = assistant.generate_reply(
        f"Summarize {len(conds)} underwriting conditions and highlight what's still required.",
        "borrower_conditions"
    )

    return render_template("borrower/conditions.html", borrower=bp, loan=loan, conditions=conds, ai_summary=ai_summary, title="Conditions", active_tab="conditions")

@dual_route("/capital/conditions/<int:cond_id>", methods=["GET"])
@dual_route("/condition/<int:cond_id>", methods=["GET"])
@role_required("borrower")
def view_condition(cond_id):
    cond = UnderwritingCondition.query.get_or_404(cond_id)
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    # Basic ownership check
    if bp and cond.borrower_profile_id != bp.id:
        return "Unauthorized", 403
    return render_template("borrower/condition_view.html", condition=cond, borrower=bp, title="Condition Detail", active_tab="conditions")

@dual_route("/capital/conditions/<int:cond_id>/history", methods=["GET"])
@dual_route("/condition/<int:cond_id>/history", methods=["GET"])
@role_required("borrower")
def condition_history(cond_id):
    cond = UnderwritingCondition.query.get_or_404(cond_id)
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if bp and cond.borrower_profile_id != bp.id:
        return "Unauthorized", 403

    history = []
    if cond.created_at:
        history.append({"timestamp": cond.created_at, "text": "Condition created"})
    if cond.file_path:
        history.append({"timestamp": cond.updated_at or cond.created_at, "text": "Document uploaded"})
    if (cond.status or "").lower() == "submitted":
        history.append({"timestamp": cond.updated_at or cond.created_at, "text": "Document submitted"})
    if (cond.status or "").lower() == "cleared":
        history.append({"timestamp": cond.updated_at or cond.created_at, "text": "Condition cleared"})
    history.sort(key=lambda x: x["timestamp"], reverse=True)

    return render_template("borrower/condition_history.html", borrower=bp, condition=cond, history=history, title="Condition History", active_tab="conditions")

@dual_route("/conditions/ai/<int:condition_id>", methods=["GET"])
@role_required("borrower")
def borrower_condition_ai(condition_id):
    cond = UnderwritingCondition.query.get_or_404(condition_id)
    ai_msg = master_ai.ask(
        f"""
        Explain this underwriting condition to an investor in simple terms:

        Condition: {getattr(cond, 'condition_type', None)}
        Description: {cond.description}
        Severity: {getattr(cond, 'severity', None)}
        """,
        role="underwriter",
    )
    return {"reply": ai_msg}

@dual_route("/conditions/upload/<int:cond_id>", methods=["POST"])
@role_required("borrower")
def upload_condition(cond_id):
    cond = UnderwritingCondition.query.get_or_404(cond_id)
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if not bp or cond.borrower_profile_id != bp.id:
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

    return redirect(url_for("borrower.conditions"))


# =========================================================
# 🧠 PROPERTY INTELLIGENCE (search/saved/tool/apis)
# =========================================================
@dual_route("/intelligence", methods=["GET"])
@dual_route("/property_search", methods=["GET"])
@role_required("borrower")
def property_search():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
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
        p.setdefault("zip", p.get("zipcode") or p.get("zipCode") or p.get("postalCode"))
        p.setdefault("city", p.get("city") or p.get("locality"))
        p.setdefault("state", p.get("state") or p.get("region") or p.get("stateCode"))
        p.setdefault("address", p.get("address") or p.get("formattedAddress") or query)
        if p.get("price") is not None:
            try:
                p["price"] = float(p["price"])
            except Exception:
                pass
        if p.get("photos") in ({}, []):
            p["photos"] = None
        return p

    if query:
        resolved = resolve_property_unified(query)
        if resolved.get("status") == "ok":
            raw_prop = resolved.get("property") or {}
            property_data = normalize_property(raw_prop)

            valuation = raw_prop.get("valuation") or {}
            rent_estimate = raw_prop.get("rent_estimate") or raw_prop.get("rentEstimate") or {}
            comps = raw_prop.get("comps") or {}
            ai_summary = resolved.get("ai_summary") or resolved.get("summary") or None

            if bp and property_data.get("address"):
                try:
                    existing = SavedProperty.query.filter(
                        SavedProperty.borrower_profile_id == bp.id,
                        db.func.lower(SavedProperty.address) == property_data["address"].lower()
                    ).first()
                    if existing:
                        saved_id = existing.id
                except Exception:
                    saved_id = None
        else:
            error = resolved.get("error") or "unknown_error"
            debug = {"provider": resolved.get("provider"), "stage": resolved.get("stage")}

    return render_template(
        "borrower/property_search.html",
        borrower=bp,
        title="Property Intelligence",
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

@dual_route("/intelligence/save", methods=["POST"])
@dual_route("/save_property", methods=["POST"])
@role_required("borrower")
def save_property():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if not bp:
        return jsonify({"status": "error", "message": "Profile not found."}), 400

    raw_property_id = (request.form.get("property_id") or "").strip()
    raw_address = (request.form.get("address") or "").strip()
    raw_price = request.form.get("price")
    raw_zipcode = (request.form.get("zipcode") or "").strip() or None
    sqft_raw = request.form.get("sqft")

    if not raw_address:
        return jsonify({"status": "error", "message": "Address required."}), 400

    sqft = None
    try:
        if sqft_raw not in (None, "", "None"):
            sqft = int(float(sqft_raw))
    except Exception:
        sqft = None

    resolved = {}
    try:
        resolved = resolve_property_unified(raw_address)
    except Exception as e:
        print("SAVE_PROPERTY resolver error:", e)
        resolved = {}

    normalized_address = raw_address
    resolved_property_id = None

    if resolved.get("status") == "ok":
        p = resolved.get("property") or {}
        normalized_address = (p.get("address") or raw_address).strip()
        resolved_property_id = (p.get("property_id") or p.get("id") or p.get("propertyId"))
        resolved_property_id = str(resolved_property_id).strip() if resolved_property_id else None
        raw_zipcode = raw_zipcode or p.get("zip") or p.get("zipCode") or p.get("postalCode")
        if sqft is None:
            try:
                sqft_val = p.get("sqft") or p.get("squareFootage")
                sqft = int(float(sqft_val)) if sqft_val not in (None, "", "None") else None
            except Exception:
                sqft = None

    final_property_id = raw_property_id or resolved_property_id or None

    existing = None
    if final_property_id:
        existing = SavedProperty.query.filter_by(
            borrower_profile_id=bp.id,
            property_id=str(final_property_id)
        ).first()

    if not existing:
        existing = SavedProperty.query.filter(
            SavedProperty.borrower_profile_id == bp.id,
            db.func.lower(SavedProperty.address) == normalized_address.lower()
        ).first()

    if existing:
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

        if hasattr(existing, "resolved_json"):
            existing.resolved_json = json.dumps(resolved) if resolved else None
            existing.resolved_at = datetime.utcnow() if resolved else None

        db.session.commit()
        return jsonify({"status": "success", "message": "Already saved (updated details).", "saved_id": existing.id})

    saved = SavedProperty(
        borrower_profile_id=bp.id,
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

    return jsonify({"status": "success", "message": "Saved.", "saved_id": saved.id})


@dual_route("/intelligence/saved", methods=["GET"])
@dual_route("/saved_properties", methods=["GET"])
@role_required("borrower")
def saved_properties():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    props = SavedProperty.query.filter_by(borrower_profile_id=bp.id).all() if bp else []

    try:
        name = bp.full_name if bp else "this investor"
        ai_summary = AIAssistant().generate_reply(
            f"Summarize {len(props)} saved properties for {name}. Prioritize investment potential.",
            "saved_properties",
        )
    except Exception:
        ai_summary = "⚠️ AI summary unavailable."

    return render_template("borrower/saved_properties.html", borrower=bp, properties=props, ai_summary=ai_summary, title="Saved Properties")


@dual_route("/intelligence/saved/manage", methods=["POST"])
@dual_route("/saved_properties/manage", methods=["POST"])
@role_required("borrower")
def saved_properties_manage():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if not bp:
        flash("Profile not found.", "danger")
        return redirect(url_for("borrower.saved_properties"))

    prop_id = request.form.get("prop_id")
    action = request.form.get("action")
    notes = request.form.get("notes", "")

    try:
        prop_id = int(prop_id)
    except Exception:
        flash("Invalid property id.", "warning")
        return redirect(url_for("borrower.saved_properties"))

    prop = SavedProperty.query.filter_by(id=prop_id, borrower_profile_id=bp.id).first()
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


@dual_route("/intelligence/save-and-analyze", methods=["POST"])
@dual_route("/save_property_and_analyze", methods=["POST"])
@role_required("borrower")
def save_property_and_analyze():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if not bp:
        flash("Profile not found.", "danger")
        return redirect(url_for("borrower.property_search"))

    raw_address = (request.form.get("address") or "").strip()
    if not raw_address:
        flash("Address required.", "warning")
        return redirect(url_for("borrower.property_search"))

    zipcode = (request.form.get("zipcode") or "").strip() or None
    price = request.form.get("price")
    sqft_raw = request.form.get("sqft")

    sqft = None
    try:
        sqft = int(float(sqft_raw)) if sqft_raw not in (None, "", "None") else None
    except Exception:
        sqft = None

    resolved = {}
    normalized_address = raw_address
    resolved_property_id = None

    try:
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

        if (price in (None, "", "None")) and (p.get("price") is not None):
            try:
                price = str(p.get("price"))
            except Exception:
                pass

    form_pid = (request.form.get("property_id") or "").strip()
    final_property_id = form_pid or resolved_property_id or None
    final_property_id = str(final_property_id).strip() if final_property_id else None

    existing = None
    if final_property_id:
        existing = SavedProperty.query.filter_by(borrower_profile_id=bp.id, property_id=final_property_id).first()

    if not existing and normalized_address:
        existing = SavedProperty.query.filter(
            SavedProperty.borrower_profile_id == bp.id,
            db.func.lower(SavedProperty.address) == normalized_address.lower()
        ).first()

    if existing:
        flash("✅ Property already saved — opening Deal Studio.", "info")
        return redirect(url_for("borrower.deal_workspace", prop_id=existing.id, mode="flip"))

    saved = SavedProperty(
        borrower_profile_id=bp.id,
        property_id=final_property_id,
        address=normalized_address,
        price=str(price or ""),
        sqft=sqft,
        zipcode=zipcode,
        saved_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )
    db.session.add(saved)
    db.session.commit()

    flash("🏠 Property saved! Opening Deal Studio…", "success")
    return redirect(url_for("borrower.deal_workspace", prop_id=saved.id, mode="flip"))


@dual_route("/intelligence/saved/<int:prop_id>", methods=["GET"])
@dual_route("/property_explore_plus/<int:prop_id>", methods=["GET"])
@role_required("borrower")
def property_explore_plus(prop_id):
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if not bp:
        flash("Profile not found.", "danger")
        return redirect(url_for("borrower.property_search"))

    prop = SavedProperty.query.filter_by(id=prop_id, borrower_profile_id=bp.id).first()
    if not prop:
        flash("Property not found.", "danger")
        return redirect(url_for("borrower.property_search"))

    resolved = resolve_property_unified(prop.address)
    resolved_property = (resolved.get("property") or {}) if resolved.get("status") == "ok" else {}
    photos = resolved_property.get("photos") or []

    from LoanMVP.services.comps_service import get_comps_for_property
    comps = get_comps_for_property(address=prop.address, zipcode=(prop.zipcode or ""), rentometer_api_key=None)
    market = get_market_snapshot(zipcode=(prop.zipcode or "")) if prop.zipcode else {}

    ai_summary = resolved.get("ai_summary") or None

    return render_template(
        "borrower/property_explore_plus.html",
        borrower=bp,
        prop=prop,
        resolved=resolved_property,
        ai_summary=ai_summary,
        comps=comps,
        market=market,
        photos=photos,
        active_page="property_search",
    )


@dual_route("/intelligence/tool", methods=["GET"])
@dual_route("/property_tool", methods=["GET"])
@role_required("borrower")
def property_tool():
    return render_template("borrower/property_tool.html", active_page="property_tool")


@dual_route("/api/intelligence/zip-search", methods=["POST"])
@dual_route("/api/property_tool_search", methods=["POST"])
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


@dual_route("/api/intelligence/save", methods=["POST"])
@dual_route("/api/property_tool_save", methods=["POST"])
@role_required("borrower")
def api_property_tool_save():
    payload = request.get_json(force=True) or {}
    address = (payload.get("address") or "").strip()
    if not address:
        return jsonify({"status": "error", "message": "Address is required to save."}), 400

    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if not bp:
        return jsonify({"status": "error", "message": "Profile not found."}), 400

    zipcode = (payload.get("zip") or "").strip() or None
    price = payload.get("price")
    sqft = payload.get("sqft")
    property_id = payload.get("property_id")

    try:
        sqft = int(float(sqft)) if sqft not in (None, "", "None") else None
    except Exception:
        sqft = None

    existing = None
    if property_id:
        existing = SavedProperty.query.filter_by(borrower_profile_id=bp.id, property_id=str(property_id)).first()

    if not existing:
        existing = SavedProperty.query.filter(
            SavedProperty.borrower_profile_id == bp.id,
            db.func.lower(SavedProperty.address) == address.lower()
        ).first()

    if existing:
        return jsonify({"status": "ok", "message": "Already saved.", "saved_id": existing.id})

    saved = SavedProperty(
        borrower_profile_id=bp.id,
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

    return jsonify({"status": "ok", "message": "Saved.", "saved_id": saved.id})


@dual_route("/api/intelligence/save-and-analyze", methods=["POST"])
@dual_route("/api/property_tool_save_and_analyze", methods=["POST"])
@role_required("borrower")
def api_property_tool_save_and_analyze():
    payload = request.get_json(force=True) or {}
    address = (payload.get("address") or "").strip()
    if not address:
        return jsonify({"status": "error", "message": "Address is required to analyze."}), 400

    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if not bp:
        return jsonify({"status": "error", "message": "Profile not found."}), 400

    zipcode = (payload.get("zip") or "").strip() or None
    price = payload.get("price")
    sqft = payload.get("sqft")
    property_id = payload.get("property_id")

    try:
        sqft = int(float(sqft)) if sqft not in (None, "", "None") else None
    except Exception:
        sqft = None

    existing = None
    if property_id:
        existing = SavedProperty.query.filter_by(borrower_profile_id=bp.id, property_id=str(property_id)).first()

    if not existing:
        existing = SavedProperty.query.filter(
            SavedProperty.borrower_profile_id == bp.id,
            db.func.lower(SavedProperty.address) == address.lower()
        ).first()

    if not existing:
        existing = SavedProperty(
            borrower_profile_id=bp.id,
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
    return jsonify({"status": "ok", "saved_id": existing.id, "deal_url": deal_url})


# =========================================================
# 💼 DEAL STUDIO (workspace + deals + visualizer + exports)
# =========================================================
@dual_route("/deals/workspace", methods=["GET", "POST"])
@dual_route("/deal_workspace", methods=["GET", "POST"])
@role_required("borrower")
def deal_workspace():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if not bp:
        flash("Profile not found.", "danger")
        return redirect(url_for("borrower.command_center"))

    saved_props = (
        SavedProperty.query
        .filter_by(borrower_profile_id=bp.id)
        .order_by(SavedProperty.created_at.desc())
        .all()
    )

    prop_id = request.values.get("prop_id")
    selected_prop = None

    if prop_id:
        try:
            pid = int(prop_id)
            selected_prop = SavedProperty.query.filter_by(id=pid, borrower_profile_id=bp.id).first()
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

    if request.method == "POST" and not selected_prop:
        flash("Please select a saved property first.", "warning")
        return render_template(
            "borrower/deal_workspace.html",
            borrower=bp,
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

    if selected_prop:
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
        borrower=bp,
        saved_props=saved_props,
        selected_prop=selected_prop,
        prop_id=(selected_prop.id if selected_prop else None),
        property_id=(selected_prop.id if selected_prop else None),
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


@dual_route("/deals", methods=["GET"])
@dual_route("/deals/list", methods=["GET"])
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


@dual_route("/deals/<int:deal_id>", methods=["GET"])
@role_required("borrower")
def deal_detail(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first_or_404()

    mockups = (RenovationMockup.query
        .filter_by(deal_id=deal_id, user_id=current_user.id)
        .order_by(RenovationMockup.created_at.desc())
        .all())

    partners = Partner.query.filter_by(user_id=current_user.id).order_by(Partner.created_at.desc()).all()

    return render_template("borrower/deal_detail.html", deal=deal, mockups=mockups, partners=partners)


@dual_route("/deals/<int:deal_id>/design/select", methods=["POST"])
@dual_route("/deals/<int:deal_id>/select_design", methods=["POST"])
@role_required("borrower")
def deal_select_design(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first_or_404()
    after_url = (request.form.get("after_url") or "").strip()
    before_url = (request.form.get("before_url") or "").strip()

    if not after_url:
        return jsonify({"status": "error", "message": "Missing after_url."}), 400

    owned = RenovationMockup.query.filter_by(
        user_id=current_user.id,
        deal_id=deal_id,
        after_url=after_url
    ).first()

    if not owned:
        return jsonify({"status": "error", "message": "Design not found for this deal."}), 404

    deal.final_after_url = after_url
    if before_url:
        deal.final_before_url = before_url

    db.session.commit()
    return jsonify({"status": "ok"})


@dual_route("/deals/<int:deal_id>/design/share", methods=["POST"])
@dual_route("/deals/<int:deal_id>/share_design", methods=["POST"])
@role_required("borrower")
def deal_share_design(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first_or_404()

    image_url = (request.form.get("image_url") or "").strip() or (getattr(deal, "final_after_url", "") or "")
    partner_ids = _split_ids(request.form.get("partner_ids") or "")
    note = (request.form.get("note") or "").strip()

    if not image_url:
        return jsonify({"status": "error", "message": "Select a design first."}), 400
    if not partner_ids:
        return jsonify({"status": "error", "message": "Choose at least one partner."}), 400

    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    bp_id = bp.id if bp else None

    now = datetime.utcnow()
    partners = (Partner.query
        .filter(Partner.id.in_(partner_ids))
        .filter(Partner.active == True)
        .filter(Partner.approved == True)
        .filter(Partner.paid_until >= now)
        .all())

    if not partners:
        return jsonify({"status": "error", "message": "No valid partners selected (must be approved + active + paid)."}), 400

    deal_link = url_for("borrower.deal_detail", deal_id=deal.id, _external=True)
    reveal_link = url_for("borrower.deal_reveal", deal_id=deal.id, _external=True)

    sent = 0
    for p in partners:
        msg = (
            (note + "\n\n" if note else "") +
            f"Selected renovation design:\n{image_url}\n\n"
            f"Deal:\n{deal_link}\n"
            f"Reveal:\n{reveal_link}\n"
        )

        existing = PartnerConnectionRequest.query.filter_by(
            borrower_user_id=current_user.id,
            partner_id=p.id,
            status="pending"
        ).order_by(PartnerConnectionRequest.created_at.desc()).first()

        if existing and (existing.message or "").strip() == msg.strip():
            continue

        db.session.add(PartnerConnectionRequest(
            borrower_user_id=current_user.id,
            borrower_profile_id=bp_id,
            partner_id=p.id,
            category=p.category,
            message=msg,
            status="pending",
        ))
        sent += 1

    db.session.commit()
    return jsonify({"status": "ok", "sent": sent, "failed": 0})


@dual_route("/deals/save", methods=["POST"])
@dual_route("/deals/save_deal", methods=["POST"])
@role_required("borrower")
def save_deal():
    property_id = request.form.get("property_id") or None
    strategy = request.form.get("mode") or request.form.get("strategy") or None
    title = request.form.get("title") or None
    saved_property_id = request.form.get("saved_property_id") or None

    try:
        saved_property_id = int(saved_property_id) if saved_property_id else None
    except Exception:
        saved_property_id = None

    results_json = _safe_json_loads(request.form.get("results_json"), default={})
    inputs_json  = _safe_json_loads(request.form.get("inputs_json"), default={})
    comps_json    = _safe_json_loads(request.form.get("comps_json"), default={})
    resolved_json = _safe_json_loads(request.form.get("resolved_json"), default={})

    if not title:
        addr = None
        try:
            addr = resolved_json.get("property", {}).get("address")
        except Exception:
            addr = None
        title = addr or (property_id and f"Deal {property_id}") or "Saved Deal"

    deal = Deal(
        user_id=current_user.id,
        saved_property_id=saved_property_id,
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


@dual_route("/deals/<int:deal_id>/edit", methods=["POST"])
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


@dual_route("/deals/<int:deal_id>/delete", methods=["POST"])
@role_required("borrower")
def deal_delete(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first_or_404()
    db.session.delete(deal)
    db.session.commit()
    flash("Deal deleted.", "success")
    return redirect(url_for("borrower.deals_list"))


@dual_route("/deals/<int:deal_id>/open", methods=["GET"])
@role_required("borrower")
def deal_open(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first_or_404()
    if deal.saved_property_id:
        return redirect(url_for("borrower.deal_workspace", prop_id=deal.saved_property_id, mode=deal.strategy or "flip"))
    flash("This deal is not linked to a saved property yet.", "warning")
    return redirect(url_for("borrower.deal_workspace"))


@dual_route("/deals/<int:deal_id>/reveal", methods=["GET"])
@dual_route("/deal/<int:deal_id>/reveal", methods=["GET"])
@role_required("borrower")
def deal_reveal(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first_or_404()

    mockups = (RenovationMockup.query
        .filter_by(deal_id=deal_id, user_id=current_user.id)
        .order_by(RenovationMockup.created_at.desc())
        .all())

    if not mockups and getattr(deal, "saved_property_id", None):
        mockups = (RenovationMockup.query
            .filter_by(saved_property_id=deal.saved_property_id, user_id=current_user.id)
            .order_by(RenovationMockup.created_at.desc())
            .all())

    return render_template("borrower/deal_reveal.html", deal=deal, deal_id=deal_id, mockups=mockups)


@dual_route("/deals/visualizer", methods=["POST"])
@dual_route("/renovation_visualizer", methods=["POST"])
@role_required("borrower")
def renovation_visualizer():
    image_file = request.files.get("image_file")
    image_url = (request.form.get("image_url") or "").strip()

    style_prompt = (request.form.get("style_prompt") or "").strip()
    style_preset = (request.form.get("style_preset") or "").strip()
    variations = _safe_int(request.form.get("variations"), default=2, min_v=1, max_v=4)
    save_to_deal = (request.form.get("save_to_deal") or "").lower() in ("1", "true", "yes", "on")

    saved_property_id_raw = (request.form.get("saved_property_id") or request.form.get("prop_id") or "").strip()
    deal_id_raw = (request.form.get("deal_id") or "").strip()
    property_id = (request.form.get("property_id") or "").strip() or None

    if not image_file and not image_url:
        return jsonify({"status": "error", "message": "Provide image_file or image_url."}), 400
    if image_url.startswith("blob:"):
        return jsonify({"status": "error", "message": "Browser preview URL detected. Please upload the image file."}), 400
    if image_url and not (image_url.startswith("http://") or image_url.startswith("https://")):
        return jsonify({"status": "error", "message": "image_url must start with http:// or https://"}), 400
    if not style_prompt and not style_preset:
        return jsonify({"status": "error", "message": "Add a style prompt or choose a preset."}), 400

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

    saved_property_id = None
    if saved_property_id_raw:
        try: saved_property_id = int(saved_property_id_raw)
        except Exception: saved_property_id = None

    deal_id = None
    if deal_id_raw:
        try: deal_id = int(deal_id_raw)
        except Exception: deal_id = None

    try:
        raw = image_file.read() if image_file else _download_image_bytes(image_url)
        if not raw:
            return jsonify({"status": "error", "message": "Empty image input."}), 400

        before_webp = _to_webp_bytes(raw, max_size=1600, quality=86)
        before_up = r2_put_bytes(
            before_webp,
            subdir=f"visualizer/{current_user.id}/before",
            content_type="image/webp",
            filename=f"{uuid.uuid4().hex}_before.webp",
        )
        before_url = before_up["url"]

        # If you use OpenAI image editing, keep your existing client call here.
        # This route is left compatible with your prior implementation.
        return jsonify({
            "status": "ok",
            "before_url": before_url,
            "images": [],
            "note": "Wire your image generator call here (kept compatible)."
        })

    except requests.RequestException as e:
        return jsonify({"status": "error", "message": f"Could not download image: {e}"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": f"Renovation generator failed: {e}"}), 500


@dual_route("/deals/upload", methods=["POST"])
@dual_route("/renovation_upload", methods=["POST"])
@role_required("borrower")
def renovation_upload():
    f = request.files.get("photo") or request.files.get("image_file")
    if not f:
        return jsonify({"status": "error", "message": "No file uploaded."}), 400

    raw = f.read()
    if not raw:
        return jsonify({"status": "error", "message": "Empty upload."}), 400

    saved_property_id_raw = (request.form.get("saved_property_id") or request.form.get("prop_id") or "").strip()
    deal_id_raw = (request.form.get("deal_id") or "").strip()

    saved_property_id = None
    if saved_property_id_raw:
        try: saved_property_id = int(saved_property_id_raw)
        except Exception: saved_property_id = None

    deal_id = None
    if deal_id_raw:
        try: deal_id = int(deal_id_raw)
        except Exception: deal_id = None

    webp = _to_webp_bytes(raw, max_size=1600, quality=86)
    up = r2_put_bytes(
        webp,
        subdir=f"uploads/{current_user.id}/rooms",
        content_type="image/webp",
        filename=f"{uuid.uuid4().hex}.webp",
    )

    return jsonify({"status": "ok", "url": up["url"], "key": up["key"], "saved_property_id": saved_property_id, "deal_id": deal_id})


@dual_route("/deals/<int:deal_id>/mockups/save", methods=["POST"])
@dual_route("/deals/<int:deal_id>/mockups/save_legacy", methods=["POST"])
@role_required("borrower")
def save_renovation_mockups(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first_or_404()
    data = request.get_json(silent=True) or {}

    before_url = (data.get("before_url") or "").strip()
    images = data.get("images") or []
    preset = (data.get("preset") or "").strip()
    prompt = (data.get("prompt") or "").strip()

    if not images or not isinstance(images, list):
        return jsonify({"status": "error", "message": "No images provided."}), 400

    saved = 0
    for img in images[:8]:
        img = (img or "").strip()
        if not img:
            continue
        db.session.add(RenovationMockup(
            user_id=current_user.id,
            deal_id=deal.id,
            before_url=before_url or None,
            after_url=img,
            preset=preset or None,
            prompt=prompt or None,
        ))
        saved += 1

    db.session.commit()
    return jsonify({"status": "ok", "saved": saved})


@dual_route("/deals/send-to-team", methods=["POST"])
@dual_route("/deals/send-to-lo", methods=["POST"])
@role_required("borrower")
def send_to_team():
    property_id = request.form.get("property_id") or None
    strategy = request.form.get("mode") or request.form.get("strategy") or None
    title = request.form.get("title") or None
    note = (request.form.get("note") or "").strip() or None

    results_json = _safe_json_loads(request.form.get("results_json"), default={})
    comps_json = _safe_json_loads(request.form.get("comps_json"), default={})
    resolved_json = _safe_json_loads(request.form.get("resolved_json"), default={})

    if not title:
        addr = (resolved_json or {}).get("property", {}).get("address")
        title = addr or (property_id and f"Deal {property_id}") or "Deal Shared"

    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()

    lo_user_id = None
    if bp:
        if getattr(bp, "assigned_officer_id", None):
            lo_profile = LoanOfficerProfile.query.get(bp.assigned_officer_id)
            if lo_profile:
                lo_user_id = lo_profile.user_id

        if not lo_user_id and getattr(bp, "assigned_to", None):
            lo_user_id = bp.assigned_to

    if not lo_user_id:
        flash("No assigned Loan Officer found.", "warning")
        return redirect(url_for("borrower.deal_workspace", prop_id=property_id, mode=strategy))

    db.session.add(DealShare(
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
    ))
    db.session.commit()

    flash("Sent to your team.", "success")
    return redirect(url_for("borrower.deal_workspace", prop_id=property_id, mode=strategy))


@dual_route("/deals/<int:deal_id>/export/report", methods=["GET"])
@dual_route("/deals/<int:deal_id>/export-report", methods=["GET"])
@role_required("borrower")
def export_deal_report_pro(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first()
    if not deal:
        abort(404)

    r = deal.results_json or {}
    resolved = deal.resolved_json or {}

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER
    y = height - 50

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "RAVLO Deal Report")
    y -= 22

    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Title: {deal.title or '—'}"); y -= 14
    c.drawString(50, y, f"Property ID: {deal.property_id or '—'}"); y -= 14
    c.drawString(50, y, f"Strategy: {deal.strategy or '—'}"); y -= 14
    if deal.created_at:
        c.drawString(50, y, f"Created: {deal.created_at.strftime('%Y-%m-%d %H:%M')}"); y -= 22
    else:
        y -= 22

    prop = (resolved.get("property") or {}) if isinstance(resolved, dict) else {}
    addr = prop.get("address"); city = prop.get("city"); state = prop.get("state"); zipc = prop.get("zip")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Property Summary"); y -= 16
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Address: {addr or '—'}"); y -= 14
    c.drawString(50, y, f"City/State/Zip: {city or '—'}, {state or '—'} {zipc or ''}"); y -= 18

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Key Results"); y -= 16
    c.setFont("Helvetica", 10)

    if "profit" in r: c.drawString(50, y, f"Flip Profit: {_fmt_money(r.get('profit'))}"); y -= 14
    if "net_cashflow" in r: c.drawString(50, y, f"Rental Net Cashflow (mo): {_fmt_money(r.get('net_cashflow'))}"); y -= 14
    if "net_monthly" in r: c.drawString(50, y, f"Airbnb Net Monthly: {_fmt_money(r.get('net_monthly'))}"); y -= 14

    y -= 10

    rehab = r.get("rehab_summary") if isinstance(r, dict) else None
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Rehab Summary"); y -= 16
    c.setFont("Helvetica", 10)

    if isinstance(rehab, dict):
        c.drawString(50, y, f"Scope: {rehab.get('scope') or '—'}"); y -= 14
        c.drawString(50, y, f"Total Rehab: {_fmt_money(rehab.get('total'))}"); y -= 14
        c.drawString(50, y, f"Cost per Sqft: {_fmt_money(rehab.get('cost_per_sqft'))}"); y -= 14
    else:
        c.drawString(50, y, "No rehab summary available."); y -= 14

    c.showPage()
    c.save()

    buffer.seek(0)
    filename = f"ravlo_deal_report_{deal.id}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")


@dual_route("/deals/<int:deal_id>/export/rehab-scope", methods=["GET"])
@dual_route("/deals/<int:deal_id>/export-rehab-scope", methods=["GET"])
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
    c.drawString(50, y, "RAVLO Rehab Scope"); y -= 22

    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Deal: {deal.title or '—'}"); y -= 14
    c.drawString(50, y, f"Property ID: {deal.property_id or '—'}"); y -= 14
    c.drawString(50, y, f"Strategy: {deal.strategy or '—'}"); y -= 22

    if not isinstance(rehab, dict):
        c.drawString(50, y, "No rehab summary available for this deal.")
        c.showPage(); c.save()
        buffer.seek(0)
        filename = f"ravlo_rehab_scope_{deal.id}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
        return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")

    c.setFont("Helvetica-Bold", 12); c.drawString(50, y, "Summary"); y -= 16
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Scope: {rehab.get('scope') or '—'}"); y -= 14
    c.drawString(50, y, f"Total Rehab: {_fmt_money(rehab.get('total'))}"); y -= 14
    c.drawString(50, y, f"Cost per Sqft: {_fmt_money(rehab.get('cost_per_sqft'))}"); y -= 18

    items = rehab.get("items") or {}
    c.setFont("Helvetica-Bold", 12); c.drawString(50, y, "Selected Items"); y -= 16
    c.setFont("Helvetica", 10)

    if isinstance(items, dict) and items:
        for k, v in items.items():
            if y < 80:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 10)
            level = v.get("level") if isinstance(v, dict) else None
            cost = v.get("cost") if isinstance(v, dict) else None
            c.drawString(50, y, f"- {str(k).capitalize()}: {str(level).capitalize() if level else '—'} | {_fmt_money(cost)}")
            y -= 14
    else:
        c.drawString(50, y, "No item selections found.")
        y -= 14

    c.showPage(); c.save()
    buffer.seek(0)
    filename = f"ravlo_rehab_scope_{deal.id}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")


# =========================================================
# 💬 MESSAGES
# =========================================================
@dual_route("/messages", methods=["GET"])
@role_required("borrower")
def messages():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    from LoanMVP.models.user_model import User
    officers = User.query.filter(User.role.in_(["loan_officer", "processor", "underwriter"])).all()

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
        borrower=bp,
        officers=officers,
        messages=msgs,
        selected_receiver=receiver_id,
        title="Messages",
    )

@dual_route("/messages/send", methods=["POST"])
@role_required("borrower")
def send_message():
    content = request.form.get("content") or ""
    receiver_id = request.form.get("receiver_id")

    if not receiver_id or not content.strip():
        flash("⚠️ Please select a recipient and enter a message.", "warning")
        return redirect(url_for("borrower.messages"))

    db.session.add(Message(
        sender_id=current_user.id,
        receiver_id=int(receiver_id),
        content=content,
        created_at=datetime.utcnow(),
    ))
    db.session.commit()

    flash("📩 Message sent!", "success")
    return redirect(url_for("borrower.messages", receiver_id=receiver_id))


# =========================================================
# 🤖 AI HUB / ASK AI
# =========================================================
@dual_route("/ai", methods=["GET"])
@dual_route("/ask-ai", methods=["GET"])
@role_required("borrower")
def ask_ai_page():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    interactions = (AIAssistantInteraction.query
        .filter_by(user_id=current_user.id)
        .order_by(AIAssistantInteraction.timestamp.desc())
        .all())

    prefill = request.args.get("prefill", "")

    class DummyForm:
        def hidden_tag(self): return ""

    dummy_question = type("obj", (), {"data": prefill})()
    form = DummyForm()
    form.question = dummy_question
    form.submit = None

    return render_template(
        "borrower/ask_ai.html",
        borrower=bp,
        prefill=prefill,
        form=form,
        interactions=interactions,
        title="Ravlo AI",
    )

@dual_route("/ai", methods=["POST"])
@dual_route("/ask-ai", methods=["POST"])
@role_required("borrower")
def ask_ai_post():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    question = request.form.get("question") or ""
    parent_id = request.form.get("parent_id")

    assistant = AIAssistant()
    ai_reply = assistant.generate_reply(question, "borrower_ai")

    chat = AIAssistantInteraction(
        user_id=current_user.id,
        borrower_profile_id=bp.id if bp else None,
        question=question,
        response=ai_reply,
        parent_id=parent_id,
        timestamp=datetime.utcnow(),
    )
    db.session.add(chat)
    db.session.commit()

    next_steps = assistant.generate_reply(
        f"Suggest next steps after answering: {question}.",
        "borrower_next_steps",
    )
    upload_trigger = "document" in question.lower() or "upload" in question.lower()

    interactions = (AIAssistantInteraction.query
        .filter_by(user_id=current_user.id)
        .order_by(AIAssistantInteraction.timestamp.desc())
        .all())

    return render_template(
        "borrower/ai_response.html",
        form=request.form,
        response=ai_reply,
        steps=next_steps,
        upload_trigger=upload_trigger,
        interactions=interactions,
        chat=chat,
        borrower=bp,
        title="Ravlo AI Response",
    )


@dual_route("/ai/hub", methods=["GET"])
@dual_route("/ai_hub", methods=["GET"])
@role_required("borrower")
def ai_hub():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    interactions = (AIAssistantInteraction.query
        .filter_by(user_id=current_user.id)
        .order_by(AIAssistantInteraction.timestamp.desc())
        .limit(5)
        .all())

    assistant = AIAssistant()
    ai_summary = assistant.generate_reply(
        f"Provide an overview of the investor’s AI activity ({len(interactions)} items).",
        "borrower_ai_hub",
    )

    return render_template(
        "borrower/ai_hub.html",
        borrower=bp,
        interactions=interactions,
        ai_summary=ai_summary,
        title="AI Hub",
    )


@dual_route("/ai/response/<int:chat_id>", methods=["GET"])
@dual_route("/ask-ai/response/<int:chat_id>", methods=["GET"])
@role_required("borrower")
def ask_ai_response(chat_id):
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    chat = AIAssistantInteraction.query.get_or_404(chat_id)

    interactions = (AIAssistantInteraction.query
        .filter_by(user_id=current_user.id)
        .order_by(AIAssistantInteraction.timestamp.desc())
        .limit(10)
        .all())

    class DummyForm:
        def hidden_tag(self): return ""

    form = DummyForm()
    form.question = type("obj", (), {"data": chat.question})()
    form.submit = None

    return render_template(
        "borrower/ai_response.html",
        borrower=bp,
        response=chat.response,
        chat=chat,
        form=form,
        interactions=interactions,
        title="AI Assistant Response",
    )


# =========================================================
# 📈 ANALYTICS + ACTIVITY + BUDGET
# =========================================================
@dual_route("/intelligence/analysis", methods=["GET"])
@dual_route("/analysis", methods=["GET"])
@role_required("borrower")
def analysis():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    loans = LoanApplication.query.filter_by(borrower_profile_id=bp.id).all() if bp else []
    total_loan_amount = sum([getattr(loan, "loan_amount", 0) or 0 for loan in loans])

    verified_docs = LoanDocument.query.filter_by(borrower_profile_id=bp.id, status="Verified").count() if bp else 0
    pending_docs = LoanDocument.query.filter_by(borrower_profile_id=bp.id, status="Pending").count() if bp else 0

    assistant = AIAssistant()
    ai_summary = assistant.generate_reply(
        f"Summarize investor analytics: {len(loans)} loans totaling ${total_loan_amount}, "
        f"{verified_docs} verified docs, {pending_docs} pending.",
        "borrower_analysis",
    )

    stats = {
        "total_loans": len(loans),
        "total_amount": f"${total_loan_amount:,.2f}",
        "verified_docs": verified_docs,
        "pending_docs": pending_docs,
    }

    return render_template("borrower/analysis.html", borrower=bp, loans=loans, stats=stats, ai_summary=ai_summary, title="Investor Analytics")


@dual_route("/intelligence/activity/<int:borrower_id>", methods=["GET"])
@dual_route("/activity/<int:borrower_id>", methods=["GET"])
@role_required("borrower")
def activity(borrower_id):
    bp = BorrowerProfile.query.get_or_404(borrower_id)
    # Security: only owner can view
    if bp.user_id != current_user.id:
        return "Unauthorized", 403

    activities = BorrowerActivity.query.filter_by(borrower_profile_id=bp.id).order_by(BorrowerActivity.timestamp.desc()).all()

    assistant = AIAssistant()
    ai_summary = assistant.generate_reply(
        f"Generate investor activity summary of {len(activities)} recent actions.",
        "borrower_activity",
    )

    return render_template("borrower/activity.html", borrower=bp, activities=activities, ai_summary=ai_summary, title="Activity")


@dual_route("/planning/budget", methods=["GET", "POST"])
@dual_route("/budget", methods=["GET", "POST"])
@role_required("borrower")
def budget():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    assistant = AIAssistant()

    if request.method == "POST":
        expenses = request.form.to_dict()
        ai_tip = assistant.generate_reply(
            f"Analyze investor expenses: {expenses}",
            "borrower_budget",
        )
        return render_template("borrower/budget_result.html", borrower=bp, ai_tip=ai_tip, title="Budget Results")

    return render_template("borrower/budget.html", borrower=bp, title="Budget Planner")


@dual_route("/ai/deal-insight", methods=["POST"])
@dual_route("/ai_deal_insight", methods=["POST"])
@role_required("borrower")
def ai_deal_insight():
    data = request.get_json() or {}
    name = data.get("name", "Unnamed Deal")
    roi = data.get("roi", 0)
    profit = data.get("profit", 0)
    total = data.get("total", 0)
    message = data.get("message", "")

    assistant = AIAssistant()
    ai_reply = assistant.generate_reply(
        f"Evaluate deal '{name}' with ROI {roi}%, profit {profit}, total cost {total}. {message}",
        "ai_deal_insight",
    )
    return jsonify({"reply": ai_reply})


# =========================================================
# ✍️ E-SIGN
# =========================================================
def add_signature_to_pdf(input_path, signature_image_path, output_path):
    # TODO: implement or move into dedicated PDF service
    pass

@dual_route("/sign", methods=["GET"])
@dual_route("/esign", methods=["GET"])
@role_required("borrower")
def investor_esign():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    docs = ESignedDocument.query.filter_by(borrower_profile_id=bp.id).all() if bp else []
    return render_template("borrower/esign.html", borrower=bp, docs=docs)

@dual_route("/sign/<int:doc_id>", methods=["POST"])
@dual_route("/esign/sign/<int:doc_id>", methods=["POST"])
@role_required("borrower")
def investor_esign_sign(doc_id):
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

    bp_id = getattr(doc, "borrower_profile_id", None)
    db.session.add(LoanDocument(
        borrower_profile_id=bp_id,
        name=f"{doc.name} (Signed)",
        file_path=signed_path,
        status="Uploaded",
        uploaded_at=datetime.utcnow(),
    ))
    db.session.commit()

    return redirect(url_for("borrower.investor_esign"))


# =========================================================
# 💳 PAYMENTS / BILLING
# =========================================================
@dual_route("/billing", methods=["GET"])
@dual_route("/payments", methods=["GET"])
@role_required("borrower")
def payments():
    user = current_user
    subscription_plan = getattr(user, "subscription_plan", "Free")

    payments = (PaymentRecord.query
        .filter_by(user_id=user.id)
        .order_by(PaymentRecord.timestamp.desc())
        .all())

    return render_template("borrower/payments.html", user=user, subscription_plan=subscription_plan, payments=payments)

@dual_route("/billing/checkout/<int:payment_id>", methods=["GET"])
@dual_route("/payments/checkout/<int:payment_id>", methods=["GET"])
@role_required("borrower")
def checkout(payment_id):
    payment = PaymentRecord.query.get_or_404(payment_id)
    borrower = getattr(payment, "borrower", None)

    checkout_session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": payment.payment_type},
                "unit_amount": int(payment.amount * 100),
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=url_for("borrower.payment_success", _external=True) + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=url_for("borrower.payments", _external=True),
        metadata={"payment_id": payment.id, "borrower_id": getattr(borrower, "id", None)},
    )

    payment.stripe_payment_intent = checkout_session.payment_intent
    db.session.commit()
    return redirect(checkout_session.url, code=303)

@dual_route("/billing/success", methods=["GET"])
@dual_route("/payments/success", methods=["GET"])
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

    payment = PaymentRecord.query.filter_by(stripe_payment_intent=payment_intent).first()
    if not payment:
        flash("Payment record not found.", "warning")
        return redirect(url_for("borrower.payments"))

    payment.status = "Paid"
    payment.paid_at = datetime.utcnow()
    db.session.commit()

    receipt_dir = "stripe_receipts"
    os.makedirs(receipt_dir, exist_ok=True)
    receipt_path = os.path.join(receipt_dir, f"{payment.id}_receipt.txt")
    with open(receipt_path, "w") as f:
        f.write(f"Payment of ${payment.amount} received for {payment.payment_type}.")

    db.session.add(LoanDocument(
        borrower_profile_id=payment.borrower_profile_id,
        loan_application_id=payment.loan_id,
        name=f"{payment.payment_type} Receipt",
        file_path=receipt_path,
        doc_type="Receipt",
        status="Uploaded",
        uploaded_at=datetime.utcnow(),
    ))
    db.session.commit()

    return render_template("borrower/payment_success.html", payment=payment)


# =========================================================
# 📊 MARKET SNAPSHOT
# =========================================================
@dual_route("/intelligence/market", methods=["GET"])
@dual_route("/market", methods=["GET"])
@role_required("borrower")
def market_snapshot_page():
    bp = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
    if not bp:
        return redirect(url_for("borrower.command_center"))

    active_property = SavedProperty.query.filter_by(borrower_profile_id=bp.id).order_by(SavedProperty.created_at.desc()).first()
    zipcode = active_property.zipcode if active_property else None

    market_snapshot = get_market_snapshot(zipcode) if zipcode else None

    return render_template(
        "borrower/market_snapshot.html",
        borrower=bp,
        active_property=active_property,
        market_snapshot=market_snapshot,
    )
