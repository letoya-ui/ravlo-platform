import os
import requests
from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from LoanMVP.extensions import db, csrf
from LoanMVP.utils.decorators import role_required
from LoanMVP.forms import BorrowerProfileForm
from LoanMVP.ai.base_ai import AIAssistant

from LoanMVP.models.loan_models import BorrowerProfile, LoanApplication, BorrowerConsent
from LoanMVP.models.document_models import LoanDocument
from LoanMVP.models.underwriter_model import UnderwritingCondition
from LoanMVP.models.crm_models import Message

borrower_bp = Blueprint("borrower", __name__, url_prefix="/borrower")

RENTCAST_API_KEY = os.getenv("RENTCAST_API_KEY", "").strip()
RENTCAST_BASE_URL = "https://api.rentcast.io/v1"
# =========================================================
# Helpers
# =========================================================


def _rentcast_headers():
    return {
        "Accept": "application/json",
        "X-Api-Key": RENTCAST_API_KEY,
    }


def _safe_request(url, params=None, timeout=20):
    """
    Small helper so your route stays clean.
    """
    resp = requests.get(
        url,
        headers=_rentcast_headers(),
        params=params or {},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()

def get_current_borrower():
    return BorrowerProfile.query.filter_by(user_id=current_user.id).first()


def get_active_loan(borrower):
    if not borrower:
        return None
    return (
        LoanApplication.query.filter_by(
            borrower_profile_id=borrower.id,
            is_active=True
        )
        .order_by(LoanApplication.created_at.desc())
        .first()
    )


def safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def save_uploaded_file(file_storage):
    filename = secure_filename(file_storage.filename)
    save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    file_storage.save(save_path)
    return filename


# =========================================================
# Dashboard
# =========================================================

@borrower_bp.route("/dashboard")
@login_required
@role_required("borrower")
def dashboard():
    borrower = get_current_borrower()
    if not borrower:
        flash("Please complete your borrower profile first.", "warning")
        return redirect(url_for("borrower.create_profile"))

    loan = get_active_loan(borrower)

    loans = (
        LoanApplication.query.filter_by(borrower_profile_id=borrower.id)
        .order_by(LoanApplication.created_at.desc())
        .all()
    )

    documents = (
        LoanDocument.query.filter_by(borrower_profile_id=borrower.id)
        .order_by(LoanDocument.created_at.desc())
        .all()
    )

    conditions = []
    if loan:
        conditions = (
            UnderwritingCondition.query.filter_by(
                borrower_profile_id=borrower.id,
                loan_id=loan.id
            )
            .order_by(UnderwritingCondition.created_at.desc())
            .all()
        )

    open_conditions = [
        c for c in conditions
        if (c.status or "").lower() not in ["cleared", "completed", "waived"]
    ]

    progress_percent = 0
    if conditions:
        cleared = len([
            c for c in conditions
            if (c.status or "").lower() in ["cleared", "completed"]
        ])
        progress_percent = int((cleared / len(conditions)) * 100)

    ai_message = None
    try:
        assistant = AIAssistant()
        if loan and open_conditions:
            prompt = (
                f"Write a short, clear next-step message for a borrower. "
                f"They have {len(open_conditions)} open conditions. "
                f"The next item is: {open_conditions[0].description}."
            )
        elif loan:
            prompt = "Write a short borrower message saying their file is in review and they should monitor conditions and messages."
        else:
            prompt = "Write a short borrower message encouraging them to start their first funding application."

        ai_message = assistant.generate_reply(prompt, "borrower_next_step")
    except Exception:
        ai_message = None

    checklist_items = []
    if loan and open_conditions:
        for cond in open_conditions[:5]:
            checklist_items.append({
                "label": f"Submit item for: {cond.description}",
                "done": False
            })
    elif loan:
        checklist_items.append({
            "label": "All current conditions appear submitted",
            "done": True
        })
    else:
        checklist_items.append({
            "label": "Start your funding application",
            "done": False
        })

    return render_template(
        "borrower/dashboard.html",
        borrower=borrower,
        loan=loan,
        loans=loans,
        documents=documents,
        conditions=conditions,
        open_conditions=open_conditions,
        progress_percent=progress_percent,
        ai_message=ai_message,
        checklist_items=checklist_items,
        active_tab="dashboard",
        title="Borrower Dashboard",
    )


# =========================================================
# Profile
# =========================================================

@borrower_bp.route("/create-profile", methods=["GET", "POST"])
@csrf.exempt
@login_required
@role_required("borrower")
def create_profile():
    existing = get_current_borrower()
    if existing:
        return redirect(url_for("borrower.dashboard"))

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

        flash("Profile created successfully.", "success")
        return redirect(url_for("borrower.dashboard"))

    return render_template(
        "borrower/create_profile.html",
        form=form,
        active_tab=None,
        title="Create Profile",
    )


# =========================================================
# Application / Loans
# =========================================================

@borrower_bp.route("/apply", methods=["GET", "POST"])
@csrf.exempt
@login_required
@role_required("borrower")
def apply():
    borrower = get_current_borrower()
    if not borrower:
        flash("Please complete your borrower profile before applying.", "warning")
        return redirect(url_for("borrower.create_profile"))

    if request.method == "POST":
        loan_type = request.form.get("loan_type")
        amount = safe_float(request.form.get("amount"))
        property_address = (request.form.get("property_address") or "").strip()
        property_value = safe_float(request.form.get("property_value"), None)
        description = (request.form.get("description") or "").strip() or None

        try:
            assistant = AIAssistant()
            ai_summary = assistant.generate_reply(
                f"Create a short summary for a borrower applying for a {loan_type} loan on {property_address}.",
                "borrower_apply",
            )
        except Exception:
            ai_summary = None

        LoanApplication.query.filter_by(
            borrower_profile_id=borrower.id,
            is_active=True
        ).update({"is_active": False})

        loan = LoanApplication(
            borrower_profile_id=borrower.id,
            loan_type=loan_type,
            amount=amount,
            property_address=property_address,
            property_value=property_value,
            description=description,
            ai_summary=ai_summary,
            status="Submitted",
            is_active=True,
            created_at=datetime.utcnow(),
        )
        db.session.add(loan)
        db.session.commit()

        flash("Application submitted successfully.", "success")
        return redirect(url_for("borrower.loan_view", loan_id=loan.id))

    return render_template(
        "borrower/apply.html",
        borrower=borrower,
        active_tab="apply",
        title="Apply for Funding",
    )

@borrower_bp.route("/loan-center")
@login_required
@role_required("borrower")
def loan_center():
    """
    Borrower loan dashboard.
    Replace placeholder loan data with your real DB query later.
    """

    loans = [
        {
            "id": 1001,
            "property": "123 Main St, Tampa, FL",
            "amount": 250000,
            "status": "Under Review",
        }
    ]

    return render_template(
        "borrower/loan_center.html",
        loans=loans,
    )


@borrower_bp.route("/property-intelligence", methods=["GET", "POST"])
@csrf.exempt
@login_required
@role_required("borrower")
def property_intelligence():
    """
    Borrower enters an address and Ravlo pulls:
    - property record
    - value estimate
    - rent estimate
    from RentCast
    """

    property_data = None
    value_data = None
    rent_data = None
    address = ""

    if request.method == "POST":
        address = (request.form.get("address") or "").strip()

        if not address:
            flash("Please enter a property address.", "warning")
            return render_template(
                "borrower/property_intelligence.html",
                property_data=None,
                value_data=None,
                rent_data=None,
                address=address,
            )

        if not RENTCAST_API_KEY:
            flash("RentCast API key is missing. Add RENTCAST_API_KEY to your environment variables.", "danger")
            return render_template(
                "borrower/property_intelligence.html",
                property_data=None,
                value_data=None,
                rent_data=None,
                address=address,
            )

        try:
            # 1) Property record lookup by address
            properties = _safe_request(
                f"{RENTCAST_BASE_URL}/properties",
                params={
                    "address": address,
                    "limit": 1,
                },
            )

            if isinstance(properties, list) and properties:
                property_data = properties[0]
            else:
                flash("No property record was found for that address.", "warning")
                return render_template(
                    "borrower/property_intelligence.html",
                    property_data=None,
                    value_data=None,
                    rent_data=None,
                    address=address,
                )

            # Pull best available fields for valuation calls
            formatted_address = property_data.get("formattedAddress") or address
            city = property_data.get("city")
            state = property_data.get("state")
            zip_code = property_data.get("zipCode")
            bedrooms = property_data.get("bedrooms")
            bathrooms = property_data.get("bathrooms")
            square_footage = property_data.get("squareFootage")
            property_type = property_data.get("propertyType")

            avm_params = {
                "address": formatted_address,
            }

            # Add optional fields when present
            if city:
                avm_params["city"] = city
            if state:
                avm_params["state"] = state
            if zip_code:
                avm_params["zipCode"] = zip_code
            if bedrooms is not None:
                avm_params["bedrooms"] = bedrooms
            if bathrooms is not None:
                avm_params["bathrooms"] = bathrooms
            if square_footage is not None:
                avm_params["squareFootage"] = square_footage
            if property_type:
                avm_params["propertyType"] = property_type

            # 2) Value estimate
            try:
                value_data = _safe_request(
                    f"{RENTCAST_BASE_URL}/avm/value",
                    params=avm_params,
                )
            except requests.HTTPError:
                value_data = None

            # 3) Rent estimate (long-term)
            try:
                rent_data = _safe_request(
                    f"{RENTCAST_BASE_URL}/avm/rent/long-term",
                    params=avm_params,
                )
            except requests.HTTPError:
                rent_data = None

        except requests.HTTPError as e:
            status_code = getattr(e.response, "status_code", None)
            if status_code == 401:
                flash("RentCast authentication failed. Check your API key.", "danger")
            elif status_code == 404:
                flash("The property could not be found.", "warning")
            else:
                flash(f"RentCast request failed ({status_code or 'unknown error'}).", "danger")

        except requests.RequestException:
            flash("Unable to reach RentCast right now. Please try again.", "danger")

        except Exception:
            flash("Something went wrong while analyzing this property.", "danger")

    return render_template(
        "borrower/property_intelligence.html",
        property_data=property_data,
        value_data=value_data,
        rent_data=rent_data,
        address=address,
    )

@borrower_bp.route("/loan/<int:loan_id>")
@login_required
@role_required("borrower")
def loan_view(loan_id):
    borrower = get_current_borrower()
    if not borrower:
        flash("Please complete your borrower profile first.", "warning")
        return redirect(url_for("borrower.create_profile"))

    loan = LoanApplication.query.get_or_404(loan_id)
    if loan.borrower_profile_id != borrower.id:
        return "Unauthorized", 403

    documents = (
        LoanDocument.query.filter_by(
            borrower_profile_id=borrower.id,
            loan_id=loan.id
        )
        .order_by(LoanDocument.created_at.desc())
        .all()
    )

    conditions = (
        UnderwritingCondition.query.filter_by(
            borrower_profile_id=borrower.id,
            loan_id=loan.id
        )
        .order_by(UnderwritingCondition.created_at.desc())
        .all()
    )

    return render_template(
        "borrower/view_loan.html",
        borrower=borrower,
        loan=loan,
        documents=documents,
        conditions=conditions,
        active_tab="loans",
        title=f"Loan #{loan.id}",
    )


# =========================================================
# Documents
# =========================================================

@borrower_bp.route("/documents")
@login_required
@role_required("borrower")
def documents():
    borrower = get_current_borrower()
    if not borrower:
        flash("Please complete your borrower profile first.", "warning")
        return redirect(url_for("borrower.create_profile"))

    documents = (
        LoanDocument.query.filter_by(borrower_profile_id=borrower.id)
        .order_by(LoanDocument.created_at.desc())
        .all()
    )

    return render_template(
        "borrower/documents.html",
        borrower=borrower,
        documents=documents,
        active_tab="documents",
        title="Documents",
    )


@borrower_bp.route("/upload-document", methods=["GET", "POST"])
@csrf.exempt
@login_required
@role_required("borrower")
def upload_document():
    borrower = get_current_borrower()
    if not borrower:
        flash("Please complete your borrower profile first.", "warning")
        return redirect(url_for("borrower.create_profile"))

    loan = get_active_loan(borrower)

    if request.method == "POST":
        file = request.files.get("file")
        document_type = request.form.get("document_type") or "Other"
        document_name = request.form.get("document_name") or document_type

        if file and file.filename:
            filename = save_uploaded_file(file)

            doc = LoanDocument(
                borrower_profile_id=borrower.id,
                loan_id=loan.id if loan else None,
                file_name=filename,
                file_path=filename,
                document_type=document_type,
                document_name=document_name,
                status="Uploaded",
                uploaded_by=getattr(current_user, "email", str(current_user.id)),
                submitted_file=filename,
                submitted_at=datetime.utcnow(),
            )
            db.session.add(doc)
            db.session.commit()

            flash("Document uploaded successfully.", "success")
            return redirect(url_for("borrower.documents"))

        flash("Please choose a file to upload.", "warning")

    return render_template(
        "borrower/upload_document.html",
        borrower=borrower,
        active_tab="documents",
        title="Upload Document",
    )


# =========================================================
# Conditions
# =========================================================

@borrower_bp.route("/conditions")
@login_required
@role_required("borrower")

def conditions():
    borrower = get_current_borrower()
    if not borrower:
        flash("Please complete your borrower profile first.", "warning")
        return redirect(url_for("borrower.create_profile"))

    loan = get_active_loan(borrower)

    conditions = []
    if loan:
        conditions = (
            UnderwritingCondition.query.filter_by(
                borrower_profile_id=borrower.id,
                loan_id=loan.id
            )
            .order_by(UnderwritingCondition.created_at.desc())
            .all()
        )

    return render_template(
        "borrower/conditions.html",
        borrower=borrower,
        loan=loan,
        conditions=conditions,
        active_tab="conditions",
        title="Conditions",
    )


@borrower_bp.route("/condition/<int:cond_id>")
@login_required
@role_required("borrower")
def view_condition(cond_id):
    borrower = get_current_borrower()
    cond = UnderwritingCondition.query.get_or_404(cond_id)

    if not borrower or cond.borrower_profile_id != borrower.id:
        return "Unauthorized", 403

    return render_template(
        "borrower/condition_view.html",
        borrower=borrower,
        condition=cond,
        active_tab="conditions",
        title="Condition Detail",
    )


@borrower_bp.route("/conditions/upload/<int:cond_id>", methods=["POST"])
@csrf.exempt
@login_required
@role_required("borrower")
def upload_condition(cond_id):
    borrower = get_current_borrower()
    cond = UnderwritingCondition.query.get_or_404(cond_id)

    if not borrower or cond.borrower_profile_id != borrower.id:
        return "Unauthorized", 403

    file = request.files.get("file")
    if not file or not file.filename:
        flash("No file uploaded.", "warning")
        return redirect(url_for("borrower.conditions"))

    filename = save_uploaded_file(file)

    new_doc = LoanDocument(
        borrower_profile_id=borrower.id,
        loan_id=cond.loan_id,
        file_name=filename,
        file_path=filename,
        document_type=cond.condition_type or "Condition Support",
        document_name=cond.description,
        status="Submitted",
        uploaded_by=getattr(current_user, "email", str(current_user.id)),
        submitted_file=filename,
        submitted_at=datetime.utcnow(),
        notes=f"Uploaded for condition #{cond.id}",
    )
    db.session.add(new_doc)

    cond.status = "Submitted"
    db.session.commit()

    flash("Condition document uploaded successfully.", "success")
    return redirect(url_for("borrower.conditions"))


# =========================================================
# Messages
# =========================================================

@borrower_bp.route("/messages", methods=["GET", "POST"])
@csrf.exempt
@login_required
@role_required("borrower")
def messages():
    borrower = get_current_borrower()
    if not borrower:
        flash("Please complete your borrower profile first.", "warning")
        return redirect(url_for("borrower.create_profile"))

    from LoanMVP.models.user_model import User

    officers = User.query.filter(
        User.role.in_(["loan_officer", "processor", "underwriter"])
    ).all()

    receiver_id = request.args.get("receiver_id", type=int)
    selected_messages = []

    if request.method == "POST":
        content = (request.form.get("content") or "").strip()
        receiver_id = request.form.get("receiver_id", type=int)

        if receiver_id and content:
            msg = Message(
                sender_id=current_user.id,
                receiver_id=receiver_id,
                content=content,
                created_at=datetime.utcnow(),
            )
            db.session.add(msg)
            db.session.commit()
            flash("Message sent successfully.", "success")
            return redirect(url_for("borrower.messages", receiver_id=receiver_id))

        flash("Please select a recipient and enter a message.", "warning")

    if receiver_id:
        selected_messages = (
            Message.query.filter(
                ((Message.sender_id == current_user.id) & (Message.receiver_id == receiver_id)) |
                ((Message.sender_id == receiver_id) & (Message.receiver_id == current_user.id))
            )
            .order_by(Message.created_at.asc())
            .all()
        )

    return render_template(
        "borrower/messages.html",
        borrower=borrower,
        officers=officers,
        messages=selected_messages,
        selected_receiver=receiver_id,
        active_tab="messages",
        title="Messages",
    )

from flask import request



# =========================================================
# Subscription
# =========================================================

@borrower_bp.route("/subscription", methods=["GET", "POST"])
@csrf.exempt
@login_required
@role_required("borrower")
def subscription():
    borrower = get_current_borrower()
    if not borrower:
        flash("Please complete your borrower profile first.", "warning")
        return redirect(url_for("borrower.create_profile"))

    if request.method == "POST":
        plan = request.form.get("plan")
        if plan:
            borrower.subscription_plan = plan
            db.session.commit()
            flash(f"Subscription updated to {plan}.", "success")
            return redirect(url_for("borrower.subscription"))

    return render_template(
        "borrower/subscription.html",
        borrower=borrower,
        active_tab="subscription",
        title="Subscription",
    )

@borrower_bp.route("/consent/credit", methods=["POST"])
@csrf.exempt
@login_required
@role_required("borrower")
def consent_credit():
    borrower = get_current_borrower()
    if not borrower:
        flash("Please complete your borrower profile first.", "warning")
        return redirect(url_for("borrower.create_profile"))

    consent = BorrowerConsent(
        borrower_id=borrower.id,
        consent_type="credit_pull",
        ip_address=request.remote_addr,
    )
    db.session.add(consent)
    db.session.commit()

    flash("Credit pull consent recorded.", "success")
    return redirect(url_for("borrower.dashboard"))
