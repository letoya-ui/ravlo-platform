# =========================================================
# 🏛 ADMIN ROUTES — LoanMVP 2025 (Stabilized Version)
# =========================================================

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import current_user
from datetime import datetime
from LoanMVP.extensions import db

from LoanMVP.ai.base_ai import AIAssistant     # ✅ Unified AI import
from LoanMVP.utils.decorators import role_required

# MODELS
from LoanMVP.models.user_model import User
from LoanMVP.models.crm_models import Message, Task
from LoanMVP.models.loan_models import LoanApplication, BorrowerProfile
from LoanMVP.models.document_models import LoanDocument
from LoanMVP.models.system_models import SystemLog

import io
import csv
import time

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
assistant = AIAssistant()

# =========================================================
# 🔐 ADMIN ONLY CHECK
# =========================================================
def admin_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            flash("⚠️ Unauthorized access.", "danger")
            return redirect(url_for("auth.login"))
        return func(*args, **kwargs)
    return wrapper


# =========================================================
# 🏠 ADMIN DASHBOARD
# =========================================================
@admin_bp.route("/dashboard")
@role_required("admin")
def dashboard():
    stats = {
        "total_users": User.query.count(),
        "total_loans": LoanApplication.query.count(),
        "total_docs": LoanDocument.query.count(),
        "pending_tasks": Task.query.filter_by(status="Pending").count(),
    }

    logs = SystemLog.query.order_by(SystemLog.created_at.desc()).limit(15).all()

    # AI Summary
    try:
        ai_summary = assistant.generate_reply(
            "Summarize admin system activity including users, loans, documents, and system logs.",
            "admin"
        )
    except:
        ai_summary = "⚠️ AI summary unavailable."

    return render_template(
        "admin/dashboard.html",
        stats=stats,
        logs=logs,
        ai_summary=ai_summary
    )


# =========================================================
# 📊 SYSTEM REPORTS (CSV EXPORT)
# =========================================================
@admin_bp.route("/reports", methods=["GET", "POST"])
@role_required("admin")
def reports():
    report_type = request.form.get("report_type")
    csv_data = None

    if request.method == "POST" and report_type:
        output = io.StringIO()
        writer = csv.writer(output)

        if report_type == "users":
            writer.writerow(["ID", "Username", "Email", "Role", "Created"])
            for u in User.query.all():
                writer.writerow([u.id, u.username, u.email, u.role, u.created_at])

        elif report_type == "loans":
            writer.writerow(["ID", "Borrower ID", "Type", "Amount", "Status", "Created"])
            for l in LoanApplication.query.all():
                writer.writerow([l.id, l.borrower_profile_id, l.loan_type, l.amount, l.status, l.created_at])

        elif report_type == "documents":
            writer.writerow(["ID", "Borrower ID", "Name", "Status", "Created"])
            for d in LoanDocument.query.all():
                writer.writerow([d.id, d.borrower_profile_id, d.document_name, d.status, d.created_at])

        output.seek(0)
        csv_data = output.getvalue()

        return send_file(
            io.BytesIO(csv_data.encode("utf-8")),
            as_attachment=True,
            download_name=f"{report_type}_report.csv",
            mimetype="text/csv"
        )

    return render_template("admin/reports.html")


# =========================================================
# 💬 ADMIN MESSAGE CENTER
# =========================================================
@admin_bp.route("/messages", methods=["GET", "POST"])
@role_required("admin")
def messages():
    if request.method == "POST":
        content = request.form.get("content")
        recipient = request.form.get("recipient_id") or None

        if not content:
            flash("⚠️ Message cannot be empty.", "warning")
            return redirect(url_for("admin.messages"))

        new_msg = Message(
            sender_id=current_user.id,
            recipient_id=recipient,
            content=content,
            timestamp=datetime.utcnow()
        )
        db.session.add(new_msg)
        db.session.commit()
        flash("Message sent.", "success")
        return redirect(url_for("admin.messages"))

    msgs = Message.query.order_by(Message.timestamp.desc()).limit(50).all()
    users = User.query.all()
    return render_template("admin/messages.html", messages=msgs, users=users)


# =========================================================
# 📑 VERIFY DOCUMENTS
# =========================================================
@admin_bp.route("/verify_data")
@role_required("admin")
def verify_data():
    docs = LoanDocument.query.order_by(LoanDocument.created_at.desc()).limit(50).all()

    # Attach borrower name
    for d in docs:
        borrower = BorrowerProfile.query.get(d.borrower_profile_id)
        d.borrower_name = borrower.full_name if borrower else "—"

    return render_template("admin/verify_data.html", docs=docs)


@admin_bp.route("/verify_doc/<int:doc_id>")
@role_required("admin")
def verify_doc(doc_id):
    doc = LoanDocument.query.get_or_404(doc_id)
    doc.status = "verified"
    db.session.commit()
    flash("Document verified.", "success")
    return redirect(url_for("admin.verify_data"))


# =========================================================
# 📊 BASIC ANALYTICS
# =========================================================
@admin_bp.route("/analytics")
@role_required("admin")
def analytics():
    stats = {
        "users": User.query.count(),
        "loans": LoanApplication.query.count(),
        "docs": LoanDocument.query.count(),
        "borrowers": User.query.filter_by(role="borrower").count(),
        "officers": User.query.filter_by(role="loan_officer").count()
    }

    return render_template("admin/analytics.html", stats=stats)


# =========================================================
# 🤖 AI CONTROL PANEL
# =========================================================
@admin_bp.route("/ai_dashboard")
@role_required("admin")
def ai_dashboard():
    return render_template(
        "admin/ai_dashboard.html",
        ai_status={
            "Analytics Engine": "Active",
            "Borrower AI": "Active",
            "Loan Engine": "Active",
        },
        last_refresh=datetime.utcnow()
    )


@admin_bp.route("/ai/refresh/<string:target>", methods=["POST"])
@role_required("admin")
def ai_refresh(target):
    time.sleep(1.2)
    flash(f"{target} refreshed successfully.", "success")
    return jsonify({"success": True, "target": target})
