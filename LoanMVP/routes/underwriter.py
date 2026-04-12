# ===============================================================
#   CAUGHMAN MASON — UNDERWRITER WORKFLOW CENTER
# ===============================================================

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from datetime import datetime
import io
from flask_login import current_user, login_required
from LoanMVP.utils.decorators import role_required
from LoanMVP.extensions import db, csrf

from LoanMVP.models.user_model import User
from LoanMVP.models.loan_models import LoanApplication, BorrowerProfile
from LoanMVP.models.document_models import LoanDocument
from LoanMVP.models.underwriter_model import UnderwritingCondition, UnderwriterTask, UnderwriterProfile
from LoanMVP.models.crm_models import Message
from LoanMVP.models.credit_models import SoftCreditReport      # FIXED

from LoanMVP.utils.pricing_engine import calculate_dti_ltv


# PDF GENERATION
from reportlab.pdfgen import canvas

# AI
from LoanMVP.ai.caughman_mason_ai import CaughmanMasonAI
ai_engine = CaughmanMasonAI()

underwriter_bp = Blueprint("underwriter", __name__, url_prefix="/underwriter")
print(">>> UNDERWRITER ROUTE LOADED FROM:", __file__)


def _underwriter_next_setup_endpoint():
    if not getattr(current_user, "ica_accepted", False):
        return "underwriter.agreement"
    if not getattr(current_user, "nda_accepted", False):
        return "underwriter.nda"
    if not getattr(current_user, "onboarding_complete", False):
        return "underwriter.onboarding"
    return "underwriter.dashboard"


def _underwriter_profile():
    return UnderwriterProfile.query.filter_by(user_id=current_user.id).first()


def _assigned_team_users_for_underwriter():
    profile = _underwriter_profile()
    if not profile:
        return []

    assigned_loans = LoanApplication.query.filter_by(underwriter_id=profile.id).all()
    user_ids = set()

    for loan in assigned_loans:
        processor = getattr(loan, "processor", None)
        loan_officer = getattr(loan, "loan_officer", None)

        if processor and getattr(processor, "user_id", None):
            user_ids.add(processor.user_id)
        if loan_officer and getattr(loan_officer, "user_id", None):
            user_ids.add(loan_officer.user_id)

    if not user_ids:
        return []

    users = User.query.filter(User.id.in_(user_ids)).all()
    return sorted(
        users,
        key=lambda user: (
            (getattr(user, "role", "") or "").lower(),
            (getattr(user, "full_name", "") or getattr(user, "email", "") or "").lower(),
        ),
    )


def _allowed_underwriter_partner_ids():
    return {user.id for user in _assigned_team_users_for_underwriter()}


# ===============================================================
#   DASHBOARD
# ===============================================================
@underwriter_bp.route("/dashboard")
@login_required
@role_required("underwriter")
def dashboard():
    loans = (
        LoanApplication.query
        .order_by(LoanApplication.created_at.desc())
        .limit(10)
        .all()
    )

    pending = LoanApplication.query.filter(
        LoanApplication.status.in_(["Submitted", "In Review", "UW Review"])
    ).count()

    approved = LoanApplication.query.filter_by(status="Approved").count()
    declined = LoanApplication.query.filter_by(status="Declined").count()
    clear_to_close = LoanApplication.query.filter_by(status="Clear to Close").count()
    conditional = LoanApplication.query.filter_by(status="Approved with Conditions").count()

    open_conditions = UnderwritingCondition.query.filter_by(status="Open").all()

    return render_template(
        "underwriter/dashboard.html",
        loans=loans,
        open_conditions=open_conditions,
        pending=pending,
        approved=approved,
        declined=declined,
        clear_to_close=clear_to_close,
        conditional=conditional,
        title="Underwriter Command Center",
        active_tab="dashboard",
    )


@underwriter_bp.route("/contracts")
@login_required
@role_required("underwriter")
def contracts():
    return render_template(
        "employee/contracts_hub.html",
        role_label="Underwriter",
        dashboard_endpoint="underwriter.dashboard",
        agreement_endpoint="underwriter.agreement",
        nda_endpoint="underwriter.nda",
        onboarding_endpoint="underwriter.onboarding",
        next_step_endpoint=_underwriter_next_setup_endpoint(),
        contracts_title="Underwriting Readiness Hub",
        contracts_subline="Review required agreements, confidentiality terms, onboarding steps, and workflow standards before issuing decisions.",
        packet_items=[
            {
                "title": "Underwriting Agreement Packet",
                "detail": "Authority, escalation expectations, audit standards, and decision accountability.",
            },
            {
                "title": "Confidentiality + Data Handling",
                "detail": "Borrower files, credit reports, and internal pricing logic must stay inside authorized workflows.",
            },
            {
                "title": "Onboarding Playbook",
                "detail": "Risk review standards, condition management, communication norms, and file turn-time expectations.",
            },
        ],
        workflow_items=[
            "Review complete borrower files before issuing a decision.",
            "Escalate guideline exceptions and policy conflicts quickly.",
            "Keep condition language specific, supportable, and measurable.",
            "Document approval and decline rationale clearly for downstream teams.",
        ],
        active_tab="contracts",
        title="Underwriter Contracts Hub",
    )


@underwriter_bp.route("/agreement", methods=["GET"])
@login_required
@role_required("underwriter")
def agreement():
    if getattr(current_user, "ica_accepted", False):
        if not getattr(current_user, "nda_accepted", False):
            return redirect(url_for("underwriter.nda"))
        if not getattr(current_user, "onboarding_complete", False):
            return redirect(url_for("underwriter.onboarding"))
        return redirect(url_for("underwriter.dashboard"))

    return render_template(
        "employee/team_agreement.html",
        role_label="Underwriter",
        dashboard_endpoint="underwriter.dashboard",
        contracts_endpoint="underwriter.contracts",
        accept_endpoint="underwriter.accept_agreement",
        agreement_label="Underwriter Operating Agreement",
        hero_title="Confirm authority, credit standards, and escalation expectations.",
        hero_text="This agreement outlines the underwriting authority, service expectations, and operating rules attached to your role inside Ravlo.",
        checkpoints=[
            "Your approvals and declines must align with credit policy and documented file support.",
            "Exceptions, overlays, and material file concerns must be escalated instead of silently worked around.",
            "Borrower information, internal strategy, and pricing details remain confidential and role-bound.",
            "Performance is measured by decision quality, timeliness, and clean communication to processing and leadership.",
        ],
        acknowledgment_items=[
            {
                "name": "status_ack",
                "text": "I understand the underwriter role, authority limits, and escalation responsibilities.",
            },
            {
                "name": "comp_ack",
                "text": "I understand that performance, scope, and role expectations are governed by this operating agreement.",
            },
            {
                "name": "no_guarantee",
                "text": "I understand Ravlo may adjust responsibilities, queue mix, and process expectations as operations evolve.",
            },
            {
                "name": "agree_terms",
                "text": "I agree to operate within underwriting policy, audit standards, and company expectations.",
            },
        ],
        active_tab="contracts",
        title="Underwriter Agreement",
    )


@underwriter_bp.route("/agreement/accept", methods=["POST"])
@login_required
@role_required("underwriter")
def accept_agreement():
    if not all([
        request.form.get("status_ack"),
        request.form.get("comp_ack"),
        request.form.get("no_guarantee"),
        request.form.get("agree_terms"),
    ]):
        flash("You must accept all agreement items before continuing.", "danger")
        return redirect(url_for("underwriter.agreement"))

    current_user.ica_accepted = True
    db.session.commit()

    flash("Agreement accepted successfully.", "success")
    return redirect(url_for("underwriter.nda"))


@underwriter_bp.route("/nda", methods=["GET"])
@login_required
@role_required("underwriter")
def nda():
    if not getattr(current_user, "ica_accepted", False):
        return redirect(url_for("underwriter.agreement"))
    if getattr(current_user, "nda_accepted", False):
        if not getattr(current_user, "onboarding_complete", False):
            return redirect(url_for("underwriter.onboarding"))
        return redirect(url_for("underwriter.dashboard"))

    return render_template(
        "employee/team_nda.html",
        role_label="Underwriter",
        dashboard_endpoint="underwriter.dashboard",
        contracts_endpoint="underwriter.contracts",
        accept_endpoint="underwriter.accept_nda",
        confidentiality_title="Underwriter Confidentiality Agreement",
        confidentiality_points=[
            "Credit reports, income documents, fraud findings, and file narratives are confidential.",
            "Internal policy overlays, scorecards, and decision rationale must stay inside approved channels.",
            "Borrower and partner data may only be used for active underwriting work.",
            "Confidentiality obligations continue after queue access or employment ends.",
        ],
        active_tab="contracts",
        title="Underwriter NDA",
    )


@underwriter_bp.route("/nda/accept", methods=["POST"])
@login_required
@role_required("underwriter")
def accept_nda():
    nda_ack = request.form.get("nda_ack")
    nda_agree = request.form.get("nda_agree")

    if not nda_ack or not nda_agree:
        flash("You must accept the NDA to continue.", "danger")
        return redirect(url_for("underwriter.nda"))

    current_user.nda_accepted = True
    db.session.commit()

    flash("NDA accepted successfully.", "success")
    return redirect(url_for("underwriter.onboarding"))


@underwriter_bp.route("/onboarding", methods=["GET"])
@login_required
@role_required("underwriter")
def onboarding():
    if not getattr(current_user, "ica_accepted", False):
        return redirect(url_for("underwriter.agreement"))
    if not getattr(current_user, "nda_accepted", False):
        return redirect(url_for("underwriter.nda"))
    if getattr(current_user, "onboarding_complete", False):
        return redirect(url_for("underwriter.dashboard"))

    return render_template(
        "employee/team_onboarding.html",
        role_label="Underwriter",
        dashboard_endpoint="underwriter.dashboard",
        contracts_endpoint="underwriter.contracts",
        complete_endpoint="underwriter.complete_onboarding",
        onboarding_title="Underwriter Onboarding",
        onboarding_subline="Learn the decision workflow, communication cadence, and file standards that keep underwriting fast and supportable.",
        progress_label="67%",
        checklist_items=[
            "Review risk, credit, income, and collateral decision standards.",
            "Understand when to approve, condition, suspend, or decline a file.",
            "Use precise condition language that processors and borrowers can action.",
            "Escalate fraud signals, policy exceptions, and missing support immediately.",
            "Keep decision notes concise, defensible, and easy for downstream teams to follow.",
            "Maintain response speed without sacrificing audit quality.",
        ],
        workflow_steps=[
            {
                "number": "01",
                "title": "File Intake",
                "text": "Confirm a complete package, identify critical gaps, and establish first-pass risk.",
            },
            {
                "number": "02",
                "title": "Risk Review",
                "text": "Evaluate borrower strength, loan structure, collateral support, and red flags.",
            },
            {
                "number": "03",
                "title": "Condition Strategy",
                "text": "Issue only the conditions needed to cure the file and communicate them clearly.",
            },
            {
                "number": "04",
                "title": "Decision Handoff",
                "text": "Publish a supportable decision and keep processor, borrower, and leadership aligned.",
            },
        ],
        active_tab="onboarding",
        title="Underwriter Onboarding",
    )


@underwriter_bp.route("/onboarding/complete", methods=["POST"])
@login_required
@role_required("underwriter")
def complete_onboarding():
    acknowledged = request.form.get("acknowledged")
    agreement = request.form.get("agreement")

    if not acknowledged or not agreement:
        flash("You must confirm all onboarding items before continuing.", "danger")
        return redirect(url_for("underwriter.onboarding"))

    current_user.onboarding_complete = True
    db.session.commit()

    flash("Onboarding completed. Welcome to the underwriting command center.", "success")
    return redirect(url_for("underwriter.dashboard"))


# ===============================================================
#   LOAN QUEUE
# ===============================================================
@underwriter_bp.route("/queue")
@login_required
@role_required("underwriter")
def queue():
    pending = LoanApplication.query.filter(
        LoanApplication.status.in_(["Submitted", "In Review", "UW Review"])
    ).all()

    return render_template(
        "underwriter/queue.html",
        queue=pending,
        title="Decision Queue",
        active_tab="queue",
    )


# ===============================================================
#   LOAN FILE REVIEW
# ===============================================================
@underwriter_bp.route("/file/<int:loan_id>")
@login_required
@role_required("underwriter")
def file_review(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    borrower = loan.borrower_profile

    credit = (
        SoftCreditReport.query
        .filter_by(borrower_profile_id=borrower.id)
        .order_by(SoftCreditReport.created_at.desc())
        .first()
    )

    ratios = calculate_dti_ltv(borrower, loan, credit)

    docs = LoanDocument.query.filter_by(loan_id=loan.id).order_by(LoanDocument.created_at.desc()).all()
    conditions = UnderwritingCondition.query.filter_by(loan_id=loan.id).order_by(UnderwritingCondition.created_at.desc()).all()

    open_conditions = [c for c in conditions if (c.status or "").strip().lower() == "open"]
    cleared_conditions = [c for c in conditions if (c.status or "").strip().lower() == "cleared"]

    return render_template(
        "underwriter/file_review.html",
        loan=loan,
        borrower=borrower,
        credit=credit,
        ratios=ratios,
        docs=docs,
        conditions=conditions,
        open_conditions=open_conditions,
        cleared_conditions=cleared_conditions,
        title="Underwriter File Review",
        active_tab="queue",
    )

# ===============================================================
#   DOCUMENT VERIFICATION
# ===============================================================
@underwriter_bp.route("/document/<int:doc_id>/verify")
@login_required
@role_required("underwriter")
def verify_doc(doc_id):
    doc = LoanDocument.query.get_or_404(doc_id)
    doc.status = "Verified"
    db.session.commit()

    flash("Document verified successfully.", "success")
    return redirect(url_for("underwriter.file_review", loan_id=doc.loan_id))


# ===============================================================
#   ADD CONDITION
# ===============================================================
@underwriter_bp.route("/add-condition/<int:loan_id>", methods=["POST"])
@csrf.exempt 
@login_required
@role_required("underwriter")
def add_condition(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)

    condition_types = request.form.getlist("type")
    description = request.form.get("description")
    severity = request.form.get("severity")

    if not condition_types:
        flash("Please select at least one condition type.", "warning")
        return redirect(url_for("underwriter.file_review", loan_id=loan.id))

    for ct in condition_types:
        new_cond = UnderwritingCondition(
            loan_id=loan.id,
            borrower_profile_id=loan.borrower_profile_id,
            condition_type=ct,
            description=description,
            severity=severity,
            status="Open"
        )
        db.session.add(new_cond)

    db.session.commit()
    flash("Condition(s) added successfully.", "success")
    return redirect(url_for("underwriter.file_review", loan_id=loan.id))

# ===============================================================
#   CLEAR CONDITION
# ===============================================================
@underwriter_bp.route("/clear-condition/<int:cond_id>")
@login_required
@role_required("underwriter")
def clear_condition(cond_id):
    c = UnderwritingCondition.query.get_or_404(cond_id)
    c.status = "Cleared"
    c.cleared_at = datetime.utcnow()
    db.session.commit()

    flash("Condition cleared successfully.", "success")
    return redirect(url_for("underwriter.file_review", loan_id=c.loan_id))

@underwriter_bp.route("/send-condition/<int:cond_id>")
@login_required
@role_required("underwriter")
def send_condition(cond_id):
    c = UnderwritingCondition.query.get_or_404(cond_id)

    # Notify processor
    send_notification(
        c.loan_id,
        "processor",
        f"Underwriter requests processor action on condition: {c.condition_type}"
    )

    flash("Condition sent to processor.", "success")
    return redirect(url_for("underwriter.file_review", loan_id=c.loan_id))

# ===============================================================
#   UW DECISION
# ===============================================================

@underwriter_bp.route("/decision/<int:loan_id>", methods=["POST"])
@login_required
@role_required("underwriter")
@csrf.exempt
def decision(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)

    loan.decision_notes = request.form.get("notes")
    loan.decision_date = datetime.utcnow()
    loan.status = request.form.get("decision")

    db.session.commit()

    flash(f"Loan decision updated to {loan.status}.", "success")
    return redirect(url_for("underwriter.file_review", loan_id=loan_id))


# ===============================================================
#   AI UNDERWRITING INSIGHT
# ===============================================================
@underwriter_bp.route("/ai", methods=["POST"])
@csrf.exempt
@login_required
@role_required("underwriter")
def ai():
    data = request.get_json()
    borrower_id = data.get("borrower_id")
    question = data.get("message")

    borrower = BorrowerProfile.query.get(borrower_id)
    loan = LoanApplication.query.filter_by(borrower_profile_id=borrower.id).first()

    credit = borrower.credit_reports[-1] if borrower.credit_reports else None
    ratios = calculate_dti_ltv(borrower, loan, credit)

    missing_docs = [d.name for d in borrower.document_requests] if hasattr(borrower, "document_requests") else []

    prompt = f"""
Provide underwriting insight.

Borrower: {borrower.full_name}
Credit Score: {credit.credit_score if credit else "N/A"}
LTV: {ratios.get("ltv")}
Front DTI: {ratios.get("front_end_dti")}
Back DTI: {ratios.get("back_end_dti")}
Loan Amount: {loan.amount}
Property Value: {loan.property_value}

Missing Documents:
{missing_docs}

Question:
{question}
"""

    reply = ai_engine.ask(prompt, role="underwriter")
    return jsonify({"reply": reply})


# ===============================================================
#   DECISION PDF SHEET
# ===============================================================
@underwriter_bp.route("/decision-sheet/<int:loan_id>")
@login_required
@role_required("underwriter")
def decision_sheet(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    borrower = loan.borrower_profile

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, 800, "Underwriting Decision Report")

    pdf.setFont("Helvetica", 12)
    pdf.drawString(50, 770, f"Borrower: {borrower.full_name}")
    pdf.drawString(50, 750, f"Loan Amount: ${loan.amount}")
    pdf.drawString(50, 730, f"Property Value: ${loan.property_value}")
    pdf.drawString(50, 710, f"Status: {loan.status}")
    pdf.drawString(50, 690, f"Decision Date: {loan.decision_date}")

    pdf.drawString(50, 660, "Decision Notes:")
    text = pdf.beginText(50, 640)
    text.setFont("Helvetica", 11)
    for line in (loan.decision_notes or "").split("\n"):
        text.textLine(line)
    pdf.drawText(text)

    pdf.save()
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name="uw_decision.pdf")


# ===============================================================
#   TASKS
# ===============================================================
@underwriter_bp.route("/tasks", methods=["GET", "POST"])
@csrf.exempt
@login_required
@role_required("underwriter")
def tasks():
    if request.method == "POST":
        t = UnderwriterTask(
            title=request.form.get("title"),  # REQUIRED
            description=request.form.get("description"),
            loan_id=request.form.get("loan_id"),
            priority=request.form.get("priority") or "Normal",
            status="Pending",
            due_date=request.form.get("due_date") or None
        )
        db.session.add(t)
        db.session.commit()
        return redirect("/underwriter/tasks")

    tasks = UnderwriterTask.query.order_by(UnderwriterTask.created_at.desc()).all()
    return render_template("underwriter/tasks.html", tasks=tasks)


# ===============================================================
#   RED FLAGS
# ===============================================================
@underwriter_bp.route("/redflags/<int:loan_id>")
@login_required
@role_required("underwriter")
def redflags(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    borrower = loan.borrower_profile
    credit = borrower.credit_reports[-1] if borrower.credit_reports else None

    flags = []

    # Address mismatch
    if credit and credit.address and borrower.address and credit.address != borrower.address:
        flags.append("Address mismatch between application and credit report.")

    # High DTI
    ratios = calculate_dti_ltv(borrower, loan, credit)
    if ratios.get("back_end_dti") and ratios["back_end_dti"] > 0.55:
        flags.append("Back-end DTI above 55% — High risk.")

    # Thin credit file
    if credit and hasattr(credit, "total_trade_lines") and credit.total_trade_lines < 2:
        flags.append("Thin credit file — Less than 2 tradelines.")

    # VoIP numbers
    if borrower.phone and borrower.phone.startswith("470"):
        flags.append("Borrower phone number identified as VoIP carrier.")

    return render_template(
        "underwriter/red_flags.html",
        loan=loan,
        borrower=borrower,
        flags=flags
    )

@underwriter_bp.route("/review-loans")
@login_required
@role_required("underwriter")
def review_loans():
    status_filter = request.args.get("status", "all")

    query = LoanApplication.query

    if status_filter != "all":
        query = query.filter_by(status=status_filter)

    loans = query.order_by(LoanApplication.created_at.desc()).all()

    return render_template(
        "underwriter/review_loans.html",
        loans=loans,
        status_filter=status_filter,
        title="Review Loans"
    )

@underwriter_bp.route("/risk-reports")
@login_required
@role_required("underwriter")
def risk_reports():
    # Pull all loans for portfolio‑level analysis
    loans = LoanApplication.query.order_by(LoanApplication.created_at.desc()).all()

    # Conditions
    open_conditions = UnderwritingCondition.query.filter_by(status="Open").all()
    critical_conditions = UnderwritingCondition.query.filter_by(severity="Critical").all()
    moderate_conditions = UnderwritingCondition.query.filter_by(severity="Moderate").all()
    low_conditions = UnderwritingCondition.query.filter_by(severity="Low").all()

    # Risk buckets
    high_risk = LoanApplication.query.filter(
        LoanApplication.status.in_(["UW Review", "In Review"])
    ).count()

    approved = LoanApplication.query.filter_by(status="Approved").count()
    declined = LoanApplication.query.filter_by(status="Declined").count()

    # Credit + DTI/LTV analysis
    risk_rows = []
    for loan in loans:
        borrower = loan.borrower_profile
        credit = borrower.credit_reports[-1] if borrower.credit_reports else None
        ratios = calculate_dti_ltv(borrower, loan, credit)

        risk_rows.append({
            "loan": loan,
            "borrower": borrower,
            "credit_score": credit.credit_score if credit else None,
            "ltv": ratios.get("ltv"),
            "front_dti": ratios.get("front_end_dti"),
            "back_dti": ratios.get("back_end_dti"),
        })

    return render_template(
        "underwriter/risk_reports.html",
        loans=loans,
        risk_rows=risk_rows,
        open_conditions=open_conditions,
        critical_conditions=critical_conditions,
        moderate_conditions=moderate_conditions,
        low_conditions=low_conditions,
        high_risk=high_risk,
        approved=approved,
        declined=declined,
        title="Risk Reports"
    )

@underwriter_bp.route("/pipeline")
@login_required
@role_required("underwriter")
def pipeline():
    submitted = LoanApplication.query.filter_by(status="Submitted").all()
    in_review = LoanApplication.query.filter_by(status="In Review").all()
    uw_review = LoanApplication.query.filter_by(status="UW Review").all()
    approved = LoanApplication.query.filter_by(status="Approved").all()
    declined = LoanApplication.query.filter_by(status="Declined").all()

    return render_template(
        "underwriter/pipeline.html",
        submitted=submitted,
        in_review=in_review,
        uw_review=uw_review,
        approved=approved,
        declined=declined,
        title="Underwriter Pipeline",
        active_tab="pipeline",
    )
    
@underwriter_bp.route("/messages")
@login_required
@role_required("underwriter")
def messages():
    allowed_users = _assigned_team_users_for_underwriter()
    allowed_partner_ids = {user.id for user in allowed_users}
    threads = []

    if allowed_partner_ids:
        partner_lookup = {user.id: user for user in allowed_users}
        conversations = (
            Message.query.filter(
                ((Message.sender_id == current_user.id) & (Message.receiver_id.in_(allowed_partner_ids))) |
                ((Message.receiver_id == current_user.id) & (Message.sender_id.in_(allowed_partner_ids)))
            )
            .order_by(Message.created_at.desc())
            .all()
        )

        seen_partner_ids = set()
        for msg in conversations:
            partner_id = msg.receiver_id if msg.sender_id == current_user.id else msg.sender_id
            if partner_id in seen_partner_ids:
                continue
            partner = partner_lookup.get(partner_id)
            if not partner:
                continue
            seen_partner_ids.add(partner_id)
            threads.append({
                "partner_id": partner_id,
                "partner_name": partner.full_name or partner.email or "Assigned Team Member",
                "last_sender_id": msg.sender_id,
                "last_message_preview": (msg.content or "")[:120],
                "updated_at": getattr(msg, "created_at", datetime.utcnow()),
            })

    return render_template(
        "underwriter/messages.html",
        threads=threads,
        title="Messages"
    )

@underwriter_bp.route("/messages/thread/<int:partner_id>", methods=["GET", "POST"])
@csrf.exempt 
@login_required
@role_required("underwriter")
def message_thread(partner_id):
    user_id = current_user.id
    allowed_partner_ids = _allowed_underwriter_partner_ids()

    if partner_id not in allowed_partner_ids:
        flash("You can only message assigned processors and loan officers.", "warning")
        return redirect(url_for("underwriter.messages"))

    if request.method == "POST":
        text = request.form.get("message")
        if text:
            new_msg = Message(
                sender_id=user_id,
                receiver_id=partner_id,
                content=text
            )
            db.session.add(new_msg)
            db.session.commit()

        return redirect(url_for("underwriter.message_thread", partner_id=partner_id))

    messages = (
        Message.query.filter(
            ((Message.sender_id == user_id) & (Message.receiver_id == partner_id)) |
            ((Message.sender_id == partner_id) & (Message.receiver_id == user_id))
        )
        .order_by(Message.created_at.asc())
        .all()
    )

    partner = User.query.get(partner_id)

    return render_template(
        "underwriter/message_thread.html",
        messages=messages,
        recipients=[partner],
        thread_title=partner.full_name,
        current_route="underwriter.message_thread",
        current_user=current_user
    )

@underwriter_bp.route("/messages/new", methods=["GET", "POST"])
@csrf.exempt 
@login_required
@role_required("underwriter")
def new_message():
    users = _assigned_team_users_for_underwriter()

    if request.method == "POST":
        partner_id = request.form.get("partner_id", type=int)
        if partner_id not in {user.id for user in users}:
            flash("Please select an assigned processor or loan officer.", "warning")
            return redirect(url_for("underwriter.new_message"))
        return redirect(url_for("underwriter.message_thread", partner_id=partner_id))

    return render_template(
        "underwriter/new_message.html",
        users=users,
        title="Start New Message"
    )
