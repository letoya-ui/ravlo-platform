# =========================================================
# ⚙️ LoanMVP Processor Routes — 2025 Unified Final Version
# =========================================================

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, jsonify, current_app, send_from_directory
)
from flask_login import login_required, current_user
from datetime import datetime
import os
from datetime import datetime
# ✅ Always import db before model files
from LoanMVP.extensions import db

# ✅ Safe model imports (no circular dependencies)
from LoanMVP.models.loan_models import LoanApplication, BorrowerProfile, LoanStatusEvent
from LoanMVP.models.document_models import LoanDocument, DocumentRequest
from LoanMVP.models.crm_models import Message
from LoanMVP.models.underwriter_model import ConditionRequest, UnderwritingCondition
from LoanMVP.models.ai_models import LoanAIConversation
from LoanMVP.models.payment_models import PaymentRecord
from LoanMVP.models.user_model import User
from LoanMVP.ai.base_ai import AIAssistant
from LoanMVP.utils.decorators import role_required  # ✅ Added for role control

# ✅ SocketIO imported safely at the bottom
from flask_socketio import emit, join_room
from LoanMVP.app import socketio

# ---------------------------------------------------------
# Blueprint Setup
# ---------------------------------------------------------
processor_bp = Blueprint("processor", __name__, url_prefix="/processor")
assistant = AIAssistant()

# ---------------------------------------------------------
# 🏠 Processor Dashboard
# ---------------------------------------------------------
@processor_bp.route("/dashboard")
@role_required("processor")
def dashboard():
    """Main Processor Dashboard — AI summary, metrics, and insights."""
    try:
        loans = (
            LoanApplication.query
            .filter_by(processor_id=current_user.id)
            .order_by(LoanApplication.created_at.desc())
            .all()
        )
    except Exception as e:
        print(" Error fetching loans:", e)
        loans = []

    in_review = len([l for l in loans if l.status and l.status.lower() in ["in_review", "under_review"]])
    cleared = len([l for l in loans if l.status and l.status.lower() == "cleared"])
    pending_docs = LoanDocument.query.filter_by(status="pending").count()

    try:
        prompt = (
            f"Summarize processor workload for {current_user.username}. "
            f"There are {len(loans)} active loans, {in_review} in review, "
            f"{cleared} cleared, and {pending_docs} pending documents. "
            "Provide a motivational summary and highlight bottlenecks or efficiency tips."
        )
        ai_summary = assistant.generate_reply(prompt, "processor")
    except Exception as e:
        print(" AI summary failed:", e)
        ai_summary = "⚠️ AI summary unavailable."

    return render_template(
        "processor/dashboard.html",
        loans=loans,
        in_review=in_review,
        cleared=cleared,
        pending_docs=pending_docs,
        ai_summary=ai_summary,
        title="Processor Dashboard"
    )

# ---------------------------------------------------------
# 📊 Dashboard Data API
# ---------------------------------------------------------
@processor_bp.route("/dashboard_data")
@role_required("processor")
def dashboard_data():
    """Return real-time metrics for charts or widgets."""
    try:
        loans = LoanApplication.query.filter_by(processor_id=current_user.id).all()
    except Exception:
        loans = []

    data = {
        "in_review": len([l for l in loans if l.status and l.status.lower() in ["in_review", "under_review"]]),
        "cleared": len([l for l in loans if l.status and l.status.lower() == "cleared"]),
        "pending_docs": LoanDocument.query.filter_by(status="pending").count(),
        "total_loans": len(loans)
    }
    return jsonify(data)

# ---------------------------------------------------------
# 🧾 Loan Queue
# ---------------------------------------------------------
@processor_bp.route("/loan_queue")
@role_required("processor")
def loan_queue():
    loans = LoanApplication.query.order_by(LoanApplication.created_at.desc()).all()
    return render_template("processor/loan_queue.html", loans=loans, title="Loan Queue")

@processor_bp.route("/api/loan_documents/<int:loan_id>")
@role_required("processor")
def api_loan_documents(loan_id):
    docs = LoanDocument.query.filter_by(loan_id=loan_id).order_by(LoanDocument.uploaded_at.desc()).all()
    return jsonify({
        "docs": [
            {
                "id": d.id,
                "document_name": d.document_name,
                "uploaded_by": d.uploaded_by or "Borrower",
                "status": d.status or "Pending",
                "file_path": f"uploads/borrowers/{d.submitted_file}"
            } for d in docs
        ]
    })

# ---------------------------------------------------------
# 🧾 Loan Review
# ---------------------------------------------------------
@processor_bp.route("/loan_review/<int:loan_id>", methods=["GET", "POST"])
@role_required("processor")
def loan_review(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    borrower = BorrowerProfile.query.get_or_404(loan.borrower_profile_id)

    # ⭐ FIX: Use the correct model
    conditions = loan.underwriting_conditions

    if request.method == "POST":
        action = request.form.get("action")
        selected_ids = request.form.getlist("condition_ids")

        if not selected_ids:
            flash("⚠️ No conditions selected.", "warning")
            return redirect(url_for("processor.loan_review", loan_id=loan.id))

        for cid in selected_ids:
            cond = UnderwritingCondition.query.get(cid)
            if cond:
                if action == "SendToBorrower":
                    doc_request = DocumentRequest(
                        borrower_id=borrower.id,
                        requested_by=current_user.username,
                        document_name=cond.description,
                        notes=f"Please upload supporting document for: {cond.description}",
                        status="Pending",
                        created_at=datetime.utcnow()
                    )
                    db.session.add(doc_request)
                else:
                    cond.status = action

        db.session.commit()

        msg = "📨 Sent to borrower." if action == "SendToBorrower" else f"✅ Marked as {action}."
        flash(msg, "success")
        return redirect(url_for("processor.loan_review", loan_id=loan.id))

    return render_template(
        "processor/loan_review.html",
        loan=loan,
        borrower=borrower,
        conditions=conditions,
        title=f"Loan Review • {borrower.full_name}"
    )
    
@processor_bp.route("/add_condition/<int:loan_id>", methods=["POST"])
@role_required("processor")
def add_condition(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    borrower = loan.borrower_profile

    condition_type = request.form.get("condition_type")
    notes = request.form.get("notes", "")

    if not condition_type:
        flash("⚠️ Please select a condition.", "warning")
        return redirect(url_for("processor.loan_review", loan_id=loan.id))

    new_cond = UnderwritingCondition(
        borrower_profile_id=borrower.id,          # ⭐ REQUIRED
        loan_id=loan.id,
        condition_type="Standard",                # or map based on dropdown
        description=condition_type,
        severity="Standard",                      # ⭐ REQUIRED if not nullable
        status="Pending",
        notes=notes,
        requested_by=current_user.username,
        updated_at=datetime.utcnow()
    )

    db.session.add(new_cond)
    db.session.commit()

    flash("➕ Condition added successfully.", "success")
    return redirect(url_for("processor.loan_review", loan_id=loan.id))

# ---------------------------------------------------------
# ✏️ Edit Loan
# ---------------------------------------------------------
@processor_bp.route("/loan/<int:loan_id>/edit", methods=["GET", "POST"])
@role_required("processor")
def edit_loan(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    borrower = BorrowerProfile.query.get_or_404(loan.borrower_profile_id)

    if request.method == "POST":
        borrower.full_name = request.form.get("borrower_name")
        loan.amount = request.form.get("amount")
        loan.status = request.form.get("status")
        db.session.commit()
        flash("💾 Loan and borrower updated successfully.", "success")
        return redirect(url_for("processor.loan_review", loan_id=loan.id))

    return render_template("processor/edit_loan.html", loan=loan, borrower=borrower, title="Edit Loan")

# ---------------------------------------------------------
# 📄 Document Management
# ---------------------------------------------------------
@processor_bp.route("/documents", methods=["GET", "POST"])
@role_required("processor")
def documents():
    docs = LoanDocument.query.order_by(LoanDocument.created_at.desc()).all()

    if request.method == "POST":
        doc_id = request.form.get("doc_id")
        action = request.form.get("action")
        doc = LoanDocument.query.get(doc_id)

        if not doc:
            flash("❌ Document not found.", "danger")
            return redirect(url_for("processor.documents"))

        if action in ["verify", "flag", "clear"]:
            doc.status = (
                "verified" if action == "verify" else
                "flagged" if action == "flag" else
                "cleared"
            )
            doc.updated_at = datetime.utcnow()
            db.session.commit()
            flash(f"✅ {doc.document_name} marked as {doc.status}.", "success")

    return render_template("processor/documents.html", documents=docs, title="Documents Pipeline")

@processor_bp.route("/request-doc/<int:loan_id>", methods=["GET", "POST"])
def request_document(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)

    if request.method == "POST":
        doc_name = request.form.get("document_name")
        notes = request.form.get("notes")

        new_req = DocumentRequest(
            borrower_id=loan.borrower_profile_id,
            loan_id=loan.id,
            name=doc_name,
            status="requested",
            notes=notes
        )
        db.session.add(new_req)
        db.session.commit()

        send_notification(loan.id, "borrower", f"New document requested: {doc_name}")

        return redirect(f"/processor/file/{loan.id}")

    # Render selection form
    return render_template("processor/request_doc.html", loan=loan)

@processor_bp.route("/add-note/<int:loan_id>", methods=["GET", "POST"])
def add_processor_note(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)

    if request.method == "POST":
        note = request.form.get("note")

        new_note = ProcessorNote(
            loan_id=loan.id,
            processor_id=current_user.id,
            note=note
        )
        db.session.add(new_note)
        db.session.commit()

        send_notification(loan.id, "underwriter", "Processor added a new note.")

        return redirect(f"/processor/file/{loan.id}")

    return render_template("processor/add_note.html", loan=loan)

@processor_bp.route("/update-status/<int:loan_id>", methods=["GET", "POST"])
def update_loan_status(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)

    statuses = ["Pending", "Processing", "Submitted", "Suspended", "Clear to Close"]

    if request.method == "POST":
        new_status = request.form.get("status")
        loan.status = new_status
        db.session.commit()

        send_notification(loan.id, "borrower", f"Your loan status updated to: {new_status}")

        return redirect(f"/processor/file/{loan.id}")

    return render_template("processor/update_status.html", loan=loan, statuses=statuses)

@processor_bp.route("/assign/<int:loan_id>", methods=["GET", "POST"])
def assign_loan(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    users = User.query.all()

    if request.method == "POST":
        new_user = request.form.get("user_id")
        loan.processor_id = new_user
        db.session.commit()

        send_notification(loan.id, "processor", "A new loan has been assigned to you.")

        return redirect(f"/processor/file/{loan.id}")

    return render_template("processor/assign_loan.html", loan=loan, users=users)

@processor_bp.route("/submit-underwriter/<int:loan_id>")
def submit_underwriter(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)

    loan.status = "Submitted"
    loan.submitted_to_uw = datetime.utcnow()

    db.session.commit()

    send_notification(loan.id, "underwriter", "A new loan file has been submitted for underwriting.")

    return redirect(f"/processor/file/{loan.id}")

@processor_bp.route("/view-file/<path:filename>")
def view_file(filename):
    upload_folder = current_app.config.get("UPLOAD_FOLDER")

    if not upload_folder:
        upload_folder = os.path.join(current_app.instance_path, "uploads")

    return send_from_directory(upload_folder, filename)

# ---------------------------------------------------------
# 📤 Upload Document
# ---------------------------------------------------------
@processor_bp.route("/upload_doc", methods=["GET", "POST"])
@role_required("processor")
def upload_doc():
    upload_folder = os.path.join(current_app.root_path, "uploads")
    os.makedirs(upload_folder, exist_ok=True)

    if request.method == "POST":
        loan_id = request.form.get("loan_id")
        file = request.files.get("file")

        if not file or file.filename == "":
            flash("❌ Please select a file.", "danger")
            return redirect(url_for("processor.upload_doc"))

        filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{file.filename}"
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)

        new_doc = LoanDocument(
            loan_id=loan_id,
            document_name=file.filename,
            file_path=filename,
            status="Pending",
            uploaded_by=current_user.username,
            created_at=datetime.utcnow()
        )
        db.session.add(new_doc)
        db.session.commit()

        flash(f"✅ Uploaded '{file.filename}'.", "success")
        return redirect(url_for("processor.documents"))

    loans = LoanApplication.query.all()
    return render_template("processor/upload_center.html", loans=loans, title="Upload Document")

# ---------------------------------------------------------
# 🔍 Verify Documents
# ---------------------------------------------------------
@processor_bp.route("/verify_docs", methods=["GET", "POST"])
@role_required("processor")
def verify_docs():
    docs = LoanDocument.query.filter(
        LoanDocument.status.in_(["Pending", "Under Review", "Uploaded"])
    ).order_by(LoanDocument.created_at.desc()).all()

    if request.method == "POST":
        doc_id = request.form.get("doc_id")
        action = request.form.get("action")
        notes = request.form.get("notes", "").strip()

        doc = LoanDocument.query.get(doc_id)
        if not doc:
            flash("❌ Document not found.", "danger")
            return redirect(url_for("processor.verify_docs"))

        if action == "approve":
            doc.status = "Verified"
        elif action == "flag":
            doc.status = "Flagged"
        elif action == "reject":
            doc.status = "Rejected"

        if notes:
            doc.notes = notes
        doc.updated_at = datetime.utcnow()
        db.session.commit()
        flash(f"✅ {doc.document_name} marked as {doc.status}.", "info")
        return redirect(url_for("processor.verify_docs"))

    try:
        ai_summary = assistant.generate_reply(
            f"Summarize verification workload: {len(docs)} total docs.", "processor"
        )
    except Exception:
        ai_summary = "AI summary unavailable."

    return render_template("processor/verify_docs.html", documents=docs, ai_summary=ai_summary, title="Verify Documents")

# ---------------------------------------------------------
# 📈 Reports / Analytics
# ---------------------------------------------------------
@processor_bp.route("/reports")
@role_required("processor")
def reports():
    total_loans = LoanApplication.query.count()
    verified_docs = LoanDocument.query.filter_by(status="Verified").count()
    pending_docs = LoanDocument.query.filter_by(status="Pending").count()

    try:
        ai_insight = assistant.generate_reply(
            f"Generate a short performance summary for processor {current_user.username}. "
            f"{total_loans} loans total, {verified_docs} verified, {pending_docs} pending.",
            "processor"
        )
    except Exception:
        ai_insight = "No AI insights available."

    return render_template(
        "processor/reports.html",
        total_loans=total_loans,
        verified_docs=verified_docs,
        pending_docs=pending_docs,
        ai_insight=ai_insight,
        title="Reports & Insights",
        timestamp=datetime.now()
    )

@processor_bp.route("/messages/new", methods=["GET", "POST"])
@role_required("processor")
def new_message():
    # Get all users except the current one
    users = User.query.filter(User.id != current_user.id).all()

    if request.method == "POST":
        partner_id = request.form.get("partner_id")
        return redirect(url_for("processor.message_thread", partner_id=partner_id))

    return render_template(
        "processor/new_message.html",
        users=users,
        current_user=current_user
    )

# =========================================================
# 🔁 Condition Review Center (Processor ↔ Borrower ↔ Underwriter)
# =========================================================
@processor_bp.route("/conditions/<int:loan_id>", methods=["GET", "POST"])
@role_required("processor")
def condition_review(loan_id):
    """Processor handles document requests from Underwriter and Borrower."""
    loan = LoanApplication.query.get_or_404(loan_id)
    borrower = BorrowerProfile.query.get_or_404(loan.borrower_profile_id)
    conditions = ConditionRequest.query.filter_by(loan_id=loan.id).all()
    borrower_docs = DocumentRequest.query.filter_by(borrower_id=borrower.id).all()

    if request.method == "POST":
        action = request.form.get("action")
        cond_id = request.form.get("condition_id")
        doc_id = request.form.get("document_id")

        # Processor forwards condition to Borrower
        if action == "send_to_borrower":
            cond = ConditionRequest.query.get(cond_id)
            if cond:
                new_req = DocumentRequest(
                    borrower_id=borrower.id,
                    requested_by=current_user.username,
                    document_name=cond.description,
                    notes=f"Please upload your supporting doc for: {cond.description}",
                    status="Pending"
                )
                cond.status = "SentToBorrower"
                db.session.add(new_req)
                db.session.commit()
                flash("📤 Sent condition to borrower.", "info")

        # Borrower returned document → Processor verifies → Underwriter notified
        elif action == "verify_document":
            doc = DocumentRequest.query.get(doc_id)
            if doc:
                doc.status = "Verified"
                doc.verified_at = datetime.utcnow()
                linked_cond = ConditionRequest.query.filter_by(description=doc.document_name, loan_id=loan.id).first()
                if linked_cond:
                    linked_cond.status = "Verified"
                    linked_cond.updated_at = datetime.utcnow()
                db.session.commit()
                flash("✅ Document verified and condition marked complete.", "success")

        return redirect(url_for("processor.condition_review", loan_id=loan_id))

    # AI Summary
    try:
        ai_summary = assistant.generate_reply(
            f"Summarize current loan condition pipeline for processor {current_user.username}: "
            f"{len(conditions)} total conditions, {len(borrower_docs)} borrower documents.",
            "processor"
        )
    except Exception:
        ai_summary = "AI summary unavailable."

    return render_template(
        "processor/condition_review.html",
        loan=loan,
        borrower=borrower,
        conditions=conditions,
        borrower_docs=borrower_docs,
        ai_summary=ai_summary,
        title="Condition Review Center"
    )

# ---------------------------------------------------------
# 💬 Messaging
# ---------------------------------------------------------
@processor_bp.route("/messages")
@role_required("processor")
def messages():
    user_id = current_user.id

    conversations = (
        db.session.query(Message)
        .filter((Message.sender_id == user_id) | (Message.receiver_id == user_id))
        .order_by(Message.created_at.desc())
        .all()
    )

    partners = {}
    for msg in conversations:
        other_id = msg.receiver_id if msg.sender_id == user_id else msg.sender_id
        if other_id not in partners:
            partners[other_id] = msg

    return render_template(
        "processor/messages.html",
        partners=partners,
        current_user=current_user,
        title="Messages"
    )

@processor_bp.route("/property_search", methods=["GET"])
@role_required("processor")
def property_search():
    address = request.args.get("query", "").strip()
    city = request.args.get("city", "").strip()
    state = request.args.get("state", "").strip()

    full_query = " ".join(x for x in [address, city, state] if x).strip()

    property_data = None
    ai_summary = None
    error = None

    if full_query:
        try:
            from services.unified_resolver import resolve_property_unified
            result = resolve_property_unified(full_query)

            if result.get("status") == "ok":
                property_data = result.get("property")
                ai_summary = result.get("ai_summary")
            else:
                error = f"Could not resolve this property. Source: {result.get('primary_source', 'NONE')}"
        except Exception as e:
            error = f"Unexpected error: {e}"

    return render_template(
        "property/search.html",
        property=property_data,
        ai_summary=ai_summary,
        error=error,
        title="Property Search | Processor"
    )


@processor_bp.route("/ai_conversations", methods=["GET", "POST"])
@role_required("processor")
def ai_conversations():
    """
    Processor AI Assistant chat and history view.
    Enables processors to interact with LoanMVP AI for
    loan analysis, borrower follow-ups, and workflow support.
    """
    borrower_id = request.args.get("borrower_id")
    conversations = (
        LoanAIConversation.query
        .filter_by(user_role="processor")
        .order_by(LoanAIConversation.created_at.desc())
        .limit(50)
        .all()
    )

    ai_reply = None
    if request.method == "POST":
        user_message = request.form.get("message", "").strip()
        if not user_message:
            flash("⚠️ Please enter a message.", "warning")
            return redirect(url_for("processor.ai_conversations"))

        try:
            # 🧠 AI generates contextual reply
            ai_reply = assistant.generate_reply(
                f"Processor inquiry: {user_message}", "processor"
            )

            # 💾 Log the conversation
            convo = LoanAIConversation(
                borrower_id=borrower_id,
                user_role="processor",
                topic="workflow_assist",
                user_message=user_message,
                ai_response=ai_reply,
                created_at=datetime.utcnow(),
            )
            db.session.add(convo)
            db.session.commit()

            flash("💬 AI response generated successfully.", "success")

        except Exception as e:
            flash(f"⚠️ AI service error: {e}", "danger")

    return render_template(
        "processor/ai_conversations.html",
        conversations=conversations,
        ai_reply=ai_reply,
        title="AI Conversations | Processor",
    )

# =========================================================
# 💬 Live AI Chat (Processor)
# =========================================================
from flask_socketio import emit, join_room
from LoanMVP.app import socketio

@processor_bp.route("/live_chat")
@role_required("processor")
def live_chat():
    """
    Live, real-time AI chat for processors.
    Uses SocketIO to stream messages instantly.
    """
    conversations = (
        LoanAIConversation.query
        .filter_by(user_role="processor")
        .order_by(LoanAIConversation.created_at.desc())
        .limit(40)
        .all()
    )
    return render_template(
        "processor/live_chat.html",
        conversations=conversations,
        title="AI Live Chat | Processor",
    )

@processor_bp.route("/profile", methods=["GET", "POST"])
@role_required("processor")
def profile():
    """
    Processor profile page — view and update personal info,
    contact details, and profile photo.
    """
    user = current_user
    upload_dir = os.path.join(current_app.root_path, "static", "uploads", "profile_pics")
    os.makedirs(upload_dir, exist_ok=True)

    if request.method == "POST":
        try:
            # ✅ Basic Info
            user.first_name = request.form.get("first_name", user.first_name)
            user.last_name = request.form.get("last_name", user.last_name)
            user.email = request.form.get("email", user.email)
            user.phone = request.form.get("phone", getattr(user, "phone", None))
            user.department = request.form.get("department", getattr(user, "department", "Processing"))

            # ✅ Profile Picture
            file = request.files.get("profile_pic")
            if file and file.filename:
                filename = secure_filename(file.filename)
                file.save(os.path.join(upload_dir, filename))
                user.profile_pic = f"/static/uploads/profile_pics/{filename}"

            db.session.commit()
            flash("✅ Profile updated successfully!", "success")
            return redirect(url_for("processor.profile"))

        except Exception as e:
            db.session.rollback()
            flash(f"⚠️ Error updating profile: {e}", "danger")

    # Example placeholder stats or audit data
    recent_activity = [
        {"time": "Today 10:24 AM", "event": "Verified borrower income documents"},
        {"time": "Yesterday 3:41 PM", "event": "Completed loan review for #2025-1198"},
        {"time": "2 days ago", "event": "Updated processor pipeline task"},
    ]

    return render_template(
        "processor/profile.html",
        user=user,
        recent_activity=recent_activity,
        title="Processor Profile | LoanMVP"
    )
# =========================================================
# 🧠 SocketIO Event: Processor sends message
# =========================================================
@socketio.on("send_processor_message")
def handle_processor_message(data):
    """
    Handle incoming messages from processor and return AI reply in real time.
    """
    message = data.get("message", "").strip()
    if not message:
        emit("receive_ai_message", {"ai": "⚠️ Please type a message first."})
        return

    try:
        # Generate AI response
        ai_response = assistant.generate_reply(f"Processor says: {message}", "processor")

        # Save to DB
        convo = LoanAIConversation(
            user_role="processor",
            topic="live_chat",
            user_message=message,
            ai_response=ai_response,
            created_at=datetime.utcnow(),
        )
        db.session.add(convo)
        db.session.commit()

        # Emit reply to the same client (or room)
        emit("receive_ai_message", {"user": message, "ai": ai_response}, broadcast=False)

    except Exception as e:
        emit("receive_ai_message", {"ai": f"⚠️ Error: {str(e)}"})

@processor_bp.route("/messages/chat/<int:user_id>", methods=["GET", "POST"])
@role_required("processor")
def chat(user_id):
    me = current_user.id

    # Load the other user
    other = User.query.get_or_404(user_id)

    # Handle sending a message
    if request.method == "POST":
        content = request.form.get("content", "").strip()
        if content:
            msg = Message(
                sender_id=me,
                receiver_id=other.id,
                content=content,
                sender_role=current_user.role,
                receiver_role=other.role,
                created_at=datetime.utcnow()
            )
            db.session.add(msg)
            db.session.commit()

        return redirect(url_for("processor.chat", user_id=other.id))

    # Load conversation history
    messages = (
        Message.query.filter(
            ((Message.sender_id == me) & (Message.receiver_id == other.id)) |
            ((Message.sender_id == other.id) & (Message.receiver_id == me))
        )
        .order_by(Message.created_at.asc())
        .all()
    )

    return render_template(
        "processor/chat_thread.html",
        other=other,
        messages=messages,
        title=f"Chat with {other.full_name}"
    )

@processor_bp.route("/messages/start")
@role_required("processor")
def start_chat():
    users = User.query.filter(User.id != current_user.id).all()
    return render_template("processor/start_chat.html", users=users)

# ---------------------------------------------------------
# 🔌 SocketIO Events
# ---------------------------------------------------------

def get_conversation_id(user1_id, user2_id):
    """Generate a stable room ID for any two users."""
    return f"{min(user1_id, user2_id)}_{max(user1_id, user2_id)}"


@socketio.on("join_chat")
def join_chat(data):
    """Join a Messenger-style conversation room."""
    user1_id = int(data.get("user1_id"))
    user2_id = int(data.get("user2_id"))

    convo_id = get_conversation_id(user1_id, user2_id)
    room = f"conversation_{convo_id}"

    join_room(room)
    emit("status", {"msg": f"Joined conversation {convo_id}."})


@socketio.on("send_message")
def send_message(data):
    """Send a real-time message between any two users."""
    sender_id = int(data.get("sender_id"))
    receiver_id = int(data.get("receiver_id"))
    text = (data.get("text") or "").strip()

    if not text:
        return

    # Save message to DB
    msg = Message(
        sender_id=sender_id,
        receiver_id=receiver_id,
        content=text,
        created_at=datetime.utcnow()
    )
    db.session.add(msg)
    db.session.commit()

    # Broadcast to the correct room
    convo_id = get_conversation_id(sender_id, receiver_id)
    room = f"conversation_{convo_id}"

    emit("new_message", {
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "text": text,
        "timestamp": datetime.utcnow().strftime("%H:%M")
    }, room=room)
    
@processor_bp.route("/messages/thread/<int:partner_id>", methods=["GET", "POST"])
@role_required("processor")
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

        return redirect(url_for("processor.message_thread", partner_id=partner_id))

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
        "processor/message_thread.html",
        messages=messages,
        recipients=[partner],
        thread_title=partner.full_name,
        current_route="processor.message_thread",
        current_user=current_user
    )

# ============================================================
#  🟣 2. PROCESSOR ↔ BORROWER LIVE CHAT (AI Conversation System)
# ============================================================

@socketio.on("processor_reply")
def processor_reply(data):
    """
    This is your existing borrower live-chat system.
    It is SEPARATE from Messenger and should remain intact.
    """
    borrower_id = data.get("borrower_id")
    message = (data.get("message") or "").strip()

    if not message:
        return

    # Save to LoanAIConversation table
    convo = LoanAIConversation(
        borrower_id=borrower_id,
        user_role="processor",
        topic="live_chat",
        user_message=message,
        ai_response=None,
        created_at=datetime.utcnow()
    )
    db.session.add(convo)
    db.session.commit()

    # Emit to borrower room
    emit("new_message", {
        "from": "Processor",
        "text": message,
        "timestamp": datetime.utcnow().strftime("%H:%M")
    }, room=f"borrower_{borrower_id}")


@processor_bp.route("/file/<int:loan_id>")
@role_required("processor")
def file_review(loan_id):
    """Unified Processor Loan File Review — Command Center"""
    loan = LoanApplication.query.get_or_404(loan_id)
    borrower = BorrowerProfile.query.get_or_404(loan.borrower_profile_id)

    # ------------------------------
    # Documents
    # ------------------------------
    docs = LoanDocument.query.filter_by(loan_id=loan.id).all()
    docs_pending = [d for d in docs if d.status.lower() in ["pending", "requested"]]
    docs_verified = [d for d in docs if d.status.lower() == "verified"]

    # ------------------------------
    # Conditions
    # ------------------------------
    conditions = UnderwritingCondition.query.filter_by(loan_id=loan.id).all()
    cond_open = [c for c in conditions if c.status.lower() == "open"]
    cond_cleared = [c for c in conditions if c.status.lower() == "cleared"]

    # ------------------------------
    # Payments
    # ------------------------------
    payments = PaymentRecord.query.filter_by(loan_id=loan.id).all()

    # ------------------------------
    # AI Summary
    # ------------------------------
    ai_summary = loan.ai_summary

    return render_template(
        "processor/file_review.html",
        loan=loan,
        borrower=borrower,
        docs_pending=docs_pending,
        docs_verified=docs_verified,
        cond_open=cond_open,
        cond_cleared=cond_cleared,
        payments=payments,
        ai_summary=ai_summary,
        title=f"Loan File Review — {borrower.full_name}"
    )

def calculate_dti_ltv(borrower, loan, credit):
    """
    Returns LTV, front-end DTI, back-end DTI, monthly debts, income totals.
    Used by Processor and Underwriter dashboards.
    """

    # Income
    primary = float(borrower.income or 0)
    secondary = float(getattr(borrower, "monthly_income_secondary", 0) or 0)
    total_income = primary + secondary

    # Housing expense
    housing_payment = float(getattr(borrower, "monthly_housing_payment", 0) or 0)

    # Debts (from credit report)
    monthly_debts = float(getattr(credit, "monthly_debt_total", 0) or 0)

    # DTI
    if total_income > 0:
        front = housing_payment / total_income
        back = (housing_payment + monthly_debts) / total_income
    else:
        front = None
        back = None

    # LTV
    if loan and loan.amount and loan.property_value:
        ltv = float(loan.amount) / float(loan.property_value)
    else:
        ltv = None

    return {
        "front_end_dti": front,
        "back_end_dti": back,
        "ltv": ltv,
        "monthly_debts": monthly_debts,
        "income_total": total_income
    }

@processor_bp.route("/analysis/<int:loan_id>")
def processor_analysis(loan_id):
    loan = LoanApplication.query.get_or_404(loan_id)
    borrower = loan.borrower_profile
    credit = borrower.credit_reports[-1] if borrower.credit_reports else None

    ratios = calculate_dti_ltv(borrower, loan, credit)

    return render_template(
        "processor/analysis.html",
        loan=loan,
        borrower=borrower,
        credit=credit,
        ratios=ratios
    )
