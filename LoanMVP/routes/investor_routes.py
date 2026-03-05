import os
import io
import json
import uuid
import base64
import requests
from datetime import datetime
from io import BytesIO
from openai import OpenAI

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

from flask_login import current_user, login_required

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import LETTER

from LoanMVP.extensions import db, stripe, csrf

from LoanMVP.utils.decorators import role_required


from LoanMVP.forms.investor_forms import InvestorSettingsForm, InvestorProfileForm
# -------------------------
# Models (updated for Investor)
# -------------------------
from LoanMVP.models.activity_models import BorrowerActivity  # ok to keep for now (schema-safe filter)
from LoanMVP.models.loan_models import LoanApplication, LoanQuote


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
from LoanMVP.models.investor_models import InvestorProfile, Investment  # adjust import paths as needed
# -------------------------
# AI / Assistants
# -------------------------
from LoanMVP.ai.master_ai import master_ai
from LoanMVP.ai.base_ai import AIAssistant
from LoanMVP.ai.master_ai import CMAIEngine  # if you use it

# -------------------------
# Services
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
from LoanMVP.services.blueprint_parser import extract_blueprint_structure, infer_room_type
from LoanMVP.services.prompt_builder import build_blueprint_prompt


from LoanMVP.utils.r2_storage import r2_put_bytes

# ---------------------------------------------------------
# Blueprint (INVESTOR ONLY)
# ---------------------------------------------------------
investor_bp = Blueprint("investor", __name__, url_prefix="/investor")

client = OpenAI()
GPU_BASE_URL = "http://your-4090-host:8000"
# =========================================================
# 🔢 SAFE NUMERIC HELPERS
# =========================================================

def safe_float(value, default=0.0):
    """Safely convert to float."""
    try:
        if value in (None, "", "None"):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def safe_decimal(value, default="0.00"):
    """Money-safe decimal conversion."""
    try:
        if value in (None, "", "None"):
            return Decimal(default)
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def safe_int(value, default=0, min_v=None, max_v=None):
    """Safe int conversion with optional clamping."""
    try:
        x = int(value)
        if min_v is not None:
            x = max(min_v, x)
        if max_v is not None:
            x = min(max_v, x)
        return x
    except (TypeError, ValueError):
        return default


# =========================================================
# 🧾 JSON + FORM SAFETY
# =========================================================

def safe_json_loads(data, default=None):
    """Safe JSON parse that accepts dict/list or string."""
    if default is None:
        default = {}

    if not data:
        return default

    if isinstance(data, (dict, list)):
        return data

    try:
        return json.loads(data)
    except Exception:
        return default


# =========================================================
# 💰 MONEY FORMATTER
# =========================================================

def fmt_money(value, blank="—"):
    try:
        if value in (None, "", "None"):
            return blank
        return f"${Decimal(str(value)):,.2f}"
    except Exception:
        return blank


# =========================================================
# 📦 CSV → UNIQUE INT LIST
# =========================================================

def split_ids(csv_string: str):
    """Convert comma/semicolon string to unique int list."""
    if not csv_string:
        return []

    parts = csv_string.replace(";", ",").split(",")
    cleaned = []

    for p in parts:
        p = p.strip()
        if not p:
            continue
        try:
            cleaned.append(int(p))
        except Exception:
            continue

    # remove duplicates while preserving order
    seen = set()
    result = []
    for i in cleaned:
        if i not in seen:
            seen.add(i)
            result.append(i)

    return result


# =========================================================
# 🌐 IMAGE UTILITIES
# =========================================================

def download_image_bytes(url: str, timeout=10) -> bytes:
    """Secure image download with header check."""
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("Invalid image URL.")

    response = requests.get(url, timeout=timeout, stream=True)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    if "image" not in content_type:
        raise ValueError("URL does not point to an image.")

    return response.content


def to_png_bytes(img_bytes: bytes, max_size=1024) -> bytes:
    im = Image.open(BytesIO(img_bytes)).convert("RGB")
    im.thumbnail((max_size, max_size))
    out = BytesIO()
    im.save(out, format="PNG", optimize=True)
    return out.getvalue()


def to_webp_bytes(img_bytes: bytes, max_size=1400, quality=86) -> bytes:
    im = Image.open(BytesIO(img_bytes)).convert("RGB")
    im.thumbnail((max_size, max_size))
    out = BytesIO()
    im.save(out, format="WEBP", quality=int(quality), method=6)
    return out.getvalue()


def generate_renovation_images(before_url: str, prompt: str, n: int = 2) -> list[str]:
    if not before_url or not prompt:
        return []

    # 1) Download BEFORE
    before_bytes = download_image_bytes(before_url)
    before_png = to_png_bytes(before_bytes, max_size=1024)
    before_b64 = base64.b64encode(before_png).decode("utf-8")

    # 2) Call /renovate on your 4090 server
    try:
        resp = requests.post(
            f"{GPU_BASE_URL}/renovate",
            json={"image_b64": before_b64, "prompt": prompt, "n": n},
            timeout=120,
        )
        resp.raise_for_status()
    except Exception as e:
        print("GPU renovate failed:", e)
        return []

    data = resp.json()
    images_b64 = data.get("images", []) or []

    after_urls = []
    for b64 in images_b64:
        try:
            img_bytes = base64.b64decode(b64)
            img_webp = to_webp_bytes(img_bytes, max_size=1600, quality=86)
            up = r2_put_bytes(
                img_webp,
                subdir=f"visualizer/{uuid.uuid4().hex}/after",
                content_type="image/webp",
                filename=f"{uuid.uuid4().hex}_after.webp",
            )
            after_urls.append(up["url"])
        except Exception as e:
            print("Upload after failed:", e)
            continue

    return after_urls

# =========================================================
# 👤 PROFILE FILTER (INVESTOR SAFE)
# =========================================================

def _profile_id_filter(model, profile_id):
    """
    Backwards-compatible filter:
    - prefers investor_profile_id
    - falls back to borrower_profile_id
    """
    if hasattr(model, "investor_profile_id"):
        return {"investor_profile_id": profile_id}
    if hasattr(model, "borrower_profile_id"):
        return {"borrower_profile_id": profile_id}
    return {}


# ---------------------------------------------------------
# Investor Capital Timeline (used for progress UI)
# ---------------------------------------------------------
INVESTOR_TIMELINE = [
    {"step": 1, "title": "Capital Request Started", "key": "request_started"},
    {"step": 2, "title": "Documents Uploaded", "key": "docs_uploaded"},
    {"step": 3, "title": "Under Review", "key": "under_review"},
    {"step": 4, "title": "Conditions Issued", "key": "conditions_issued"},
    {"step": 5, "title": "Conditions Cleared", "key": "conditions_cleared"},
    {"step": 6, "title": "Final Review", "key": "final_review"},
    {"step": 7, "title": "Cleared to Close", "key": "ctc"},
]

TIMELINES = {
    "capital": INVESTOR_TIMELINE,
    "construction": [
        {"step": 1, "title": "Project Submitted", "key": "project_submitted"},
        {"step": 2, "title": "Budget Approved", "key": "budget_approved"},
        {"step": 3, "title": "Draw Schedule Created", "key": "draw_schedule"},
        {"step": 4, "title": "Construction Started", "key": "construction_started"},
        {"step": 5, "title": "Final Inspection", "key": "final_inspection"},
        {"step": 6, "title": "Project Completed", "key": "project_completed"},
    ]
}


# ---------------------------------------------------------
# Investor Command Center Routes
# ---------------------------------------------------------

@investor_bp.route("/", methods=["GET"], endpoint="command_center")
@investor_bp.route("/index", methods=["GET"])
@investor_bp.route("/command", methods=["GET"])
@investor_bp.route("/dashboard", methods=["GET"])
@login_required
@role_required("investor")
def command_center():
    """
    Investor Command Center — single source of truth.
    '/' '/index' '/command' '/dashboard' all land here.
    """

    # Respect ?next= if present
    next_page = (request.args.get("next") or "").strip()
    if next_page and next_page.startswith("/"):
        return redirect(next_page)

    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    capital_requests = []
    active_request = None
    conditions = []
    doc_requests = []
    saved_props = []
    primary_stage = None

    assistant = AIAssistant()
    next_step_ai = None
    next_step_text = "No active capital request. Start a new deal when ready."

    if ip:
        # Saved properties / watchlist
        saved_props = (
            SavedProperty.query
            .filter_by(investor_profile_id=ip.id)
            .order_by(SavedProperty.created_at.desc())
            .all()
        )

        # All capital requests
        capital_requests = (
            LoanApplication.query
            .filter_by(investor_profile_id=ip.id)
            .order_by(LoanApplication.created_at.desc())
            .all()
        )

        # Active capital request
        active_request = (
            LoanApplication.query
            .filter_by(investor_profile_id=ip.id, is_active=True)
            .order_by(LoanApplication.created_at.desc())
            .first()
        )

        # Document requests
        doc_requests = (
            LoanDocument.query
            .filter_by(investor_profile_id=ip.id)
            .order_by(LoanDocument.created_at.desc())
            .all()
        )

        if active_request:
            conditions = (
                UnderwritingCondition.query
                .filter_by(investor_profile_id=ip.id, loan_id=active_request.id)
                .order_by(UnderwritingCondition.created_at.desc())
                .all()
            )

            primary_stage = getattr(active_request, "status", None) or "Application"

            pending_conditions = [
                c for c in conditions
                if (c.status or "").strip().lower() not in {"submitted", "cleared", "completed"}
            ]

            if pending_conditions:
                next_step_text = (
                    f"You have {len(pending_conditions)} pending items. "
                    f"Next: {pending_conditions[0].description}."
                )
            else:
                next_step_text = "All items are in. Waiting on capital review."

    # Progress snapshot
    progress_percent = 0
    if active_request:
        total_conditions = len(conditions)
        cleared_conditions = len([
            c for c in conditions
            if (c.status or "").strip().lower() == "cleared"
        ])
        if total_conditions > 0:
            progress_percent = int((cleared_conditions / total_conditions) * 100)

    snapshot = {
        "loan_type": getattr(active_request, "loan_type", None) if active_request else None,
        "amount": getattr(active_request, "amount", None) if active_request else None,
        "status": getattr(active_request, "status", None) if active_request else None,
        "address": getattr(active_request, "property_address", None) if active_request else None,
        "progress_percent": progress_percent,
    }

    try:
        next_step_ai = assistant.generate_reply(
            f"Create a calm, professional investor-facing next step message: {next_step_text}",
            "investor_next_step"
        )
    except Exception:
        next_step_ai = "Next step guidance is unavailable right now."

    now_str = datetime.now().strftime("%b %d, %Y • %I:%M %p")

    return render_template(
        "investor/dashboard.html",
        investor=ip,
        capital_requests=capital_requests,
        active_request=active_request,
        conditions=conditions,
        doc_requests=doc_requests,
        saved_props=saved_props,
        snapshot=snapshot,
        next_step_ai=next_step_ai,
        primary_stage=primary_stage,
        now_str=now_str,
        investor_profile=ip,   # ← FIXED
        active_tab="command",
        title="RAVLO • Command Center",
    )

@investor_bp.route("/test_blueprint", methods=["GET"])
@login_required
def test_blueprint():
    return render_template("test_blueprint.html")


@investor_bp.route("/resources", methods=["GET"])
@login_required
@role_required("investor")
def resource_center():
    """
    Investor Resource Center
    Tools, FAQs, Partners, AI Help
    """

    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    partners = Partner.query.order_by(Partner.name.asc()).all()

    faqs = [
        {"q": "How long does approval take?", "a": "Most approvals are 5–10 business days."},
        {"q": "What documents are required?", "a": "Purchase contract, scope, bank statements."},
    ]

    return render_template(
        "investor/resource_center.html",
        investor=ip,
        partners=partners,
        faqs=faqs,
        title="RAVLO Resource Center",
        active_tab="resources"
    )

@investor_bp.route("/dismiss_dashboard_tour", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
def dismiss_dashboard_tour():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if ip:
        ip.has_seen_dashboard_tour = True
        db.session.commit()
    return jsonify({"status": "ok"})


# =========================================================
# 👤 INVESTOR ACCOUNT (profile/settings/privacy/notifications)
# =========================================================
@investor_bp.route("/account", methods=["GET", "POST"])
@login_required
@role_required("investor")
def account():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    now_str = datetime.now().strftime("%b %d, %Y • %I:%M %p")

    return render_template(
        "investor/account.html",
        investor=current_user,
        investor_profile=ip,
        now_str=now_str,
        active_tab="account",
        title="RAVLO • Account"
    )

@investor_bp.route("/profile", methods=["GET"])
@login_required
@role_required("investor")
def profile():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    return render_template("investor/profile.html", investor=ip)


@investor_bp.route("/settings", methods=["GET", "POST"])
@csrf.exempt
@login_required
@role_required("investor")
def settings():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    if request.method == "POST":
        current_user.first_name = request.form.get("first_name")
        current_user.last_name = request.form.get("last_name")
        current_user.email = request.form.get("email")

    form = InvestorSettingsForm()

    if form.validate_on_submit():
        db.session.commit()
        flash("Settings updated successfully.", "success")
        return redirect(url_for("investor.settings"))

    return render_template(
        "investor/settings.html",
        investor=current_user,
        investor_profile=ip
    )

@investor_bp.route("/privacy", methods=["GET", "POST"])
@login_required
@role_required("investor")
def privacy():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if ip and request.method == "POST":
        ip.subscription_plan = request.form.get("subscription_plan")
        db.session.commit()
        flash("Privacy preferences updated.", "success")
        return redirect(url_for("investor.privacy"))
    return render_template("investor/privacy.html", investor=ip)


@investor_bp.route("/notifications-settings", methods=["GET", "POST"])
@login_required
@role_required("investor")
def notifications_settings():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if ip and request.method == "POST":
        ip.email_notifications = True if request.form.get("email_notifications") else False
        ip.sms_notifications = True if request.form.get("sms_notifications") else False
        db.session.commit()
        flash("Notification settings updated.", "success")
        return redirect(url_for("investor.notifications_settings"))
    return render_template("investor/notifications_settings.html", investor=ip)


# =========================================================
# 🧾 INVESTOR PROFILE CREATE/UPDATE
# =========================================================

@investor_bp.route("/create_profile", methods=["GET", "POST"])
@login_required
@role_required("investor")
def create_profile():
    from LoanMVP.forms.investor_forms import InvestorProfileForm
    form = InvestorProfileForm()

    if form.validate_on_submit():
        ip = InvestorProfile(
            user_id=current_user.id,
            full_name=form.full_name.data,
            email=form.email.data,
            phone=form.phone.data,
            address=form.address.data,
            city=form.city.data,
            state=form.state.data,
            zip_code=form.zip_code.data,
            employment_status=form.employment_status.data,
            annual_income=form.annual_income.data,
            credit_score=form.credit_score.data,

            strategy=form.strategy.data,
            experience_level=form.experience_level.data,
            target_markets=form.target_markets.data,
            property_types=form.property_types.data,
            min_price=form.min_price.data,
            max_price=form.max_price.data,
            min_sqft=form.min_sqft.data,
            max_sqft=form.max_sqft.data,
            capital_available=form.capital_available.data,
            min_cash_on_cash=form.min_cash_on_cash.data,
            min_roi=form.min_roi.data,
            timeline_days=form.timeline_days.data,
            risk_tolerance=form.risk_tolerance.data,
        )

        db.session.add(ip)
        db.session.commit()

        flash("Investor profile created successfully!", "success")
        return redirect(url_for("investor.command_center"))

    return render_template(
        "investor/create_profile.html",
        form=form,
        title="Create Investor Profile"
    )

@investor_bp.route("/update_profile", methods=["POST"])
@login_required
@role_required("investor")
def update_profile():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        return jsonify({"status": "error", "message": "Profile not found."}), 404

    for field, value in request.form.items():
        if hasattr(ip, field) and (value or "").strip():
            setattr(ip, field, value)

    ip.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"status": "success", "message": "Profile updated successfully."})
    
# =========================================================
# 📝 INVESTOR • CAPITAL APPLICATION + STATUS
# =========================================================

@investor_bp.route("/capital/apply", methods=["GET", "POST"])
@investor_bp.route("/apply", methods=["GET", "POST"])
@login_required
@role_required("investor")
def apply():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        flash("Please create your investor profile before applying for capital.", "warning")
        return redirect(url_for("investor.create_profile"))

    assistant = AIAssistant()

    if request.method == "POST":
        loan_type = request.form.get("loan_type")
        amount = safe_float(request.form.get("amount"))
        property_address = request.form.get("property_address")

        try:
            ai_summary = assistant.generate_reply(
                f"Create a short investor-facing capital request summary for {ip.full_name} "
                f"for a {loan_type} at {property_address}.",
                "investor_apply",
            )
        except Exception:
            ai_summary = None

        # Build kwargs safely across schemas
        profile_fk = _profile_id_filter(LoanApplication, ip.id)

        loan = LoanApplication(
            **profile_fk,
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

        flash("✅ Capital request submitted successfully!", "success")
        return redirect(url_for("investor.status"))

    return render_template("investor/apply.html", investor=ip, title="Apply for Capital")


@investor_bp.route("/capital/status", methods=["GET"])
@investor_bp.route("/status", methods=["GET"])
@login_required
@role_required("investor")
def status():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        flash("Please complete your investor profile first.", "warning")
        return redirect(url_for("investor.create_profile"))

    profile_fk = _profile_id_filter(LoanApplication, ip.id)
    doc_fk = _profile_id_filter(LoanDocument, ip.id)

    loans = LoanApplication.query.filter_by(**profile_fk).all()
    documents = LoanDocument.query.filter_by(**doc_fk).all()

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
            f"Summarize investor capital status for {ip.full_name} with: {stats}",
            "investor_status",
        )
    except Exception:
        ai_summary = "⚠️ AI summary unavailable."

    return render_template(
        "investor/status.html",
        investor=ip,
        loans=loans,
        documents=documents,
        stats=stats,
        ai_summary=ai_summary,
        title="Capital Status",
    )


# =========================================================
# 📄 INVESTOR • LOAN VIEW / EDIT (security-safe)
# =========================================================

@investor_bp.route("/capital/loan/<int:loan_id>", methods=["GET"])
@investor_bp.route("/loan/<int:loan_id>", methods=["GET"])
@login_required
@role_required("investor")
def loan_view(loan_id):
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    loan = LoanApplication.query.get_or_404(loan_id)

    # Ownership check (supports both schemas)
    owns = False
    if ip:
        if hasattr(loan, "investor_profile_id") and loan.investor_profile_id == ip.id:
            owns = True
        if hasattr(loan, "borrower_profile_id") and loan.borrower_profile_id == ip.id:
            owns = True

    if not ip or not owns:
        return "Unauthorized", 403

    cond_fk = _profile_id_filter(UnderwritingCondition, ip.id)

    conditions = UnderwritingCondition.query.filter_by(
        **cond_fk,
        loan_id=loan.id
    ).all()

    assistant = AIAssistant()
    try:
        ai_summary = assistant.generate_reply(
            f"Summarize {len(conditions)} underwriting items for investor {ip.full_name}.",
            "investor_loan_conditions",
        )
    except Exception:
        ai_summary = None

    return render_template(
        "investor/view_loan.html",
        investor=ip,
        loan=loan,
        conditions=conditions,
        ai_summary=ai_summary,
        active_tab="capital",
        title=f"Loan #{loan.id}",
    )


@investor_bp.route("/capital/loan/<int:loan_id>/edit", methods=["GET", "POST"])
@investor_bp.route("/loan/<int:loan_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("investor")
def edit_loan(loan_id):
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    loan = LoanApplication.query.get_or_404(loan_id)

    # Ownership check (supports both schemas)
    owns = False
    if ip:
        if hasattr(loan, "investor_profile_id") and loan.investor_profile_id == ip.id:
            owns = True
        if hasattr(loan, "borrower_profile_id") and loan.borrower_profile_id == ip.id:
            owns = True

    if not ip or not owns:
        return "Unauthorized", 403

    if request.method == "POST":
        loan.loan_amount = safe_float(request.form.get("amount"))
        loan.status = request.form.get("status")
        loan.loan_type = request.form.get("loan_type")
        loan.property_address = request.form.get("property_address")
        loan.interest_rate = safe_float(request.form.get("interest_rate"))
        loan.term = request.form.get("term")

        db.session.commit()
        flash("✅ Capital request updated successfully!", "success")
        return redirect(url_for("investor.loan_view", loan_id=loan.id))

    return render_template("investor/edit_loan.html", loan=loan, investor=ip, title="Edit Loan")


# =========================================================
# 💰 INVESTOR • QUOTES + CONVERSION
# =========================================================

@investor_bp.route("/capital/quote", methods=["GET", "POST"])
@investor_bp.route("/quote", methods=["GET", "POST"])
@login_required
@role_required("investor")
def quote():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        flash("Please complete your investor profile before requesting a quote.", "warning")
        return redirect(url_for("investor.create_profile"))

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
            ai_suggestion = assistant.generate_reply(prompt, "investor_quote")
        except Exception:
            ai_suggestion = "⚠️ AI system unavailable. Displaying mock results."

        mock_lenders = [
            {"lender_name": "Lima One Capital", "rate": 6.20, "loan_type": "30-Year Fixed", "deal_type": "Conventional"},
            {"lender_name": "RCN Capital", "rate": 6.05, "loan_type": "FHA 30-Year", "deal_type": "Residential"},
            {"lender_name": "LendingOne", "rate": 5.90, "loan_type": "5/1 ARM", "deal_type": "Hybrid"},
        ]

        quote_fk = _profile_id_filter(LoanQuote, ip.id)

        for lender in mock_lenders:
            db.session.add(LoanQuote(
                **quote_fk,
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
            "investor/quote_results.html",
            investor=ip,
            lenders=mock_lenders,
            property_address=property_address,
            property_value=property_value,
            loan_amount=loan_amount,
            fico_score=fico_score,
            ltv=ltv,
            ai_response=ai_suggestion,
            title="Loan Quote Results",
        )

    return render_template("investor/quote.html", investor=ip, title="Get a Loan Quote")


@investor_bp.route("/capital/quote/convert/<int:quote_id>", methods=["POST"])
@investor_bp.route("/quote/convert/<int:quote_id>", methods=["POST"])
@login_required
@role_required("investor")
def convert_quote_to_application(quote_id):
    quote = LoanQuote.query.get_or_404(quote_id)
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        flash("Please complete your investor profile before applying.", "warning")
        return redirect(url_for("investor.create_profile"))

    # Ensure quote belongs to current investor (supports both schemas)
    quote_owner_ok = False
    if hasattr(quote, "investor_profile_id") and quote.investor_profile_id == ip.id:
        quote_owner_ok = True
    if hasattr(quote, "borrower_profile_id") and quote.borrower_profile_id == ip.id:
        quote_owner_ok = True

    if not quote_owner_ok:
        return "Unauthorized", 403

    # Prevent duplicate conversion
    app_fk = _profile_id_filter(LoanApplication, ip.id)
    existing_app = LoanApplication.query.filter_by(
        **app_fk,
        loan_amount=quote.loan_amount,
        property_address=quote.property_address,
    ).first()

    if existing_app:
        flash("This quote has already been converted.", "info")
        return redirect(url_for("investor.status"))

    new_app = LoanApplication(
        **app_fk,
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

    # Activity log (switch to InvestorActivity if you have it)
    activity_model = InvestorActivity if "InvestorActivity" in globals() else BorrowerActivity
    activity_fk = _profile_id_filter(activity_model, ip.id)

    db.session.add(activity_model(
        **activity_fk,
        category="Capital Conversion",
        description=f"Converted quote #{quote.id} into capital request #{new_app.id}.",
        timestamp=datetime.utcnow(),
    ))

    msg = (
        f"📢 Investor {ip.full_name} converted quote #{quote.id} into "
        f"Capital Request #{new_app.id} for {quote.property_address or 'a new property'}."
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
        notify_team_on_conversion(ip, quote, new_app)
    except Exception as e:
        print("Notification error:", e)

    flash("🎯 Quote converted and team notified!", "success")
    return redirect(url_for("investor.status"))


@investor_bp.route("/ai/quote", methods=["POST"])
@investor_bp.route("/get_quote_ai", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
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
    ai_reply = (
        getattr(ai, "generate", None)(msg, role="investor")
        if getattr(ai, "generate", None)
        else ai.generate_reply(msg, role="investor")
    )

    return jsonify({"quote": ai_reply})

# =========================================================
# 📁 INVESTOR • DOCUMENTS + REQUESTS
# =========================================================

@investor_bp.route("/documents", methods=["GET"])
@login_required
@role_required("investor")
def documents():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    docs = LoanDocument.query.filter_by(**_profile_id_filter(LoanDocument, ip.id)).all() if ip else []

    assistant = AIAssistant()
    try:
        ai_summary = assistant.generate_reply(
            f"Summarize the investor’s {len(docs)} uploaded documents and highlight missing items.",
            "investor_documents"
        )
    except Exception:
        ai_summary = "⚠️ AI summary unavailable."

    return render_template(
        "investor/documents.html",
        investor=ip,
        documents=docs,
        ai_summary=ai_summary,
        title="Documents",
        active_tab="documents"
    )


@investor_bp.route("/document_requests", methods=["GET"])
@login_required
@role_required("investor")
def document_requests():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        return redirect(url_for("investor.create_profile"))

    # Document requests: supports DocumentRequest.borrower_id OR .investor_id
    req_fk = _profile_id_filter(DocumentRequest, ip.id)
    doc_requests = DocumentRequest.query.filter_by(**req_fk).all() if req_fk else []

    # Conditions tied to active request (supports ip.active_loan_id or ip.active_capital_id)
    active_loan_id = getattr(ip, "active_loan_id", None) or getattr(ip, "active_capital_id", None)

    cond_fk = _profile_id_filter(UnderwritingCondition, ip.id)
    conditions = UnderwritingCondition.query.filter_by(
        **cond_fk,
        loan_id=active_loan_id
    ).all() if (cond_fk and active_loan_id) else []

    unified = []
    for req in doc_requests:
        unified.append({
            "id": req.id,
            "type": "request",
            "document_name": getattr(req, "document_name", None),
            "requested_by": getattr(req, "requested_by", None),
            "notes": getattr(req, "notes", None),
            "status": getattr(req, "status", None),
            "file_path": getattr(req, "file_path", None),
        })

    for cond in conditions:
        unified.append({
            "id": cond.id,
            "type": "condition",
            "document_name": getattr(cond, "description", None),
            "requested_by": getattr(cond, "requested_by", None) or "Processor",
            "notes": getattr(cond, "notes", None),
            "status": getattr(cond, "status", None),
            "file_path": getattr(cond, "file_path", None),
        })

    assistant = AIAssistant()
    try:
        ai_summary = assistant.generate_reply(
            f"List {len(unified)} outstanding document requests/conditions for investor {ip.full_name}.",
            "investor_document_requests",
        )
    except Exception:
        ai_summary = "⚠️ AI summary unavailable."

    return render_template(
        "investor/document_requests.html",
        investor=ip,
        requests=unified,
        ai_summary=ai_summary,
        title="Document Requests",
        active_tab="documents"
    )


@investor_bp.route("/upload_document", methods=["GET", "POST"])
@login_required
@role_required("investor")
def upload_document():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    if request.method == "POST":
        file = request.files.get("file")
        doc_type = request.form.get("doc_type")

        if file and ip:
            filename = secure_filename(file.filename)
            save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
            file.save(save_path)

            doc_fk = _profile_id_filter(LoanDocument, ip.id)

            db.session.add(LoanDocument(
                **doc_fk,
                file_path=filename,
                doc_type=doc_type,
                status="uploaded"
            ))
            db.session.commit()
            return redirect(url_for("investor.documents"))

    return render_template(
        "investor/upload_document.html",
        investor=ip,
        title="Upload Document",
        active_tab="documents"
    )


@investor_bp.route("/upload_request", methods=["GET", "POST"])
@login_required
@role_required("investor")
def upload_request():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        return redirect(url_for("investor.create_profile"))

    item_id = request.args.get("item_id")
    item_type = request.args.get("type")  # request|condition

    item = DocumentRequest.query.get(item_id) if item_type == "request" else UnderwritingCondition.query.get(item_id)

    # Basic ownership check for request/condition
    if item_type == "request" and item:
        ok = False
        if hasattr(item, "investor_id") and item.investor_id == ip.id:
            ok = True
        if hasattr(item, "borrower_id") and item.borrower_id == ip.id:
            ok = True
        if not ok:
            return "Unauthorized", 403

    if item_type == "condition" and item:
        ok = False
        if hasattr(item, "investor_profile_id") and item.investor_profile_id == ip.id:
            ok = True
        if hasattr(item, "borrower_profile_id") and item.borrower_profile_id == ip.id:
            ok = True
        if not ok:
            return "Unauthorized", 403

    if request.method == "POST":
        file = request.files.get("file")
        if file and ip and item:
            filename = secure_filename(file.filename)
            save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
            file.save(save_path)

            doc_fk = _profile_id_filter(LoanDocument, ip.id)

            db.session.add(LoanDocument(
                **doc_fk,
                file_path=filename,
                doc_type=getattr(item, "description", None) or getattr(item, "document_name", "Document"),
                status="submitted",
                request_id=item.id if item_type == "request" else None,
                condition_id=item.id if item_type == "condition" else None
            ))

            item.status = "submitted"
            db.session.commit()
            return redirect(url_for("investor.document_requests"))

    return render_template(
        "investor/upload_request.html",
        investor=ip,
        item=item,
        item_type=item_type,
        title="Upload Document",
        active_tab="documents"
    )


@investor_bp.route("/delete_document/<int:doc_id>", methods=["POST"])
@login_required
@role_required("investor")
def delete_document(doc_id):
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    doc = LoanDocument.query.get_or_404(doc_id)

    # Ownership check (supports both schemas)
    owns = False
    if ip:
        if hasattr(doc, "investor_profile_id") and doc.investor_profile_id == ip.id:
            owns = True
        if hasattr(doc, "borrower_profile_id") and doc.borrower_profile_id == ip.id:
            owns = True

    if not ip or not owns:
        return "Unauthorized", 403

    try:
        os.remove(os.path.join(current_app.config["UPLOAD_FOLDER"], doc.file_path))
    except Exception:
        pass

    db.session.delete(doc)
    db.session.commit()
    return redirect(url_for("investor.documents"))


# =========================================================
# ✅ INVESTOR • CONDITIONS (capital requirements)
# =========================================================

@investor_bp.route("/capital/conditions", methods=["GET"])
@investor_bp.route("/conditions", methods=["GET"])
@login_required
@role_required("investor")
def conditions():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    loan = None
    if ip:
        loan_fk = _profile_id_filter(LoanApplication, ip.id)
        loan = LoanApplication.query.filter_by(**loan_fk, is_active=True).first() if loan_fk else None

    conds = []
    if loan and ip:
        cond_fk = _profile_id_filter(UnderwritingCondition, ip.id)
        conds = UnderwritingCondition.query.filter_by(**cond_fk, loan_id=loan.id).all() if cond_fk else []

    assistant = AIAssistant()
    try:
        ai_summary = assistant.generate_reply(
            f"Summarize {len(conds)} underwriting conditions and highlight what's still required.",
            "investor_conditions"
        )
    except Exception:
        ai_summary = "⚠️ AI summary unavailable."

    return render_template(
        "investor/conditions.html",
        investor=ip,
        loan=loan,
        conditions=conds,
        ai_summary=ai_summary,
        title="Conditions",
        active_tab="conditions"
    )


@investor_bp.route("/capital/conditions/<int:cond_id>", methods=["GET"])
@investor_bp.route("/condition/<int:cond_id>", methods=["GET"])
@login_required
@role_required("investor")
def view_condition(cond_id):
    cond = UnderwritingCondition.query.get_or_404(cond_id)
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    # Ownership check (supports both schemas)
    ok = False
    if ip:
        if hasattr(cond, "investor_profile_id") and cond.investor_profile_id == ip.id:
            ok = True
        if hasattr(cond, "borrower_profile_id") and cond.borrower_profile_id == ip.id:
            ok = True
    if not ip or not ok:
        return "Unauthorized", 403

    return render_template(
        "investor/condition_view.html",
        condition=cond,
        investor=ip,
        title="Condition Detail",
        active_tab="conditions"
    )


@investor_bp.route("/capital/conditions/<int:cond_id>/history", methods=["GET"])
@investor_bp.route("/condition/<int:cond_id>/history", methods=["GET"])
@login_required
@role_required("investor")
def condition_history(cond_id):
    cond = UnderwritingCondition.query.get_or_404(cond_id)
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    ok = False
    if ip:
        if hasattr(cond, "investor_profile_id") and cond.investor_profile_id == ip.id:
            ok = True
        if hasattr(cond, "borrower_profile_id") and cond.borrower_profile_id == ip.id:
            ok = True
    if not ip or not ok:
        return "Unauthorized", 403

    history = []
    if getattr(cond, "created_at", None):
        history.append({"timestamp": cond.created_at, "text": "Condition created"})
    if getattr(cond, "file_path", None):
        history.append({"timestamp": getattr(cond, "updated_at", None) or cond.created_at, "text": "Document uploaded"})
    if (getattr(cond, "status", "") or "").lower() == "submitted":
        history.append({"timestamp": getattr(cond, "updated_at", None) or cond.created_at, "text": "Document submitted"})
    if (getattr(cond, "status", "") or "").lower() == "cleared":
        history.append({"timestamp": getattr(cond, "updated_at", None) or cond.created_at, "text": "Condition cleared"})

    history = [h for h in history if h.get("timestamp")]
    history.sort(key=lambda x: x["timestamp"], reverse=True)

    return render_template(
        "investor/condition_history.html",
        investor=ip,
        condition=cond,
        history=history,
        title="Condition History",
        active_tab="conditions"
    )


@investor_bp.route("/conditions/ai/<int:condition_id>", methods=["GET"])
@login_required
@role_required("investor")
def investor_condition_ai(condition_id):
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


@investor_bp.route("/conditions/upload/<int:cond_id>", methods=["POST"])
@login_required
@role_required("investor")
def upload_condition(cond_id):
    cond = UnderwritingCondition.query.get_or_404(cond_id)
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    ok = False
    if ip:
        if hasattr(cond, "investor_profile_id") and cond.investor_profile_id == ip.id:
            ok = True
        if hasattr(cond, "borrower_profile_id") and cond.borrower_profile_id == ip.id:
            ok = True
    if not ip or not ok:
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

    return redirect(url_for("investor.conditions"))

# =========================================================
# 🧠 INVESTOR • PROPERTY INTELLIGENCE (search/saved/tool/apis)
# =========================================================

@investor_bp.route("/intelligence", methods=["GET"])
@investor_bp.route("/property_search", methods=["GET"])
@login_required
@role_required("investor")
def property_search():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
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

            if ip and property_data.get("address"):
                try:
                    existing = SavedProperty.query.filter(
                        getattr(SavedProperty, "investor_profile_id", SavedProperty.borrower_profile_id) == ip.id,
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
        "investor/property_search.html",
        investor=ip,
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


@investor_bp.route("/intelligence/save", methods=["POST"])
@investor_bp.route("/save_property", methods=["POST"])
@login_required
@role_required("investor")
def save_property():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
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
    fk = _profile_id_filter(SavedProperty, ip.id)

    if final_property_id:
        existing = SavedProperty.query.filter_by(
            **fk,
            property_id=str(final_property_id)
        ).first()

    if not existing and normalized_address:
        existing = SavedProperty.query.filter(
            getattr(SavedProperty, "investor_profile_id", SavedProperty.borrower_profile_id) == ip.id,
            db.func.lower(SavedProperty.address) == normalized_address.lower()
        ).first()

    if existing:
        if not existing.address and normalized_address:
            existing.address = normalized_address
        if (not getattr(existing, "zipcode", None)) and raw_zipcode:
            existing.zipcode = raw_zipcode
        if (getattr(existing, "sqft", None) is None or getattr(existing, "sqft", 0) == 0) and sqft:
            existing.sqft = sqft
        if (not getattr(existing, "price", None)) and raw_price is not None:
            existing.price = str(raw_price)
        if (not getattr(existing, "property_id", None)) and final_property_id:
            existing.property_id = str(final_property_id)

        if hasattr(existing, "resolved_json"):
            existing.resolved_json = json.dumps(resolved) if resolved else None
            existing.resolved_at = datetime.utcnow() if resolved else None

        db.session.commit()
        return jsonify({"status": "success", "message": "Already saved (updated details).", "saved_id": existing.id})

    saved = SavedProperty(
        **fk,
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


@investor_bp.route("/intelligence/saved", methods=["GET"])
@investor_bp.route("/saved_properties", methods=["GET"])
@login_required
@role_required("investor")
def saved_properties():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    props = SavedProperty.query.filter_by(**_profile_id_filter(SavedProperty, ip.id)).all() if ip else []

    try:
        name = ip.full_name if ip else "this investor"
        ai_summary = AIAssistant().generate_reply(
            f"Summarize {len(props)} saved properties for {name}. Prioritize investment potential.",
            "investor_saved_properties",
        )
    except Exception:
        ai_summary = "⚠️ AI summary unavailable."

    return render_template(
        "investor/saved_properties.html",
        investor=ip,
        properties=props,
        ai_summary=ai_summary,
        title="Saved Properties",
        active_tab="property_search"
    )


@investor_bp.route("/intelligence/saved/manage", methods=["POST"])
@investor_bp.route("/saved_properties/manage", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
def saved_properties_manage():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        flash("Profile not found.", "danger")
        return redirect(url_for("investor.saved_properties"))

    prop_id = request.form.get("prop_id")
    action = request.form.get("action")
    notes = request.form.get("notes", "")

    try:
        prop_id = int(prop_id)
    except Exception:
        flash("Invalid property id.", "warning")
        return redirect(url_for("investor.saved_properties"))

    prop = SavedProperty.query.filter_by(id=prop_id, **_profile_id_filter(SavedProperty, ip.id)).first()
    if not prop:
        flash("Saved property not found.", "warning")
        return redirect(url_for("investor.saved_properties"))

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

    return redirect(url_for("investor.saved_properties"))


@investor_bp.route("/intelligence/save-and-analyze", methods=["POST"])
@investor_bp.route("/save_property_and_analyze", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
def save_property_and_analyze():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        flash("Profile not found.", "danger")
        return redirect(url_for("investor.property_search"))

    raw_address = (request.form.get("address") or "").strip()
    if not raw_address:
        flash("Address required.", "warning")
        return redirect(url_for("investor.property_search"))

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

    fk = profile_id_filter(SavedProperty, ip.id)

    existing = None
    if final_property_id:
        existing = SavedProperty.query.filter_by(**fk, property_id=final_property_id).first()

    if not existing and normalized_address:
        existing = SavedProperty.query.filter(
            getattr(SavedProperty, "investor_profile_id", SavedProperty.borrower_profile_id) == ip.id,
            db.func.lower(SavedProperty.address) == normalized_address.lower()
        ).first()

    if existing:
        flash("✅ Property already saved — opening Deal Studio.", "info")
        return redirect(url_for("investor.deal_workspace", prop_id=existing.id, mode="flip"))

    saved = SavedProperty(
        **fk,
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
    return redirect(url_for("investor.deal_workspace", prop_id=saved.id, mode="flip"))


@investor_bp.route("/intelligence/saved/<int:prop_id>", methods=["GET"])
@investor_bp.route("/property_explore_plus/<int:prop_id>", methods=["GET"])
@login_required
@role_required("investor")
def property_explore_plus(prop_id):
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        flash("Profile not found.", "danger")
        return redirect(url_for("investor.property_search"))

    prop = SavedProperty.query.filter_by(id=prop_id, **_profile_id_filter(SavedProperty, ip.id)).first()
    if not prop:
        flash("Property not found.", "danger")
        return redirect(url_for("investor.property_search"))

    resolved = resolve_property_unified(prop.address)
    resolved_property = (resolved.get("property") or {}) if resolved.get("status") == "ok" else {}
    photos = resolved_property.get("photos") or []

    from LoanMVP.services.comps_service import get_comps_for_property
    comps = get_comps_for_property(address=prop.address, zipcode=(prop.zipcode or ""), rentometer_api_key=None)
    market = get_market_snapshot(zipcode=(prop.zipcode or "")) if prop.zipcode else {}

    ai_summary = resolved.get("ai_summary") or None

    return render_template(
        "investor/property_explore_plus.html",
        investor=ip,
        prop=prop,
        resolved=resolved_property,
        ai_summary=ai_summary,
        comps=comps,
        market=market,
        photos=photos,
        active_page="property_search",
    )


@investor_bp.route("/intelligence/tool", methods=["GET"])
@investor_bp.route("/property_tool", methods=["GET"])
@login_required
@role_required("investor")
def property_tool():
    return render_template("investor/property_tool.html", active_page="property_tool")


# =========================================================
# 🔌 INVESTOR • APIs (Property Tool)
# =========================================================

@investor_bp.route("/api/intelligence/zip-search", methods=["POST"])
@investor_bp.route("/api/property_tool_search", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
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


@investor_bp.route("/api/intelligence/save", methods=["POST"])
@investor_bp.route("/api/property_tool_save", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
def api_property_tool_save():
    payload = request.get_json(force=True) or {}
    address = (payload.get("address") or "").strip()
    if not address:
        return jsonify({"status": "error", "message": "Address is required to save."}), 400

    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        return jsonify({"status": "error", "message": "Profile not found."}), 400

    zipcode = (payload.get("zip") or "").strip() or None
    price = payload.get("price")
    sqft = payload.get("sqft")
    property_id = payload.get("property_id")

    try:
        sqft = int(float(sqft)) if sqft not in (None, "", "None") else None
    except Exception:
        sqft = None

    fk = profile_id_filter(SavedProperty, ip.id)

    existing = None
    if property_id:
        existing = SavedProperty.query.filter_by(**fk, property_id=str(property_id)).first()

    if not existing:
        existing = SavedProperty.query.filter(
            getattr(SavedProperty, "investor_profile_id", SavedProperty.borrower_profile_id) == ip.id,
            db.func.lower(SavedProperty.address) == address.lower()
        ).first()

    if existing:
        return jsonify({"status": "ok", "message": "Already saved.", "saved_id": existing.id})

    saved = SavedProperty(
        **fk,
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


@investor_bp.route("/api/intelligence/save-and-analyze", methods=["POST"])
@investor_bp.route("/api/property_tool_save_and_analyze", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
def api_property_tool_save_and_analyze():
    payload = request.get_json(force=True) or {}
    address = (payload.get("address") or "").strip()
    if not address:
        return jsonify({"status": "error", "message": "Address is required to analyze."}), 400

    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        return jsonify({"status": "error", "message": "Profile not found."}), 400

    zipcode = (payload.get("zip") or "").strip() or None
    price = payload.get("price")
    sqft = payload.get("sqft")
    property_id = payload.get("property_id")

    try:
        sqft = int(float(sqft)) if sqft not in (None, "", "None") else None
    except Exception:
        sqft = None

    fk = _profile_id_filter(SavedProperty, ip.id)

    existing = None
    if property_id:
        existing = SavedProperty.query.filter_by(**fk, property_id=str(property_id)).first()

    if not existing:
        existing = SavedProperty.query.filter(
            getattr(SavedProperty, "investor_profile_id", SavedProperty.borrower_profile_id) == ip.id,
            db.func.lower(SavedProperty.address) == address.lower()
        ).first()

    if not existing:
        existing = SavedProperty(
            **fk,
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

    deal_url = url_for("investor.deal_workspace", prop_id=existing.id, mode="flip")
    return jsonify({"status": "ok", "saved_id": existing.id, "deal_url": deal_url})

# =========================================================
# 💼 INVESTOR • DEAL STUDIO (workspace + deals + visualizer + exports)
# =========================================================

@investor_bp.route("/deals/workspace", methods=["GET", "POST"])
@investor_bp.route("/deal_workspace", methods=["GET", "POST"])
@login_required
@role_required("investor")
def deal_workspace():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        flash("Profile not found.", "danger")
        return redirect(url_for("investor.command_center"))

    saved_props = (
        SavedProperty.query
        .filter_by(**_profile_id_filter(SavedProperty, ip.id))
        .order_by(SavedProperty.created_at.desc())
        .all()
    )

    prop_id = request.values.get("prop_id")
    selected_prop = None

    if prop_id:
        try:
            pid = int(prop_id)
            selected_prop = SavedProperty.query.filter_by(
                id=pid, **_profile_id_filter(SavedProperty, ip.id)
            ).first()
        except Exception:
            selected_prop = None

    mode = (request.values.get("mode") or "flip").lower()
    if mode not in ("flip", "rental", "airbnb"):
        mode = "flip"

    inputs = request.form if request.method == "POST" else ImmutableMultiDict()

    comps = {}
    resolved = None
    comparison = None
    recommendation = None
    results = None
    ai_summary = None
    risk_flags = []
    timeline = {}
    material_costs = {}
    rehab_notes = {}

    # POST with no property selected (keep behavior)
    if request.method == "POST" and not selected_prop:
        flash("Please select a saved property first.", "warning")
        return render_template(
            "investor/deal_workspace.html",
            investor=ip,
            saved_props=saved_props,
            selected_prop=None,
            prop_id=None,
            mode=mode,
            comps=comps,
            deal=deal,
            resolved=resolved,
            comparison=None,
            recommendation=recommendation,
            results=None,
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

    if request.method == "POST" and selected_prop and comps and comparison:
        base = comparison.get(mode) or comparison.get("flip") or {}
        results = dict(base) if isinstance(base, dict) else base.__dict__.copy()

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
        "investor/deal_workspace.html",
        investor=ip,
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


@investor_bp.route("/deals", methods=["GET"])
@investor_bp.route("/deals/list", methods=["GET"])
@login_required
@role_required("investor")
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
    return render_template("investor/deals_list.html", deals=deals, status=status, q=q)


@investor_bp.route("/deals/<int:deal_id>", methods=["GET"])
@login_required
@role_required("investor")
def deal_detail(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first_or_404()

    mockups = (RenovationMockup.query
        .filter_by(deal_id=deal_id, user_id=current_user.id)
        .order_by(RenovationMockup.created_at.desc())
        .all())

    partners = Partner.query.filter_by(user_id=current_user.id).order_by(Partner.created_at.desc()).all()

    return render_template("investor/deal_detail.html", deal=deal, mockups=mockups, partners=partners)
    
@investor_bp.route("/deals/<int:deal_id>/dealbook", methods=["GET"])
@login_required
@role_required("investor")
def deal_book(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first_or_404()

    results = deal.results_json or {}
    comps = deal.comps_json or {}
    resolved = deal.resolved_json or {}

    rehab = (resolved.get("rehab") or {})
    featured = rehab.get("featured") or {}

    # Optional convenience pulls
    prop = (resolved.get("property") or {})
    address = prop.get("address") or deal.title or f"Deal #{deal.id}"
    
    saved_property_id=deal.saved_property_id
   
    mockups = RenovationMockup.query.filter_by(
        deal_id=deal_id,
        user_id=current_user.id
    ).order_by(RenovationMockup.created_at.desc()).all()

   
    return render_template(
        "investor/deal_book.html",
        deal=deal,
        results=results,
        comps=comps,
        resolved=resolved,
        rehab=rehab,
        mockups=mockups,
        featured=featured,
        address=address,
    )

@investor_bp.route("/deals/<int:deal_id>/design/select", methods=["POST"])
@investor_bp.route("/deals/<int:deal_id>/select_design", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
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

# =========================================================
# 🤝 INVESTOR • DESIGN SHARE + DEAL CRUD + REVEAL + VISUALIZER
# =========================================================

@investor_bp.route("/deals/<int:deal_id>/design/share", methods=["POST"])
@investor_bp.route("/deals/<int:deal_id>/share_design", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
def deal_share_design(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first_or_404()

    image_url = (request.form.get("image_url") or "").strip() or (getattr(deal, "final_after_url", "") or "")
    partner_ids = split_ids(request.form.get("partner_ids") or "")
    note = (request.form.get("note") or "").strip()

    if not image_url:
        return jsonify({"status": "error", "message": "Select a design first."}), 400
    if not partner_ids:
        return jsonify({"status": "error", "message": "Choose at least one partner."}), 400

    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    ip_id = ip.id if ip else None

    now = datetime.utcnow()
    partners = (Partner.query
        .filter(Partner.id.in_(partner_ids))
        .filter(Partner.active == True)
        .filter(Partner.approved == True)
        .filter(Partner.paid_until >= now)
        .all())

    if not partners:
        return jsonify({"status": "error", "message": "No valid partners selected (must be approved + active + paid)."}), 400

    deal_link = url_for("investor.deal_detail", deal_id=deal.id, _external=True)
    rehab_link = url_for("investor.deal_rehab", deal_id=deal.id, _external=True)
    reveal_link = url_for("investor.deal_reveal", deal_id=deal.id, _external=True)

    sent = 0
    for p in partners:
        msg = (
            (note + "\n\n" if note else "") +
            f"Selected renovation design:\n{image_url}\n\n"
            f"Rehab Studio:\n{rehab_link}\n"
            f"Deal:\n{deal_link}\n"
            f"Reveal:\n{reveal_link}\n"
        )

        # Existing pending request (supports old borrower_* field names or new investor_* names)
        existing_q = PartnerConnectionRequest.query.filter_by(
            partner_id=p.id,
            status="pending"
        )

        if hasattr(PartnerConnectionRequest, "investor_user_id"):
            existing_q = existing_q.filter_by(investor_user_id=current_user.id)
        else:
            existing_q = existing_q.filter_by(borrower_user_id=current_user.id)

        existing = existing_q.order_by(PartnerConnectionRequest.created_at.desc()).first()

        if existing and (getattr(existing, "message", "") or "").strip() == msg.strip():
            continue

        req = PartnerConnectionRequest(
            partner_id=p.id,
            category=p.category,
            message=msg,
            status="pending",
        )

        # Prefer investor fields if present, otherwise fallback to borrower fields
        if not _set_if_attr(req, "investor_user_id", current_user.id):
            _set_if_attr(req, "borrower_user_id", current_user.id)

        if ip_id is not None:
            if not _set_if_attr(req, "investor_profile_id", ip_id):
                _set_if_attr(req, "borrower_profile_id", ip_id)

        db.session.add(req)
        sent += 1

    db.session.commit()
    return jsonify({"status": "ok", "sent": sent, "failed": 0})

@investor_bp.route("/deals/<int:deal_id>/rehab", methods=["GET"])
@login_required
@role_required("investor")
def deal_rehab(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first_or_404()

    payload = deal.resolved_json or {}
    payload = payload if isinstance(payload, dict) else {}
    before_url = (payload.get("rehab", {}) or {}).get("before_url") or ""
    
    mockups = (RenovationMockup.query
        .filter_by(deal_id=deal_id, user_id=current_user.id)
        .order_by(RenovationMockup.created_at.desc())
        .all())

    # fallback (if you generated before attaching deal_id)
    if not mockups and getattr(deal, "saved_property_id", None):
        mockups = (RenovationMockup.query
            .filter_by(saved_property_id=deal.saved_property_id, user_id=current_user.id)
            .order_by(RenovationMockup.created_at.desc())
            .all())

    featured = (deal.resolved_json or {}).get("rehab", {}).get("featured", {})
    return render_template(
        "investor/deal_rehab_studio.html",
        deal=deal,
        mockups=mockups,
        before_url=before_url,
        featured=featured
    )

@investor_bp.route("/deals/<int:deal_id>/rehab", methods=["GET"])
@login_required
@role_required("investor")
def deal_rehab_studio(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first_or_404()

    mockups = (RenovationMockup.query
        .filter_by(deal_id=deal_id, user_id=current_user.id)
        .order_by(RenovationMockup.created_at.desc())
        .all())

    # "before" seed (best effort)
    before_url = None
    try:
        before_url = (deal.resolved_json or {}).get("rehab", {}).get("before_url")
    except Exception:
        before_url = None
    if not before_url and mockups:
        before_url = mockups[0].before_url

    return render_template(
        "investor/deal_rehab_studio.html",
        deal=deal,
        mockups=mockups,
        before_url=before_url
    )


@investor_bp.route("/deals/<int:deal_id>/rehab/feature", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
def deal_feature_reveal(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first()
    if not deal:
        return jsonify({"status": "error", "message": "Deal not found."}), 404

    after_url = (request.form.get("after_url") or "").strip()
    before_url = (request.form.get("before_url") or "").strip()  # optional, but nice to store
    style_preset = (request.form.get("style_preset") or "").strip()
    style_prompt = (request.form.get("style_prompt") or "").strip()

    if not after_url:
        return jsonify({"status": "error", "message": "after_url is required."}), 400

    # ✅ Keep internal only
    deal.reveal_is_public = False

    # ✅ Persist featured “HGTV reveal” info in resolved_json (no migration)
    data = deal.resolved_json or {}
    data.setdefault("rehab", {})
    rehab = data["rehab"]

    rehab["featured"] = {
        "after_url": after_url,
        "before_url": before_url or rehab.get("featured", {}).get("before_url"),
        "style_preset": style_preset or rehab.get("featured", {}).get("style_preset"),
        "style_prompt": style_prompt or rehab.get("featured", {}).get("style_prompt"),
        "featured_at": datetime.utcnow().isoformat()
    }
    data["rehab"] = rehab
    deal.resolved_json = data

    db.session.commit()

    return jsonify({
        "status": "ok",
        "deal_id": deal.id,
        "featured": rehab["featured"]
    })
    
@investor_bp.route("/deals/save", methods=["POST"])
@investor_bp.route("/deals/save_deal", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
def save_deal():
    property_id = request.form.get("property_id") or None
    strategy = request.form.get("mode") or request.form.get("strategy") or None
    title = request.form.get("title") or None
    saved_property_id = request.form.get("saved_property_id") or None

    try:
        saved_property_id = int(saved_property_id) if saved_property_id else None
    except Exception:
        saved_property_id = None

    results_json = safe_json_loads(request.form.get("results_json"), default={})
    inputs_json  = safe_json_loads(request.form.get("inputs_json"), default={})
    comps_json    = safe_json_loads(request.form.get("comps_json"), default={})
    resolved_json = safe_json_loads(request.form.get("resolved_json"), default={})

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
    return redirect(url_for("investor.deal_detail", deal_id=deal.id))

@investor_bp.route("/deals/<int:deal_id>/reveal/publish", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
def publish_reveal(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first_or_404()

    if not deal.reveal_public_id:
        deal.reveal_public_id = uuid.uuid4().hex[:16]  # short + shareable

    deal.reveal_is_public = True
    deal.reveal_published_at = datetime.utcnow()

    db.session.commit()

    public_url = url_for("investor.public_reveal", public_id=deal.reveal_public_id, _external=True)
    return jsonify({"status": "ok", "public_url": public_url})

@investor_bp.route("/reveal/<string:public_id>", methods=["GET"])
def public_reveal(public_id):
    deal = Deal.query.filter_by(reveal_public_id=public_id, reveal_is_public=True).first_or_404()

    mockups = (RenovationMockup.query
        .filter_by(deal_id=deal.id)
        .order_by(RenovationMockup.created_at.desc())
        .all())

    return render_template("public/deal_reveal_public.html", deal=deal, mockups=mockups)

@investor_bp.route("/deals/<int:deal_id>/edit", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
def deal_edit(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first_or_404()
    deal.title = request.form.get("title", deal.title)
    deal.notes = request.form.get("notes", deal.notes)

    status = request.form.get("status")
    if status in ("active", "archived"):
        deal.status = status

    db.session.commit()
    flash("Deal updated.", "success")
    return redirect(url_for("investor.deal_detail", deal_id=deal.id))


@investor_bp.route("/deals/<int:deal_id>/delete", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
def deal_delete(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first_or_404()
    db.session.delete(deal)
    db.session.commit()
    flash("Deal deleted.", "success")
    return redirect(url_for("investor.deals_list"))


@investor_bp.route("/deals/<int:deal_id>/open", methods=["GET"])
@login_required
@role_required("investor")
def deal_open(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first_or_404()
    if deal.saved_property_id:
        return redirect(url_for("investor.deal_workspace", prop_id=deal.saved_property_id, mode=deal.strategy or "flip"))
    flash("This deal is not linked to a saved property yet.", "warning")
    return redirect(url_for("investor.deal_workspace"))


@investor_bp.route("/deals/<int:deal_id>/reveal", methods=["GET"])
@investor_bp.route("/deal/<int:deal_id>/reveal", methods=["GET"])
@login_required
@role_required("investor")
def deal_reveal(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first_or_404()
    
    after_url = request.form.get("after_url")
    resolved = deal.resolved_json or {}
    rehab = resolved.get("rehab", {})
    featured = rehab.get("featured")
    
    # Pull mockups tied to deal first
    mockups = (RenovationMockup.query
        .filter_by(deal_id=deal_id, user_id=current_user.id)
        .filter(RenovationMockup.after_url == after_url)
        .filter((RenovationMockup.deal_id == deal_id) | (RenovationMockup.saved_property_id == deal.saved_property_id))
        .order_by(RenovationMockup.created_at.desc())
        .first())

    # Fallback: if none tied to deal, use saved_property_id mockups
    if not mockups and getattr(deal, "saved_property_id", None):
        mockups = (RenovationMockup.query
            .filter_by(saved_property_id=deal.saved_property_id, user_id=current_user.id)
            .order_by(RenovationMockup.created_at.desc())
            .all())

    # ✅ Featured reveal support (internal)
    featured_after = None
    try:
        featured_after = (deal.resolved_json or {}).get("rehab", {}).get("featured", {}).get("after_url")
    except Exception:
        featured_after = None

    featured_mockup = None
    if featured_after and mockups:
        for m in mockups:
            if (m.after_url or "").strip() == (featured_after or "").strip():
                featured_mockup = m
                break

    # Pass featured_mockup so template can use it as lead
    return render_template(
        "investor/deal_reveal.html",
        deal=deal,
        deal_id=deal_id,
        mockups=mockups,
        featured_mockup=featured_mockup,
        featured=featured
    )

@investor_bp.route("/deals/visualizer", methods=["POST"])
@investor_bp.route("/renovation_visualizer", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
def renovation_visualizer():
    image_file = request.files.get("image_file")
    image_url = (request.form.get("image_url") or "").strip()

    style_prompt = (request.form.get("style_prompt") or "").strip()
    style_preset = (request.form.get("style_preset") or "").strip()
    variations = safe_int(request.form.get("variations"), default=2, min_v=1, max_v=4)
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

    # ----------------------------
    # Parse IDs + deal linking
    # ----------------------------
    saved_property_id = None
    if saved_property_id_raw:
        try:
            saved_property_id = int(saved_property_id_raw)
        except Exception:
            saved_property_id = None

    deal = None
    deal_id = None
    if deal_id_raw:
        try:
            deal_id = int(deal_id_raw)
        except Exception:
            deal_id = None

    if deal_id:
        deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first()
        if not deal:
            return jsonify({"status": "error", "message": "Deal not found or not authorized."}), 404

        if saved_property_id is None and getattr(deal, "saved_property_id", None):
            saved_property_id = deal.saved_property_id

        if not property_id and getattr(deal, "property_id", None):
            property_id = deal.property_id

    try:
        raw = image_file.read() if image_file else download_image_bytes(image_url)
        if not raw:
            return jsonify({"status": "error", "message": "Empty image input."}), 400

        # ----------------------------
        # Upload BEFORE to R2
        # ----------------------------
        before_webp = to_webp_bytes(raw, max_size=1600, quality=86)
        before_up = r2_put_bytes(
            before_webp,
            subdir=f"visualizer/{current_user.id}/before",
            content_type="image/webp",
            filename=f"{uuid.uuid4().hex}_before.webp",
        )
        before_url = before_up["url"]

        # ----------------------------
        # Persist "current before" on deal
        # ----------------------------
        if deal is not None:
            try:
                payload = deal.resolved_json or {}
                payload = payload if isinstance(payload, dict) else {}
                payload.setdefault("rehab", {})
                payload["rehab"]["before_url"] = before_url
                deal.resolved_json = payload
                db.session.commit()
            except Exception:
                db.session.rollback()

        # ----------------------------
        # 🔥 CALL YOUR GPU RENOVATION ENGINE (NEW: /v1/renovate) 
        # ----------------------------
        mode = (request.form.get("mode") or "photo").strip()  # "photo" or "blueprint"

        # Engine preset should be one of your server presets
        engine_preset = "luxury_modern"
        if style_preset == "modern":
            engine_preset = "clean_minimal"
        elif style_preset == "luxury":
            engine_preset = "luxury_modern"
        elif style_preset in ("airbnb", "flip", "budget"):
            engine_preset = "modern_farmhouse"

        # Send either image_url OR base64. Since you already uploaded to R2, use image_url.
        payload = {
            "image_url": before_url,
            "mode": mode,
            "preset": engine_preset,
            "prompt": final_prompt,
            "count": variations,
            "steps": 33 if mode == "photo" else 38,
            "strength": 0.38 if mode == "photo" else 0.48,
            "controlnet_scale": 0.78 if mode == "photo" else 0.93,
            "guidance": 6.5,
            "width": 1024,
            "height": 1024,
        }

        # ✅ point to your engine (local dev)
        headers={"X-API-Key": os.getenv("RENOVATION_API_KEY","")}
        RENOVATION_ENGINE_URL = os.getenv("RENOVATION_ENGINE_URL", "http://localhost:8000/v1/renovate")

        engine_res = requests.post(
            RENOVATION_ENGINE_URL,
            json={
                "image_url": before_url,          # ✅ use the R2-hosted before image
                "mode": "photo",
                "preset": "luxury_modern",        # or map from your Ravlo presets
                "prompt": final_prompt,
                "count": variations,
                "steps": 28,
                "strength": 0.38,
                "controlnet_scale": 0.78,
                "guidance": 6.5,
                "width": 1024,
                "height": 1024,
            },
            timeout=900
        )
        engine_res.raise_for_status()
        engine_json = engine_res.json()

        images_b64 = engine_json.get("images_base64", [])
        after_urls = []

        for b64 in images_b64:
            try:
                # decode base64 → bytes
                raw_png = base64.b64decode(b64)

                # open image
                img = Image.open(io.BytesIO(raw_png)).convert("RGB")

                # convert to WEBP for Ravlo (smaller + faster)
                buf = io.BytesIO()
                img.save(buf, format="WEBP", quality=90)

                upload = r2_put_bytes(
                    buf.getvalue(),
                    subdir=f"visualizer/{current_user.id}/after",
                    content_type="image/webp",
                    filename=f"{uuid.uuid4().hex}_after.webp",
                )

                after_urls.append(upload["url"])

            except Exception as e:
                print("After image upload failed:", e)

        # ----------------------------
        # Save mockups to DB
        # ----------------------------
        if save_to_deal and deal is not None and after_urls:
            ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
            ip_id = ip.id if ip else None

            for after_url in after_urls:
                db.session.add(RenovationMockup(
                    user_id=current_user.id,
                    investor_profile_id=ip_id,
                    deal_id=deal.id,
                    saved_property_id=saved_property_id,
                    property_id=property_id,
                    before_url=before_url,
                    after_url=after_url,
                    style_prompt=final_prompt,
                    style_preset=style_preset
                ))
            db.session.commit()

        return jsonify({
            "status": "ok",
            "before_url": before_url,
            "images": after_urls,
            "prompt": final_prompt,
            "variations": variations,
            "save_to_deal": save_to_deal,
            "deal_id": deal_id,
            "saved_property_id": saved_property_id,
            "property_id": property_id,
        })

    except Exception as e:
        return jsonify({"status": "error", "message": f"Renovation generator failed: {e}"}), 500

# =========================================================
# 📤 INVESTOR • UPLOADS + MOCKUPS + SEND TO TEAM + EXPORTS
# =========================================================

@investor_bp.route("/renovation_upload", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
def renovation_upload():

    file = request.files.get("photo")
    deal_id_raw = (request.form.get("deal_id") or "").strip()

    if not file or not deal_id_raw:
        return jsonify({"status": "error", "message": "Missing photo or deal_id"}), 400

    deal_id = int(deal_id_raw)

    try:
        raw = file.read()

        before_webp = to_webp_bytes(raw, max_size=1600, quality=86)

        up = r2_put_bytes(
            before_webp,
            subdir=f"visualizer/{current_user.id}/before",
            content_type="image/webp",
            filename=f"{uuid.uuid4().hex}_before.webp",
        )

        before_url = up["url"]

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first()

    if deal:
        payload = deal.resolved_json or {}
        payload = payload if isinstance(payload, dict) else {}
        payload.setdefault("rehab", {})
        payload["rehab"]["before_url"] = before_url
        deal.resolved_json = payload
        db.session.commit()

    return jsonify({
        "status": "ok",
        "url": before_url
    })

@investor_bp.route("/deals/<int:deal_id>/mockups/save", methods=["POST"])
@investor_bp.route("/deals/<int:deal_id>/mockups/save_legacy", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
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

@investor_bp.route("/blueprint_to_room", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
def blueprint_to_room():
    blueprint_file = request.files.get("blueprint_file")
    blueprint_url = (request.form.get("blueprint_url") or "").strip()
    
    style_preset = (request.form.get("style_preset") or "luxury_modern").strip()
    renovation_level = (request.form.get("renovation_level") or "medium").lower()

    deal_id = request.form.get("deal_id")
    saved_property_id = request.form.get("saved_property_id")

    if not blueprint_file and not blueprint_url:
        return jsonify({"status": "error", "message": "Provide blueprint_file or blueprint_url."}), 400

    # 1) Upload blueprint to R2
    try:
        raw = blueprint_file.read() if blueprint_file else download_image_bytes(blueprint_url)
        if not raw:
            return jsonify({"status": "error", "message": "Empty blueprint input."}), 400

        blueprint_webp = to_webp_bytes(raw, max_size=2000, quality=90)
        up = r2_put_bytes(
            blueprint_webp,
            subdir=f"blueprints/{current_user.id}",
            content_type="image/webp",
            filename=f"{uuid.uuid4().hex}_blueprint.webp",
        )
        blueprint_url = up["url"]
    except Exception as e:
        return jsonify({"status": "error", "message": f"Blueprint upload failed: {e}"}), 500

    # 2) Optional: Extract structure + infer room type (keep your current logic)
    structure = None
    room_type = "room"
    try:
        structure = extract_blueprint_structure(blueprint_url)
        room_type = infer_room_type(structure) or "room"
        ENGINE_PRESETS = {"luxury_modern","modern_farmhouse","clean_minimal"}
        engine_preset = style_preset if style_preset in ENGINE_PRESETS else "luxury_modern"
    except Exception as e:
        # You can decide if blueprint parsing is REQUIRED or OPTIONAL.
        # For now: optional (still generate even if parsing fails).
        print("Blueprint parsing warning:", e)

    # 3) Build prompt for the engine
    # Make sure build_blueprint_prompt returns a strong SDXL-friendly description.
    style_prompt = build_blueprint_prompt(room_type, style_preset, renovation_level)

    # 4) Call GPU engine: we can use image_url since your blueprint is hosted (R2)
    # Engine returns base64 PNGs -> we upload them to R2 as webp for your app.
    try:
        payload = {
            "image_url": blueprint_url,
            "preset": style_preset if style_preset in ("luxury_modern", "modern_farmhouse", "clean_minimal") else "luxury_modern",
            "prompt": style_prompt,
            "count": 2,
            "steps": 35,
            "strength": 0.40,           # blueprint -> render usually needs a bit more change
            "controlnet_scale": 0.85,   # keep layout locked
            "guidance": 6.5,
            "width": 1024,
            "height": 1024,
        }

        engine_res = requests.post(
            f"{GPU_BASE_URL}/v1/renovate",
            json=payload,
            timeout=900
        )
        engine_res.raise_for_status()
        engine_json = engine_res.json()
        images_b64 = engine_json.get("images_base64", []) or []
    except Exception as e:
        return jsonify({"status": "error", "message": f"Renovation engine failed: {e}"}), 500

    # 5) Upload AFTER images to R2
    after_urls: list[str] = []
    for b64 in images_b64:
        try:
            img_bytes = base64.b64decode(b64)
            img_webp = to_webp_bytes(img_bytes, max_size=1600, quality=86)
            up = r2_put_bytes(
                img_webp,
                subdir=f"visualizer/{uuid.uuid4().hex}/after",
                content_type="image/webp",
                filename=f"{uuid.uuid4().hex}_after.webp",
            )
            after_urls.append(up["url"])
        except Exception as e:
            print("Upload after failed:", e)

    # 6) Save to deal (if provided)
    if deal_id and after_urls:
        try:
            for url in after_urls:
                db.session.add(RenovationMockup(
                    user_id=current_user.id,
                    deal_id=deal_id,
                    saved_property_id=saved_property_id,
                    before_url=blueprint_url,
                    after_url=url,
                    style_preset=style_preset,
                    style_prompt=f"Blueprint → {room_type} ({renovation_level})",
                    mode="blueprint"
                ))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print("DB save failed:", e)

    return jsonify({
        "status": "ok",
        "blueprint_url": blueprint_url,
        "room_type": room_type,
        "structure": structure,
        "after": after_urls
    })

@investor_bp.route("/ai/rehab_scope", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
def ai_rehab_scope():

    image_url = request.json.get("image_url")

    engine_url = os.getenv("RENOVATION_ENGINE_URL").replace(
        "/v1/renovate",
        "/v1/rehab_scope"
    )

    res = requests.post(
        engine_url,
        json={"image_url": image_url},
        timeout=60
    )

    return jsonify(res.json())


@investor_bp.route("/deals/send-to-team", methods=["POST"])
@investor_bp.route("/deals/send-to-lo", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
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

    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    lo_user_id = None
    if ip:
        if getattr(ip, "assigned_officer_id", None):
            lo_profile = LoanOfficerProfile.query.get(ip.assigned_officer_id)
            if lo_profile:
                lo_user_id = lo_profile.user_id

        if not lo_user_id and getattr(ip, "assigned_to", None):
            lo_user_id = ip.assigned_to

    if not lo_user_id:
        flash("No assigned Loan Officer found.", "warning")
        return redirect(url_for("investor.deal_workspace", prop_id=property_id, mode=strategy))

    share = DealShare(
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

    # Prefer investor fields if present, otherwise fallback to borrower fields
    if not _set_if_attr(share, "investor_user_id", current_user.id):
        _set_if_attr(share, "borrower_user_id", current_user.id)

    db.session.add(share)
    db.session.commit()

    flash("Sent to your team.", "success")
    return redirect(url_for("investor.deal_workspace", prop_id=property_id, mode=strategy))


@investor_bp.route("/deals/<int:deal_id>/export/report", methods=["GET"])
@investor_bp.route("/deals/<int:deal_id>/export-report", methods=["GET"])
@login_required
@role_required("investor")
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


@investor_bp.route("/deals/<int:deal_id>/export/rehab-scope", methods=["GET"])
@investor_bp.route("/deals/<int:deal_id>/export-rehab-scope", methods=["GET"])
@login_required
@role_required("investor")
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
# 💬 INVESTOR • MESSAGES
# =========================================================

@investor_bp.route("/messages", methods=["GET"])
@login_required
@role_required("investor")
def messages():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
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
        "investor/messages.html",
        investor=ip,
        officers=officers,
        messages=msgs,
        selected_receiver=receiver_id,
        title="Messages",
        active_tab="messages"
    )


@investor_bp.route("/messages/send", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
def send_message():
    content = request.form.get("content") or ""
    receiver_id = request.form.get("receiver_id")

    if not receiver_id or not content.strip():
        flash("⚠️ Please select a recipient and enter a message.", "warning")
        return redirect(url_for("investor.messages"))

    db.session.add(Message(
        sender_id=current_user.id,
        receiver_id=int(receiver_id),
        content=content,
        created_at=datetime.utcnow(),
    ))
    db.session.commit()

    flash("📩 Message sent!", "success")
    return redirect(url_for("investor.messages", receiver_id=receiver_id))


# =========================================================
# 🤖 INVESTOR • AI HUB / ASK AI
# =========================================================

@investor_bp.route("/ai", methods=["GET"])
@investor_bp.route("/ask-ai", methods=["GET"])
@login_required
@role_required("investor")
def ask_ai_page():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

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
        "investor/ask_ai.html",
        investor=ip,
        prefill=prefill,
        form=form,
        interactions=interactions,
        title="Ravlo AI",
        active_tab="ai"
    )


@investor_bp.route("/ai", methods=["POST"])
@investor_bp.route("/ask-ai", methods=["POST"])
@login_required
@role_required("investor")
def ask_ai_post():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    question = request.form.get("question") or ""
    parent_id = request.form.get("parent_id")

    assistant = AIAssistant()
    ai_reply = assistant.generate_reply(question, "investor_ai")

    chat = AIAssistantInteraction(
        user_id=current_user.id,
        question=question,
        response=ai_reply,
        parent_id=parent_id,
        timestamp=datetime.utcnow(),
    )

    # schema-safe: store investor_profile_id if exists, else borrower_profile_id
    if ip:
        if hasattr(chat, "investor_profile_id"):
            chat.investor_profile_id = ip.id
        elif hasattr(chat, "borrower_profile_id"):
            chat.borrower_profile_id = ip.id

    db.session.add(chat)
    db.session.commit()

    next_steps = assistant.generate_reply(
        f"Suggest next steps after answering: {question}.",
        "investor_next_steps",
    )
    upload_trigger = "document" in question.lower() or "upload" in question.lower()

    interactions = (AIAssistantInteraction.query
        .filter_by(user_id=current_user.id)
        .order_by(AIAssistantInteraction.timestamp.desc())
        .all())

    return render_template(
        "investor/ai_response.html",
        form=request.form,
        response=ai_reply,
        steps=next_steps,
        upload_trigger=upload_trigger,
        interactions=interactions,
        chat=chat,
        investor=ip,
        title="Ravlo AI Response",
        active_tab="ai"
    )


@investor_bp.route("/ai/hub", methods=["GET"])
@investor_bp.route("/ai_hub", methods=["GET"])
@login_required
@role_required("investor")
def ai_hub():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    interactions = (AIAssistantInteraction.query
        .filter_by(user_id=current_user.id)
        .order_by(AIAssistantInteraction.timestamp.desc())
        .limit(5)
        .all())

    assistant = AIAssistant()
    try:
        ai_summary = assistant.generate_reply(
            f"Provide an overview of the investor’s AI activity ({len(interactions)} items).",
            "investor_ai_hub",
        )
    except Exception:
        ai_summary = "⚠️ AI summary unavailable."

    return render_template(
        "investor/ai_hub.html",
        investor=ip,
        interactions=interactions,
        ai_summary=ai_summary,
        title="AI Hub",
        active_tab="ai"
    )


@investor_bp.route("/ai/response/<int:chat_id>", methods=["GET"])
@investor_bp.route("/ask-ai/response/<int:chat_id>", methods=["GET"])
@login_required
@role_required("investor")
def ask_ai_response(chat_id):
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    chat = AIAssistantInteraction.query.get_or_404(chat_id)

    # Security: only owner can view
    if chat.user_id != current_user.id:
        return "Unauthorized", 403

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
        "investor/ai_response.html",
        investor=ip,
        response=chat.response,
        chat=chat,
        form=form,
        interactions=interactions,
        title="AI Assistant Response",
        active_tab="ai"
    )


# =========================================================
# 📈 INVESTOR • ANALYTICS + ACTIVITY + BUDGET
# =========================================================

@investor_bp.route("/intelligence/analysis", methods=["GET"])
@investor_bp.route("/analysis", methods=["GET"])
@login_required
@role_required("investor")
def analysis():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    loans = LoanApplication.query.filter_by(**_profile_id_filter(LoanApplication, ip.id)).all() if ip else []
    total_loan_amount = sum([getattr(loan, "loan_amount", 0) or 0 for loan in loans])

    # NOTE: your statuses are inconsistent elsewhere ("Verified"/"Pending" vs "verified"/"pending")
    verified_docs = LoanDocument.query.filter_by(**_profile_id_filter(LoanDocument, ip.id), status="Verified").count() if ip else 0
    pending_docs  = LoanDocument.query.filter_by(**_profile_id_filter(LoanDocument, ip.id), status="Pending").count() if ip else 0

    assistant = AIAssistant()
    try:
        ai_summary = assistant.generate_reply(
            f"Summarize investor analytics: {len(loans)} loans totaling ${total_loan_amount}, "
            f"{verified_docs} verified docs, {pending_docs} pending.",
            "investor_analysis",
        )
    except Exception:
        ai_summary = "⚠️ AI summary unavailable."

    stats = {
        "total_loans": len(loans),
        "total_amount": f"${total_loan_amount:,.2f}",
        "verified_docs": verified_docs,
        "pending_docs": pending_docs,
    }

    return render_template(
        "investor/analysis.html",
        investor=ip,
        loans=loans,
        stats=stats,
        ai_summary=ai_summary,
        title="Investor Analytics",
        active_tab="analysis"
    )


@investor_bp.route("/intelligence/activity", methods=["GET"])
@investor_bp.route("/activity", methods=["GET"])
@login_required
@role_required("investor")
def activity():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        flash("Profile not found.", "danger")
        return redirect(url_for("investor.command_center"))

    # BorrowerActivity model name kept for now (schema-safe)
    activities = (BorrowerActivity.query
        .filter_by(**_profile_id_filter(BorrowerActivity, ip.id))
        .order_by(BorrowerActivity.timestamp.desc())
        .all())

    assistant = AIAssistant()
    try:
        ai_summary = assistant.generate_reply(
            f"Generate investor activity summary of {len(activities)} recent actions.",
            "investor_activity",
        )
    except Exception:
        ai_summary = "⚠️ AI summary unavailable."

    return render_template(
        "investor/activity.html",
        investor=ip,
        activities=activities,
        ai_summary=ai_summary,
        title="Activity",
        active_tab="activity"
    )


@investor_bp.route("/planning/budget", methods=["GET", "POST"])
@investor_bp.route("/budget", methods=["GET", "POST"])
@login_required
@role_required("investor")
def budget():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    assistant = AIAssistant()

    if request.method == "POST":
        expenses = request.form.to_dict()
        ai_tip = assistant.generate_reply(
            f"Analyze investor expenses: {expenses}",
            "investor_budget",
        )
        return render_template(
            "investor/budget_result.html",
            investor=ip,
            ai_tip=ai_tip,
            title="Budget Results",
            active_tab="budget"
        )

    return render_template(
        "investor/budget.html",
        investor=ip,
        title="Budget Planner",
        active_tab="budget"
    )


@investor_bp.route("/ai/deal-insight", methods=["POST"])
@investor_bp.route("/ai_deal_insight", methods=["POST"])
@login_required
@role_required("investor")
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
        "investor_ai_deal_insight",
    )
    return jsonify({"reply": ai_reply})


# =========================================================
# ✍️ INVESTOR • E-SIGN
# =========================================================

@investor_bp.route("/sign", methods=["GET"])
@investor_bp.route("/esign", methods=["GET"])
@login_required
@role_required("investor")
def investor_esign():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    docs = ESignedDocument.query.filter_by(**_profile_id_filter(ESignedDocument, ip.id)).all() if ip else []
    return render_template("investor/esign.html", investor=ip, docs=docs, title="E-Sign", active_tab="esign")

# =========================================================
# ✍️ INVESTOR • E-SIGN SIGN ACTION
# =========================================================




@investor_bp.route("/sign/<int:doc_id>", methods=["POST"])
@investor_bp.route("/esign/sign/<int:doc_id>", methods=["POST"])
@login_required
@role_required("investor")
def investor_esign_sign(doc_id):
    doc = ESignedDocument.query.get_or_404(doc_id)

    # Security: ensure this doc belongs to the current investor (schema-safe)
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if ip:
        owner_ok = False
        if hasattr(doc, "investor_profile_id") and doc.investor_profile_id == ip.id:
            owner_ok = True
        elif hasattr(doc, "borrower_profile_id") and doc.borrower_profile_id == ip.id:
            owner_ok = True
        if not owner_ok:
            return "Unauthorized", 403

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

    # Attach signed doc into LoanDocument (schema-safe)
    ip_id = ip.id if ip else (getattr(doc, "investor_profile_id", None) or getattr(doc, "borrower_profile_id", None))

    ld = LoanDocument(
        name=f"{doc.name} (Signed)",
        file_path=signed_path,
        status="Uploaded",
        uploaded_at=datetime.utcnow(),
    )
    # Prefer investor_profile_id if available, else borrower_profile_id
    if hasattr(ld, "investor_profile_id"):
        ld.investor_profile_id = ip_id
    else:
        ld.borrower_profile_id = ip_id

    db.session.add(ld)
    db.session.commit()

    return redirect(url_for("investor.investor_esign"))


# =========================================================
# 💳 INVESTOR • PAYMENTS / BILLING
# =========================================================

@investor_bp.route("/billing", methods=["GET"])
@investor_bp.route("/payments", methods=["GET"])
@login_required
@role_required("investor")
def payments():
    user = current_user
    subscription_plan = getattr(user, "subscription_plan", "Free")

    payments = (PaymentRecord.query
        .filter_by(user_id=user.id)
        .order_by(PaymentRecord.timestamp.desc())
        .all())

    return render_template(
        "investor/payments.html",
        user=user,
        subscription_plan=subscription_plan,
        payments=payments,
        title="Billing",
        active_tab="billing"
    )


@investor_bp.route("/billing/checkout/<int:payment_id>", methods=["GET"])
@investor_bp.route("/payments/checkout/<int:payment_id>", methods=["GET"])
@login_required
@role_required("investor")
def checkout(payment_id):
    payment = PaymentRecord.query.get_or_404(payment_id)

    # Security: payment must belong to current user
    if getattr(payment, "user_id", None) != current_user.id:
        return "Unauthorized", 403

    borrower = getattr(payment, "borrower", None)

    checkout_session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": payment.payment_type},
                "unit_amount": int(float(payment.amount) * 100),
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=url_for("investor.payment_success", _external=True) + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=url_for("investor.payments", _external=True),
        metadata={"payment_id": payment.id, "borrower_id": getattr(borrower, "id", None)},
    )

    payment.stripe_payment_intent = checkout_session.payment_intent
    db.session.commit()
    return redirect(checkout_session.url, code=303)


@investor_bp.route("/billing/success", methods=["GET"])
@investor_bp.route("/payments/success", methods=["GET"])
@login_required
@role_required("investor")
def payment_success():
    session_id = request.args.get("session_id")
    if not session_id:
        flash("Payment session missing.", "warning")
        return redirect(url_for("investor.payments"))

    try:
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        payment_intent = checkout_session.get("payment_intent")
    except Exception as e:
        print("Stripe error:", e)
        flash("Unable to verify payment.", "danger")
        return redirect(url_for("investor.payments"))

    payment = PaymentRecord.query.filter_by(stripe_payment_intent=payment_intent).first()
    if not payment:
        flash("Payment record not found.", "warning")
        return redirect(url_for("investor.payments"))

    # Security: ensure payment belongs to this user
    if getattr(payment, "user_id", None) != current_user.id:
        return "Unauthorized", 403

    payment.status = "Paid"
    payment.paid_at = datetime.utcnow()
    db.session.commit()

    receipt_dir = "stripe_receipts"
    os.makedirs(receipt_dir, exist_ok=True)
    receipt_path = os.path.join(receipt_dir, f"{payment.id}_receipt.txt")
    with open(receipt_path, "w") as f:
        f.write(f"Payment of ${payment.amount} received for {payment.payment_type}.")

    # attach receipt as LoanDocument (schema-safe)
    ld = LoanDocument(
        loan_application_id=getattr(payment, "loan_id", None),
        name=f"{payment.payment_type} Receipt",
        file_path=receipt_path,
        doc_type="Receipt",
        status="Uploaded",
        uploaded_at=datetime.utcnow(),
    )

    pid = getattr(payment, "investor_profile_id", None) or getattr(payment, "borrower_profile_id", None)

    if hasattr(ld, "investor_profile_id"):
        ld.investor_profile_id = pid
    else:
        ld.borrower_profile_id = pid

    db.session.add(ld)
    db.session.commit()

    return render_template("investor/payment_success.html", payment=payment, title="Payment Success", active_tab="billing")


# =========================================================
# 📊 INVESTOR • MARKET SNAPSHOT
# =========================================================

@investor_bp.route("/intelligence/market", methods=["GET"])
@investor_bp.route("/market", methods=["GET"])
@login_required
@role_required("investor")
def market_snapshot_page():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        return redirect(url_for("investor.command_center"))

    active_property = (SavedProperty.query
        .filter_by(**_profile_id_filter(SavedProperty, ip.id))
        .order_by(SavedProperty.created_at.desc())
        .first())

    zipcode = active_property.zipcode if active_property else None
    market_snapshot = get_market_snapshot(zipcode) if zipcode else None

    return render_template(
        "investor/market_snapshot.html",
        investor=ip,
        active_property=active_property,
        market_snapshot=market_snapshot,
        title="Market Snapshot",
        active_tab="market"
    )
