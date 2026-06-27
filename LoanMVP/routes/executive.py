from collections import defaultdict
from datetime import datetime, timedelta

from flask import Blueprint, current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from LoanMVP.extensions import db
from LoanMVP.models.admin import AccessRequest, Company, UserInvite
from LoanMVP.models.crm_models import Lead, Task
from LoanMVP.models.document_models import LoanDocument
from LoanMVP.models.loan_models import LoanApplication
from LoanMVP.models.system_models import SystemLog
from LoanMVP.models.user_model import User

try:
    from LoanMVP.models.ai_models import AIAssistantInteraction
except Exception:  # pragma: no cover - optional model during migrations
    AIAssistantInteraction = None

try:
    from LoanMVP.models.payment_models import PaymentRecord
except Exception:  # pragma: no cover - optional model during migrations
    PaymentRecord = None

executive_bp = Blueprint("executive", __name__, url_prefix="/executive")


def _owner_admin_email() -> str:
    return (current_app.config.get("OWNER_ADMIN_EMAIL") or "").strip().lower()


# Accounts that should always have executive dashboard access regardless
# of their stored role.  Keep addresses lower-cased.
_EXECUTIVE_DASHBOARD_EMAILS: set[str] = {
    "letoya@ravlohq.com",
    "jamaine.caughman@ravlohq.com",
}


def _can_access_executive_dashboard(user) -> bool:
    email = (getattr(user, "email", "") or "").strip().lower()
    if email in _EXECUTIVE_DASHBOARD_EMAILS:
        return True

    role = (getattr(user, "role", "") or "").strip().lower()
    company = getattr(user, "company", None)
    company_name = (getattr(company, "name", "") or "").strip().lower()

    return role in {"executive", "platform_admin", "master_admin", "lending_admin"} and company_name == "ravlo"


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


def _count_since(model, since, company_id=None):
    try:
        if not model or not hasattr(model, "created_at"):
            return 0
        q = model.query.filter(model.created_at >= since)
        if company_id and hasattr(model, "company_id"):
            q = q.filter(model.company_id == company_id)
        return q.count()
    except Exception:
        return 0


def _count_all(model):
    try:
        return model.query.count() if model else 0
    except Exception:
        return 0


def _mission_control_payload(stats, company, company_id):
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    last_24h = now - timedelta(hours=24)

    ai_today = _count_since(AIAssistantInteraction, today, company_id)
    ai_24h = _count_since(AIAssistantInteraction, last_24h, company_id)
    new_users_today = _count_since(User, today, company_id)
    new_loans_today = _count_since(LoanApplication, today, company_id)
    new_docs_today = _count_since(LoanDocument, today, company_id)
    new_leads_today = _count_since(Lead, today, company_id)
    payments_today = _count_since(PaymentRecord, today, company_id)

    try:
        recent_error_logs = SystemLog.query.filter(SystemLog.created_at >= last_24h).filter(
            db.or_(
                SystemLog.action.ilike("%error%"),
                SystemLog.action.ilike("%fail%"),
                SystemLog.description.ilike("%error%"),
                SystemLog.description.ilike("%fail%"),
            )
        ).count()
    except Exception:
        recent_error_logs = 0

    health_level = "Healthy" if recent_error_logs == 0 else "Review"
    threat_level = "Normal" if recent_error_logs == 0 else "Attention"

    mission_brief = [
        f"{new_users_today} new user(s) joined today.",
        f"{ai_today} AI interaction(s) logged today.",
        f"{new_loans_today} new loan file(s) and {new_docs_today} document(s) added today.",
        f"{stats.get('pending_requests', 0)} access request(s) and {stats.get('pending_invites', 0)} invite(s) need visibility.",
    ]

    focus_items = []
    if stats.get("pending_requests", 0):
        focus_items.append({"level": "warning", "title": "Review access requests", "detail": f"{stats['pending_requests']} request(s) are waiting."})
    if stats.get("pending_invites", 0):
        focus_items.append({"level": "info", "title": "Follow up on pending invites", "detail": f"{stats['pending_invites']} invite(s) have not been accepted."})
    if recent_error_logs:
        focus_items.append({"level": "danger", "title": "Check platform logs", "detail": f"{recent_error_logs} error/failure log(s) in the last 24 hours."})
    if not focus_items:
        focus_items.append({"level": "success", "title": "No urgent issues", "detail": "Platform activity looks stable right now."})

    return {
        "generated_at": now.strftime("%I:%M %p"),
        "company_name": company.name if company else "Ravlo",
        "health_level": health_level,
        "threat_level": threat_level,
        "brief": mission_brief,
        "focus_items": focus_items,
        "cards": [
            {"label": "New Users Today", "value": new_users_today, "detail": "Fresh accounts since midnight"},
            {"label": "AI Today", "value": ai_today, "detail": f"{ai_24h} in last 24h"},
            {"label": "New Leads Today", "value": new_leads_today, "detail": "CRM and intake momentum"},
            {"label": "Payments Today", "value": payments_today, "detail": "Payment records logged"},
        ],
        "systems": [
            {"name": "Web App", "status": "Online", "tone": "success"},
            {"name": "Database", "status": "Connected", "tone": "success"},
            {"name": "AI Services", "status": "Active" if ai_24h else "Ready", "tone": "success"},
            {"name": "Security", "status": threat_level, "tone": "success" if threat_level == "Normal" else "warning"},
        ],
    }


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

    mission_control = _mission_control_payload(stats, company, company_id)
    server_load_value = 68
    ai_summary = (
        f"Mission Control snapshot for {(company.name if company else 'Ravlo')}: "
        f"{stats['total_users']} user(s), {stats['total_loans']} loan file(s), "
        f"{stats['pending_requests']} pending request(s), "
        f"{stats['pending_invites']} pending invite(s), and "
        f"{mission_control['cards'][1]['value']} AI interaction(s) today."
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
        mission_control=mission_control,
        loan_volume_labels=loan_volume_labels,
        loan_volume_series=loan_volume_series,
        user_growth_labels=user_growth_labels,
        user_growth_series=user_growth_series,
        server_load_value=server_load_value,
    )
