import csv
import io
import json
from collections import defaultdict
from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, text

from LoanMVP.extensions import db
from LoanMVP.models.admin import AccessRequest, Company, LicenseApplication, LicenseInviteEvent, UserInvite
from LoanMVP.models.crm_models import Lead, Message, Task
from LoanMVP.models.document_models import LoanDocument
from LoanMVP.models.loan_models import BorrowerProfile, LoanApplication
from LoanMVP.models.system_models import SystemLog
from LoanMVP.models.user_model import User
from LoanMVP.routes import admin as admin_routes

executive_bp = Blueprint("executive", __name__, url_prefix="/executive")


def _ravlo_company() -> Company:
    company = Company.query.filter(
        (func.lower(Company.name) == "ravlo")
        | (func.lower(func.coalesce(Company.email_domain, "")) == "ravlohq.com")
    ).first()

    if company:
        return company

    company = Company(
        name="Ravlo",
        email_domain="ravlohq.com",
        is_active=True,
        subscription_tier="enterprise",
    )
    db.session.add(company)
    db.session.flush()
    return company


def _can_access_executive_dashboard(user) -> bool:
    role = (getattr(user, "role", "") or "").strip().lower()
    ravlo_company_id = getattr(_ravlo_company(), "id", None)
    return (
        role in {"executive", "platform_admin", "master_admin", "lending_admin"}
        and getattr(user, "company_id", None) == ravlo_company_id
    )


def _ensure_executive_access():
    if _can_access_executive_dashboard(current_user):
        return None
    flash("Your account doesn't have access to that page yet.", "warning")
    return redirect(url_for("auth.post_login_redirect"))


def _executive_company():
    return getattr(current_user, "company", None)


def _executive_company_id():
    return getattr(current_user, "company_id", None)


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


def _executive_request_query():
    company_id = _executive_company_id()
    if company_id:
        return AccessRequest.query.filter_by(company_id=company_id)
    return AccessRequest.query


def _executive_invite_query():
    company_id = _executive_company_id()
    if company_id:
        return UserInvite.query.filter_by(company_id=company_id)
    return UserInvite.query


def _executive_loan_query():
    company_id = _executive_company_id()
    if company_id and hasattr(LoanApplication, "company_id"):
        return LoanApplication.query.filter_by(company_id=company_id)
    return LoanApplication.query


def _executive_user_query():
    company_id = _executive_company_id()
    if company_id:
        return User.query.filter_by(company_id=company_id)
    return User.query


@executive_bp.route("/")
@executive_bp.route("/dashboard")
@login_required
def dashboard():
    access_redirect = _ensure_executive_access()
    if access_redirect:
        return access_redirect

    company = _executive_company()
    team_users = _executive_user_query().all()
    scoped_invites = _executive_invite_query()
    scoped_requests = _executive_request_query()
    scoped_loans = _executive_loan_query()

    stats = {
        "total_users": len(team_users),
        "total_loans": scoped_loans.count(),
        "total_docs": LoanDocument.query.count() if LoanDocument else 0,
        "pending_tasks": (
            Task.query.filter(db.func.lower(Task.status) == "pending").count()
            if Task and hasattr(Task, "status")
            else 0
        ),
        "pending_requests": scoped_requests.filter(db.func.lower(AccessRequest.status) == "pending").count(),
        "approved_requests": scoped_requests.filter(db.func.lower(AccessRequest.status) == "approved").count(),
        "total_companies": Company.query.count(),
        "pending_invites": scoped_invites.filter(db.func.lower(UserInvite.status) == "pending").count(),
    }

    recent_requests = scoped_requests.order_by(AccessRequest.created_at.desc()).limit(5).all()
    users = _executive_user_query().order_by(User.created_at.desc()).limit(5).all()
    recent_invites = scoped_invites.order_by(UserInvite.created_at.desc()).limit(5).all()
    leads = Lead.query.order_by(Lead.created_at.desc()).limit(5).all() if Lead and hasattr(Lead, "created_at") else []
    logs = SystemLog.query.order_by(SystemLog.created_at.desc()).limit(8).all() if SystemLog and hasattr(SystemLog, "created_at") else []

    loan_records = scoped_loans.all() if hasattr(LoanApplication, "created_at") else []
    loan_volume_labels, loan_volume_series = _monthly_series(loan_records, "created_at", 6)
    user_growth_labels, user_growth_series = _monthly_series(team_users, "created_at", 6)
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
        demo_dashboards=admin_routes._demo_dashboard_cards(),
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
        server_load_value=68,
    )


@executive_bp.route("/demo-center")
@login_required
def demo_center():
    access_redirect = _ensure_executive_access()
    if access_redirect:
        return access_redirect

    demo_dashboards = admin_routes._demo_dashboard_cards()
    spotlight_metrics = {
        "dashboards_ready": len(demo_dashboards),
        "single_admin_mode": "Disabled",
        "owner_admin_email": (current_app.config.get("OWNER_ADMIN_EMAIL") or "").strip().lower() or "Not set",
    }
    return render_template(
        "admin/demo_center.html",
        demo_dashboards=demo_dashboards,
        spotlight_metrics=spotlight_metrics,
        single_admin_mode=False,
        owner_admin_email="",
        route_namespace="executive",
    )


@executive_bp.route("/analytics")
@login_required
def analytics():
    access_redirect = _ensure_executive_access()
    if access_redirect:
        return access_redirect

    company = _executive_company()
    if company:
        users_query = User.query.filter_by(company_id=company.id)
        total_users = users_query.count()
        total_loans = LoanApplication.query.filter_by(company_id=company.id).count() if hasattr(LoanApplication, "company_id") else 0
        total_docs = LoanDocument.query.filter_by(company_id=company.id).count() if hasattr(LoanDocument, "company_id") else 0
        active_borrowers = BorrowerProfile.query.filter_by(company_id=company.id).count() if hasattr(BorrowerProfile, "company_id") else 0
        loan_rows = LoanApplication.query.filter_by(company_id=company.id).all() if hasattr(LoanApplication, "company_id") else []
        user_rows = users_query.all()
        ai_summary = (
            f"{company.name} executive analytics: {total_users} team user(s), "
            f"{total_loans} loan file(s), {total_docs} document(s), and "
            f"{active_borrowers} borrower profile(s) in this workspace."
        )
    else:
        users_query = User.query
        total_users = users_query.count()
        total_loans = LoanApplication.query.count()
        total_docs = LoanDocument.query.count()
        active_borrowers = User.query.filter_by(role="borrower").count()
        loan_rows = LoanApplication.query.all()
        user_rows = users_query.all()
        ai_summary = (
            f"Platform executive analytics: {total_users} total user(s), {total_loans} loan file(s), "
            f"{total_docs} document(s), and {active_borrowers} borrower account(s)."
        )

    loan_status_counts = defaultdict(int)
    for loan in loan_rows:
        loan_status_counts[(getattr(loan, "status", None) or "unknown").replace("_", " ").title()] += 1

    role_counts = defaultdict(int)
    for user in user_rows:
        role_counts[(getattr(user, "role", None) or "unknown").replace("_", " ").title()] += 1

    return render_template(
        "admin/analytics.html",
        company=company,
        total_users=total_users,
        total_loans=total_loans,
        total_docs=total_docs,
        active_borrowers=active_borrowers,
        loan_status_labels=list(loan_status_counts.keys()),
        loan_status_values=list(loan_status_counts.values()),
        role_labels=list(role_counts.keys()),
        role_values=list(role_counts.values()),
        ai_summary=ai_summary,
        route_namespace="executive",
        analytics_title="Executive Analytics Dashboard",
    )


@executive_bp.route("/access-requests", methods=["GET"])
@executive_bp.route("/requests", methods=["GET"])
@login_required
def access_requests():
    access_redirect = _ensure_executive_access()
    if access_redirect:
        return access_redirect

    requests_list = _executive_request_query().order_by(AccessRequest.created_at.desc()).all()
    return render_template(
        "admin/requests_dashboard.html",
        requests_list=requests_list,
        title="Executive Access Requests",
        active_tab="access_requests",
        route_namespace="executive",
    )


@executive_bp.route("/requests/<int:request_id>")
@login_required
def request_detail(request_id):
    access_redirect = _ensure_executive_access()
    if access_redirect:
        return access_redirect

    access_request = AccessRequest.query.get_or_404(request_id)
    return render_template(
        "admin/request_detail.html",
        access_request=access_request,
        route_namespace="executive",
    )


@executive_bp.route("/access-requests/<int:req_id>/deny", methods=["POST"])
@login_required
def deny_access_request(req_id):
    access_redirect = _ensure_executive_access()
    if access_redirect:
        return access_redirect

    req = AccessRequest.query.get_or_404(req_id)
    req.status = "denied"
    req.reviewed_by = current_user.id
    req.reviewed_at = datetime.utcnow()
    db.session.commit()
    flash(f"Access request denied for {req.email}.", "warning")
    return redirect(url_for("executive.access_requests"))


@executive_bp.route("/access-requests/<int:req_id>/approve", methods=["POST"])
@login_required
def approve_access_request(req_id):
    access_redirect = _ensure_executive_access()
    if access_redirect:
        return access_redirect

    access_request = AccessRequest.query.get_or_404(req_id)
    company = Company.query.get(access_request.company_id) if access_request.company_id else None
    if not company and access_request.company_name:
        company = Company.query.filter(func.lower(Company.name) == access_request.company_name.strip().lower()).first()

    if not company:
        subscription_tier, max_users = admin_routes._plan_defaults("team")
        company = Company(
            name=access_request.company_name or access_request.contact_name,
            email_domain=(access_request.email.split("@")[-1].lower() if access_request.email and "@" in access_request.email else None),
            subscription_tier=subscription_tier,
            max_users=max_users,
            is_active=True,
        )
        db.session.add(company)
        db.session.flush()
    else:
        company.is_active = True
        if not company.subscription_tier:
            company.subscription_tier = "team"
        if company.max_users is None:
            company.max_users = 10

    access_request.status = "approved"
    access_request.company_id = company.id
    access_request.reviewed_by = current_user.id
    access_request.reviewed_at = datetime.utcnow()
    db.session.commit()
    flash(f"Access request approved for {access_request.email}.", "success")
    return redirect(url_for("executive.access_requests"))


@executive_bp.route("/companies")
@login_required
def companies():
    access_redirect = _ensure_executive_access()
    if access_redirect:
        return access_redirect

    companies = Company.query.order_by(Company.created_at.desc()).all()
    return render_template(
        "admin/companies.html",
        companies=companies,
        route_namespace="executive",
    )


@executive_bp.route("/licensing/applications")
@login_required
def licensing_applications():
    access_redirect = _ensure_executive_access()
    if access_redirect:
        return access_redirect

    applications = LicenseApplication.query.order_by(LicenseApplication.created_at.desc()).all()
    invite_lookup = {}
    invite_event_lookup = {}
    for app in applications:
        company = Company.query.filter(func.lower(Company.name) == (app.company_name or "").strip().lower()).first()
        if company:
            invite = UserInvite.query.filter_by(company_id=company.id, email=app.email).order_by(UserInvite.created_at.desc()).first()
            if invite:
                invite_lookup[app.id] = invite
                invite_events = LicenseInviteEvent.query.filter_by(invite_token=invite.token).order_by(LicenseInviteEvent.created_at.desc()).all()
                invite_event_lookup[app.id] = {
                    "open_count": len(invite_events),
                    "last_opened_at": invite_events[0].created_at if invite_events else None,
                }

    return render_template(
        "admin/licensing_applications.html",
        applications=applications,
        invite_lookup=invite_lookup,
        invite_event_lookup=invite_event_lookup,
        route_namespace="executive",
    )


@executive_bp.route("/licensing/applications/<int:app_id>/contact", methods=["POST"])
@login_required
def contact_license_application(app_id):
    access_redirect = _ensure_executive_access()
    if access_redirect:
        return access_redirect

    app_row = LicenseApplication.query.get_or_404(app_id)
    if app_row.status == "approved":
        flash("Approved applications are already in onboarding.", "info")
        return redirect(url_for("executive.licensing_applications"))
    if app_row.status == "declined":
        flash("Declined applications cannot be moved to contacted.", "warning")
        return redirect(url_for("executive.licensing_applications"))

    app_row.status = "contacted"
    db.session.commit()
    flash("Application marked as contacted.", "success")
    return redirect(url_for("executive.licensing_applications"))


@executive_bp.route("/licensing/applications/<int:app_id>/approve", methods=["POST"])
@login_required
def approve_license_application(app_id):
    access_redirect = _ensure_executive_access()
    if access_redirect:
        return access_redirect

    app_row = LicenseApplication.query.get_or_404(app_id)
    if app_row.status == "approved":
        flash("This application was already approved.", "info")
        return redirect(url_for("executive.licensing_applications"))

    subscription_tier, max_users = admin_routes._plan_defaults(app_row.plan_interest)
    company = Company.query.filter(func.lower(Company.name) == (app_row.company_name or "").strip().lower()).first()
    if not company:
        company = Company(
            name=app_row.company_name,
            email_domain=None,
            subscription_tier=subscription_tier,
            max_users=max_users,
            is_active=True,
        )
        db.session.add(company)
        db.session.flush()
    else:
        company.subscription_tier = company.subscription_tier or subscription_tier
        company.max_users = company.max_users or max_users
        company.is_active = True

    app_row.status = "approved"
    db.session.commit()
    flash("Application approved.", "success")
    return redirect(url_for("executive.licensing_applications"))


@executive_bp.route("/licensing/applications/<int:app_id>/decline", methods=["POST"])
@login_required
def decline_license_application(app_id):
    access_redirect = _ensure_executive_access()
    if access_redirect:
        return access_redirect

    app_row = LicenseApplication.query.get_or_404(app_id)
    if app_row.status == "approved":
        flash("Approved applications cannot be declined here.", "warning")
        return redirect(url_for("executive.licensing_applications"))

    app_row.status = "declined"
    db.session.commit()
    flash("License application declined.", "success")
    return redirect(url_for("executive.licensing_applications"))


@executive_bp.route("/licensing/applications/<int:app_id>/resend-invite", methods=["POST"])
@login_required
def resend_license_application_invite(app_id):
    access_redirect = _ensure_executive_access()
    if access_redirect:
        return access_redirect

    app_row = LicenseApplication.query.get_or_404(app_id)
    if app_row.status != "approved":
        flash("Approve the application before sending an onboarding invite.", "warning")
        return redirect(url_for("executive.licensing_applications"))

    company = Company.query.filter(func.lower(Company.name) == (app_row.company_name or "").strip().lower()).first()
    if not company:
        flash("No company record was found for this approved application.", "danger")
        return redirect(url_for("executive.licensing_applications"))

    invite = UserInvite.query.filter_by(company_id=company.id, email=app_row.email).order_by(UserInvite.created_at.desc()).first()
    if not invite:
        flash("No invite was found for this application yet.", "warning")
        return redirect(url_for("executive.licensing_applications"))

    if invite.status == "accepted":
        flash("This invite has already been accepted.", "info")
        return redirect(url_for("executive.licensing_applications"))

    if invite.is_expired():
        admin_routes._refresh_invite(invite)

    try:
        admin_routes._deliver_license_invite(invite, company, app_row)
        db.session.commit()
        flash("Onboarding invite sent successfully.", "success")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to resend licensing invite email")
        flash("The invite exists, but the email could not be sent.", "warning")

    return redirect(url_for("executive.licensing_applications"))
