from flask import (
    Blueprint, render_template, request, jsonify,
    redirect, url_for, flash, session
)
from flask_login import login_required, current_user
from datetime import datetime
import random

from LoanMVP.extensions import db
from LoanMVP.models.loan_models import BorrowerProfile, LoanApplication
from LoanMVP.models.crm_models import Message
from LoanMVP.ai.base_ai import AIAssistant
from LoanMVP.utils.decorators import role_required  # ✅ NEW unified security layer

# =========================================================
# 🧠 AI Command Center — LoanMVP Unified Suite 2025
# =========================================================
ai_bp = Blueprint("ai", __name__, url_prefix="/ai")
assistant = AIAssistant()

# =========================================================
#  DASHBOARD — Central AI Intelligence Hub
# =========================================================
@ai_bp.route("/dashboard")
@role_required("ai")
def dashboard():
    """Main AI Command Center — system analytics & loan insights."""
    loans = LoanApplication.query.limit(15).all()
    for loan in loans:
        loan.amount = random.randint(100_000, 850_000)
        loan.risk_score = random.randint(10, 90)
        loan.ai_performance = random.randint(60, 100)
        loan.created_at = datetime.utcnow()
        loan.borrower_name = getattr(loan, "borrower_name", f"Client {random.randint(100,999)}")
        loan.loan_type = getattr(loan, "loan_type", "Conventional")
        loan.status = getattr(loan, "status", random.choice(["approved", "pending", "declined"]))

    stats = {
        "total_loans": len(loans),
        "funded": random.randint(5, 15),
        "pending": random.randint(3, 10),
        "declined": random.randint(1, 5),
    }

    chart = {
        "labels": ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],
        "values": [random.randint(250, 850) for _ in range(12)]
    }

    return render_template(
        "ai/dashboard.html",
        title="AI Command Center",
        loans=loans,
        stats=stats,
        chart=chart,
        role="ai"
    )

# =========================================================
# 💬 AI CHAT ASSISTANT
# =========================================================
@ai_bp.route("/chat", methods=["POST"])
@role_required("ai")
def chat():
    """Conversational AI assistant with memory for each user context."""
    data = request.get_json()
    user_message = data.get("message", "").strip()
    context = data.get("context", "general")

    if not user_message:
        return jsonify({"reply": "Please enter a message."}), 400

    role_prompts = {
        "borrower": "You are assisting a borrower with a loan inquiry.",
        "loan_officer": "You are supporting a loan officer with deal structuring.",
        "processor": "You are helping a loan processor manage documentation and files.",
        "underwriter": "You are aiding an underwriter in risk evaluation.",
        "admin": "You are assisting a system administrator with operational insights.",
        "executive": "You are advising an executive on portfolio strategy.",
        "crm": "You are helping manage client relationships and communication.",
        "property": "You are assisting with real estate market insights.",
        "general": "You are a helpful financial AI assistant."
    }

    system_message = role_prompts.get(context, role_prompts["general"])
    memory_key = f"ai_memory_{context}_{current_user.id}"
    history = session.get(memory_key, [])
    history.append({"role": "user", "content": user_message})
    history = history[-6:]  # Keep recent conversation memory

    memory_text = "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in history])
    prompt = f"{system_message}\n\nConversation so far:\n{memory_text}\n\nAI, please continue helpfully."

    try:
        reply = assistant.generate_reply(prompt, context)
    except Exception as e:
        print("AI Chat Error:", e)
        return jsonify({"reply": "⚠️ Error generating AI response."}), 500

    history.append({"role": "assistant", "content": reply})
    session[memory_key] = history
    return jsonify({"reply": reply})

# =========================================================
# 🧾 BORROWER AI INTAKE FORM
# =========================================================
@ai_bp.route("/borrower_intake", methods=["GET", "POST"])
@role_required("ai")
def borrower_intake():
    """AI-assisted borrower intake analysis."""
    if request.method == "POST":
        borrower_name = request.form.get("full_name")
        project_type = request.form.get("project_type")
        data = {
            "loan_type": request.form.get("loan_type"),
            "property_address": request.form.get("property_address"),
            "credit_score": request.form.get("credit_score"),
            "income": request.form.get("income"),
            "employment": request.form.get("employment"),
            "citizenship": request.form.get("citizenship"),
            "marital_status": request.form.get("marital_status"),
        }
        insight = assistant.generate_reply(
            f"Summarize loan readiness for borrower {borrower_name}, project {project_type}, and data: {data}",
            "loan_intake"
        )
        flash("✅ AI borrower intake completed successfully.", "success")
        return render_template("ai/borrower_intake_result.html", data=data, insight=insight)

    return render_template("ai/borrower_intake.html", title="AI Borrower Intake")

# =========================================================
# 📈 PREDICTIVE INSIGHTS
# =========================================================
@ai_bp.route("/predictive")
@role_required("ai")
def predictive():
    """AI-generated predictive analytics for loan outcomes."""
    mock_data = {
        "approval_rate": 82,
        "default_risk": 7.5,
        "avg_turnaround": "3.2 days",
        "key_drivers": ["Credit Score", "LTV", "Loan Purpose", "Income Ratio"]
    }
    return render_template("ai/predictive.html", data=mock_data, title="AI Predictive Insights")

# =========================================================
# 🌐 OMNI PANEL / VOICE / WORKFLOW
# =========================================================
@ai_bp.route("/omni")
@role_required("ai")
def omni():
    contexts = ["CRM", "Borrower", "Processor", "Loan Officer", "Underwriter"]
    return render_template("ai/omni.html", contexts=contexts, title="AI Omni Panel")

@ai_bp.route("/voice")
@role_required("ai")
def voice():
    return render_template("ai/voice.html", title="AI Voice Interaction")

@ai_bp.route("/workflow", methods=["GET", "POST"])
@role_required("ai")
def workflow():
    """AI workflow generation — task automation assistant."""
    if request.method == "POST":
        task_name = request.form.get("task")
        description = request.form.get("description")
        response = assistant.generate_reply(
            f"Create a detailed step-by-step workflow for {task_name} ({description}).",
            "workflow"
        )
        return jsonify({"workflow": response})

    return render_template("ai/workflow.html", title="AI Workflow Builder")

@ai_bp.route("/memory")
@role_required("ai")
def memory():
    """Display AI memory cache."""
    memories = assistant.list_memories(limit=10)
    return render_template("ai/memory.html", memories=memories, title="AI Memory Console")

# =========================================================
# 💡 AI TIP + WIDGET DATA ENDPOINTS
# =========================================================
@ai_bp.route("/tip")
@role_required("ai")
def ai_tip():
    """Quick context-based AI tips for dashboard widgets."""
    query = request.args.get("query", "")
    context = request.args.get("context", "loan")
    response = assistant.generate_reply(query or "Provide a useful loan insight.", context)
    return jsonify({"reply": response})

@ai_bp.route("/widget/data")
@role_required("ai")
def widget_data():
    """Randomized AI widget messages for dashboard cards."""
    messages = [
        "📈 AI predicts increased loan approvals this week.",
        "🧠 Risk scores are stabilizing across portfolios.",
        "💡 New borrower insights available in CRM dashboard."
    ]
    return jsonify({"message": random.choice(messages)})
