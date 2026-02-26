
# LoanMVP/routes/borrower_ai.py
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from datetime import datetime
from LoanMVP.extensions import db
from LoanMVP.ai.base_ai import AIAssistant
from LoanMVP.models.loan_models import LoanApplication, LoanQuote, BorrowerProfile
from LoanMVP.models.borrowers import PropertyAnalysis
from LoanMVP.utils.decorators import role_required

borrower_ai_bp = Blueprint("borrower_ai", __name__, url_prefix="/borrower_ai")
assistant = AIAssistant()

# =========================================================
# 🏠 Borrower AI Dashboard
# =========================================================
@borrower_ai_bp.route("/dashboard")
@role_required("borrower_ai")
def dashboard():
    """Borrower AI Hub — shows loans, quotes, and smart AI insights."""
    borrower = BorrowerProfile.query.first()
    loans = LoanApplication.query.filter_by(borrower_id=borrower.id).all() if borrower else []
    quotes = LoanQuote.query.filter_by(borrower_profile_id=borrower.id).all() if borrower else []

    stats = {
        "loan_count": len(loans),
        "quote_count": len(quotes),
        "approval_rate": "72%",
    }

    ai_summary = assistant.generate_reply(
        f"Summarize borrower AI dashboard for {borrower.full_name if borrower else 'User'} with stats {stats}",
        "borrower_ai_dashboard"
    )

    return render_template(
        "borrower_ai/dashboard.html",
        borrower=borrower,
        loans=loans,
        quotes=quotes,
        stats=stats,
        ai_summary=ai_summary,
        title="Borrower AI Dashboard"
    )


# =========================================================
# 🧾 AI Intake Session
# =========================================================
@borrower_ai_bp.route("/intake", methods=["GET", "POST"])
@role_required("borrower_ai")
def intake():
    """AI-powered loan intake that gathers borrower data automatically."""
    if request.method == "POST":
        form = request.form.to_dict()
        session_data = {
            k: form.get(k) for k in [
                "name", "email", "loan_type", "amount", "property_address",
                "credit_score", "employment", "income", "citizenship",
                "marital_status", "arv", "as_is_value", "construction_budget", "purchase_price"
            ]
        }

        ai_summary = assistant.generate_reply(
            f"Collect borrower intake details and verify eligibility: {session_data}",
            "borrower_ai_intake"
        )

        return render_template(
            "borrower_ai/intake_result.html",
            data=session_data,
            ai_summary=ai_summary,
            title="AI Intake Results"
        )

    return render_template("borrower_ai/intake.html", title="AI Loan Intake")


# =========================================================
# 💰 Quote Request + Predictive Quote AI
# =========================================================
@borrower_ai_bp.route("/quote", methods=["GET", "POST"])
@role_required("borrower_ai")
def quote():
    """Borrower requests loan quote; AI predicts best offer."""
    if request.method == "POST":
        amount = float(request.form.get("amount", 0))
        loan_type = request.form.get("loan_type", "Fix & Flip")
        arv = float(request.form.get("arv", 0))
        ltv = round(amount / arv * 100, 2) if arv else 0

        prediction = assistant.generate_reply(
            f"Predict best loan quote for type {loan_type}, amount {amount}, LTV {ltv}%.",
            "borrower_ai_quote"
        )

        quote = LoanQuote(loan_type=loan_type, amount=amount, ltv=ltv)
        db.session.add(quote)
        db.session.commit()

        return render_template(
            "borrower_ai/quote_result.html",
            quote=quote,
            prediction=prediction,
            title="AI Loan Quote"
        )

    return render_template("borrower_ai/quote.html", title="Request Loan Quote")


# =========================================================
# 🏘 Property Analyzer
# =========================================================
@borrower_ai_bp.route("/property_analysis", methods=["GET", "POST"])
@role_required("borrower_ai")
def property_analysis():
    """AI property analysis for investment potential."""
    if request.method == "POST":
        address = request.form.get("address")
        ai_result = assistant.generate_reply(
            f"Analyze investment potential for {address}. Include ARV, rent estimate, and rehab ROI.",
            "borrower_ai_property"
        )

        property_obj = PropertyAnalysis(address=address)
        db.session.add(property_obj)
        db.session.commit()

        return render_template(
            "borrower_ai/property_result.html",
            analysis=ai_result,
            address=address,
            title="Property Analysis"
        )

    return render_template("borrower_ai/property_analysis.html", title="AI Property Analyzer")


# =========================================================
# 🧮 Predictive Loan Performance
# =========================================================
@borrower_ai_bp.route("/predictive")
@role_required("borrower_ai")
def predictive():
    """AI predictive analytics for borrower loan performance."""
    portfolio = LoanApplication.query.all()
    prediction = assistant.generate_reply(
        f"Run predictive analytics for borrower portfolio with {len(portfolio)} loans.",
        "borrower_ai_predictive"
    )
    return render_template(
        "borrower_ai/predictive.html",
        portfolio=portfolio,
        prediction=prediction,
        title="Predictive Analytics"
    )


# =========================================================
# 🧩 Workflow Hub
# =========================================================
@borrower_ai_bp.route("/workflow", methods=["GET", "POST"])
@role_required("borrower_ai")
def workflow():
    """Borrower AI workflows (automated triggers, follow-ups)."""
    if request.method == "POST":
        trigger = request.form.get("trigger")
        result = assistant.generate_reply(
            f"Activate borrower AI workflow for {trigger}",
            "borrower_ai_workflow"
        )
        return jsonify({"workflow_result": result})

    workflows = [
        {"name": "Follow-Up Reminder", "status": "Active"},
        {"name": "Credit Improvement Plan", "status": "Paused"},
        {"name": "Pre-Approval Optimization", "status": "Active"},
    ]
    return render_template("borrower_ai/workflow.html", workflows=workflows, title="Borrower AI Workflows")


# =========================================================
# ⚙️ AI Tip Endpoint
# =========================================================
@borrower_ai_bp.route("/ai_tip")
@role_required("borrower_ai")
def ai_tip():
    query = request.args.get("query", "")
    context = request.args.get("context", "borrower_ai")
    reply = assistant.generate_reply(query, context)
    return jsonify({"reply": reply})
