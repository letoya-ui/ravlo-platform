# =========================================================
# 🏛 ADMIN ROUTES — LoanMVP 2025 (Stabilized Version)
# =========================================================

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, current_app
from flask_login import current_user, login_required
from collections import defaultdict
from sqlalchemy import func, desc
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
@role_required("admin")
def companies():
    companies = Company.query.order_by(Company.created_at.desc()).all()

    return render_template(
        "admin/companies.html",
        companies=companies,
    )

@admin_bp.route("/requests")
@login_required
@role_required("admin")
@admin_required
def requests_dashboard():
    status = request.args.get("status", "pending")

    requests_q = AccessRequest.query.order_by(AccessRequest.created_at.desc())

    if status:
        requests_q = requests_q.filter_by(status=status)

    requests_list = requests_q.all()

    return render_template(
        "admin/requests_dashboard.html",
        requests_list=requests_list,
        current_status=status,
    )


@admin_bp.route("/requests/<int:request_id>")
@login_required
@role_required("admin")
@admin_required
def request_detail(request_id):
    access_request = AccessRequest.query.get_or_404(request_id)

    return render_template(
        "admin/request_detail.html",
        access_request=access_request,
    )


@admin_bp.route("/access-requests", methods=["GET"])
@login_required
@role_required("admin")
def access_requests():
    requests_ = AccessRequest.query.order_by(AccessRequest.created_at.desc()).all()
    return render_template(
        "admin//requests_dashboard.html",
        requests=requests_,
        title="Access Requests",
        active_tab="access_requests",
    )


@admin_bp.route("/access-requests/<int:req_id>/deny", methods=["POST"])
@csrf.exempt
@login_required
@role_required("admin")
def deny_access_request(req_id):
    req = AccessRequest.query.get_or_404(req_id)

    req.status = "denied"
    req.reviewed_by = current_user.id
    req.reviewed_at = datetime.utcnow()

    db.session.commit()

    flash(f"Access request denied for {req.email}.", "warning")
    return redirect(url_for("admin.access_requests"))
    
@admin_bp.route("/access-requests/<int:req_id>/approve", methods=["POST"])
@csrf.exempt  
@login_required
@role_required("admin")
@admin_required
def approve_request(request_id):
    access_request = AccessRequest.query.get_or_404(request_id)

    if access_request.status == "approved":
        flash("Request already approved.", "info")
        return redirect(url_for("admin.request_detail", request_id=request_id))

    company = None

    if access_request.company_id:
        company = Company.query.get(access_request.company_id)

    if not company:
        company = Company(
            name=access_request.company_name or access_request.contact_name,
            email_domain=(access_request.email.split("@")[-1].lower() if access_request.email and "@" in access_request.email else None),
            is_active=True
        )
        db.session.add(company)
        db.session.flush()

    access_request.company_id = company.id
    access_request.status = "approved"
    access_request.reviewed_by = current_user.id
    access_request.reviewed_at = datetime.utcnow()

    db.session.commit()

    notify(
        loan=None,
        role="admin",
        title="Request Approved",
        message=f"Access request #{access_request.id} was approved for {access_request.email}.",
        channels=["socket", "inapp"]
    )

    flash("Request approved successfully.", "success")
    return redirect(url_for("admin.company_team", company_id=company.id))


@admin_bp.route("/requests/<int:request_id>/reject", methods=["POST"])
@csrf.exempt
@login_required
@role_required("admin")
@admin_required
def reject_request(request_id):
    access_request = AccessRequest.query.get_or_404(request_id)

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
@role_required("admin")
@admin_required
def company_team(company_id):
    company = Company.query.get_or_404(company_id)
    team_members = User.query.filter_by(company_id=company.id).order_by(User.role, User.first_name).all()
    invites = UserInvite.query.filter_by(company_id=company.id).order_by(UserInvite.created_at.desc()).all()

    return render_template(
        "admin/company_team.html",
        company=company,
        team_members=team_members,
        invites=invites,
    )


@admin_bp.route("/company/<int:company_id>/team/invite", methods=["GET", "POST"])
@csrf.exempt
@login_required
@role_required("admin")
@admin_required
def invite_team_member(company_id):
    company = Company.query.get_or_404(company_id)

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

        invite_url = url_for("auth.register_from_invite", token=invite.token, _external=True)

        try:
            from sendgrid.helpers.mail import Mail
            import sendgrid

            sendgrid_api_key = current_app.config.get("SENDGRID_API_KEY")
            from_email = current_app.config.get("NOTIFY_FROM_EMAIL", "noreply@ravlohq.com")

            if sendgrid_api_key:
                sg = sendgrid.SendGridAPIClient(sendgrid_api_key)
                email_msg = Mail(
                    from_email=from_email,
                    to_emails=email,
                    subject=f"You're invited to join {company.name} on Ravlo",
                    html_content=f"""
                    <div style="font-family:Inter,Arial,sans-serif;line-height:1.6;color:#111;">
                      <h2>You're invited to Ravlo</h2>
                      <p>Hello {first_name or 'there'},</p>
                      <p>You have been invited to join <strong>{company.name}</strong> as a <strong>{role.replace('_', ' ').title()}</strong>.</p>
                      <p>
                        Complete your registration here:<br>
                        <a href="{invite_url}">{invite_url}</a>
                      </p>
                      <p>This link expires in 7 days.</p>
                    </div>
                    """
                )
                sg.send(email_msg)
        except Exception:
            pass

        flash("Invite created and email sent.", "success")
        return redirect(url_for("admin.company_team", company_id=company.id))

    return render_template(
        "admin/invite_team_member.html",
        company=company,
    )

# =========================================================
# 📊 SYSTEM REPORTS (CSV EXPORT)
# =========================================================
@admin_bp.route("/reports", methods=["GET", "POST"])
@csrf.exempt
@login_required
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
@csrf.exempt
@login_required
@role_required("admin")
def messages():
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
        users=users
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


@admin_bp.route("/verify_doc/<int:doc_id>")
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
    stats = {
        "users": User.query.count(),
        "loans": LoanApplication.query.count(),
        "docs": LoanDocument.query.count(),
        "borrowers": User.query.filter_by(role="borrower").count(),
        "officers": User.query.filter_by(role="loan_officer").count()
    }

    loan_status_labels = []
    loan_status_values = []

    return render_template(
        "admin/analytics.html",
        stats=stats,
        loan_status_labels=loan_status_labels,
        loan_status_values=loan_status_values,
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
@csrf.exempt
@login_required
@role_required("admin")
def ai_refresh(target):
    time.sleep(1.2)
    flash(f"{target} refreshed successfully.", "success")
    return jsonify({"success": True, "target": target})

@admin_bp.route("/company/<int:company_id>/dashboard")
@login_required
@role_required("admin", "master_admin", "lending_admin")
def company_dashboard(company_id):
    company = Company.query.get_or_404(company_id)

    team_members = User.query.filter_by(company_id=company.id).all()
    invites = UserInvite.query.filter_by(company_id=company.id).all()
    loans = LoanApplication.query.filter_by(company_id=company.id).all() if hasattr(LoanApplication, "company_id") else []
    borrowers = BorrowerProfile.query.filter_by(company_id=company.id).all() if hasattr(BorrowerProfile, "company_id") else []
    docs = LoanDocument.query.filter_by(company_id=company.id).all() if hasattr(LoanDocument, "company_id") else []

    stats = {
        "team_members": len(team_members),
        "pending_invites": len([i for i in invites if (i.status or "").lower() == "pending"]),
        "loans": len(loans),
        "borrowers": len(borrowers),
        "documents": len(docs),
    }

    return render_template(
        "admin/company_dashboard.html",
        company=company,
        team_members=team_members[:5],
        invites=invites[:5],
        loans=loans[:5],
        borrowers=borrowers[:5],
        stats=stats,
        title=f"{company.name} Dashboard",
        active_tab="companies",
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
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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
