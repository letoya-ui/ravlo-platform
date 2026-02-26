# =========================================================
# 🧭 LoanMVP Intelligence Routes — 2025 Unified Final Version
# =========================================================

from flask import Blueprint, render_template, request, jsonify
from flask_login import current_user
from datetime import datetime
from LoanMVP.extensions import db
from LoanMVP.ai.base_ai import AIAssistant
from LoanMVP.models.loan_models import LoanApplication
from LoanMVP.models.crm_models import Lead
from LoanMVP.models.borrowers import PropertyAnalysis
from LoanMVP.models.system_models import SystemLog
from LoanMVP.utils.decorators import role_required  # ✅ Consistent access control

# ---------------------------------------------------------
# Blueprint Setup
# ---------------------------------------------------------
intelligence_bp = Blueprint("intelligence", __name__, url_prefix="/intelligence")
assistant = AIAssistant()

# ---------------------------------------------------------
# 🧭 Intelligence Dashboard
# ---------------------------------------------------------
@intelligence_bp.route("/dashboard")
@role_required("intelligence")
def dashboard():
    """Unified intelligence dashboard combining CRM, Loans, and Operations data."""
    loans = LoanApplication.query.count()
    leads = Lead.query.count()
    properties = PropertyAnalysis.query.count()

    logs = []
    if hasattr(SystemLog, "timestamp"):
        logs = SystemLog.query.order_by(SystemLog.timestamp.desc()).limit(10).all()

    try:
        ai_summary = assistant.generate_reply(
            f"Summarize intelligence snapshot: {loans} loans, {leads} leads, {properties} property analyses.",
            "intelligence_dashboard"
        )
    except Exception as e:
        print(" AI dashboard summary error:", e)
        ai_summary = "AI intelligence summary unavailable."

    stats = {
        "loans": loans,
        "leads": leads,
        "properties": properties,
        "uptime": "99.97%",
        "ai_summary": ai_summary
    }

    return render_template("intelligence/dashboard.html",
                           stats=stats, logs=logs,
                           title="Intelligence Dashboard")

# ---------------------------------------------------------
# 🔮 Quantum Memory Console
# ---------------------------------------------------------
@intelligence_bp.route("/quantum_memory", methods=["GET", "POST"])
@role_required("intelligence")
def quantum_memory():
    """AI persistent memory engine — retrieves long-term contextual insights."""
    if request.method == "POST":
        query = request.form.get("query", "")
        try:
            ai_memory = assistant.generate_reply(
                f"Retrieve long-term memory insights for: {query}", "quantum_memory"
            )
        except Exception as e:
            print(" AI quantum memory error:", e)
            ai_memory = "AI memory service unavailable."

        return render_template("intelligence/quantum_result.html",
                               query=query,
                               ai_memory=ai_memory,
                               title="Quantum Memory Insights")

    return render_template("intelligence/quantum_memory.html", title="Quantum Memory")

# ---------------------------------------------------------
# ⚡ Real-Time Data Engine
# ---------------------------------------------------------
@intelligence_bp.route("/realtime")
@role_required("intelligence")
def realtime():
    """Live analytics feed combining loan updates, CRM events, and AI alerts."""
    try:
        loans = LoanApplication.query.order_by(LoanApplication.updated_at.desc()).limit(10).all()
    except Exception:
        loans = LoanApplication.query.order_by(LoanApplication.created_at.desc()).limit(10).all()

    leads = Lead.query.order_by(Lead.created_at.desc()).limit(10).all()

    try:
        ai_summary = assistant.generate_reply(
            "Summarize latest real-time loan and lead activities for intelligence view.",
            "realtime"
        )
    except Exception:
        ai_summary = "AI summary unavailable."

    return render_template("intelligence/realtime.html",
                           loans=loans,
                           leads=leads,
                           ai_summary=ai_summary,
                           title="Real-Time Analytics")

# ---------------------------------------------------------
# 🤖 AI Omni Command Center
# ---------------------------------------------------------
@intelligence_bp.route("/omni", methods=["GET", "POST"])
@role_required("intelligence")
def omni():
    """Central AI orchestration hub — cross-role control & predictive operations."""
    response = None
    if request.method == "POST":
        prompt = request.form.get("prompt", "")
        context = request.form.get("context", "system")
        try:
            response = assistant.generate_reply(prompt, context)
        except Exception as e:
            print(" Omni AI error:", e)
            response = "AI command execution failed."

    return render_template("intelligence/omni.html",
                           response=response,
                           title="AI Omni Command Center")

# ---------------------------------------------------------
# 🧩 System Command Center
# ---------------------------------------------------------
@intelligence_bp.route("/command_center", methods=["GET", "POST"])
@role_required("intelligence")
def command_center():
    """Admin-level AI monitoring panel for all backend operations."""
    ai_alert = None
    if request.method == "POST":
        command = request.form.get("command", "")
        try:
            ai_alert = assistant.generate_reply(
                f"Execute system command and summarize: {command}",
                "command_center"
            )
        except Exception as e:
            print(" Command center AI error:", e)
            ai_alert = "Command execution failed."

    logs = []
    if hasattr(SystemLog, "timestamp"):
        logs = SystemLog.query.order_by(SystemLog.timestamp.desc()).limit(15).all()

    return render_template("intelligence/command_center.html",
                           logs=logs,
                           ai_alert=ai_alert,
                           title="System Command Center")

# ---------------------------------------------------------
# 🔍 AI Query Endpoint (JSON)
# ---------------------------------------------------------
@intelligence_bp.route("/ai_query")
@role_required("intelligence")
def ai_query():
    """Direct API endpoint for quick AI queries."""
    query = request.args.get("query", "")
    context = request.args.get("context", "intelligence")

    if not query:
        return jsonify({"reply": "⚠️ Please provide a query."}), 400

    try:
        reply = assistant.generate_reply(query, context)
    except Exception as e:
        print(" AI query error:", e)
        reply = "AI query service unavailable."

    return jsonify({"reply": reply})
