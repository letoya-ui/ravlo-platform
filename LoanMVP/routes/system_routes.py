# =========================================================
# 🧩 System Control & Monitoring — LoanMVP Unified Version
# =========================================================

from flask import (
    Blueprint, render_template, request,
    jsonify, redirect, url_for, flash
)
from flask_login import current_user
from datetime import datetime

from LoanMVP.extensions import db
from LoanMVP.models.system_models import System, SystemLog, AuditLog, SystemSettings
from LoanMVP.models.crm_models import Lead
from LoanMVP.models.loan_models import LoanApplication, LoanNotification
from LoanMVP.models.document_models import DocumentRequest
from LoanMVP.models.user_model import User

from LoanMVP.utils.decorators import role_required
from LoanMVP.ai.master_ai import master_ai   # Correct AI engine

system_bp = Blueprint("system", __name__, url_prefix="/system")
print(">>> SYSTEM ROUTES LOADED FROM:", __file__)


# =========================================================
# 🧭 Helper — Context Builder
# =========================================================
def get_system_context():
    """Central helper for system-wide context (info, logs, audits, uptime)."""

    system = System.query.first()
    if not system:
        system = System(
            name="LoanMVP Core",
            version="v1.0",
            uptime_start=datetime.utcnow()
        )
        db.session.add(system)
        db.session.commit()

    uptime_days = (datetime.utcnow() - system.uptime_start).days

    logs = SystemLog.query.order_by(SystemLog.created_at.desc()).limit(20).all()
    audits = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(20).all()

    return {
        "system": system,
        "uptime_days": uptime_days,
        "logs": logs,
        "audits": audits
    }


# =========================================================
# 🧠 CM MASTER OPERATIONS DASHBOARD
# =========================================================
@system_bp.route("/cm-dashboard")
@role_required("system")
def cm_dashboard():

    # ---- LEADS ----
    leads = Lead.query.order_by(Lead.created_at.desc()).limit(5).all()

    # ---- LOANS ----
    loans = LoanApplication.query.order_by(LoanApplication.created_at.desc()).limit(5).all()

    # ---- PENDING DOCUMENT REQUESTS ----
    pending_docs = (
        DocumentRequest.query.filter_by(status="requested")
        .order_by(DocumentRequest.created_at.desc())
        .limit(10)
        .all()
    )

    # ---- STATS ----
    stats = {
        "total_leads": Lead.query.count(),
        "active_loans": LoanApplication.query.filter(LoanApplication.status != "completed").count(),
        "pending_conditions": DocumentRequest.query.filter_by(status="requested").count(),
    }

    # ---- AI Summary ----
    try:
        ai_summary = master_ai.ask(
            """
            Provide an executive-level summary of all departments:
            - Loan Officer
            - Processor
            - Underwriter
            
            Be direct, clear, and actionable.
            """,
            role="executive"
        )
    except:
        ai_summary = "⚠️ AI summary unavailable."

    return render_template(
        "system/cm_dashboard.html",
        leads=leads,
        loans=loans,
        pending_docs=pending_docs,
        stats=stats,
        ai_summary=ai_summary,
        title="CM Master Dashboard"
    )


# =========================================================
# 🔁 Heartbeat (System Ping)
# =========================================================
@system_bp.route("/heartbeat", methods=["POST"])
@role_required("system")
def heartbeat():
    system = System.query.first()
    if not system:
        return jsonify({"status": "error", "message": "System not initialized"}), 404

    system.last_heartbeat = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "status": "ok",
        "timestamp": system.last_heartbeat.strftime("%Y-%m-%d %H:%M:%S")
    })


# =========================================================
# 📜 System Logs
# =========================================================
@system_bp.route("/logs")
@role_required("system")
def logs():
    ctx = get_system_context()
    ctx["logs"] = SystemLog.query.order_by(SystemLog.created_at.desc()).limit(50).all()
    ctx["title"] = "System Logs"
    return render_template("system/logs.html", **ctx)


# =========================================================
# 🧾 Audit Console
# =========================================================
@system_bp.route("/audits")
@role_required("system")
def audits():
    ctx = get_system_context()
    ctx["audits"] = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(50).all()
    ctx["title"] = "Audit Console"
    return render_template("system/audits.html", **ctx)




# =========================================================
# 👥 User Management
# =========================================================
@system_bp.route("/users")
@role_required("system")
def users():
    ctx = get_system_context()
    ctx["users"] = User.query.order_by(User.created_at.desc()).all()
    ctx["title"] = "User Management"
    return render_template("system/users.html", **ctx)


# =========================================================
# 🟢 Toggle User Active Status
# =========================================================
@system_bp.route("/toggle_user/<int:user_id>")
@role_required("system")
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()

    flash(f"{'Deactivated' if not user.is_active else 'Activated'} user {user.email}.", "info")
    return redirect(url_for("system.users"))


# =========================================================
# 🗑️ Delete User
# =========================================================
@system_bp.route("/delete_user/<int:user_id>")
@role_required("system")
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()

    flash(f"🗑️ Deleted user {user.email}.", "info")
    return redirect(url_for("system.users"))


# =========================================================
# 🔬 Diagnostics
# =========================================================
@system_bp.route("/diagnostics")
@role_required("system")
def diagnostics():
    ctx = get_system_context()

    metrics = {
        "total_users": User.query.count(),
        "uptime_days": ctx["uptime_days"],
        "recent_logs": len(ctx["logs"]),
        "system_name": ctx["system"].name,
        "version": ctx["system"].version,
    }

    return render_template(
        "system/diagnostics.html",
        metrics=metrics,
        title="System Diagnostics"
    )
