# ===============================================================
#   CAUGHMAN MASON — UNDERWRITER WORKFLOW CENTER
# ===============================================================

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from datetime import datetime
import io
from flask_login import current_user, login_required
from LoanMVP.extensions import db
from LoanMVP.models.user_model import User
from LoanMVP.models.loan_models import LoanApplication, BorrowerProfile
from LoanMVP.models.document_models import LoanDocument
from LoanMVP.models.underwriter_model import UnderwritingCondition, UnderwriterTask
from LoanMVP.models.crm_models import MessageThread, Message
from LoanMVP.models.credit_models import SoftCreditReport      # FIXED
from LoanMVP.utils.notify import send_notification
from LoanMVP.utils.pricing_engine import calculate_dti_ltv

# PDF GENERATION
from reportlab.pdfgen import canvas

# AI
from LoanMVP.ai.caughman_mason_ai import CaughmanMasonAI
ai_engine = CaughmanMasonAI()

underwriter_bp = Blueprint("underwriter", __name__, url_prefix="/underwriter")
print(">>> UNDERWRITER ROUTE LOADED FROM:", __file__)


# ===============================================================
#   DASHBOARD
# ===============================================================
@underwriter_bp.route("/dashboard")
def dashboard():
    # Recent loans
    loans = LoanApplication.query.order_by(LoanApplication.created_at.desc()).limit(10).all()

    # KPI counts
    pending = LoanApplication.query.filter(
        LoanApplication.status.in_(["Submitted", "In Review", "UW Review"])
    ).count()

    approved = LoanApplication.query.filter_by(status="Approved").count()
    declined = LoanApplication.query.filter_by(status="Declined").count()

    # Open conditions
    open_conditions = UnderwritingCondition.query.filter_by(status="Open").all()

    return render_template(
        "underwriter/dashboard.html",
        loans=loans,
        open_conditions=open_conditions,
        pending=pending,
        approved=approved,
        declined=declined,
        title="Underwriter Dashboard"
    )


# ===============================================================
#   LOAN QUEUE
# ===============================================================
@underwriter_bp.route("/queue")
def queue():
    pending = LoanApplication.query.filter(
        LoanApplication.status.in_(["Submitted", "In Review", "UW Review"])
    ).all()

    return render_template(
        "underwriter/queue.html",
        queue=pending,
        title="Underwriting Queue"
    )


# ===============================================================
#   LOAN FILE REVIEW
# ===============================================================
@underwriter_bp.route("/file/<int:loan_id>")
def file_review(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    borrower = loan.borrower_profile

    credit = SoftCreditReport.query.filter_by(borrower_profile_id=borrower.id)\
        .order_by(SoftCreditReport.created_at.desc()).first()

    ratios = calculate_dti_ltv(borrower, loan, credit)

    docs = LoanDocument.query.filter_by(loan_id=loan.id).all()
    conditions = UnderwritingCondition.query.filter_by(loan_id=loan_id).all()

    return render_template(
        "underwriter/file_review.html",
        loan=loan,
        borrower=borrower,
        credit=credit,
        ratios=ratios,
        docs=docs,
        conditions=conditions,
        title="Underwriter File Review"
    )


# ===============================================================
#   DOCUMENT VERIFICATION
# ===============================================================
@underwriter_bp.route("/document/<int:doc_id>/verify")
def verify_doc(doc_id):
    doc = LoanDocument.query.get_or_404(doc_id)
    doc.status = "Verified"
    db.session.commit()

    loan = LoanApplication.query.get(doc.loan_id)
    borrower = loan.borrower_profile

    notify(
        borrower=borrower,
        loan=loan,
        role="processor",
        title="Document Verified",
        message=f"Document verified by Underwriter: {doc.document_name}"
    )

    return redirect(url_for("underwriter.file_review", loan_id=doc.loan_id))



# ===============================================================
#   ADD CONDITION
# ===============================================================
@underwriter_bp.route("/add-condition/<int:loan_id>", methods=["POST"])
def add_condition(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)

    condition_types = request.form.getlist("type")

    for ct in condition_types:
        new_cond = UnderwritingCondition(
            loan_id=loan.id,
            borrower_profile_id=loan.borrower_profile_id,
            condition_type=ct,
            description=request.form.get("description"),
            severity=request.form.get("severity"),
            status="Open"
        )
        db.session.add(new_cond)

    db.session.commit()

    send_notification(
        loan.id,
        "processor",
        f"New underwriting condition: {new_cond.condition_type}"
    )

    return redirect(url_for("underwriter.file_review", loan_id=loan.id))


# ===============================================================
#   CLEAR CONDITION
# ===============================================================
@underwriter_bp.route("/clear-condition/<int:cond_id>")
def clear_condition(cond_id):
    c = UnderwritingCondition.query.get_or_404(cond_id)
    c.status = "Cleared"
    c.cleared_at = datetime.utcnow()
    db.session.commit()

    send_notification(
        c.loan_id,
        "processor",
        f"Condition Cleared: {c.condition_type}"
    )

    return redirect(url_for("underwriter.file_review", loan_id=c.loan_id))

@underwriter_bp.route("/send-condition/<int:cond_id>")
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
def decision(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)

    loan.decision_notes = request.form.get("notes")
    loan.decision_date = datetime.utcnow()
    loan.status = request.form.get("decision")

    db.session.commit()

    send_notification(
        loan.id,
        "processor",
        f"Underwriter Decision: {loan.status}"
    )

    return redirect(url_for("underwriter.file_review", loan_id=loan_id))


# ===============================================================
#   AI UNDERWRITING INSIGHT
# ===============================================================
@underwriter_bp.route("/ai", methods=["POST"])
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
def pipeline():
    # Group loans by underwriting stage
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
        title="Underwriter Pipeline"
    )

@underwriter_bp.route("/messages")
def messages():
    
    threads = MessageThread.query.filter_by(
        sender_id=current_user.id
    ).order_by(MessageThread.sent_at.desc()).all()

    return render_template(
        "underwriter/messages.html",
        threads=threads,
        title="Messages"
    )

@underwriter_bp.route("/messages/thread/<int:partner_id>", methods=["GET", "POST"])
def message_thread(partner_id):
    user_id = current_user.id

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
def new_message():
    users = User.query.filter(User.id != current_user.id).all()

    if request.method == "POST":
        partner_id = request.form.get("partner_id")
        return redirect(url_for("underwriter.message_thread", partner_id=partner_id))

    return render_template(
        "underwriter/new_message.html",
        users=users,
        title="Start New Message"
    )
