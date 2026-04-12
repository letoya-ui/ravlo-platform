from collections import defaultdict
from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from LoanMVP.extensions import db
from LoanMVP.models.admin import AccessRequest, Company, UserInvite
from LoanMVP.models.crm_models import Lead, Task
from LoanMVP.models.document_models import LoanDocument
from LoanMVP.models.loan_models import LoanApplication
from LoanMVP.models.system_models import SystemLog
from LoanMVP.models.user_model import User
executive_bp = Blueprint("executive", __name__, url_prefix="/executive")


def _owner_admin_email() -> str:
    return (current_app.config.get("OWNER_ADMIN_EMAIL") or "").strip().lower()


def _can_access_executive_dashboard(user) -> bool:
    role = (getattr(user, "role", "") or "").strip().lower()
    if role in {"executive", "platform_admin", "master_admin", "lending_admin"}:
        return True

    email = (getattr(user, "email", "") or "").strip().lower()
    return bool(email) and email == _owner_admin_email()


def _demo_dashboard_cards():
    return [
        {
            "role": "Investor",
            "tagline": "Capital pipeline, deal room, and subscription-led access.",
            "theme": "Investor OS",
            "kpis": [
                {"label": "Live Deals", "value": "12"},
                {"label": "Funding Ready", "value": "$4.8M"},
                {"label": "Active Plan", "value": "Pro"},
            ],
        },
        {
            "role": "Partners",
            "tagline": "Marketplace visibility, request intake, and service ops.",
            "theme": "Partner Network",
            "kpis": [
                {"label": "New Requests", "value": "18"},
                {"label": "Acceptance Rate", "value": "86%"},
                {"label": "Tier", "value": "Enterprise"},
            ],
        },
        {
            "role": "Loan Officers",
            "tagline": "Pipeline command center for leads, files, and capital submissions.",
            "theme": "Origination Desk",
            "kpis": [
                {"label": "Assigned Leads", "value": "34"},
                {"label": "Active Files", "value": "21"},
                {"label": "Capital Requests", "value": "7"},
            ],
        },
        {
            "role": "Underwriting",
            "tagline": "Conditions, risk review, and file movement through approval.",
            "theme": "Risk Console",
            "kpis": [
                {"label": "Files in Review", "value": "14"},
                {"label": "Conditions Cleared", "value": "92"},
                {"label": "Avg Turn", "value": "2.1d"},
            ],
        },
    ]


def _last_n_months(n=6):
    now = datetime.utcnow()
    months = []
    year = now.year
    month = now.month

    for _ in range(n):
        months.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1

    months.reverse()
    return months


def _monthly_series(records, date_attr="created_at", months_back=6):
    month_keys = _last_n_months(months_back)
    labels = [datetime(year, month, 1).strftime("%b") for year, month in month_keys]
    counts = defaultdict(int)

    for row in records:
        dt = getattr(row, date_attr, None)
        if dt:
            counts[(dt.year, dt.month)] += 1

    series = [counts.get((year, month), 0) for year, month in month_keys]
    return labels, series


@executive_bp.route("/")
@executive_bp.route("/dashboard")
@login_required
def dashboard():
    if not _can_access_executive_dashboard(current_user):
        flash("Your account doesn’t have access to that page yet.", "warning")
        return redirect(url_for("admin.dashboard"))

    company = getattr(current_user, "company", None)
    company_id = getattr(current_user, "company_id", None)

    if company_id:
        team_users = User.query.filter_by(company_id=company_id).all()
        scoped_invites = UserInvite.query.filter_by(company_id=company_id)
        scoped_requests = AccessRequest.query.filter_by(company_id=company_id)
        scoped_loans = (
            LoanApplication.query.filter_by(company_id=company_id)
            if hasattr(LoanApplication, "company_id")
            else LoanApplication.query
        )
    else:
        team_users = User.query.all()
        scoped_invites = UserInvite.query
        scoped_requests = AccessRequest.query
        scoped_loans = LoanApplication.query

    total_loans = scoped_loans.count() if LoanApplication else 0

    stats = {
        "total_users": len(team_users),
        "total_loans": total_loans,
        "total_docs": LoanDocument.query.count() if LoanDocument else 0,
        "pending_tasks": (
            Task.query.filter(db.func.lower(Task.status) == "pending").count()
            if Task and hasattr(Task, "status")
            else 0
        ),
        "pending_requests": scoped_requests.filter(
            db.func.lower(AccessRequest.status) == "pending"
        ).count(),
        "approved_requests": scoped_requests.filter(
            db.func.lower(AccessRequest.status) == "approved"
        ).count(),
        "total_companies": Company.query.count(),
        "pending_invites": scoped_invites.filter(
            db.func.lower(UserInvite.status) == "pending"
        ).count(),
    }

    recent_requests = (
        scoped_requests.order_by(AccessRequest.created_at.desc()).limit(5).all()
    )
    users = (
        User.query
        .order_by(User.created_at.desc())
        .limit(5)
        .all()
        if not company_id
        else User.query.filter_by(company_id=company_id).order_by(User.created_at.desc()).limit(5).all()
    )
    recent_invites = (
        scoped_invites.order_by(UserInvite.created_at.desc()).limit(5).all()
    )
    leads = (
        Lead.query.order_by(Lead.created_at.desc()).limit(5).all()
        if Lead and hasattr(Lead, "created_at")
        else []
    )
    logs = (
        SystemLog.query.order_by(SystemLog.created_at.desc()).limit(8).all()
        if SystemLog and hasattr(SystemLog, "created_at")
        else []
    )

    loan_records = scoped_loans.all() if LoanApplication and hasattr(LoanApplication, "created_at") else []
    loan_volume_labels, loan_volume_series = _monthly_series(loan_records, "created_at", 6)
    user_growth_labels, user_growth_series = _monthly_series(team_users, "created_at", 6)

    server_load_value = 68
    ai_summary = (
        f"Executive snapshot for {(company.name if company else 'Ravlo')}: "
        f"{stats['total_users']} user(s), {stats['total_loans']} loan file(s), "
        f"{stats['pending_requests']} pending request(s), and "
        f"{stats['pending_invites']} pending invite(s)."
    )

    return render_template(
        "executive/dashboard.html",
        company=company,
        stats=stats,
        demo_dashboards=_demo_dashboard_cards(),
        single_admin_mode=False,
        owner_admin_email="",
        recent_requests=recent_requests,
        users=users,
        recent_invites=recent_invites,
        leads=leads,
        logs=logs,
        ai_summary=ai_summary,
        loan_volume_labels=loan_volume_labels,
        loan_volume_series=loan_volume_series,
        user_growth_labels=user_growth_labels,
        user_growth_series=user_growth_series,
        server_load_value=server_load_value,
    )
