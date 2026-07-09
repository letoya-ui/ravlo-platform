# =========================================================
# 🏛 ADMIN ROUTES — LoanMVP 2025 (Stabilized Version)
# =========================================================

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, current_app, abort
from flask_login import current_user, login_required
from collections import defaultdict
from sqlalchemy import func, desc, inspect, text
from sqlalchemy.orm import aliased
from datetime import datetime, timedelta
import json
from LoanMVP.extensions import db, csrf
from werkzeug.security import generate_password_hash

from LoanMVP.ai.base_ai import AIAssistant     # ✅ Unified AI import
from LoanMVP.utils.decorators import role_required
from LoanMVP.utils.emailer import send_email  # or wherever you saved it
from LoanMVP.utils.role_helpers import is_admin, company_billing_hold_reason
from LoanMVP.services.compliance_service import loan_relevant_state, loan_officer_can_serve_state


# MODELS
from LoanMVP.models.user_model import User
from LoanMVP.models.crm_models import Lead, Message, Task, Partner
from LoanMVP.models.loan_models import LoanApplication, BorrowerProfile
from LoanMVP.models.loan_officer_model import LoanOfficerProfile
from LoanMVP.models.processor_model import ProcessorProfile
from LoanMVP.models.underwriter_model import UnderwriterProfile
from LoanMVP.models.document_models import LoanDocument
from LoanMVP.models.system_models import SystemLog
from LoanMVP.models.admin import Company, AccessRequest, UserInvite, BusinessInquiry, LicenseInviteEvent, SubscriptionRequest
from LoanMVP.models.investor_models import InvestorProfile
from LoanMVP.models.ai_models import AIAssistantInteraction
from LoanMVP.models.payment_models import PaymentRecord
from LoanMVP.models.vip_models import VIPIncome, VIPProfile
from LoanMVP.models.company_finance_models import CMFinanceEntry, DIVISIONS, INCOME_CATEGORIES, EXPENSE_CATEGORIES
from LoanMVP.models.contractor_models import ContractorBidOpportunity
from LoanMVP.services.notify_service import notify

import io
import csv
import stripe
import time

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
assistant = AIAssistant()
FULL_ADMIN_ROLES = {"platform_admin", "master_admin", "lending_admin", "executive"}
FUNDED_LOAN_STATUSES = {"closed", "funded", "completed", "paid"}
ACTIVE_LOAN_STATUSES = {
    "application submitted",
    "submitted",
    "capital submitted",
    "pending",
    "processing",
    "in review",
    "in_review",
    "under review",
    "approved",
    "clear to close",
    "ctc",
}
COMPENSATION_DEFAULTS = {
    "loan_officer_rate": 0.01,
    "processor_file_pay": 350,
    "underwriter_file_pay": 500,
}
COMPANY_INVITABLE_ROLES = [
    ("admin", "Admin"),
    ("loan_officer", "Loan Officer"),
    ("processor", "Processor"),
    ("underwriter", "Underwriter"),
    ("borrower", "Borrower"),
    ("compliance", "Compliance"),
    ("crm", "CRM"),
    ("property", "Property"),
    ("ai", "AI"),
    ("intelligence", "Intelligence"),
]
COMPANY_INVITABLE_ROLE_SET = {role for role, _label in COMPANY_INVITABLE_ROLES}

RAVLO_STAFF_ROLES = [
    ("platform_admin", "Platform Admin"),
    ("master_admin", "Master Admin"),
    ("admin", "Admin"),
    ("intelligence", "Intelligence"),
]
RAVLO_STAFF_ROLE_SET = {role for role, _ in RAVLO_STAFF_ROLES}


def _single_admin_mode_enabled() -> bool:
    return False


def _owner_admin_email() -> str:
    return (current_app.config.get("OWNER_ADMIN_EMAIL") or "").strip().lower()


def _is_owner_account(user) -> bool:
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
            "bullets": [
                "Deal sourcing, rehab planning, and funding status in one command view.",
                "Subscription-aware premium tooling, exports, and AI analysis states.",
                "Investor-ready next steps, document progress, and saved-property watchlist.",
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
            "bullets": [
                "Shows partner request flow, proposal value, and unlocked tier features.",
                "Highlights CRM, instant quote, AI assist, and portfolio showcase modules.",
                "Works as a pitch surface for contractors, title, insurance, and vendors.",
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
            "bullets": [
                "Pipeline stages for submitted, in review, approved, and investor capital loans.",
                "Intake coverage, lead conversion, and borrower communication workload.",
                "Designed as a live demo for lenders, broker partners, and recruiting.",
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
            "bullets": [
                "Communicates operational control and review velocity for partners and investors.",
                "Frames conditions, risk flags, and decision support as one clean workspace.",
                "Pairs naturally with the investor funding timeline for cross-role storytelling.",
            ],
        },
    ]

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


# Self-serve Stripe plans (fixed price). "lender" (Scale) and "white_label"
# (Enterprise) are custom-quote tiers with no fixed price -- those upgrade
# through a sales conversation, not a Checkout button.
#
# Reuses the STRIPE_PRICE_INDIVIDUAL_LOAN_OFFICER / STRIPE_PRICE_BROKERAGE_SMALL_TEAM
# price IDs already configured in config.py for these exact seat counts --
# checkout_routes.py's "loan_officer"/"brokerage" plan entries point Stripe
# at the same prices but only ever set User.subscription, never touching
# Company at all, so they never actually granted Lending OS seats.
_COMPANY_SELF_SERVE_PLANS = {
    "individual": {
        "label": "Starter",
        "price": "$149/mo",
        "price_config_key": "STRIPE_PRICE_INDIVIDUAL_LOAN_OFFICER",
    },
    "team": {
        "label": "Growth",
        "price": "$799/mo",
        "price_config_key": "STRIPE_PRICE_BROKERAGE_SMALL_TEAM",
    },
}

_COMPANY_PLAN_LABELS = {
    "individual": "Starter",
    "team": "Growth",
    "lender": "Scale",
    "white_label": "Enterprise",
}


def _company_dashboard_defaults():
    return {
        "overview": True,
        "tools": True,
        "analytics": True,
        "empty_state": True,
        "applicants": True,
        "team": True,
        "invites": True,
        "requests": True,
        "messages": True,
        "compensation": True,
    }


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _company_loan_officers(company_id):
    return (
        db.session.query(LoanOfficerProfile)
        .join(User, LoanOfficerProfile.user_id == User.id)
        .filter(User.company_id == company_id)
        .order_by(func.lower(func.coalesce(LoanOfficerProfile.name, User.email)))
        .all()
    )


def _company_processors(company_id):
    return (
        db.session.query(ProcessorProfile)
        .join(User, ProcessorProfile.user_id == User.id)
        .filter(User.company_id == company_id)
        .order_by(func.lower(func.coalesce(ProcessorProfile.full_name, User.email)))
        .all()
    )


def _company_underwriters(company_id):
    return (
        db.session.query(UnderwriterProfile)
        .join(User, UnderwriterProfile.user_id == User.id)
        .filter(User.company_id == company_id)
        .order_by(func.lower(func.coalesce(UnderwriterProfile.full_name, User.email)))
        .all()
    )


def _profile_user_company_id(profile):
    if not profile:
        return None
    user = getattr(profile, "user", None)
    if user is None and getattr(profile, "user_id", None):
        user = User.query.get(getattr(profile, "user_id"))
    return getattr(user, "company_id", None) if user else None


def _borrower_matches_company(borrower, company):
    if not borrower or not company:
        return False

    borrower_user = getattr(borrower, "user", None)
    borrower_company_id = getattr(borrower_user, "company_id", None)
    if borrower_company_id == company.id:
        return True

    borrower_company_name = (getattr(borrower, "company", "") or "").strip().lower()
    company_name = (getattr(company, "name", "") or "").strip().lower()
    return bool(company_name and borrower_company_name == company_name)


def _loan_matches_company(loan, company):
    if not loan or not company:
        return False

    if getattr(loan, "company_id", None) == company.id:
        return True

    borrower = getattr(loan, "borrower_profile", None)
    if _borrower_matches_company(borrower, company):
        return True

    assigned_profiles = [
        getattr(loan, "loan_officer", None),
        getattr(loan, "processor", None),
        getattr(loan, "underwriter", None),
    ]
    return any(_profile_user_company_id(profile) == company.id for profile in assigned_profiles)


def _company_loans(company_id, limit=500):
    return (
        LoanApplication.query
        .filter_by(company_id=company_id)
        .order_by(LoanApplication.created_at.desc(), LoanApplication.id.desc())
        .limit(limit)
        .all()
    )


def _company_recent_applicants(company_id, limit=8):
    company = Company.query.get(company_id)
    if not company:
        return []

    scoped_loans = _company_loans(company.id, limit=200)
    return scoped_loans[:limit]


def _loan_status_key(loan):
    return (getattr(loan, "status", "") or "").strip().lower()


def _loan_amount_value(loan):
    try:
        return float(getattr(loan, "amount", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _profile_name(profile, fallback):
    return (
        getattr(profile, "name", None)
        or getattr(profile, "full_name", None)
        or getattr(profile, "email", None)
        or fallback
    )


def _compensation_rows_for_profiles(profiles, loans, role_key, display_role):
    profile_id_attr = f"{role_key}_id"
    rows = []

    for profile in profiles:
        assigned = [
            loan for loan in loans
            if getattr(loan, profile_id_attr, None) == getattr(profile, "id", None)
        ]
        funded = [loan for loan in assigned if _loan_status_key(loan) in FUNDED_LOAN_STATUSES]
        active = [loan for loan in assigned if _loan_status_key(loan) in ACTIVE_LOAN_STATUSES]
        funded_volume = sum(_loan_amount_value(loan) for loan in funded)

        if role_key == "loan_officer":
            pay_basis = f"{COMPENSATION_DEFAULTS['loan_officer_rate'] * 100:.2f}% funded volume"
            estimated_pay = funded_volume * COMPENSATION_DEFAULTS["loan_officer_rate"]
        elif role_key == "processor":
            pay_basis = f"${COMPENSATION_DEFAULTS['processor_file_pay']:,} per funded file"
            estimated_pay = len(funded) * COMPENSATION_DEFAULTS["processor_file_pay"]
        else:
            pay_basis = f"${COMPENSATION_DEFAULTS['underwriter_file_pay']:,} per funded file"
            estimated_pay = len(funded) * COMPENSATION_DEFAULTS["underwriter_file_pay"]

        rows.append({
            "profile_id": getattr(profile, "id", None),
            "name": _profile_name(profile, f"{display_role} #{getattr(profile, 'id', '')}"),
            "email": getattr(profile, "email", None),
            "role": display_role,
            "assigned_count": len(assigned),
            "active_count": len(active),
            "funded_count": len(funded),
            "funded_volume": funded_volume,
            "estimated_pay": estimated_pay,
            "pay_basis": pay_basis,
        })

    return rows


def _table_exists(table_name):
    try:
        return inspect(db.engine).has_table(table_name)
    except Exception:
        return False


def _company_pending_compensation_requests(company, loans):
    pending = []
    company_user_ids = {user.id for user in User.query.filter_by(company_id=company.id).all()}
    company_loan_ids = {loan.id for loan in loans}

    payment_rows = (
        PaymentRecord.query
        .filter(func.lower(func.coalesce(PaymentRecord.status, "")) != "paid")
        .order_by(PaymentRecord.timestamp.desc(), PaymentRecord.id.desc())
        .limit(100)
        .all()
    )
    for row in payment_rows:
        payment_type = (getattr(row, "payment_type", "") or "").strip().lower()
        if not any(term in payment_type for term in ("commission", "comp", "pay", "bonus", "origination")):
            continue
        if getattr(row, "user_id", None) not in company_user_ids and getattr(row, "loan_id", None) not in company_loan_ids:
            continue
        pending.append({
            "source": "Payment",
            "person": getattr(getattr(row, "user", None), "full_name", None) or getattr(getattr(row, "user", None), "email", None) or "Unassigned",
            "type": getattr(row, "payment_type", None) or "Compensation",
            "amount": float(getattr(row, "amount", 0) or 0),
            "status": getattr(row, "status", None) or "Pending",
            "created_at": getattr(row, "timestamp", None),
        })

    if _table_exists("vip_income") and _table_exists("vip_profiles"):
        try:
            vip_rows = (
                db.session.query(VIPIncome, VIPProfile, User)
                .join(VIPProfile, VIPIncome.vip_profile_id == VIPProfile.id)
                .join(User, VIPProfile.user_id == User.id)
                .filter(User.company_id == company.id)
                .filter(func.lower(func.coalesce(VIPIncome.status, "")) == "pending")
                .order_by(VIPIncome.created_at.desc(), VIPIncome.id.desc())
                .limit(100)
                .all()
            )
            for income, profile, user in vip_rows:
                pending.append({
                    "source": "VIP Income",
                    "person": getattr(user, "full_name", None) or getattr(profile, "display_name", None) or getattr(user, "email", None),
                    "type": getattr(income, "category", None) or "Commission",
                    "amount": float(getattr(income, "amount", 0) or 0),
                    "status": getattr(income, "status", None) or "Pending",
                    "created_at": getattr(income, "income_date", None) or getattr(income, "created_at", None),
                })
        except Exception:
            current_app.logger.exception("Unable to load company VIP pending income rows")

    return pending[:12]


def _company_compensation_summary(company, loans):
    loan_officer_rows = _compensation_rows_for_profiles(
        _company_loan_officers(company.id),
        loans,
        "loan_officer",
        "Loan Officer",
    )
    processor_rows = _compensation_rows_for_profiles(
        _company_processors(company.id),
        loans,
        "processor",
        "Processor",
    )
    underwriter_rows = _compensation_rows_for_profiles(
        _company_underwriters(company.id),
        loans,
        "underwriter",
        "Underwriter",
    )

    rows = loan_officer_rows + processor_rows + underwriter_rows
    totals = {
        "team_members": len(rows),
        "assigned_loans": sum(row["assigned_count"] for row in rows),
        "active_loans": sum(row["active_count"] for row in rows),
        "funded_loans": sum(row["funded_count"] for row in rows),
        "funded_volume": sum(row["funded_volume"] for row in rows),
        "estimated_pay": sum(row["estimated_pay"] for row in rows),
    }

    return {
        "loan_officers": loan_officer_rows,
        "processors": processor_rows,
        "underwriters": underwriter_rows,
        "rows": rows,
        "totals": totals,
        "pending_requests": _company_pending_compensation_requests(company, loans),
        "pay_basis_note": "Estimated from company defaults until a formal commission schedule is configured.",
    }


def _company_dashboard_column_exists():
    try:
        columns = inspect(db.engine).get_columns("companies")
        return any(column.get("name") == "dashboard_settings" for column in columns)
    except Exception:
        return False


def _company_dashboard_settings(company):
    defaults = _company_dashboard_defaults()
    if not _company_dashboard_column_exists():
        return defaults

    try:
        raw = db.session.execute(
            text("SELECT dashboard_settings FROM companies WHERE id = :company_id"),
            {"company_id": company.id},
        ).scalar()
    except Exception:
        raw = None

    raw = (raw or "").strip()
    if not raw:
        return defaults

    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return defaults

    if not isinstance(payload, dict):
        return defaults

    merged = defaults.copy()
    for key in defaults:
        if key in payload:
            merged[key] = bool(payload[key])
    return merged


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
    if role in COMPANY_INVITABLE_ROLE_SET:
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
    if (
        (getattr(current_user, "role", "") or "").strip().lower() == "executive"
        or _is_owner_account(current_user)
    ):
        return redirect(url_for("executive.dashboard"))

    if _is_company_admin(current_user) and current_user.company_id:
        return redirect(url_for("admin.company_dashboard", company_id=current_user.company_id))

    if _is_company_admin(current_user) and not _is_full_admin(current_user):
        # Company-scoped admin with no company_id assigned — a misconfigured
        # account, not a signal to fall through to platform-wide stats below.
        abort(403)

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

    construction_office_statuses = [
        "bid_package_needed",
        "missing_information",
        "draft_bid_prepared",
        "jamaine_review_needed",
        "ready_to_send",
        "follow_up_needed",
    ]

    try:
        bid_support_queue = (
            ContractorBidOpportunity.query
            .filter(ContractorBidOpportunity.status.in_(construction_office_statuses))
            .order_by(
                ContractorBidOpportunity.updated_at.desc(),
                ContractorBidOpportunity.created_at.desc(),
            )
            .limit(25)
            .all()
        )
    except Exception as exc:
        current_app.logger.warning("bid support queue unavailable: %s", exc)
        db.session.rollback()
        bid_support_queue = []

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
        demo_dashboards=_demo_dashboard_cards(),
        single_admin_mode=_single_admin_mode_enabled(),
        owner_admin_email=_owner_admin_email(),
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
        bid_support_queue=bid_support_queue,
    )


@admin_bp.route("/demo-center")
@login_required
@role_required("admin_group")
def demo_center():
    demo_dashboards = _demo_dashboard_cards()
    spotlight_metrics = {
        "dashboards_ready": len(demo_dashboards),
        "single_admin_mode": "Enabled" if _single_admin_mode_enabled() else "Disabled",
        "owner_admin_email": _owner_admin_email() or "Not set",
    }

    return render_template(
        "admin/demo_center.html",
        demo_dashboards=demo_dashboards,
        spotlight_metrics=spotlight_metrics,
        single_admin_mode=_single_admin_mode_enabled(),
        owner_admin_email=_owner_admin_email(),
    )


@admin_bp.route("/companies")
@login_required
@role_required("admin_group")
def companies():
    if _is_company_admin(current_user) and current_user.company_id:
        return redirect(url_for("admin.company_dashboard", company_id=current_user.company_id))

    if _is_company_admin(current_user) and not _is_full_admin(current_user):
        # Company-scoped admin with no company_id assigned — a misconfigured
        # account, not a signal to fall through to the full company list.
        abort(403)

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
        # Onboarding a brand-new licensed company is a Ravlo-only action.
        # _can_access_request() lets a company admin approve their own
        # employees' requests, but that must never fall through to
        # creating an entirely new tenant.
        if not _is_full_admin(current_user):
            flash("Only Ravlo admins can onboard a new company.", "warning")
            return redirect(_admin_home_endpoint())
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
        # A name/domain heuristic match could point at a company other than
        # the approving admin's own — only a full admin may reassign a
        # request to a company the admin doesn't belong to.
        if not _is_full_admin(current_user) and getattr(current_user, "company_id", None) != company.id:
            flash("You do not have access to that request.", "warning")
            return redirect(_admin_home_endpoint())
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


# =========================================================
# Subscription / tier upgrade requests
#
# Partner tier upgrades (partners.confirm_subscription) and the borrower
# "become an Investor" upgrade (borrower.subscription) both queue a
# SubscriptionRequest instead of applying instantly -- neither flow has a
# real payment step wired up yet, so self-service would let anyone grant
# themselves a paid tier or a new account role for free. Only a Ravlo
# admin (never a company-scoped admin) can confirm one of these.
# =========================================================

@admin_bp.route("/subscription-requests", methods=["GET"])
@login_required
@role_required("admin_group")
def subscription_requests():
    if not _is_full_admin(current_user):
        flash("Only Ravlo admins can review subscription requests.", "warning")
        return redirect(_admin_home_endpoint())

    all_requests = SubscriptionRequest.query.order_by(
        SubscriptionRequest.created_at.desc()
    ).all()
    pending = [r for r in all_requests if r.status == "pending"]
    reviewed = [r for r in all_requests if r.status != "pending"][:25]
    user_map = {
        u.id: u for u in User.query.filter(
            User.id.in_({r.user_id for r in all_requests})
        ).all()
    } if all_requests else {}

    return render_template(
        "admin/subscription_requests.html",
        pending=pending,
        reviewed=reviewed,
        user_map=user_map,
        title="Subscription Requests",
        active_tab="subscription_requests",
    )


@admin_bp.route("/subscription-requests/<int:request_id>/approve", methods=["POST"])
@login_required
@role_required("admin_group")
@admin_required
def approve_subscription_request(request_id):
    if not _is_full_admin(current_user):
        flash("Only Ravlo admins can approve subscription requests.", "warning")
        return redirect(_admin_home_endpoint())

    sub_request = SubscriptionRequest.query.get_or_404(request_id)
    if sub_request.status != "pending":
        flash("This request has already been reviewed.", "info")
        return redirect(url_for("admin.subscription_requests"))

    plan = (sub_request.plan_requested or "").strip()
    context = sub_request.context or "investor_preview"

    if context == "partner_tier":
        partner = Partner.query.filter_by(user_id=sub_request.user_id).first()
        if not partner:
            flash("Partner profile no longer exists.", "danger")
            return redirect(url_for("admin.subscription_requests"))
        partner.subscription_tier = plan
        partner.featured = plan.lower() in {"featured", "premium", "enterprise"}

    elif context == "borrower_plan":
        if plan == "investor_upgrade":
            user = User.query.get(sub_request.user_id)
            user.role = "investor"
            if not InvestorProfile.query.filter_by(user_id=user.id).first():
                db.session.add(InvestorProfile(
                    user_id=user.id,
                    full_name=f"{user.first_name or ''} {user.last_name or ''}".strip() or None,
                    email=user.email,
                ))
        else:
            borrower = BorrowerProfile.query.filter_by(user_id=sub_request.user_id).first()
            if borrower:
                borrower.subscription_plan = plan

    else:
        # investor_preview -- the existing self-contained flow in preview_routes.py
        user = User.query.get(sub_request.user_id)
        alias = {"core": "core", "explorer": "core", "operator": "operator", "pro": "operator"}
        user.subscription = alias.get(plan.lower(), "core")
        user.trial_ends_at = None

    sub_request.status = "approved"
    sub_request.reviewed_by = current_user.id
    sub_request.reviewed_at = datetime.utcnow()
    db.session.commit()

    flash(f"Subscription request approved: {plan}.", "success")
    return redirect(url_for("admin.subscription_requests"))


@admin_bp.route("/subscription-requests/<int:request_id>/deny", methods=["POST"])
@login_required
@role_required("admin_group")
@admin_required
def deny_subscription_request(request_id):
    if not _is_full_admin(current_user):
        flash("Only Ravlo admins can review subscription requests.", "warning")
        return redirect(_admin_home_endpoint())

    sub_request = SubscriptionRequest.query.get_or_404(request_id)
    if sub_request.status != "pending":
        flash("This request has already been reviewed.", "info")
        return redirect(url_for("admin.subscription_requests"))

    sub_request.status = "denied"
    sub_request.reviewed_by = current_user.id
    sub_request.reviewed_at = datetime.utcnow()
    db.session.commit()

    flash("Subscription request denied.", "warning")
    return redirect(url_for("admin.subscription_requests"))


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

    officer_user_ids = [u.id for u in team_members if (u.role or "").strip().lower() == "loan_officer"]
    license_by_user_id = {
        profile.user_id: profile
        for profile in LoanOfficerProfile.query.filter(LoanOfficerProfile.user_id.in_(officer_user_ids)).all()
    } if officer_user_ids else {}

    return render_template(
        "admin/company_team.html",
        company=company,
        team_members=team_members,
        invites=invites,
        license_by_user_id=license_by_user_id,
    )


@admin_bp.route("/company/<int:company_id>/team/<int:user_id>/license", methods=["GET", "POST"])
@login_required
@role_required("admin_group")
@admin_required
def loan_officer_license(company_id, user_id):
    company = Company.query.get_or_404(company_id)
    access_redirect = _ensure_company_access(company)
    if access_redirect:
        return access_redirect

    member = User.query.filter_by(id=user_id, company_id=company.id).first_or_404()
    if (member.role or "").strip().lower() != "loan_officer":
        flash("That team member isn't a loan officer.", "warning")
        return redirect(url_for("admin.company_team", company_id=company.id))

    profile = LoanOfficerProfile.query.filter_by(user_id=member.id).first()
    if not profile:
        profile = LoanOfficerProfile(user_id=member.id, name=member.first_name or member.email or "Loan Officer")
        db.session.add(profile)
        db.session.commit()

    if request.method == "POST":
        profile.nmls = (request.form.get("nmls") or "").strip() or None
        states_raw = request.form.get("licensed_states") or ""
        states = [s.strip().upper() for s in states_raw.split(",") if s.strip()]
        profile.licensed_states = ",".join(states) or None

        mark_verified = request.form.get("verified") == "on"
        if mark_verified and not profile.license_verified:
            profile.license_verified = True
            profile.license_verified_by = current_user.id
            profile.license_verified_at = datetime.utcnow()
        elif not mark_verified:
            profile.license_verified = False
            profile.license_verified_by = None
            profile.license_verified_at = None

        db.session.commit()
        flash(f"Updated license info for {member.first_name or member.email}.", "success")
        return redirect(url_for("admin.company_team", company_id=company.id))

    return render_template(
        "admin/loan_officer_license.html",
        company=company,
        member=member,
        profile=profile,
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

    if _single_admin_mode_enabled() and not _is_full_admin(current_user):
        flash(
            f"Single-admin mode is active. Company admins cannot invite users while {_owner_admin_email()} controls workspace access.",
            "warning",
        )
        return redirect(url_for("admin.company_dashboard", company_id=company.id))

    if request.method == "POST":
        first_name = (request.form.get("first_name") or "").strip()
        last_name = (request.form.get("last_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        role = (request.form.get("role") or "").strip()

        if not company.has_seat_available():
            flash(
                f"{company.name} has reached its plan's user limit "
                f"({company.max_users}). Upgrade the plan to invite more team members.",
                "warning",
            )
            return redirect(url_for("admin.company_team", company_id=company.id))

        if not email or not role:
            flash("Email and role are required.", "danger")
            return redirect(url_for("admin.invite_team_member", company_id=company.id))

        if role not in COMPANY_INVITABLE_ROLE_SET:
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
        invitable_roles=COMPANY_INVITABLE_ROLES,
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

    if _single_admin_mode_enabled() and not _is_full_admin(current_user):
        flash(
            f"Single-admin mode is active. Company admins cannot resend invites while {_owner_admin_email()} controls workspace access.",
            "warning",
        )
        return redirect(url_for("admin.company_dashboard", company_id=company.id))

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


@admin_bp.route("/company/<int:company_id>/team/<int:user_id>/remove", methods=["POST"])
@login_required
@role_required("admin_group")
@admin_required
def remove_team_member(company_id, user_id):
    company = Company.query.get_or_404(company_id)
    access_redirect = _ensure_company_access(company)
    if access_redirect:
        return access_redirect

    if user_id == current_user.id:
        flash("You cannot remove yourself from the team.", "warning")
        return redirect(url_for("admin.company_team", company_id=company.id))

    user = User.query.get_or_404(user_id)
    if user.company_id != company.id:
        flash("That user is not on this team.", "warning")
        return redirect(url_for("admin.company_team", company_id=company.id))

    user.company_id = None
    db.session.commit()

    name = ((user.first_name or "") + " " + (user.last_name or "")).strip() or user.email
    flash(f"{name} has been removed from {company.name}.", "success")
    return redirect(url_for("admin.company_team", company_id=company.id))


@admin_bp.route("/company/<int:company_id>/team/invites/<int:invite_id>/delete", methods=["POST"])
@login_required
@role_required("admin_group")
@admin_required
def delete_team_invite(company_id, invite_id):
    company = Company.query.get_or_404(company_id)
    access_redirect = _ensure_company_access(company)
    if access_redirect:
        return access_redirect

    invite = UserInvite.query.get_or_404(invite_id)
    if invite.company_id != company.id:
        flash("That invite does not belong to this company.", "danger")
        return redirect(url_for("admin.company_dashboard", company_id=company.id))

    if invite.status == "accepted":
        flash("Accepted invites cannot be deleted; remove the user from the team instead.", "warning")
        return redirect(url_for("admin.company_dashboard", company_id=company.id))

    db.session.delete(invite)
    db.session.commit()
    flash("Invite deleted.", "success")

    next_url = request.form.get("next") or request.referrer or ""
    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    return redirect(url_for("admin.company_dashboard", company_id=company.id))


# =========================================================
# 👥 RAVLO STAFF MANAGEMENT
# =========================================================

def _get_or_create_ravlo_company():
    company = Company.query.filter_by(email_domain="ravlohq.com").first()
    if not company:
        company = Company(name="Ravlo HQ", email_domain="ravlohq.com", is_active=True)
        db.session.add(company)
        db.session.commit()
    return company


def _send_ravlo_staff_invite_email(invite):
    invite_url = url_for("auth.register_from_invite", token=invite.token, _external=True)
    role_label = (invite.role or "").replace("_", " ").title()
    first_name = (invite.first_name or "").strip() or "there"

    subject = "You've been added to the Ravlo team"
    body = f"""
Hi {first_name},

You've been invited to join the Ravlo team.

Complete your registration here:
{invite_url}

Role: {role_label}

This link expires in 14 days.
""".strip()

    html = f"""
    <div style="font-family:Inter,Arial,sans-serif;background:#071018;padding:32px;color:#f4f7fb;">
      <div style="max-width:680px;margin:0 auto;background:#0f1a26;border:1px solid rgba(255,255,255,.08);border-radius:20px;padding:32px;">
        <div style="font-size:12px;letter-spacing:.18em;font-weight:800;color:#8ec5ff;margin-bottom:12px;">RAVLO TEAM INVITE</div>
        <h1 style="margin:0 0 12px;font-size:28px;line-height:1.1;">Welcome to the team</h1>
        <p style="margin:0 0 14px;color:#c9d6e3;">
          Hi {first_name}, you've been added to the Ravlo platform as a <strong>{role_label}</strong>.
        </p>
        <a href="{invite_url}" style="display:inline-block;padding:14px 20px;background:#1f8fff;color:#fff;text-decoration:none;border-radius:12px;font-weight:700;">
          Accept Invite &amp; Create Account
        </a>
        <p style="margin:18px 0 0;color:#8da3b8;font-size:13px;">This link expires in 14 days.</p>
      </div>
    </div>
    """.strip()

    send_email(to=invite.email, subject=subject, html_body=html, text_body=body)


@admin_bp.route("/staff")
@login_required
@role_required("admin_group")
def staff():
    if not (_is_full_admin(current_user) or _is_owner_account(current_user) or (getattr(current_user, "role", "") or "").strip().lower() == "executive"):
        flash("Access restricted to platform administrators.", "warning")
        return redirect(url_for("admin.dashboard"))

    ravlo_co = _get_or_create_ravlo_company()
    team_members = (
        User.query
        .filter_by(company_id=ravlo_co.id)
        .order_by(User.role, User.first_name)
        .all()
    )
    invites = (
        UserInvite.query
        .filter_by(company_id=ravlo_co.id)
        .order_by(UserInvite.created_at.desc())
        .all()
    )
    return render_template(
        "admin/staff.html",
        team_members=team_members,
        invites=invites,
        ravlo_roles=RAVLO_STAFF_ROLES,
    )


@admin_bp.route("/staff/invite", methods=["POST"])
@login_required
@role_required("admin_group")
def invite_staff_member():
    if not (_is_full_admin(current_user) or _is_owner_account(current_user) or (getattr(current_user, "role", "") or "").strip().lower() == "executive"):
        flash("Access restricted.", "warning")
        return redirect(url_for("admin.dashboard"))

    first_name = (request.form.get("first_name") or "").strip()
    last_name = (request.form.get("last_name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    role = (request.form.get("role") or "platform_admin").strip()

    if not email:
        flash("Email is required.", "danger")
        return redirect(url_for("admin.staff"))

    if role not in RAVLO_STAFF_ROLE_SET:
        flash("Invalid role selected.", "danger")
        return redirect(url_for("admin.staff"))

    if User.query.filter_by(email=email).first():
        flash("A user with that email already exists.", "warning")
        return redirect(url_for("admin.staff"))

    ravlo_co = _get_or_create_ravlo_company()

    existing = UserInvite.query.filter_by(email=email, company_id=ravlo_co.id, status="pending").first()
    if existing and not existing.is_expired():
        flash("An active invite already exists for that email.", "warning")
        return redirect(url_for("admin.staff"))

    invite = UserInvite(
        company_id=ravlo_co.id,
        email=email,
        first_name=first_name,
        last_name=last_name,
        role=role,
        token=UserInvite.generate_token(),
        invited_by=current_user.id,
        expires_at=UserInvite.default_expiration(days=14),
        status="pending",
    )
    db.session.add(invite)
    db.session.commit()

    try:
        _send_ravlo_staff_invite_email(invite)
    except Exception:
        current_app.logger.exception("Failed to send Ravlo staff invite email")

    flash(f"Invite sent to {email}.", "success")
    return redirect(url_for("admin.staff"))


@admin_bp.route("/staff/invites/<int:invite_id>/resend", methods=["POST"])
@login_required
@role_required("admin_group")
def resend_staff_invite(invite_id):
    if not (_is_full_admin(current_user) or _is_owner_account(current_user) or (getattr(current_user, "role", "") or "").strip().lower() == "executive"):
        flash("Access restricted.", "warning")
        return redirect(url_for("admin.dashboard"))

    ravlo_co = _get_or_create_ravlo_company()
    invite = UserInvite.query.get_or_404(invite_id)
    if invite.company_id != ravlo_co.id:
        flash("Invalid invite.", "danger")
        return redirect(url_for("admin.staff"))

    if invite.status == "accepted":
        flash("This invite has already been accepted.", "info")
        return redirect(url_for("admin.staff"))

    _refresh_invite(invite)
    try:
        _send_ravlo_staff_invite_email(invite)
        db.session.commit()
        flash("Invite resent.", "success")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to resend Ravlo staff invite")
        flash("Invite refreshed but email could not be sent.", "warning")

    return redirect(url_for("admin.staff"))


@admin_bp.route("/staff/invites/<int:invite_id>/delete", methods=["POST"])
@login_required
@role_required("admin_group")
def delete_staff_invite(invite_id):
    if not (_is_full_admin(current_user) or _is_owner_account(current_user) or (getattr(current_user, "role", "") or "").strip().lower() == "executive"):
        flash("Access restricted.", "warning")
        return redirect(url_for("admin.dashboard"))

    ravlo_co = _get_or_create_ravlo_company()
    invite = UserInvite.query.get_or_404(invite_id)
    if invite.company_id != ravlo_co.id:
        flash("Invalid invite.", "danger")
        return redirect(url_for("admin.staff"))

    if invite.status == "accepted":
        flash("Accepted invites cannot be removed here; manage the user account instead.", "warning")
        return redirect(url_for("admin.staff"))

    db.session.delete(invite)
    db.session.commit()
    flash("Invite cancelled.", "success")
    return redirect(url_for("admin.staff"))


@admin_bp.route("/staff/<int:user_id>/remove", methods=["POST"])
@login_required
@role_required("admin_group")
def remove_staff_member(user_id):
    if not (_is_full_admin(current_user) or _is_owner_account(current_user) or (getattr(current_user, "role", "") or "").strip().lower() == "executive"):
        flash("Access restricted.", "warning")
        return redirect(url_for("admin.dashboard"))

    if user_id == current_user.id:
        flash("You cannot remove yourself from the team.", "warning")
        return redirect(url_for("admin.staff"))

    ravlo_co = _get_or_create_ravlo_company()
    user = User.query.get_or_404(user_id)

    if user.company_id != ravlo_co.id:
        flash("That user is not on the Ravlo team.", "warning")
        return redirect(url_for("admin.staff"))

    user.company_id = None
    db.session.commit()

    name = ((user.first_name or "") + " " + (user.last_name or "")).strip() or user.email
    flash(f"{name} has been removed from the Ravlo team.", "success")
    return redirect(url_for("admin.staff"))


@admin_bp.route("/staff/link", methods=["POST"])
@login_required
@role_required("admin_group")
def link_staff_member():
    if not (_is_full_admin(current_user) or _is_owner_account(current_user) or (getattr(current_user, "role", "") or "").strip().lower() == "executive"):
        flash("Access restricted.", "warning")
        return redirect(url_for("admin.dashboard"))

    email = (request.form.get("email") or "").strip().lower()
    role = (request.form.get("role") or "").strip()

    if not email:
        flash("Email is required.", "danger")
        return redirect(url_for("admin.staff"))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash(f"No account found for {email}. Use the invite form to send them a registration link.", "warning")
        return redirect(url_for("admin.staff"))

    ravlo_co = _get_or_create_ravlo_company()
    user.company_id = ravlo_co.id

    if role and role in RAVLO_STAFF_ROLE_SET:
        user.role = role

    db.session.commit()
    name = ((user.first_name or "") + " " + (user.last_name or "")).strip() or user.email
    flash(f"{name} has been added to the Ravlo team.", "success")
    return redirect(url_for("admin.staff"))


# =========================================================
# 💰 CAUGHMAN MASON FINANCE HUB
# =========================================================

def _cm_finance_guard():
    role = (getattr(current_user, "role", "") or "").strip().lower()
    return (
        _is_full_admin(current_user)
        or _is_owner_account(current_user)
        or role == "executive"
        or role == "partner"
    )


@admin_bp.route("/finances", methods=["GET"])
@login_required
def company_finances():
    if not _cm_finance_guard():
        flash("Access restricted.", "warning")
        return redirect(url_for("admin.dashboard"))

    selected_division = request.args.get("division", "all")
    selected_type     = request.args.get("type", "all")

    from datetime import datetime as _dt

    try:
        q = CMFinanceEntry.query
        if selected_division != "all":
            q = q.filter_by(division=selected_division)
        if selected_type in ("income", "expense"):
            q = q.filter_by(entry_type=selected_type)

        entries = q.order_by(CMFinanceEntry.entry_date.desc(), CMFinanceEntry.created_at.desc()).limit(200).all()

        all_entries = CMFinanceEntry.query.all()
        division_summary = {}
        for e in all_entries:
            d = e.division
            if d not in division_summary:
                division_summary[d] = {"income": 0.0, "expense": 0.0}
            if e.entry_type == "income":
                division_summary[d]["income"] += e.amount or 0
            else:
                division_summary[d]["expense"] += e.amount or 0

        for d in division_summary:
            division_summary[d]["net"] = division_summary[d]["income"] - division_summary[d]["expense"]

        total_income  = sum(e.amount for e in all_entries if e.entry_type == "income")
        total_expense = sum(e.amount for e in all_entries if e.entry_type == "expense")

    except Exception as exc:
        db.session.rollback()
        current_app.logger.warning("[company_finances] table not ready yet: %s", exc)
        flash("Financial Hub is setting up — the database table will be ready shortly after the next deploy.", "info")
        entries = []
        division_summary = {}
        total_income = total_expense = 0.0

    return render_template(
        "admin/company_finances.html",
        entries           = entries,
        divisions         = DIVISIONS,
        income_categories = INCOME_CATEGORIES,
        expense_categories= EXPENSE_CATEGORIES,
        division_summary  = division_summary,
        total_income      = total_income,
        now               = _dt.utcnow(),
        total_expense     = total_expense,
        total_net         = total_income - total_expense,
        selected_division = selected_division,
        selected_type     = selected_type,
    )


@admin_bp.route("/finances/add", methods=["POST"])
@login_required
def company_finances_add():
    if not _cm_finance_guard():
        flash("Access restricted.", "warning")
        return redirect(url_for("admin.dashboard"))

    amount_raw = (request.form.get("amount") or "").replace(",", "").replace("$", "").strip()
    try:
        amount = float(amount_raw)
    except ValueError:
        flash("Invalid amount.", "danger")
        return redirect(url_for("admin.company_finances"))

    date_raw = (request.form.get("entry_date") or "").strip()
    from datetime import date as _date, datetime as _dt
    try:
        entry_date = _dt.strptime(date_raw, "%Y-%m-%d").date() if date_raw else _date.today()
    except ValueError:
        entry_date = _date.today()

    entry = CMFinanceEntry(
        created_by_id = current_user.id,
        division      = (request.form.get("division") or "construction").strip(),
        entry_type    = (request.form.get("entry_type") or "expense").strip(),
        category      = (request.form.get("category") or "").strip() or None,
        description   = (request.form.get("description") or "").strip() or None,
        amount        = amount,
        entry_date    = entry_date,
        project_name  = (request.form.get("project_name") or "").strip() or None,
        notes         = (request.form.get("notes") or "").strip() or None,
    )
    db.session.add(entry)
    db.session.commit()
    flash("Entry added.", "success")
    return redirect(url_for("admin.company_finances"))


@admin_bp.route("/finances/<int:entry_id>/delete", methods=["POST"])
@login_required
def company_finances_delete(entry_id):
    if not _cm_finance_guard():
        flash("Access restricted.", "warning")
        return redirect(url_for("admin.dashboard"))

    entry = CMFinanceEntry.query.get_or_404(entry_id)
    db.session.delete(entry)
    db.session.commit()
    flash("Entry removed.", "success")
    return redirect(url_for("admin.company_finances"))


# =========================================================
# 📊 SYSTEM REPORTS (CSV EXPORT)
# =========================================================
@admin_bp.route("/reports", methods=["GET", "POST"])
@login_required
@role_required("admin_group")
def reports():
    company = _company_scope()
    if not company and not _is_full_admin(current_user):
        # _company_scope() returns None both for full admins (intentional,
        # platform-wide) and for a company-admin with no company_id
        # assigned (misconfigured) — the latter must not fall through to
        # the platform-wide counts/CSV exports below.
        abort(403)
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
    if not company and not _is_full_admin(current_user):
        # See reports()/analytics(): a misconfigured company-admin with no
        # company_id must not fall through to the platform-wide branches.
        abort(403)
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
    q = LoanDocument.query
    if not _is_full_admin(current_user):
        q = q.filter_by(company_id=getattr(current_user, "company_id", None))
    docs = q.order_by(LoanDocument.created_at.desc()).limit(50).all()

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
    if not _is_full_admin(current_user) and doc.company_id != getattr(current_user, "company_id", None):
        abort(404)
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
    if not company and not _is_full_admin(current_user):
        # See reports()/messages(): a misconfigured company-admin with no
        # company_id must not fall through to the platform-wide branch.
        abort(403)

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

    # role_required("admin") also admits plain company admins, not just
    # platform_admin/master_admin/executive — scope every query below to
    # their company so one company's AI usage isn't visible to another's.
    scoping_company_id = None
    if not _is_full_admin(current_user):
        scoping_company_id = getattr(current_user, "company_id", None)
        if not scoping_company_id:
            abort(403)

    def _company_scoped(query):
        if scoping_company_id is None:
            return query
        return query.join(User, AIAssistantInteraction.user_id == User.id).filter(
            User.company_id == scoping_company_id
        )

    # -----------------------------------
    # Overall stats
    # -----------------------------------
    total_interactions = _company_scoped(AIAssistantInteraction.query).count()

    total_users_with_ai_query = db.session.query(
        func.count(func.distinct(AIAssistantInteraction.user_id))
    )
    if scoping_company_id is not None:
        total_users_with_ai_query = total_users_with_ai_query.join(
            User, AIAssistantInteraction.user_id == User.id
        ).filter(User.company_id == scoping_company_id)
    total_users_with_ai = total_users_with_ai_query.scalar() or 0

    total_questions = (
        _company_scoped(AIAssistantInteraction.query)
        .filter(AIAssistantInteraction.question.isnot(None))
        .count()
    )

    total_responses = (
        _company_scoped(AIAssistantInteraction.query)
        .filter(AIAssistantInteraction.response.isnot(None))
        .count()
    )

    # -----------------------------------
    # Recent AI activity
    # -----------------------------------
    recent_interactions = (
        _company_scoped(AIAssistantInteraction.query)
        .order_by(AIAssistantInteraction.timestamp.desc())
        .limit(20)
        .all()
    )

    # -----------------------------------
    # Usage by user role
    # -----------------------------------
    interactions_by_role_query = (
        db.session.query(
            User.role,
            func.count(AIAssistantInteraction.id)
        )
        .join(AIAssistantInteraction, AIAssistantInteraction.user_id == User.id)
    )
    if scoping_company_id is not None:
        interactions_by_role_query = interactions_by_role_query.filter(User.company_id == scoping_company_id)
    interactions_by_role_rows = (
        interactions_by_role_query
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
        context_query = db.session.query(
            AIAssistantInteraction.context_type,
            func.count(AIAssistantInteraction.id)
        )
        if scoping_company_id is not None:
            context_query = context_query.join(
                User, AIAssistantInteraction.user_id == User.id
            ).filter(User.company_id == scoping_company_id)
        context_rows = (
            context_query
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
        context_query = db.session.query(
            AIAssistantInteraction.assistant_type,
            func.count(AIAssistantInteraction.id)
        )
        if scoping_company_id is not None:
            context_query = context_query.join(
                User, AIAssistantInteraction.user_id == User.id
            ).filter(User.company_id == scoping_company_id)
        context_rows = (
            context_query
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
    most_active_users_query = (
        db.session.query(
            User.id,
            User.first_name,
            User.last_name,
            User.email,
            User.role,
            func.count(AIAssistantInteraction.id).label("interaction_count")
        )
        .join(AIAssistantInteraction, AIAssistantInteraction.user_id == User.id)
    )
    if scoping_company_id is not None:
        most_active_users_query = most_active_users_query.filter(User.company_id == scoping_company_id)
    most_active_users_rows = (
        most_active_users_query
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
            _company_scoped(AIAssistantInteraction.query)
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
    if (getattr(current_user, "role", "") or "").strip().lower() == "executive":
        return redirect(url_for("executive.dashboard"))

    company = Company.query.get_or_404(company_id)
    access_redirect = _ensure_company_access(company)
    if access_redirect:
        return access_redirect

    team_members = User.query.filter_by(company_id=company.id).order_by(User.created_at.desc()).all()
    company_loan_officers = _company_loan_officers(company.id)
    company_processors = _company_processors(company.id)
    invites = UserInvite.query.filter_by(company_id=company.id).order_by(UserInvite.created_at.desc()).all()
    loans = _company_loans(company.id)
    borrowers = list({
        getattr(loan, "borrower_profile_id", None): getattr(loan, "borrower_profile", None)
        for loan in loans
        if getattr(loan, "borrower_profile", None) is not None
    }.values())
    docs = LoanDocument.query.filter_by(company_id=company.id).all() if hasattr(LoanDocument, "company_id") else []
    applicant_loans = _company_recent_applicants(company.id)
    compensation_summary = _company_compensation_summary(company, loans)
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
    dashboard_preferences = _company_dashboard_settings(company)

    stats = {
        "team_members": len(team_members),
        "active_team_members": active_team_count,
        "pending_invites": len(pending_invites),
        "accepted_invites": len(accepted_invites),
        "loans": len(loans),
        "assigned_loan_officers": len([loan for loan in applicant_loans if getattr(loan, "loan_officer_id", None)]),
        "assigned_processors": len([loan for loan in applicant_loans if getattr(loan, "processor_id", None)]),
        "assigned_underwriters": len([loan for loan in applicant_loans if getattr(loan, "underwriter_id", None)]),
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
        applicant_loans=applicant_loans,
        company_loan_officers=company_loan_officers,
        company_processors=company_processors,
        recent_messages=recent_messages,
        access_requests=access_requests[:5],
        compensation_summary=compensation_summary,
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
        dashboard_preferences=dashboard_preferences,
        title=f"{company.name} Dashboard",
        active_tab="companies",
    )


@admin_bp.route("/company/<int:company_id>/applications/<int:loan_id>/assign", methods=["POST"])
@login_required
@role_required("admin_group")
def assign_company_applicant(company_id, loan_id):
    company = Company.query.get_or_404(company_id)
    access_redirect = _ensure_company_access(company)
    if access_redirect:
        return access_redirect

    loan = LoanApplication.query.get_or_404(loan_id)
    if not _loan_matches_company(loan, company):
        flash("That applicant is not part of this company workspace.", "warning")
        return redirect(url_for("admin.company_dashboard", company_id=company.id))

    available_officers = {profile.id: profile for profile in _company_loan_officers(company.id)}
    available_processors = {profile.id: profile for profile in _company_processors(company.id)}

    officer_id = _as_int(request.form.get("loan_officer_id"))
    processor_id = _as_int(request.form.get("processor_id"))

    if officer_id and officer_id not in available_officers:
        flash("Please choose a loan officer assigned to this company.", "warning")
        return redirect(url_for("admin.company_dashboard", company_id=company.id))

    if processor_id and processor_id not in available_processors:
        flash("Please choose a processor assigned to this company.", "warning")
        return redirect(url_for("admin.company_dashboard", company_id=company.id))

    if officer_id:
        target_state = loan_relevant_state(loan)
        if not loan_officer_can_serve_state(available_officers.get(officer_id), target_state):
            flash(
                f"That loan officer isn't verified/licensed in {target_state}. "
                "Verify their license for that state first, or choose a different officer.",
                "warning",
            )
            return redirect(url_for("admin.company_dashboard", company_id=company.id))

    borrower = getattr(loan, "borrower_profile", None)

    loan.loan_officer_id = officer_id or None
    loan.processor_id = processor_id or None

    if borrower is not None:
        borrower.assigned_officer_id = officer_id or None
        if officer_id:
            officer_profile = available_officers.get(officer_id)
            borrower.assigned_to = getattr(officer_profile, "user_id", None)

    db.session.commit()

    flash("Applicant assignments updated.", "success")
    return redirect(url_for("admin.company_dashboard", company_id=company.id))


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
        action_type = (request.form.get("action_type") or "profile").strip().lower()

        if action_type == "dashboard_layout":
            raw_layout = (request.form.get("dashboard_layout_json") or "").strip()
            try:
                parsed_layout = json.loads(raw_layout) if raw_layout else {}
            except (TypeError, ValueError):
                parsed_layout = {}

            merged_layout = _company_dashboard_defaults()
            if isinstance(parsed_layout, dict):
                for key in merged_layout:
                    if key in parsed_layout:
                        merged_layout[key] = bool(parsed_layout[key])

            if _company_dashboard_column_exists():
                db.session.execute(
                    text("UPDATE companies SET dashboard_settings = :payload WHERE id = :company_id"),
                    {"payload": json.dumps(merged_layout), "company_id": company.id},
                )
                db.session.commit()
                flash("Dashboard layout saved for this company workspace.", "success")
            else:
                flash("Dashboard layout migration is not active yet. Run the latest database migration to persist this across devices.", "warning")
            return redirect(url_for("admin.company_settings", company_id=company.id))

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
        dashboard_preferences=_company_dashboard_settings(company),
    )


@admin_bp.route("/company/<int:company_id>/billing", methods=["GET"])
@login_required
@role_required("admin_group")
@admin_required
def company_billing(company_id):
    company = Company.query.get_or_404(company_id)
    access_redirect = _ensure_company_access(company)
    if access_redirect:
        return access_redirect

    current_plan = (company.subscription_tier or "team").strip().lower()

    return render_template(
        "admin/company_billing.html",
        company=company,
        current_plan_label=_COMPANY_PLAN_LABELS.get(current_plan, current_plan.title()),
        self_serve_plans=_COMPANY_SELF_SERVE_PLANS,
        billing_enabled=bool(current_app.config.get("STRIPE_BILLING_ENABLED")),
    )


@admin_bp.route("/company/<int:company_id>/billing/checkout/<plan>", methods=["GET"])
@login_required
@role_required("admin_group")
@admin_required
def company_billing_checkout(company_id, plan):
    company = Company.query.get_or_404(company_id)
    access_redirect = _ensure_company_access(company)
    if access_redirect:
        return access_redirect

    plan_cfg = _COMPANY_SELF_SERVE_PLANS.get((plan or "").strip().lower())
    if not plan_cfg:
        flash("That plan isn't available for self-service checkout. Contact us to upgrade to Scale or Enterprise.", "warning")
        return redirect(url_for("admin.company_billing", company_id=company.id))

    if not current_app.config.get("STRIPE_BILLING_ENABLED"):
        flash("Billing is not enabled on this server.", "warning")
        return redirect(url_for("admin.company_billing", company_id=company.id))

    price_id = current_app.config.get(plan_cfg["price_config_key"], "")
    if not price_id:
        current_app.logger.error(
            "company_billing_checkout: no price ID configured for plan=%s key=%s",
            plan, plan_cfg["price_config_key"],
        )
        flash("This plan is not currently available. Please contact us.", "danger")
        return redirect(url_for("admin.company_billing", company_id=company.id))

    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]

    base = request.host_url.rstrip("/")
    success_url = base + url_for("admin.company_billing", company_id=company.id) + "?checkout=success"
    cancel_url = base + url_for("admin.company_billing", company_id=company.id)

    session_kwargs = dict(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        metadata={"company_id": str(company.id), "company_plan": plan.lower()},
        success_url=success_url,
        cancel_url=cancel_url,
    )
    if company.stripe_customer_id:
        session_kwargs["customer"] = company.stripe_customer_id
    else:
        session_kwargs["customer_email"] = current_user.email

    try:
        session = stripe.checkout.Session.create(**session_kwargs)
    except stripe.error.StripeError as exc:
        current_app.logger.error("company_billing_checkout stripe error plan=%s: %s", plan, exc)
        flash("Could not start checkout. Please try again.", "danger")
        return redirect(url_for("admin.company_billing", company_id=company.id))

    return redirect(session.url, code=303)


@admin_bp.route("/billing-hold", methods=["GET"])
@login_required
def billing_hold():
    company = Company.query.get(getattr(current_user, "company_id", None))
    reason = company_billing_hold_reason(company) if company else None

    if not reason:
        # Nothing (or nothing anymore) to hold on -- send them back home
        # instead of showing a stale/incorrect suspension page.
        return redirect(_admin_home_endpoint())

    return render_template(
        "admin/billing_hold.html",
        company=company,
        reason=reason,
        is_company_admin=_is_company_admin(current_user),
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
@role_required("platform_admin", "master_admin", "lending_admin")
def licensing_applications():
    applications = BusinessInquiry.query.order_by(
        BusinessInquiry.created_at.desc()
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
@role_required("platform_admin", "master_admin", "lending_admin")
def contact_license_application(app_id):
    app_row = BusinessInquiry.query.get_or_404(app_id)

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
@role_required("platform_admin", "master_admin", "lending_admin")
def approve_license_application(app_id):
    app_row = BusinessInquiry.query.get_or_404(app_id)

    if app_row.status == "approved":
        flash("This application was already approved.", "info")
        return redirect(url_for("admin.licensing_applications"))

    # Only real license applications go through the full company/invite
    # workflow. Contact/challenge/referral/feedback entries just get
    # marked accepted for record-keeping -- there's no company to create.
    if app_row.inquiry_type != "license_application":
        app_row.status = "approved"
        db.session.commit()
        flash("Marked as accepted.", "success")
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
        notes=f"Approved from BusinessInquiry #{app_row.id}",
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
@role_required("platform_admin", "master_admin", "lending_admin")
def decline_license_application(app_id):
    app_row = BusinessInquiry.query.get_or_404(app_id)

    if app_row.status == "approved":
        flash("Approved applications cannot be declined here.", "warning")
        return redirect(url_for("admin.licensing_applications"))

    app_row.status = "declined"
    db.session.commit()

    flash("License application declined.", "success")
    return redirect(url_for("admin.licensing_applications"))


@admin_bp.route("/licensing/applications/<int:app_id>/resend-invite", methods=["POST"])
@login_required
@role_required("platform_admin", "master_admin", "lending_admin")
def resend_license_application_invite(app_id):
    app_row = BusinessInquiry.query.get_or_404(app_id)

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
    if _is_company_admin(current_user) and getattr(user, "company_id", None) != getattr(current_user, "company_id", None):
        flash("You can only manage users from your own company.", "warning")
        return redirect(url_for("admin.company_dashboard", company_id=current_user.company_id))

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
    if _is_company_admin(current_user) and getattr(user, "company_id", None) != getattr(current_user, "company_id", None):
        flash("You can only manage users from your own company.", "warning")
        return redirect(url_for("admin.company_dashboard", company_id=current_user.company_id))

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
    # Blocking an entire company workspace is a platform-operator action
    # (e.g. non-payment), not something a company's own admin should ever
    # trigger — even against their own company. Unlike block_user/unblock_user
    # just above (which correctly scope company-admins to their own
    # company's users), this route had no ownership check at all: any
    # company-level "admin" could block or unblock *any other company's*
    # entire workspace by ID.
    if not _is_full_admin(current_user):
        abort(403)

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
    if not _is_full_admin(current_user):
        abort(403)

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


# ─────────────────────────────────────────────────────────────────────────────
# AI EMAIL ASSISTANT
# ─────────────────────────────────────────────────────────────────────────────

@admin_bp.route("/ai-email-assistant", methods=["GET"])
@login_required
@role_required("admin_group")
def ai_email_assistant():
    """AI Email Assistant — generate and send outreach emails for partner leads and requests."""
    from LoanMVP.models.partner_models import ExternalPartnerLead, PartnerConnectionRequest

    external_leads_raw = (
        ExternalPartnerLead.query
        .filter(ExternalPartnerLead.invite_status.in_(["new", "saved"]))
        .order_by(ExternalPartnerLead.created_at.desc())
        .limit(30)
        .all()
    )

    open_requests_raw = (
        PartnerConnectionRequest.query
        .filter(PartnerConnectionRequest.status.in_(["awaiting_match", "pending"]))
        .filter(PartnerConnectionRequest.source.in_(["external", "fallback_search"]))
        .order_by(PartnerConnectionRequest.created_at.desc())
        .limit(30)
        .all()
    )

    # Serialize to plain dicts — SQLAlchemy models are not JSON-serializable
    external_leads = [
        {
            "id":            l.id,
            "name":          l.name or "",
            "business_name": l.business_name or "",
            "category":      l.category or "",
            "address":       l.address or "",
            "city":          l.city or "",
            "state":         l.state or "",
            "zip_code":      l.zip_code or "",
            "invite_status": l.invite_status or "",
            "created_at":    l.created_at.strftime("%b %d, %Y") if l.created_at else "",
        }
        for l in external_leads_raw
    ]

    open_requests = [
        {
            "id":       r.id,
            "title":    r.title or "",
            "category": r.category or "",
            "status":   r.status or "",
            "message":  r.message or "",
            "budget":   float(r.budget) if r.budget else None,
            "timeline": r.timeline or "",
            "created_at": r.created_at.strftime("%b %d, %Y") if r.created_at else "",
            "lead_name": (r.external_partner_lead.name or r.external_partner_lead.business_name or "")
                         if r.external_partner_lead else "",
        }
        for r in open_requests_raw
    ]

    return render_template(
        "admin/ai_email_assistant.html",
        external_leads=external_leads,
        open_requests=open_requests,
    )


@admin_bp.route("/ai/generate-email", methods=["POST"])
@login_required
@role_required("admin_group")
def ai_generate_email():
    """AJAX: AI drafts an email given a type + context payload."""
    from openai import OpenAI

    data = request.get_json(silent=True) or {}
    email_type    = (data.get("email_type") or "partner_invite").strip()
    context       = data.get("context") or {}
    custom_prompt = (data.get("custom_prompt") or "").strip()

    partner_name     = (context.get("partner_name") or "").strip()
    partner_address  = (context.get("partner_address") or "").strip()
    partner_category = (context.get("partner_category") or "contractor").strip()
    investor_message = (context.get("investor_message") or "").strip()
    property_title   = (context.get("property_title") or "").strip()
    budget           = context.get("budget")
    timeline         = (context.get("timeline") or "").strip()
    investor_name    = (context.get("investor_name") or "a Ravlo investor").strip()

    if email_type == "partner_invite":
        system = (
            "You are the outreach coordinator for Ravlo, a real estate investment platform that "
            "connects investors with local contractors, realtors, and inspectors. "
            "Your tone is professional, warm, and direct. Emails should be under 200 words. "
            "Never mention internal platform details or use placeholder text. "
            "Always sign off as 'The Ravlo Team'."
        )
        try:
            budget_line = f"\n- Budget: ${float(budget):,.0f}" if budget else ""
        except (TypeError, ValueError):
            budget_line = f"\n- Budget: {budget}" if budget else ""
        timeline_line = f"\n- Timeline: {timeline}" if timeline else ""
        prompt = (
            f"Write an outreach email inviting {partner_name or 'a local business'} to join the Ravlo partner network.\n\n"
            f"Context:\n"
            f"- Business name: {partner_name or 'unknown'}\n"
            f"- Category: {partner_category}\n"
            f"- Location: {partner_address or 'local area'}\n"
            f"- One of our investors is specifically looking to work with them\n"
            f"- Project: {property_title or 'a local real estate project'}\n"
            f"- Investor note: {investor_message or 'Looking for a reliable local professional'}"
            f"{budget_line}{timeline_line}\n\n"
            f"Format:\n"
            f"Line 1 — Subject: <subject here>\n"
            f"Line 2 — blank\n"
            f"Lines 3+ — email body\n\n"
            f"Do not use any placeholder brackets like [Name]."
        )

    elif email_type == "investor_update":
        system = (
            "You are a client success manager at Ravlo. "
            "Write warm, professional status updates to investors. "
            "Keep it under 150 words. Sign off as 'The Ravlo Team'."
        )
        prompt = (
            f"Write a brief update email to {investor_name} about their partner request.\n\n"
            f"Context:\n"
            f"- They requested a {partner_category}\n"
            f"- Partner they selected: {partner_name or 'a local professional'}\n"
            f"- Project: {property_title or 'their real estate project'}\n"
            f"- Update: Ravlo has reached out to this partner and is facilitating the connection\n\n"
            f"Format:\n"
            f"Line 1 — Subject: <subject here>\n"
            f"Line 2 — blank\n"
            f"Lines 3+ — email body"
        )

    elif email_type == "custom":
        if not custom_prompt:
            return jsonify({"status": "error", "message": "Custom prompt is required."}), 400
        system = (
            "You are an AI writing assistant for Ravlo, a real estate investment platform. "
            "Write professional, concise emails. "
            "Always put the subject on line 1 (format: 'Subject: ...'). "
            "Sign off as 'The Ravlo Team'. Never use placeholder brackets."
        )
        prompt = custom_prompt

    else:
        return jsonify({"status": "error", "message": "Unknown email type."}), 400

    try:
        ai_client = OpenAI()
        ai_model = current_app.config.get("AI_MODEL") or "gpt-4o-mini"
        response = ai_client.chat.completions.create(
            model=ai_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.6,
            max_tokens=700,
        )
        raw = (response.choices[0].message.content or "").strip()

        # Split subject from body
        subject = ""
        body = raw
        lines = raw.split("\n")
        if lines and lines[0].lower().startswith("subject:"):
            subject = lines[0][8:].strip()
            body = "\n".join(lines[2:]).strip() if len(lines) > 2 else ""

        return jsonify({"status": "ok", "subject": subject, "body": body})

    except Exception as exc:
        current_app.logger.error("[ai-generate-email] %s", exc)
        return jsonify({"status": "error", "message": "AI generation failed. Please try again."}), 500


@admin_bp.route("/ai/send-email", methods=["POST"])
@login_required
@role_required("admin_group")
def ai_send_email():
    """AJAX: send an AI-drafted email and update the related lead/request status."""
    from LoanMVP.models.partner_models import ExternalPartnerLead, PartnerConnectionRequest

    data       = request.get_json(silent=True) or {}
    to_email   = (data.get("to_email") or "").strip()
    subject    = (data.get("subject") or "").strip()
    body       = (data.get("body") or "").strip()
    lead_id    = data.get("lead_id")
    request_id = data.get("request_id")

    if not to_email or "@" not in to_email:
        return jsonify({"status": "error", "message": "A valid recipient email is required."}), 400
    if not subject:
        return jsonify({"status": "error", "message": "Subject line cannot be empty."}), 400
    if not body:
        return jsonify({"status": "error", "message": "Email body cannot be empty."}), 400

    safe_body = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
    html = (
        f"<div style='font-family:sans-serif;line-height:1.6;max-width:600px;'>"
        f"{safe_body}"
        f"</div>"
    )

    try:
        send_email(to=to_email, subject=subject, html_body=html, text_body=body)
    except Exception as exc:
        current_app.logger.error("[ai-send-email] %s", exc)
        return jsonify({"status": "error", "message": "Email delivery failed. Check mail configuration."}), 500

    # Update lead/request status after successful send
    try:
        if lead_id:
            lead = ExternalPartnerLead.query.get(int(lead_id))
            if lead and lead.invite_status in ("new", "saved"):
                lead.invite_status = "invited"
                db.session.commit()
        if request_id:
            req = PartnerConnectionRequest.query.get(int(request_id))
            if req and req.status == "awaiting_match":
                req.status = "pending"
                db.session.commit()
    except Exception as db_exc:
        db.session.rollback()
        current_app.logger.error("[ai-send-email] status update failed: %s", db_exc)

    return jsonify({"status": "ok", "message": "Email sent successfully."})


# ─────────────────────────────────────────────────────────────────────────────
# UNIVERSAL AI CHAT  (login_required only — all roles may use this)
# ─────────────────────────────────────────────────────────────────────────────

@admin_bp.route("/ai/chat", methods=["POST"])
@login_required
def ai_chat():
    """Universal conversational AI — adapts system prompt to the user's role."""
    from openai import OpenAI

    data    = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    raw_history = data.get("history")
    history = raw_history if isinstance(raw_history, list) else []
    image_data_url = (data.get("image") or "").strip()

    if not message and not image_data_url:
        return jsonify({"ok": False, "reply": "Please say something."}), 400

    if len(message) > 4000:
        return jsonify({"ok": False, "reply": "Message too long."}), 400

    if image_data_url and not image_data_url.startswith("data:image/"):
        return jsonify({"ok": False, "reply": "That doesn't look like an image."}), 400

    # A generous but bounded cap — base64 images can get large; this keeps
    # the request payload sane without needing a separate upload endpoint.
    if image_data_url and len(image_data_url) > 12_000_000:
        return jsonify({"ok": False, "reply": "That photo is too large. Try a smaller image."}), 400

    role = (getattr(current_user, "role", "") or "").lower()
    name = getattr(current_user, "first_name", None) or getattr(current_user, "username", None) or "there"

    if role in ("admin", "platform_admin", "master_admin", "lending_admin", "executive"):
        system = (
            f"You are Ravlo AI — the intelligent assistant for Ravlo platform administrators and executives. "
            f"You help with partner outreach strategy, investor request management, platform operations, team oversight, "
            f"deal pipeline visibility, and business growth. "
            f"When the user asks about generating emails, guide them to the AI Email Assistant (/admin/ai-email-assistant). "
            f"When they ask about partner leads, mention the partner queue. "
            f"Be concise, strategic, and action-oriented. Suggest specific next steps where relevant. "
            f"You are speaking with {name}."
        )
    elif role == "investor":
        system = (
            f"You are Ravlo AI — an intelligent real estate investment assistant. "
            f"You help investors analyze deals, evaluate rehab budgets, find contractors and realtors, "
            f"understand market conditions, and navigate the Ravlo platform. "
            f"Be concise, data-grounded, and practical. Focus on deal underwriting, strategy, and execution. "
            f"You are speaking with {name}."
        )
    else:
        system = (
            f"You are Ravlo AI — a professional assistant for the Ravlo real estate platform. "
            f"Help the user with any platform questions, workflow guidance, or real estate topics. "
            f"Be concise and helpful. You are speaking with {name}."
        )

    # Build messages with last 12 turns of history (cap each turn at 2000 chars)
    messages = [{"role": "system", "content": system}]
    for turn in history[-12:]:
        if not isinstance(turn, dict):
            continue
        r = (turn.get("role") or "").strip()
        c = (turn.get("content") or "").strip()[:2000]
        if r in ("user", "assistant") and c:
            messages.append({"role": r, "content": c})
    if image_data_url:
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": message or "What do you see in this photo?"},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ],
        })
    else:
        messages.append({"role": "user", "content": message})

    try:
        ai_client = OpenAI()
        ai_model  = current_app.config.get("AI_MODEL") or "gpt-4o-mini"
        response  = ai_client.chat.completions.create(
            model=ai_model,
            messages=messages,
            temperature=0.65,
            max_tokens=500,
        )
        reply = (response.choices[0].message.content or "").strip()

        try:
            from LoanMVP.services.ravlo_memory_service import log_ai_exchange
            log_ai_exchange(
                module="ravlo_ai_chat",
                feature="image_chat" if image_data_url else "chat",
                prompt=message[:4000],
                response=reply,
                user_id=current_user.id,
                role_view=role,
                provider="openai",
                model=ai_model,
                metadata={"has_image": bool(image_data_url)},
            )
        except Exception:
            pass

        return jsonify({"ok": True, "reply": reply})
    except Exception as exc:
        current_app.logger.error("[ai-chat] %s", exc)
        return jsonify({"ok": False, "reply": "I ran into an issue. Please try again."}), 500
