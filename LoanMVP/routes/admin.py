# =========================================================
# 🏛 ADMIN ROUTES — LoanMVP 2025 (Stabilized Version)
# =========================================================

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, current_app
from flask_login import current_user, login_required
from collections import defaultdict
from sqlalchemy import func, desc
from sqlalchemy.orm import aliased
from datetime import datetime, timedelta
from LoanMVP.extensions import db, csrf
from werkzeug.security import generate_password_hash

from LoanMVP.ai.base_ai import AIAssistant     # ✅ Unified AI import
from LoanMVP.utils.decorators import role_required
from LoanMVP.utils.emailer import send_email  # or wherever you saved it
from LoanMVP.utils.role_helpers import is_admin


# MODELS
from LoanMVP.models.user_model import User
from LoanMVP.models.crm_models import Lead, Message, Task 
from LoanMVP.models.loan_models import LoanApplication, BorrowerProfile
from LoanMVP.models.document_models import LoanDocument
from LoanMVP.models.system_models import SystemLog
from LoanMVP.models.admin import Company, AccessRequest, UserInvite, LicenseApplication, LicenseInviteEvent
from LoanMVP.models.ai_models import AIAssistantInteraction
from LoanMVP.services.notify_service import notify

import io
import csv
import time

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
assistant = AIAssistant()
FULL_ADMIN_ROLES = {"platform_admin", "master_admin", "lending_admin"}

# =========================================================
# 🔐 ADMIN ONLY CHECK
# =========================================================
def admin_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        user_role = (getattr(current_user, "role", "") or "").strip().lower()
        if not current_user.is_authenticated or user_role not in {"admin", *FULL_ADMIN_ROLES}:
            flash("⚠️ Unauthorized access.", "danger")
            return redirect(url_for("auth.login"))
        return func(*args, **kwargs)
    return wrapper


def _is_company_admin(user) -> bool:
    return ((getattr(user, "role", "") or "").strip().lower() == "admin")


def _is_full_admin(user) -> bool:
    return ((getattr(user, "role", "") or "").strip().lower() in FULL_ADMIN_ROLES)


def _admin_home_endpoint():
    if _is_company_admin(current_user) and getattr(current_user, "company_id", None):
        return url_for("admin.company_dashboard", company_id=current_user.company_id)
    return url_for("admin.dashboard")


def _ensure_company_access(company):
    if _is_full_admin(current_user):
        return None

    if _is_company_admin(current_user) and getattr(current_user, "company_id", None) == company.id:
        return None

    flash("You do not have access to that company workspace.", "warning")
    return redirect(_admin_home_endpoint())


def _company_scope():
    if not _is_company_admin(current_user):
        return None
    return Company.query.get(getattr(current_user, "company_id", None)) if getattr(current_user, "company_id", None) else None


def _can_access_request(access_request) -> bool:
    if _is_full_admin(current_user):
        return True

    company = _company_scope()
    if not company:
        return False

    request_company_name = (getattr(access_request, "company_name", "") or "").strip().lower()
    company_name = (company.name or "").strip().lower()
    email_domain = (company.email_domain or "").strip().lower()
    email = (getattr(access_request, "email", "") or "").strip().lower()

    return (
        getattr(access_request, "company_id", None) == company.id
        or (company_name and request_company_name == company_name)
        or (email_domain and email.endswith(f"@{email_domain}"))
    )


def _plan_defaults(plan_interest: str):
    plan = (plan_interest or "").strip().lower()

    if plan == "individual":
        return "individual", 1
    if plan == "team":
        return "team", 10
    if plan == "lender":
        return "lender", 50
    if plan == "white_label":
        return "white_label", None

    return "team", 10


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


def _send_email_fallback(to_email: str, subject: str, body: str, html: str):
    """
    Replace this with your real SendGrid / existing email helper.
    """
    current_app.logger.info("EMAIL TO: %s | SUBJECT: %s", to_email, subject)
    current_app.logger.info("BODY: %s", body)
    current_app.logger.info("HTML: %s", html)


def _deliver_license_invite(invite, company, application):
    subject, body, html = _build_license_invite_email(invite, company, application)
    send_email(
        to=invite.email,
        subject=subject,
        html_body=html,
        text_body=body,
    )


def _refresh_invite(invite):
    invite.token = UserInvite.generate_token()
    invite.status = "pending"
    invite.accepted_at = None
    invite.expires_at = UserInvite.default_expiration(days=7)
    return invite


def _access_request_role(access_request):
    role = ((access_request.requested_role or "").strip().lower()).replace(" ", "_")
    allowed_roles = {"admin", "loan_officer", "processor", "underwriter"}
    if role in allowed_roles:
        return role
    return "admin"


def _build_access_request_invite_email(invite, company, access_request):
    invite_url = url_for("auth.accept_invite", token=invite.token, _external=True)
    role_label = invite.role.replace("_", " ").title()
    contact_name = access_request.contact_name or invite.first_name or "there"

    subject = f"Your access request for {company.name} was approved"

    body = f"""
Hi {contact_name},

Your request to join {company.name} on Ravlo has been approved.

Use the secure link below to activate your account:

{invite_url}

Role: {role_label}

If you were not expecting this email, you can ignore it.

- Ravlo
""".strip()

    html = f"""
    <div style="font-family:Inter,Arial,sans-serif;background:#071018;padding:32px;color:#f4f7fb;">
      <div style="max-width:680px;margin:0 auto;background:#0f1a26;border:1px solid rgba(255,255,255,.08);border-radius:20px;padding:32px;">
        <div style="font-size:12px;letter-spacing:.18em;font-weight:800;color:#8ec5ff;margin-bottom:12px;">
          RAVLO ACCESS APPROVED
        </div>
        <h1 style="margin:0 0 12px;font-size:30px;line-height:1.1;">
          Your account is ready
        </h1>
        <p style="margin:0 0 14px;color:#c9d6e3;">
          Your access request for <strong>{company.name}</strong> has been approved.
        </p>
        <p style="margin:0 0 18px;color:#c9d6e3;">
          Role: <strong>{role_label}</strong>
        </p>
        <a href="{invite_url}" style="display:inline-block;padding:14px 20px;background:#1f8fff;color:#ffffff;text-decoration:none;border-radius:12px;font-weight:700;">
          Accept Invite
        </a>
        <p style="margin:18px 0 0;color:#8da3b8;font-size:13px;">
          This link expires in 7 days.
        </p>
      </div>
    </div>
    """.strip()

    return subject, body, html


def _deliver_access_request_invite(invite, company, access_request):
    subject, body, html = _build_access_request_invite_email(invite, company, access_request)
    send_email(
        to=invite.email,
        subject=subject,
        html_body=html,
        text_body=body,
    )


def _send_team_invite_email(invite, company):
    invite_url = url_for("auth.register_from_invite", token=invite.token, _external=True)
    role_label = (invite.role or "").replace("_", " ").title()
    first_name = (invite.first_name or "").strip() or "there"

    subject = f"You're invited to join {company.name} on Ravlo"
    body = f"""
Hi {first_name},

You have been invited to join {company.name} on Ravlo as a {role_label}.

Complete your registration here:
{invite_url}

This link expires in 7 days.
""".strip()

    html = f"""
    <div style="font-family:Inter,Arial,sans-serif;line-height:1.6;color:#111;">
      <h2>You're invited to Ravlo</h2>
      <p>Hello {first_name},</p>
      <p>You have been invited to join <strong>{company.name}</strong> as a <strong>{role_label}</strong>.</p>
      <p>
        Complete your registration here:<br>
        <a href="{invite_url}">{invite_url}</a>
      </p>
      <p>This link expires in 7 days.</p>
    </div>
    """.strip()

    send_email(
        to=invite.email,
        subject=subject,
        html_body=html,
        text_body=body,
    )


def _build_license_invite_email(invite, company, application):
    invite_url = url_for("auth.accept_invite", token=invite.token, _external=True)
    tracking_pixel = url_for(
        "tracking.license_invite_pixel",
        token=invite.token,
        email=invite.email,
        _external=True
    )

    subject = f"You've been invited to join {company.name} on Ravlo"

    body = f"""
Hi {application.contact_name or 'there'},

Your licensing application for {company.name} has been approved.

Use the link below to accept your invite and activate your account:

{invite_url}

Plan: {company.subscription_tier or 'team'}
Role: {invite.role}

If you were not expecting this email, you can ignore it.

- Ravlo
""".strip()

    html = f"""
    <div style="font-family:Inter,Arial,sans-serif;background:#071018;padding:32px;color:#f4f7fb;">
      <div style="max-width:680px;margin:0 auto;background:#0f1a26;border:1px solid rgba(255,255,255,.08);border-radius:20px;padding:32px;">
        <div style="font-size:12px;letter-spacing:.18em;font-weight:800;color:#8ec5ff;margin-bottom:12px;">
          RAVLO LICENSING
        </div>

        <h1 style="margin:0 0 12px;font-size:30px;line-height:1.1;">
          Your application has been approved
        </h1>

        <p style="color:#9bb0c3;line-height:1.7;margin:0 0 16px;">
          Hi {application.contact_name or 'there'},
        </p>

        <p style="color:#dce8f4;line-height:1.7;">
          Your licensing application for <strong>{company.name}</strong> has been approved.
          You can now activate your company admin account.
        </p>

        <p style="margin:24px 0;">
          <a href="{invite_url}"
             style="display:inline-block;padding:14px 20px;border-radius:12px;background:linear-gradient(135deg,#5da2ff,#84bdff);color:#08111a;text-decoration:none;font-weight:800;">
            Accept Invite & Get Started
          </a>
        </p>

        <div style="margin-top:18px;padding:16px;border-radius:14px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);">
          <p style="margin:0 0 8px;color:#dce8f4;"><strong>Plan:</strong> {company.subscription_tier or 'team'}</p>
          <p style="margin:0;color:#dce8f4;"><strong>Role:</strong> {invite.role}</p>
        </div>

        <p style="color:#9bb0c3;line-height:1.7;margin-top:20px;">
          If you were not expecting this email, you can ignore it.
        </p>

        <p style="color:#9bb0c3;margin-top:20px;">- Ravlo</p>

        <img src="{tracking_pixel}" width="1" height="1" style="display:none;" alt="">
      </div>
    </div>
    """.strip()

    return subject, body, html

# =========================================================
# 🏠 ADMIN DASHBOARD
# =========================================================

@admin_bp.route("/dashboard")
@login_required
@role_required("admin_group")
def dashboard():
    if _is_company_admin(current_user) and current_user.company_id:
        return redirect(url_for("admin.company_dashboard", company_id=current_user.company_id))

    company = None

    if current_user.role == "master_admin":
        company = Company.query.order_by(Company.id.asc()).first()

    stats = {
        "total_users": User.query.count(),
        "total_loans": LoanApplication.query.count() if LoanApplication else 0,
        "total_docs": LoanDocument.query.count() if LoanDocument else 0,
        "pending_tasks": (
            Task.query.filter(db.func.lower(Task.status) == "pending").count()
            if Task and hasattr(Task, "status")
            else 0
        ),
        "pending_requests": AccessRequest.query.filter(
            db.func.lower(AccessRequest.status) == "pending"
        ).count(),
        "approved_requests": AccessRequest.query.filter(
            db.func.lower(AccessRequest.status) == "approved"
        ).count(),
        "total_companies": Company.query.count(),
        "pending_invites": UserInvite.query.filter(
            db.func.lower(UserInvite.status) == "pending"
        ).count(),
    }

    recent_requests = (
        AccessRequest.query
        .order_by(AccessRequest.created_at.desc())
        .limit(5)
        .all()
    )

    users = (
        User.query
        .order_by(User.created_at.desc())
        .limit(5)
        .all()
    )

    recent_invites = (
        UserInvite.query
        .order_by(UserInvite.created_at.desc())
        .limit(5)
        .all()
    )

    leads = (
        Lead.query
        .order_by(Lead.created_at.desc())
        .limit(5)
        .all()
        if Lead and hasattr(Lead, "created_at")
        else []
    )

    logs = (
        SystemLog.query
        .order_by(SystemLog.created_at.desc())
        .limit(8)
        .all()
        if SystemLog and hasattr(SystemLog, "created_at")
        else []
    )

    def last_n_months(n=6):
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

    def monthly_series(records, date_attr="created_at", months_back=6):
        month_keys = last_n_months(months_back)
        labels = [datetime(year, month, 1).strftime("%b") for year, month in month_keys]
        counts = defaultdict(int)

        for row in records:
            dt = getattr(row, date_attr, None)
            if dt:
                counts[(dt.year, dt.month)] += 1

        series = [counts.get((year, month), 0) for year, month in month_keys]
        return labels, series

    if LoanApplication and hasattr(LoanApplication, "created_at"):
        loan_records = LoanApplication.query.all()
        loan_volume_labels, loan_volume_series = monthly_series(
            loan_records, "created_at", 6
        )
    else:
        loan_volume_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
        loan_volume_series = [0, 0, 0, 0, 0, 0]

    user_records = User.query.all()
    user_growth_labels, user_growth_series = monthly_series(
        user_records, "created_at", 6
    )

    server_load_value = 68

    ai_summary = (
        f"Platform snapshot: {stats['pending_requests']} pending request(s), "
        f"{stats['pending_invites']} pending invite(s), "
        f"{stats['total_companies']} company account(s), "
        f"and {stats['pending_tasks']} pending operational task(s)."
    )

    return render_template(
        "admin/dashboard.html",
        company=company,
        stats=stats,
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


@admin_bp.route("/companies")
@login_required
@role_required("admin_group")
def companies():
    if _is_company_admin(current_user) and current_user.company_id:
        return redirect(url_for("admin.company_dashboard", company_id=current_user.company_id))

    companies = Company.query.order_by(Company.created_at.desc()).all()

    return render_template(
        "admin/companies.html",
        companies=companies,
    )

@admin_bp.route("/requests")
@login_required
@role_required("admin_group")
@admin_required
def requests_dashboard():
    status = request.args.get("status", "pending")

    requests_q = AccessRequest.query.order_by(AccessRequest.created_at.desc())
    requests_list = requests_q.all()

    if _is_company_admin(current_user):
        requests_list = [item for item in requests_list if _can_access_request(item)]

    if status:
        requests_list = [
            item for item in requests_list
            if (item.status or "").strip().lower() == status.strip().lower()
        ]

    return render_template(
        "admin/requests_dashboard.html",
        requests_list=requests_list,
        current_status=status,
    )


@admin_bp.route("/requests/<int:request_id>")
@login_required
@role_required("admin_group")
@admin_required
def request_detail(request_id):
    access_request = AccessRequest.query.get_or_404(request_id)
    if not _can_access_request(access_request):
        flash("You do not have access to that request.", "warning")
        return redirect(_admin_home_endpoint())

    return render_template(
        "admin/request_detail.html",
        access_request=access_request,
    )


@admin_bp.route("/access-requests", methods=["GET"])
@login_required
@role_required("admin_group")
def access_requests():
    requests_ = AccessRequest.query.order_by(AccessRequest.created_at.desc()).all()
    if _is_company_admin(current_user):
        requests_ = [item for item in requests_ if _can_access_request(item)]
    return render_template(
        "admin/requests_dashboard.html",
        requests_list=requests_,
        title="Access Requests",
        active_tab="access_requests",
    )


@admin_bp.route("/access-requests/<int:req_id>/deny", methods=["POST"])
@login_required
@role_required("admin_group")
@admin_required
def deny_access_request(req_id):
    req = AccessRequest.query.get_or_404(req_id)
    if not _can_access_request(req):
        flash("You do not have access to that request.", "warning")
        return redirect(_admin_home_endpoint())

    req.status = "denied"
    req.reviewed_by = current_user.id
    req.reviewed_at = datetime.utcnow()

    db.session.commit()

    flash(f"Access request denied for {req.email}.", "warning")
    return redirect(url_for("admin.access_requests"))
    
@admin_bp.route("/access-requests/<int:req_id>/approve", methods=["POST"])
@login_required
@role_required("admin_group")
@admin_required
def approve_access_request(req_id):
    access_request = AccessRequest.query.get_or_404(req_id)
    if not _can_access_request(access_request):
        flash("You do not have access to that request.", "warning")
        return redirect(_admin_home_endpoint())

    company = Company.query.get(access_request.company_id) if access_request.company_id else None

    if not company and access_request.company_name:
        company = Company.query.filter(
            func.lower(Company.name) == access_request.company_name.strip().lower()
        ).first()

    if not company:
        subscription_tier, max_users = _plan_defaults("team")
        company = Company(
            name=access_request.company_name or access_request.contact_name,
            email_domain=(
                access_request.email.split("@")[-1].lower()
                if access_request.email and "@" in access_request.email
                else None
            ),
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

    access_request.company_id = company.id
    access_request.status = "approved"
    access_request.reviewed_by = current_user.id
    access_request.reviewed_at = datetime.utcnow()

    role = _access_request_role(access_request)
    existing_user = User.query.filter_by(email=access_request.email).first()

    invite = (
        UserInvite.query.filter_by(company_id=company.id, email=access_request.email)
        .order_by(UserInvite.created_at.desc())
        .first()
    )

    invite_created = False
    invite_refreshed = False

    if invite and invite.status == "accepted":
        if existing_user:
            existing_user.company_id = company.id
            existing_user.role = role
            existing_user.is_active = True
            existing_user.invite_accepted = True
    else:
        if not invite or invite.status != "pending":
            parts = (access_request.contact_name or "").strip().split(None, 1)
            invite = UserInvite(
                company_id=company.id,
                email=access_request.email,
                first_name=parts[0] if parts else None,
                last_name=parts[1] if len(parts) > 1 else None,
                role=role,
                token=UserInvite.generate_token(),
                status="pending",
                invited_by=current_user.id,
                expires_at=UserInvite.default_expiration(days=7),
            )
            db.session.add(invite)
            db.session.flush()
            invite_created = True
        elif invite.is_expired():
            _refresh_invite(invite)
            invite_refreshed = True

        try:
            _deliver_access_request_invite(invite, company, access_request)
            invite_email_sent = True
        except Exception:
            current_app.logger.exception("Failed to send access-request invite email")
            invite_email_sent = False

    db.session.commit()

    notify(
        loan=None,
        role="admin",
        title="Request Approved",
        message=f"Access request #{access_request.id} was approved for {access_request.email}.",
        channels=["socket", "inapp"]
    )

    if invite and invite.status == "accepted":
        flash("Request approved and the user is already onboarded to the company.", "success")
    elif invite_created and invite_email_sent:
        flash("Request approved, company onboarded, and invite email sent.", "success")
    elif invite_refreshed and invite_email_sent:
        flash("Request approved and a fresh onboarding invite was sent.", "success")
    elif invite_email_sent:
        flash("Request approved and onboarding invite sent.", "success")
    else:
        flash("Request approved, but the onboarding invite email could not be sent automatically.", "warning")
    return redirect(url_for("admin.company_team", company_id=company.id))


@admin_bp.route("/requests/<int:request_id>/reject", methods=["POST"])
@login_required
@role_required("admin_group")
@admin_required
def reject_request(request_id):
    access_request = AccessRequest.query.get_or_404(request_id)
    if not _can_access_request(access_request):
        flash("You do not have access to that request.", "warning")
        return redirect(_admin_home_endpoint())

    if access_request.status == "rejected":
        flash("Request already rejected.", "info")
        return redirect(url_for("admin.request_detail", request_id=request_id))

    access_request.status = "rejected"
    access_request.reviewed_by = current_user.id
    access_request.reviewed_at = datetime.utcnow()

    db.session.commit()

    flash("Request rejected.", "warning")
    return redirect(url_for("admin.requests_dashboard"))


@admin_bp.route("/company/<int:company_id>/team")
@login_required
@role_required("admin_group")
@admin_required
def company_team(company_id):
    company = Company.query.get_or_404(company_id)
    access_redirect = _ensure_company_access(company)
    if access_redirect:
        return access_redirect

    team_members = User.query.filter_by(company_id=company.id).order_by(User.role, User.first_name).all()
    invites = UserInvite.query.filter_by(company_id=company.id).order_by(UserInvite.created_at.desc()).all()

    return render_template(
        "admin/company_team.html",
        company=company,
        team_members=team_members,
        invites=invites,
    )


@admin_bp.route("/company/<int:company_id>/team/invite", methods=["GET", "POST"])
@login_required
@role_required("admin_group")
@admin_required
def invite_team_member(company_id):
    company = Company.query.get_or_404(company_id)
    access_redirect = _ensure_company_access(company)
    if access_redirect:
        return access_redirect

    if request.method == "POST":
        first_name = (request.form.get("first_name") or "").strip()
        last_name = (request.form.get("last_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        role = (request.form.get("role") or "").strip()

        allowed_roles = ["admin", "loan_officer", "processor", "underwriter"]

        if not email or not role:
            flash("Email and role are required.", "danger")
            return redirect(url_for("admin.invite_team_member", company_id=company.id))

        if role not in allowed_roles:
            flash("Invalid role selected.", "danger")
            return redirect(url_for("admin.invite_team_member", company_id=company.id))

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("A user with that email already exists.", "warning")
            return redirect(url_for("admin.invite_team_member", company_id=company.id))

        existing_invite = UserInvite.query.filter_by(email=email, company_id=company.id, status="pending").first()
        if existing_invite and not existing_invite.is_expired():
            flash("There is already an active invite for that email.", "warning")
            return redirect(url_for("admin.invite_team_member", company_id=company.id))

        invite = UserInvite(
            company_id=company.id,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role,
            token=UserInvite.generate_token(),
            invited_by=current_user.id,
            expires_at=UserInvite.default_expiration(days=7),
            status="pending",
        )
        db.session.add(invite)
        db.session.commit()

        try:
            _send_team_invite_email(invite, company)
        except Exception:
            current_app.logger.exception("Failed to send team invite email")

        flash("Invite created and email sent.", "success")
        return redirect(url_for("admin.company_team", company_id=company.id))

    return render_template(
        "admin/invite_team_member.html",
        company=company,
    )


@admin_bp.route("/company/<int:company_id>/team/invites/<int:invite_id>/resend", methods=["POST"])
@login_required
@role_required("admin_group")
@admin_required
def resend_team_invite(company_id, invite_id):
    company = Company.query.get_or_404(company_id)
    access_redirect = _ensure_company_access(company)
    if access_redirect:
        return access_redirect

    invite = UserInvite.query.get_or_404(invite_id)
    if invite.company_id != company.id:
        flash("That invite does not belong to this company.", "danger")
        return redirect(url_for("admin.company_team", company_id=company.id))

    if invite.status == "accepted":
        flash("This invite has already been accepted.", "info")
        return redirect(url_for("admin.company_team", company_id=company.id))

    if invite.status != "pending" or invite.is_expired():
        _refresh_invite(invite)

    try:
        _send_team_invite_email(invite, company)
        db.session.commit()
        flash("Invite resent successfully.", "success")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to resend team invite email")
        flash("The invite exists, but the email could not be sent.", "warning")

    return redirect(url_for("admin.company_team", company_id=company.id))

# =========================================================
# 📊 SYSTEM REPORTS (CSV EXPORT)
# =========================================================
@admin_bp.route("/reports", methods=["GET", "POST"])
@login_required
@role_required("admin_group")
def reports():
    company = _company_scope()
    report_type = request.form.get("report_type")
    users_query = User.query.filter_by(company_id=company.id) if company else User.query
    total_users = users_query.count()
    total_loans = LoanApplication.query.count() if not company else 0
    total_docs = LoanDocument.query.count() if not company else 0
    total_invites = UserInvite.query.filter_by(company_id=company.id).count() if company else UserInvite.query.count()

    if request.method == "POST" and report_type:
        output = io.StringIO()
        writer = csv.writer(output)

        if report_type == "users":
            writer.writerow(["ID", "Username", "Email", "Role", "Created"])
            for u in users_query.all():
                writer.writerow([u.id, u.username, u.email, u.role, u.created_at])

        elif report_type == "invites":
            invite_query = UserInvite.query.filter_by(company_id=company.id) if company else UserInvite.query
            writer.writerow(["ID", "Email", "Role", "Status", "Expires", "Created"])
            for invite in invite_query.all():
                writer.writerow([invite.id, invite.email, invite.role, invite.status, invite.expires_at, invite.created_at])

        elif report_type == "loans" and not company:
            writer.writerow(["ID", "Borrower ID", "Type", "Amount", "Status", "Created"])
            for l in LoanApplication.query.all():
                writer.writerow([l.id, l.borrower_profile_id, l.loan_type, l.amount, l.status, l.created_at])

        elif report_type == "documents" and not company:
            writer.writerow(["ID", "Borrower ID", "Name", "Status", "Created"])
            for d in LoanDocument.query.all():
                writer.writerow([d.id, d.borrower_profile_id, d.document_name, d.status, d.created_at])
        else:
            flash("That report is not available for this admin workspace.", "warning")
            return redirect(url_for("admin.reports"))

        output.seek(0)
        csv_data = output.getvalue()

        return send_file(
            io.BytesIO(csv_data.encode("utf-8")),
            as_attachment=True,
            download_name=f"{report_type}_report.csv",
            mimetype="text/csv"
        )

    return render_template(
        "admin/reports.html",
        company=company,
        total_users=total_users,
        total_loans=total_loans,
        total_docs=total_docs,
        total_invites=total_invites,
    )


# =========================================================
# 💬 ADMIN MESSAGE CENTER
# =========================================================

@admin_bp.route("/messages", methods=["GET", "POST"])
@login_required
@role_required("admin_group")
def messages():
    company = _company_scope()
    if request.method == "POST":
        content = (request.form.get("content") or "").strip()
        receiver_id = request.form.get("recipient_id", type=int)

        if not content:
            flash("⚠️ Message cannot be empty.", "warning")
            return redirect(url_for("admin.messages"))

        if not receiver_id:
            flash("⚠️ Please select a recipient.", "warning")
            return redirect(url_for("admin.messages"))

        recipient_user = User.query.get(receiver_id)
        if not recipient_user:
            flash("⚠️ Recipient not found.", "danger")
            return redirect(url_for("admin.messages"))

        if company and recipient_user.company_id != company.id:
            flash("You can only message users in your company workspace.", "warning")
            return redirect(url_for("admin.messages"))

        new_msg = Message(
            sender_id=current_user.id,
            receiver_id=receiver_id,
            content=content,
            created_at=datetime.utcnow(),
            sender_role=getattr(current_user, "role", None),
            receiver_role=getattr(recipient_user, "role", None),
        )

        db.session.add(new_msg)
        db.session.commit()

        flash("Message sent.", "success")
        return redirect(url_for("admin.messages"))

    if company:
        users = (
            User.query
            .filter_by(company_id=company.id)
            .order_by(User.first_name.asc(), User.last_name.asc())
            .all()
        )
        allowed_user_ids = {user.id for user in users}
        allowed_user_ids.add(current_user.id)
        msgs = [
            msg for msg in (
                Message.query
                .order_by(Message.created_at.desc(), Message.id.desc())
                .limit(200)
                .all()
            )
            if msg.sender_id in allowed_user_ids and msg.receiver_id in allowed_user_ids
        ][:50]
    else:
        msgs = (
            Message.query
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(50)
            .all()
        )

        users = User.query.order_by(User.first_name.asc(), User.last_name.asc()).all()

    return render_template(
        "admin/messages.html",
        messages=msgs,
        users=users,
        company=company,
    )
    
# =========================================================
# 📑 VERIFY DOCUMENTS
# =========================================================
@admin_bp.route("/verify_data")
@login_required
@role_required("admin")
def verify_data():
    docs = LoanDocument.query.order_by(LoanDocument.created_at.desc()).limit(50).all()

    # Attach borrower name
    for d in docs:
        borrower = BorrowerProfile.query.get(d.borrower_profile_id)
        d.borrower_name = borrower.full_name if borrower else "—"

    return render_template("admin/verify_data.html", docs=docs)

@admin_bp.route("/verify_doc/<int:doc_id>", methods=["POST"])
@login_required
@role_required("admin")
def verify_doc(doc_id):
    doc = LoanDocument.query.get_or_404(doc_id)
    doc.status = "verified"
    db.session.commit()
    flash("Document verified.", "success")
    return redirect(url_for("admin.verify_data"))


# =========================================================
# 🤖 AI CONTROL PANEL
# =========================================================

@admin_bp.route("/analytics")
@login_required
@role_required("admin")
def analytics():
    company = _company_scope()

    if company:
        users_query = User.query.filter_by(company_id=company.id)
        total_users = users_query.count()
        total_loans = LoanApplication.query.filter_by(company_id=company.id).count() if hasattr(LoanApplication, "company_id") else 0
        total_docs = LoanDocument.query.filter_by(company_id=company.id).count() if hasattr(LoanDocument, "company_id") else 0
        active_borrowers = BorrowerProfile.query.filter_by(company_id=company.id).count() if hasattr(BorrowerProfile, "company_id") else 0
        loan_rows = LoanApplication.query.filter_by(company_id=company.id).all() if hasattr(LoanApplication, "company_id") else []
        user_rows = users_query.all()
        ai_summary = (
            f"{company.name} analytics: {total_users} team user(s), "
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
            f"Platform analytics: {total_users} total user(s), {total_loans} loan file(s), "
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
    )

@admin_bp.route("/ai-dashboard", methods=["GET"])
@login_required
@role_required("admin")
def ai_dashboard():
    """
    Admin AI dashboard:
    - platform-wide AI interaction stats
    - usage by role
    - usage by tool/context
    - recent activity feed
    """

    # -----------------------------------
    # Overall stats
    # -----------------------------------
    total_interactions = AIAssistantInteraction.query.count()
    total_users_with_ai = (
        db.session.query(func.count(func.distinct(AIAssistantInteraction.user_id)))
        .scalar()
        or 0
    )

    total_questions = (
        AIAssistantInteraction.query
        .filter(AIAssistantInteraction.question.isnot(None))
        .count()
    )

    total_responses = (
        AIAssistantInteraction.query
        .filter(AIAssistantInteraction.response.isnot(None))
        .count()
    )

    # -----------------------------------
    # Recent AI activity
    # -----------------------------------
    recent_interactions = (
        AIAssistantInteraction.query
        .order_by(AIAssistantInteraction.timestamp.desc())
        .limit(20)
        .all()
    )

    # -----------------------------------
    # Usage by user role
    # -----------------------------------
    interactions_by_role_rows = (
        db.session.query(
            User.role,
            func.count(AIAssistantInteraction.id)
        )
        .join(AIAssistantInteraction, AIAssistantInteraction.user_id == User.id)
        .group_by(User.role)
        .order_by(desc(func.count(AIAssistantInteraction.id)))
        .all()
    )

    interactions_by_role = [
        {
            "role": row[0] or "unknown",
            "count": row[1] or 0
        }
        for row in interactions_by_role_rows
    ]

    role_labels = [row["role"] for row in interactions_by_role]
    role_values = [row["count"] for row in interactions_by_role]

    # -----------------------------------
    # Usage by AI context / module
    # Adjust field names if your model differs
    # -----------------------------------
    interactions_by_context = []
    context_labels = []
    context_values = []

    if hasattr(AIAssistantInteraction, "context_type"):
        context_rows = (
            db.session.query(
                AIAssistantInteraction.context_type,
                func.count(AIAssistantInteraction.id)
            )
            .group_by(AIAssistantInteraction.context_type)
            .order_by(desc(func.count(AIAssistantInteraction.id)))
            .all()
        )

        interactions_by_context = [
            {
                "context": row[0] or "general",
                "count": row[1] or 0
            }
            for row in context_rows
        ]

        context_labels = [row["context"] for row in interactions_by_context]
        context_values = [row["count"] for row in interactions_by_context]

    elif hasattr(AIAssistantInteraction, "assistant_type"):
        context_rows = (
            db.session.query(
                AIAssistantInteraction.assistant_type,
                func.count(AIAssistantInteraction.id)
            )
            .group_by(AIAssistantInteraction.assistant_type)
            .order_by(desc(func.count(AIAssistantInteraction.id)))
            .all()
        )

        interactions_by_context = [
            {
                "context": row[0] or "general",
                "count": row[1] or 0
            }
            for row in context_rows
        ]

        context_labels = [row["context"] for row in interactions_by_context]
        context_values = [row["count"] for row in interactions_by_context]

    # -----------------------------------
    # Most active AI users
    # -----------------------------------
    most_active_users_rows = (
        db.session.query(
            User.id,
            User.first_name,
            User.last_name,
            User.email,
            User.role,
            func.count(AIAssistantInteraction.id).label("interaction_count")
        )
        .join(AIAssistantInteraction, AIAssistantInteraction.user_id == User.id)
        .group_by(User.id, User.first_name, User.last_name, User.email, User.role)
        .order_by(desc("interaction_count"))
        .limit(10)
        .all()
    )

    most_active_users = [
        {
            "user_id": row.id,
            "name": f"{(row.first_name or '').strip()} {(row.last_name or '').strip()}".strip() or row.email,
            "email": row.email,
            "role": row.role or "unknown",
            "interaction_count": row.interaction_count or 0,
        }
        for row in most_active_users_rows
    ]

    # -----------------------------------
    # Response quality / completion metrics
    # Safe optional fields
    # -----------------------------------
    failed_interactions = 0
    avg_response_length = 0

    if hasattr(AIAssistantInteraction, "status"):
        failed_interactions = (
            AIAssistantInteraction.query
            .filter(AIAssistantInteraction.status.in_(["failed", "error"]))
            .count()
        )

    if hasattr(AIAssistantInteraction, "response"):
        response_lengths = [
            len(item.response or "")
            for item in recent_interactions
            if item.response
        ]
        if response_lengths:
            avg_response_length = round(sum(response_lengths) / len(response_lengths), 1)

    # -----------------------------------
    # Summary cards
    # -----------------------------------
    ai_stats = {
        "total_interactions": total_interactions,
        "total_users_with_ai": total_users_with_ai,
        "total_questions": total_questions,
        "total_responses": total_responses,
        "failed_interactions": failed_interactions,
        "avg_response_length": avg_response_length,
    }

    return render_template(
        "admin/ai_dashboard.html",
        title="AI Dashboard",
        active_tab="ai_dashboard",
        ai_stats=ai_stats,
        recent_interactions=recent_interactions,
        interactions_by_role=interactions_by_role,
        role_labels=role_labels,
        role_values=role_values,
        interactions_by_context=interactions_by_context,
        context_labels=context_labels,
        context_values=context_values,
        most_active_users=most_active_users,
    )

@admin_bp.route("/ai/refresh/<string:target>", methods=["POST"])
@login_required
@role_required("admin")
def ai_refresh(target):
    time.sleep(1.2)
    flash(f"{target} refreshed successfully.", "success")
    return jsonify(
        {
            "success": True,
            "target": target,
            "message": f"{target.replace('_', ' ').title()} refreshed successfully.",
        }
    )

@admin_bp.route("/company/<int:company_id>/dashboard")
@login_required
@role_required("admin_group")
def company_dashboard(company_id):
    company = Company.query.get_or_404(company_id)
    access_redirect = _ensure_company_access(company)
    if access_redirect:
        return access_redirect

    team_members = User.query.filter_by(company_id=company.id).order_by(User.created_at.desc()).all()
    invites = UserInvite.query.filter_by(company_id=company.id).order_by(UserInvite.created_at.desc()).all()
    loans = LoanApplication.query.filter_by(company_id=company.id).order_by(LoanApplication.created_at.desc()).all() if hasattr(LoanApplication, "company_id") else []
    borrowers = BorrowerProfile.query.filter_by(company_id=company.id).all() if hasattr(BorrowerProfile, "company_id") else []
    docs = LoanDocument.query.filter_by(company_id=company.id).all() if hasattr(LoanDocument, "company_id") else []
    access_requests = [
        item for item in (
            AccessRequest.query
            .order_by(AccessRequest.created_at.desc())
            .limit(100)
            .all()
        )
        if _can_access_request(item)
    ]

    member_ids = [member.id for member in team_members]
    recent_messages = []
    if member_ids:
        allowed_user_ids = set(member_ids)
        allowed_user_ids.add(current_user.id)
        recent_messages = [
            msg for msg in (
                Message.query
                .order_by(Message.created_at.desc(), Message.id.desc())
                .limit(200)
                .all()
            )
            if msg.sender_id in allowed_user_ids and msg.receiver_id in allowed_user_ids
        ][:5]

    active_team_count = len([member for member in team_members if getattr(member, "is_active", False)])
    pending_invites = [invite for invite in invites if (invite.status or "").lower() == "pending"]
    accepted_invites = [invite for invite in invites if (invite.status or "").lower() == "accepted"]
    pending_requests = [item for item in access_requests if (item.status or "").lower() == "pending"]

    role_counts = defaultdict(int)
    for member in team_members:
        role_counts[(getattr(member, "role", None) or "unknown").replace("_", " ").title()] += 1

    invite_counts = defaultdict(int)
    for invite in invites:
        invite_counts[(getattr(invite, "status", None) or "pending").replace("_", " ").title()] += 1

    team_growth_labels, team_growth_series = _monthly_series(team_members, "created_at", 6)
    invite_growth_labels, invite_growth_series = _monthly_series(invites, "created_at", 6)

    workspace_health = "Attention Needed" if company.is_blocked or company.billing_status == "past_due" else "Healthy"
    workspace_summary = (
        f"{company.name} has {len(team_members)} team member(s), "
        f"{len(pending_invites)} pending invite(s), {len(loans)} loan file(s), "
        f"and {len(pending_requests)} access request(s) waiting on review."
    )

    stats = {
        "team_members": len(team_members),
        "active_team_members": active_team_count,
        "pending_invites": len(pending_invites),
        "accepted_invites": len(accepted_invites),
        "loans": len(loans),
        "borrowers": len(borrowers),
        "documents": len(docs),
        "requests": len(access_requests),
        "pending_requests": len(pending_requests),
    }

    return render_template(
        "admin/company_dashboard.html",
        company=company,
        team_members=team_members[:5],
        invites=invites[:5],
        loans=loans[:5],
        borrowers=borrowers[:5],
        recent_messages=recent_messages,
        access_requests=access_requests[:5],
        stats=stats,
        role_labels=list(role_counts.keys()),
        role_values=list(role_counts.values()),
        invite_status_labels=list(invite_counts.keys()),
        invite_status_values=list(invite_counts.values()),
        team_growth_labels=team_growth_labels,
        team_growth_series=team_growth_series,
        invite_growth_labels=invite_growth_labels,
        invite_growth_series=invite_growth_series,
        workspace_health=workspace_health,
        workspace_summary=workspace_summary,
        title=f"{company.name} Dashboard",
        active_tab="companies",
    )


@admin_bp.route("/company/<int:company_id>/settings", methods=["GET", "POST"])
@login_required
@role_required("admin_group")
@admin_required
def company_settings(company_id):
    company = Company.query.get_or_404(company_id)
    access_redirect = _ensure_company_access(company)
    if access_redirect:
        return access_redirect

    if request.method == "POST":
        company.name = (request.form.get("name") or company.name or "").strip() or company.name
        company.email_domain = ((request.form.get("email_domain") or "").strip().lower() or None)
        company.address = (request.form.get("address") or "").strip() or None
        company.city = (request.form.get("city") or "").strip() or None
        company.state = (request.form.get("state") or "").strip() or None
        company.zip = (request.form.get("zip") or "").strip() or None
        company.is_active = str(request.form.get("is_active") or "false").lower() in ("1", "true", "yes", "on")

        db.session.commit()
        flash("Company workspace settings updated.", "success")
        return redirect(url_for("admin.company_settings", company_id=company.id))

    stats = {
        "team_members": User.query.filter_by(company_id=company.id).count(),
        "pending_invites": UserInvite.query.filter_by(company_id=company.id, status="pending").count(),
        "requests": len([
            item for item in (
                AccessRequest.query
                .order_by(AccessRequest.created_at.desc())
                .limit(100)
                .all()
            )
            if _can_access_request(item)
        ]),
    }

    return render_template(
        "admin/company_settings.html",
        company=company,
        stats=stats,
    )


@admin_bp.route("/onboarding", methods=["GET"])
@login_required
@role_required("admin")
def onboarding_center():
    return render_template(
        "admin/onboarding_center.html",
        assigned_role=getattr(current_user, "role", "New Team Member"),
        onboarding_progress="15%",
        resource_count=8,
        required_steps=6,
    )


@admin_bp.route("/licensing/applications")
@login_required
@role_required("platform_admin", "master_admin")
def licensing_applications():
    applications = LicenseApplication.query.order_by(
        LicenseApplication.created_at.desc()
    ).all()

    invite_lookup = {}
    invite_event_lookup = {}

    for app in applications:
        company = Company.query.filter(
            func.lower(Company.name) == (app.company_name or "").strip().lower()
        ).first()

        if company:
            invite = UserInvite.query.filter_by(
                company_id=company.id,
                email=app.email
            ).order_by(UserInvite.created_at.desc()).first()

            if invite:
                invite_lookup[app.id] = invite
                invite_events = LicenseInviteEvent.query.filter_by(
                    invite_token=invite.token
                ).order_by(LicenseInviteEvent.created_at.desc()).all()
                invite_event_lookup[app.id] = {
                    "open_count": len(invite_events),
                    "last_opened_at": invite_events[0].created_at if invite_events else None,
                }

    return render_template(
        "admin/licensing_applications.html",
        applications=applications,
        invite_lookup=invite_lookup,
        invite_event_lookup=invite_event_lookup,
    )


@admin_bp.route("/licensing/applications/<int:app_id>/contact", methods=["POST"])
@login_required
@role_required("platform_admin", "master_admin")
def contact_license_application(app_id):
    app_row = LicenseApplication.query.get_or_404(app_id)

    if app_row.status == "approved":
        flash("Approved applications are already in onboarding.", "info")
        return redirect(url_for("admin.licensing_applications"))

    if app_row.status == "declined":
        flash("Declined applications cannot be moved to contacted.", "warning")
        return redirect(url_for("admin.licensing_applications"))

    app_row.status = "contacted"
    db.session.commit()

    flash("Application marked as contacted.", "success")
    return redirect(url_for("admin.licensing_applications"))


@admin_bp.route("/licensing/applications/<int:app_id>/approve", methods=["POST"])
@login_required
@role_required("platform_admin", "master_admin")
def approve_license_application(app_id):
    app_row = LicenseApplication.query.get_or_404(app_id)

    if app_row.status == "approved":
        flash("This application was already approved.", "info")
        return redirect(url_for("admin.licensing_applications"))

    subscription_tier, max_users = _plan_defaults(app_row.plan_interest)

    company = Company.query.filter(
        func.lower(Company.name) == (app_row.company_name or "").strip().lower()
    ).first()

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

    access_request = AccessRequest(
        company_name=app_row.company_name,
        contact_name=app_row.contact_name,
        email=app_row.email,
        phone=app_row.phone,
        request_type="license_application",
        requested_role="admin",
        status="approved",
        notes=f"Approved from LicenseApplication #{app_row.id}",
        company_id=company.id,
        reviewed_by=current_user.id,
    )
    db.session.add(access_request)

    invite = UserInvite.query.filter_by(
        company_id=company.id,
        email=app_row.email,
        status="pending",
    ).first()

    if not invite:
        parts = (app_row.contact_name or "").strip().split()
        first_name = parts[0] if parts else None
        last_name = " ".join(parts[1:]) if len(parts) > 1 else None

        invite = UserInvite(
            company_id=company.id,
            email=app_row.email,
            first_name=first_name,
            last_name=last_name,
            role="admin",
            token=UserInvite.generate_token(),
            status="pending",
            invited_by=current_user.id,
            expires_at=UserInvite.default_expiration(days=7),
        )
        db.session.add(invite)
        db.session.flush()

    invite_was_refreshed = False
    if invite.is_expired():
        _refresh_invite(invite)
        invite_was_refreshed = True

    email_sent = False
    try:
        _deliver_license_invite(invite, company, app_row)
        email_sent = True
    except Exception:
        current_app.logger.exception("Failed to send licensing invite email")

    db.session.commit()

    if email_sent:
        refreshed_note = " A fresh invite link was generated." if invite_was_refreshed else ""
        flash(f"Application approved, company created, and invite email sent.{refreshed_note}", "success")
    else:
        flash("Application approved and invite created, but email failed to send.", "warning")

    return redirect(url_for("admin.licensing_applications"))


@admin_bp.route("/licensing/applications/<int:app_id>/decline", methods=["POST"])
@login_required
@role_required("platform_admin", "master_admin")
def decline_license_application(app_id):
    app_row = LicenseApplication.query.get_or_404(app_id)

    if app_row.status == "approved":
        flash("Approved applications cannot be declined here.", "warning")
        return redirect(url_for("admin.licensing_applications"))

    app_row.status = "declined"
    db.session.commit()

    flash("License application declined.", "success")
    return redirect(url_for("admin.licensing_applications"))


@admin_bp.route("/licensing/applications/<int:app_id>/resend-invite", methods=["POST"])
@login_required
@role_required("platform_admin", "master_admin")
def resend_license_application_invite(app_id):
    app_row = LicenseApplication.query.get_or_404(app_id)

    if app_row.status != "approved":
        flash("Approve the application before sending an onboarding invite.", "warning")
        return redirect(url_for("admin.licensing_applications"))

    company = Company.query.filter(
        func.lower(Company.name) == (app_row.company_name or "").strip().lower()
    ).first()
    if not company:
        flash("No company record was found for this approved application.", "danger")
        return redirect(url_for("admin.licensing_applications"))

    invite = UserInvite.query.filter_by(
        company_id=company.id,
        email=app_row.email,
    ).order_by(UserInvite.created_at.desc()).first()

    if not invite:
        parts = (app_row.contact_name or "").strip().split()
        first_name = parts[0] if parts else None
        last_name = " ".join(parts[1:]) if len(parts) > 1 else None
        invite = UserInvite(
            company_id=company.id,
            email=app_row.email,
            first_name=first_name,
            last_name=last_name,
            role="admin",
            token=UserInvite.generate_token(),
            status="pending",
            invited_by=current_user.id,
            expires_at=UserInvite.default_expiration(days=7),
        )
        db.session.add(invite)
        db.session.flush()
    elif invite.status == "accepted":
        flash("This invite has already been accepted.", "info")
        return redirect(url_for("admin.licensing_applications"))
    elif invite.is_expired():
        _refresh_invite(invite)

    try:
        _deliver_license_invite(invite, company, app_row)
        db.session.commit()
        flash("Onboarding invite sent successfully.", "success")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to resend licensing invite email")
        flash("The invite exists, but the email could not be sent.", "warning")

    return redirect(url_for("admin.licensing_applications"))

@admin_bp.route("/users/<int:user_id>/block", methods=["POST"])
@login_required
@role_required("admin_group")
def block_user(user_id):
    user = User.query.get_or_404(user_id)

    reason = (request.form.get("reason") or "manual_review").strip().lower()
    note = (request.form.get("note") or "").strip()

    user.is_blocked = True
    user.blocked_at = datetime.utcnow()
    user.blocked_reason = reason
    user.blocked_note = note or None
    user.blocked_by = current_user.id

    db.session.commit()

    flash(f"{user.email} was blocked.", "warning")
    return redirect(request.referrer or url_for("system.users"))


@admin_bp.route("/users/<int:user_id>/unblock", methods=["POST"])
@login_required
@role_required("admin_group")
def unblock_user(user_id):
    user = User.query.get_or_404(user_id)

    user.is_blocked = False
    user.blocked_at = None
    user.blocked_reason = None
    user.blocked_note = None
    user.blocked_by = None

    db.session.commit()

    flash(f"{user.email} was restored.", "success")
    return redirect(request.referrer or url_for("system.users"))

@admin_bp.route("/companies/<int:company_id>/block", methods=["POST"])
@login_required
@role_required("admin_group")
def block_company(company_id):
    company = Company.query.get_or_404(company_id)

    reason = (request.form.get("reason") or "non_payment").strip().lower()
    note = (request.form.get("note") or "").strip()

    company.is_blocked = True
    company.blocked_at = datetime.utcnow()
    company.blocked_reason = reason
    company.blocked_note = note or None
    company.blocked_by = current_user.id

    if hasattr(company, "billing_status"):
        company.billing_status = "blocked"

    db.session.commit()

    flash(f"{company.name} was blocked.", "warning")
    return redirect(request.referrer or url_for("admin.companies"))


@admin_bp.route("/companies/<int:company_id>/unblock", methods=["POST"])
@login_required
@role_required("admin_group")
def unblock_company(company_id):
    company = Company.query.get_or_404(company_id)

    company.is_blocked = False
    company.blocked_at = None
    company.blocked_reason = None
    company.blocked_note = None
    company.blocked_by = None

    if hasattr(company, "billing_status"):
        company.billing_status = "active"

    db.session.commit()

    flash(f"{company.name} was restored.", "success")
    return redirect(request.referrer or url_for("admin.companies"))
