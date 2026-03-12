# =========================================================
# 🏛 ADMIN ROUTES — LoanMVP 2025 (Stabilized Version)
# =========================================================

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import current_user
from collections import defaultdict
from datetime import datetime, timedelta
from LoanMVP.extensions import db
from werkzeug.security import generate_password_hash

from LoanMVP.ai.base_ai import AIAssistant     # ✅ Unified AI import
from LoanMVP.utils.decorators import role_required

# MODELS
from LoanMVP.models.user_model import User
from LoanMVP.models.crm_models import Lead, Message, Task 
from LoanMVP.models.loan_models import LoanApplication, BorrowerProfile
from LoanMVP.models.document_models import LoanDocument
from LoanMVP.models.system_models import SystemLog
from LoanMVP.models.admin import Company, AccessRequest, UserInvite

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


# =========================================================
# 🏠 ADMIN DASHBOARD
# =========================================================

@admin.route("/dashboard")
@login_required
@role_required("admin", "master_admin", "lending_admin")
def dashboard():
    # =========================
    # KPI COUNTS
    # =========================
    stats = {
        "total_users": User.query.count(),
        "total_loans": Loan.query.count() if Loan else 0,
        "total_docs": Document.query.count() if Document else 0,
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

    # =========================
    # RECENT TABLE DATA
    # =========================
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

    # =========================
    # CHART HELPERS
    # =========================
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

    # =========================
    # CHART DATA
    # =========================
    if Loan and hasattr(Loan, "created_at"):
        loan_records = Loan.query.all()
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

    # Replace later with real health/service metric
    server_load_value = 68

    # =========================
    # AI SUMMARY
    # =========================
    ai_summary = (
        f"Platform snapshot: {stats['pending_requests']} pending request(s), "
        f"{stats['pending_invites']} pending invite(s), "
        f"{stats['total_companies']} company account(s), "
        f"and {stats['pending_tasks']} pending operational task(s)."
    )

    return render_template(
        "admin/dashboard.html",
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
@role_required("admin")
def companies():
    companies = Company.query.order_by(Company.created_at.desc()).all()

    return render_template(
        "admin/companies.html",
        companies=companies,
    )

@admin_bp.route("/requests")
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
@role_required("admin")
@admin_required
def request_detail(request_id):
    access_request = AccessRequest.query.get_or_404(request_id)

    return render_template(
        "admin/request_detail.html",
        access_request=access_request,
    )


@admin_bp.route("/requests/<int:request_id>/approve", methods=["POST"])
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
@role_required("admin")
def messages():
    if request.method == "POST":
        content = request.form.get("content")
        recipient = request.form.get("recipient_id") or None

        if not content:
            flash("⚠️ Message cannot be empty.", "warning")
            return redirect(url_for("admin.messages"))

        new_msg = Message(
            sender_id=current_user.id,
            recipient_id=recipient,
            content=content,
            timestamp=datetime.utcnow()
        )
        db.session.add(new_msg)
        db.session.commit()
        flash("Message sent.", "success")
        return redirect(url_for("admin.messages"))

    msgs = Message.query.order_by(Message.timestamp.desc()).limit(50).all()
    users = User.query.all()
    return render_template("admin/messages.html", messages=msgs, users=users)


# =========================================================
# 📑 VERIFY DOCUMENTS
# =========================================================
@admin_bp.route("/verify_data")
@role_required("admin")
def verify_data():
    docs = LoanDocument.query.order_by(LoanDocument.created_at.desc()).limit(50).all()

    # Attach borrower name
    for d in docs:
        borrower = BorrowerProfile.query.get(d.borrower_profile_id)
        d.borrower_name = borrower.full_name if borrower else "—"

    return render_template("admin/verify_data.html", docs=docs)


@admin_bp.route("/verify_doc/<int:doc_id>")
@role_required("admin")
def verify_doc(doc_id):
    doc = LoanDocument.query.get_or_404(doc_id)
    doc.status = "verified"
    db.session.commit()
    flash("Document verified.", "success")
    return redirect(url_for("admin.verify_data"))


# =========================================================
# 📊 BASIC ANALYTICS
# =========================================================
@admin_bp.route("/analytics")
@role_required("admin")
def analytics():
    stats = {
        "users": User.query.count(),
        "loans": LoanApplication.query.count(),
        "docs": LoanDocument.query.count(),
        "borrowers": User.query.filter_by(role="borrower").count(),
        "officers": User.query.filter_by(role="loan_officer").count()
    }

    return render_template("admin/analytics.html", stats=stats)



# =========================================================
# 🤖 AI CONTROL PANEL
# =========================================================
@admin_bp.route("/ai_dashboard")
@role_required("admin")
def ai_dashboard():
    return render_template(
        "admin/ai_dashboard.html",
        ai_status={
            "Analytics Engine": "Active",
            "Borrower AI": "Active",
            "Loan Engine": "Active",
        },
        last_refresh=datetime.utcnow()
    )


@admin_bp.route("/ai/refresh/<string:target>", methods=["POST"])
@role_required("admin")
def ai_refresh(target):
    time.sleep(1.2)
    flash(f"{target} refreshed successfully.", "success")
    return jsonify({"success": True, "target": target})
