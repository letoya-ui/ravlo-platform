# =========================================================
# 🏛 LoanMVP Executive Routes — 2025 Unified Final Version
# =========================================================

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import current_user
from datetime import datetime
from LoanMVP.extensions import db
from LoanMVP.ai.base_ai import AIAssistant
from LoanMVP.models.loan_models import LoanApplication, LoanQuote
from LoanMVP.models.crm_models import Lead, Partner
from LoanMVP.models.borrowers import PropertyAnalysis
from LoanMVP.utils.decorators import role_required  # ✅ Secure access

# ---------------------------------------------------------
# Blueprint Setup
# ---------------------------------------------------------
executive_bp = Blueprint("executive", __name__, url_prefix="/executive")
assistant = AIAssistant()

# ---------------------------------------------------------
# 🏛 Executive Dashboard
# ---------------------------------------------------------
@executive_bp.route("/dashboard")
@role_required("executive")
def dashboard():
    """C-suite dashboard — global portfolio metrics & AI summary."""
    total_loans = LoanApplication.query.count()
    approved = LoanApplication.query.filter_by(status="approved").count()
    declined = LoanApplication.query.filter_by(status="declined").count()
    total_volume = sum([l.amount or 0 for l in LoanApplication.query.all()])
    investors = Partner.query.count()
    leads = Lead.query.count()

    stats = {
        "total_loans": total_loans,
        "approved": approved,
        "declined": declined,
        "total_volume": f"${total_volume:,.0f}",
        "investors": investors,
        "leads": leads,
    }

    try:
        ai_summary = assistant.generate_reply(
            f"Summarize executive portfolio metrics: {stats}", "executive_dashboard"
        )
    except Exception:
        ai_summary = "AI summary unavailable."

    return render_template("executive/dashboard.html",
                           stats=stats, ai_summary=ai_summary,
                           title="Executive Dashboard")

# ---------------------------------------------------------
# 💰 Capital Management & AI Allocation
# ---------------------------------------------------------
@executive_bp.route("/capital", methods=["GET", "POST"])
@role_required("executive")
def capital():
    """Manage funding pools, allocations, and capital performance."""
    capital_pools = [
        {"name": "CM Lending Fund I", "balance": 12_500_000, "utilization": 68},
        {"name": "CM Private Equity II", "balance": 8_750_000, "utilization": 52},
        {"name": "Partner Capital Pool", "balance": 3_900_000, "utilization": 84},
    ]

    if request.method == "POST":
        request_data = request.form.get("allocation_request", "")
        try:
            ai_advice = assistant.generate_reply(
                f"Analyze capital allocation request: {request_data}", "capital_ai"
            )
        except Exception:
            ai_advice = "AI analysis unavailable."

        flash("✅ Capital allocation processed successfully.", "success")
        return render_template("executive/capital_result.html",
                               pools=capital_pools, ai_advice=ai_advice,
                               title="Capital Intelligence Result")

    return render_template("executive/capital.html", pools=capital_pools, title="Capital Management")

# ---------------------------------------------------------
# 📈 Deal Forecast & Pipeline Insights
# ---------------------------------------------------------
@executive_bp.route("/forecast")
@role_required("executive")
def forecast():
    """AI-predicted future closing volume and approval probabilities."""
    loans = LoanApplication.query.order_by(LoanApplication.created_at.desc()).limit(25).all()
    forecast_data = {
        "expected_volume": 4_800_000,
        "approval_chance": "77%",
        "avg_turnaround": "9 days",
    }

    try:
        ai_forecast = assistant.generate_reply(
            f"Predict quarterly closing trends using {len(loans)} loans.", "deal_forecast"
        )
    except Exception:
        ai_forecast = "AI forecast unavailable."

    return render_template("executive/forecast.html",
                           loans=loans, forecast=forecast_data,
                           ai_forecast=ai_forecast, title="Deal Forecast")

# ---------------------------------------------------------
# 🧮 Financial Intelligence / DSCR Analysis
# ---------------------------------------------------------
@executive_bp.route("/finance_ai", methods=["GET", "POST"])
@role_required("executive")
def finance_ai():
    """Perform DSCR, ROI, and yield analysis using AI."""
    if request.method == "POST":
        metrics = request.form.to_dict()
        try:
            ai_analysis = assistant.generate_reply(
                f"Analyze financial ratios and yields: {metrics}", "finance_ai"
            )
        except Exception:
            ai_analysis = "AI analysis unavailable."
        return render_template("executive/finance_result.html",
                               analysis=ai_analysis, title="Finance AI Result")
    return render_template("executive/finance_ai.html", title="Financial Intelligence")

# ---------------------------------------------------------
# ⚠️ Risk & Exposure Map
# ---------------------------------------------------------
@executive_bp.route("/risk")
@role_required("executive")
def risk():
    """Regional exposure and risk visualization."""
    from LoanMVP.models.loan_models import BorrowerProfile

    loans = LoanApplication.query.join(BorrowerProfile, LoanApplication.borrower_profile_id == BorrowerProfile.id).all()

    risk_map = {
        "NY": sum((l.loan_balance or 0) for l in loans if l.borrower_profile and (l.borrower_profile.state or "").upper() == "NY"),
        "NJ": sum((l.loan_balance or 0) for l in loans if l.borrower_profile and (l.borrower_profile.state or "").upper() == "NJ"),
        "PA": sum((l.loan_balance or 0) for l in loans if l.borrower_profile and (l.borrower_profile.state or "").upper() == "PA"),
    }

    total_exposure = sum(risk_map.values())
    risk_percentages = {
        state: (value / total_exposure * 100 if total_exposure > 0 else 0)
        for state, value in risk_map.items()
    }

    chart_data = [
        {"state": s, "exposure": v, "percent": round(risk_percentages[s], 2)} for s, v in risk_map.items()
    ]

    return render_template("executive/risk.html",
                           risk_map=risk_map,
                           total_exposure=total_exposure,
                           chart_data=chart_data,
                           title="Risk & Exposure Map")

# ---------------------------------------------------------
# 🤝 Investor Portal / Partner Insights
# ---------------------------------------------------------
@executive_bp.route("/investors")
@role_required("executive")
def investors():
    """Investor and partner performance summary."""
    partners = Partner.query.order_by(Partner.name.asc()).all()
    try:
        ai_insight = assistant.generate_reply(
            f"Summarize investor metrics for {len(partners)} investors.", "investor_portal"
        )
    except Exception:
        ai_insight = "AI insight unavailable."

    return render_template("executive/investors.html",
                           partners=partners,
                           ai_insight=ai_insight,
                           title="Investor Portal")

# ---------------------------------------------------------
# 🤖 Auto Funding Decision
# ---------------------------------------------------------
@executive_bp.route("/auto_funding", methods=["POST"])
@role_required("executive")
def auto_funding():
    """Automatically approve or flag loans based on AI assessment."""
    loan_id = request.form.get("loan_id")
    loan = LoanApplication.query.get(loan_id)
    try:
        ai_decision = assistant.generate_reply(
            f"Decide funding approval for loan {loan_id} amount {loan.amount if loan else 'N/A'}",
            "auto_funding"
        )
    except Exception:
        ai_decision = "AI decision unavailable."

    if loan and "approve" in ai_decision.lower():
        loan.status = "approved"
        db.session.commit()
        flash("✅ Loan approved by AI Funding Engine.", "success")
    else:
        flash("⚠️ AI flagged this loan for manual review.", "warning")

    return jsonify({"decision": ai_decision})

# ---------------------------------------------------------
# 🤝 Partner & Vendor Management
# ---------------------------------------------------------
@executive_bp.route("/partners", methods=["GET", "POST"])
@role_required("executive")
def partners():
    """Executive partner management — lenders, affiliates, vendors."""
    if not Partner.query.first():
        seed_partners = [
            Partner(name="Lima One Capital", type="Lender", email="info@limaone.com",
                    status="Active", deals=12, volume=1_200_000, rating=4.7, created_at=datetime.utcnow()),
            Partner(name="Roc Capital", type="Lender", email="partners@roccapital.com",
                    status="Active", deals=8, volume=870_000, rating=4.5, created_at=datetime.utcnow()),
            Partner(name="Lev Capital", type="Affiliate", email="team@levcap.com",
                    status="Pending", deals=5, volume=500_000, rating=4.2, created_at=datetime.utcnow()),
        ]
        db.session.add_all(seed_partners)
        db.session.commit()
        flash("✨ Partner list initialized with demo data.", "info")

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        partner_type = request.form.get("type")

        if not name or not partner_type:
            flash("⚠️ Name and Type are required.", "warning")
            return redirect(url_for("executive.partners"))

        new_partner = Partner(
            name=name,
            email=email,
            type=partner_type,
            status="Pending",
            deals=0,
            volume=0.0,
            rating=0.0,
            created_at=datetime.utcnow()
        )
        db.session.add(new_partner)
        db.session.commit()
        flash(f"✅ Partner '{name}' added successfully.", "success")
        return redirect(url_for("executive.partners"))

    partners = Partner.query.order_by(Partner.created_at.desc()).all()
    total_volume = sum(p.volume or 0 for p in partners)
    avg_rating = round(sum(p.rating or 0 for p in partners) / len(partners), 2) if partners else 0

    return render_template("executive/partners.html",
                           partners=partners,
                           total_volume=total_volume,
                           avg_rating=avg_rating,
                           title="Partner Intelligence Hub")

# ---------------------------------------------------------
# 🔍 Partner Detail
# ---------------------------------------------------------
@executive_bp.route("/partners/<int:partner_id>")
@role_required("executive")
def partner_detail(partner_id):
    """Detailed partner performance and activity overview."""
    partner = Partner.query.get(partner_id)
    if not partner:
        flash("⚠️ Partner not found or removed.", "warning")
        return redirect(url_for("executive.partners"))

    return render_template("executive/partner_detail.html",
                           partner=partner,
                           title=f"{partner.name} Overview")
