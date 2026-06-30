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
from LoanMVP.models.contractor_models import ContractorBidOpportunity
from LoanMVP.models.company_finance_models import CMFinanceEntry
from LoanMVP.routes import admin as admin_routes

_JAMAINE_EMAIL = "jamaine.caughman@ravlohq.com"

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
    from datetime import timedelta
    from LoanMVP.models.property import SavedProperty
    from LoanMVP.models.partner_models import PartnerConnectionRequest, ExternalPartnerLead
    from LoanMVP.models.training_models import UserCourseUnlock
    from LoanMVP.models.discovery_models import DiscoveryEvent

    access_redirect = _ensure_executive_access()
    if access_redirect:
        return access_redirect

    if (getattr(current_user, "email", "") or "").strip().lower() == _JAMAINE_EMAIL:
        return redirect(url_for("executive.construction_center"))

    company  = _executive_company()
    all_users = _executive_user_query().all()
    scoped_loans = _executive_loan_query()

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday   = today_start - timedelta(days=1)

    # ── Business metrics ─────────────────────────────────────────────
    total_users   = len(all_users)
    active_today  = sum(1 for u in all_users if u.last_login and u.last_login >= today_start)
    free_trials   = sum(1 for u in all_users if u.trial_ends_at and u.trial_ends_at > now)
    paid_members  = sum(1 for u in all_users
                        if (u.subscription or "").lower() not in ("free", "core", "") and not u.trial_ends_at)
    new_overnight = sum(1 for u in all_users if u.created_at and u.created_at >= yesterday)

    # ── Investor OS ───────────────────────────────────────────────────
    saved_props   = SavedProperty.query.count()
    new_saves_today = SavedProperty.query.filter(SavedProperty.created_at >= today_start).count()

    # ── Lending OS pipeline ───────────────────────────────────────────
    def _stage_count(stage_fragment):
        return scoped_loans.filter(
            func.lower(LoanApplication.milestone_stage).contains(stage_fragment.lower())
        ).count()

    loan_pipeline = {
        "Applications Started": _stage_count("application"),
        "Processing":           _stage_count("processing"),
        "Underwriting":         _stage_count("underwriting"),
        "Conditions":           _stage_count("condition"),
        "Clear to Close":       _stage_count("clear"),
        "Funded":               _stage_count("funded"),
    }
    total_loans = scoped_loans.count()

    # ── Academy ───────────────────────────────────────────────────────
    academy_students  = UserCourseUnlock.query.with_entities(UserCourseUnlock.user_id).distinct().count()
    academy_graduates = UserCourseUnlock.query.count()

    # ── Partner Network ───────────────────────────────────────────────
    partner_cats = ["Realtor", "Contractor", "Designer", "Architect",
                    "Property Manager", "Lender", "Inspector"]
    partner_breakdown = {}
    for cat in partner_cats:
        partner_breakdown[cat] = PartnerConnectionRequest.query.filter(
            func.lower(PartnerConnectionRequest.category).contains(cat.lower())
        ).count()

    req_waiting   = PartnerConnectionRequest.query.filter(
        PartnerConnectionRequest.status.in_(["pending", "awaiting_match"])).count()
    req_accepted  = PartnerConnectionRequest.query.filter_by(status="accepted").count()
    req_completed = PartnerConnectionRequest.query.filter_by(status="completed").count()

    # ── Attention center ──────────────────────────────────────────────
    loans_need_review = scoped_loans.filter(
        func.lower(LoanApplication.status).in_(["pending", "stalled", "needs review"])
    ).count()
    partner_waiting = req_waiting
    challenge_signups = sum(1 for u in all_users
                            if u.trial_ends_at and u.trial_ends_at > now
                            and (u.role or "").lower() == "investor")
    enterprise_leads = LicenseApplication.query.filter(
        LicenseApplication.status == "new"
    ).count()

    # ── Lives Changed (mission metrics) ──────────────────────────────
    lives = {
        "properties_saved":   saved_props,
        "loans_closed":       loan_pipeline["Funded"],
        "projects_completed": req_completed,
        "academy_graduates":  academy_graduates,
    }

    # ── Discovery / Who's watching Ravlo ─────────────────────────────
    try:
        _discovery_rows = (
            db.session.query(DiscoveryEvent.source, func.count(DiscoveryEvent.id))
            .filter(DiscoveryEvent.created_at >= today_start)
            .group_by(DiscoveryEvent.source)
            .all()
        )
        discovery_today = {row[0]: row[1] for row in _discovery_rows}
        discovery_feed = (
            DiscoveryEvent.query
            .order_by(DiscoveryEvent.created_at.desc())
            .limit(20)
            .all()
        )
    except Exception as exc:
        db.session.rollback()
        discovery_today = {}
        discovery_feed = []
        current_app.logger.warning("discovery_events query failed (table may not exist yet): %s", exc)

    # ── Platform health ───────────────────────────────────────────────
    critical_issues = loans_need_review + enterprise_leads
    mission_status = "On Track" if critical_issues < 5 else "Needs Attention"
    mission_color  = "#2cb67d" if critical_issues < 5 else "#f59e0b"

    # ── User growth for sparkline ─────────────────────────────────────
    user_growth_labels, user_growth_series = _monthly_series(all_users, "created_at", 6)
    loan_records = scoped_loans.all()
    loan_volume_labels, loan_volume_series = _monthly_series(loan_records, "created_at", 6)

    first_name = getattr(current_user, "first_name", None) or \
                 getattr(current_user, "username", None) or "there"

    return render_template(
        "executive/dashboard.html",
        company=company,
        first_name=first_name,
        # business
        total_users=total_users,
        active_today=active_today,
        free_trials=free_trials,
        paid_members=paid_members,
        new_overnight=new_overnight,
        # investor
        saved_props=saved_props,
        new_saves_today=new_saves_today,
        # lending
        loan_pipeline=loan_pipeline,
        total_loans=total_loans,
        # academy
        academy_students=academy_students,
        academy_graduates=academy_graduates,
        # partners
        partner_breakdown=partner_breakdown,
        req_waiting=req_waiting,
        req_accepted=req_accepted,
        req_completed=req_completed,
        # attention
        loans_need_review=loans_need_review,
        partner_waiting=partner_waiting,
        challenge_signups=challenge_signups,
        enterprise_leads=enterprise_leads,
        # lives
        lives=lives,
        # mission
        mission_status=mission_status,
        mission_color=mission_color,
        # charts
        user_growth_labels=user_growth_labels,
        user_growth_series=user_growth_series,
        loan_volume_labels=loan_volume_labels,
        loan_volume_series=loan_volume_series,
        # discovery
        discovery_today=discovery_today,
        discovery_feed=discovery_feed,
    )


@executive_bp.route("/ai-briefing", methods=["GET"])
@login_required
def ai_briefing():
    """AJAX: Generate a real-time AI executive briefing."""
    from LoanMVP.extensions import csrf
    from openai import OpenAI
    from LoanMVP.models.property import SavedProperty
    from LoanMVP.models.partner_models import PartnerConnectionRequest

    access_redirect = _ensure_executive_access()
    if access_redirect:
        from flask import jsonify
        return jsonify({"briefing": "Access restricted."}), 403

    from flask import jsonify
    from datetime import timedelta

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday   = today_start - timedelta(days=1)
    all_users   = _executive_user_query().all()
    scoped_loans = _executive_loan_query()

    new_overnight  = sum(1 for u in all_users if u.created_at and u.created_at >= yesterday)
    active_today   = sum(1 for u in all_users if u.last_login and u.last_login >= today_start)
    saves_today    = SavedProperty.query.filter(SavedProperty.created_at >= today_start).count()
    loans_total    = scoped_loans.count()
    req_waiting    = PartnerConnectionRequest.query.filter(
        PartnerConnectionRequest.status.in_(["pending", "awaiting_match"])).count()

    first_name = getattr(current_user, "first_name", None) or \
                 getattr(current_user, "username", None) or "there"

    prompt = (
        f"You are the AI chief of staff for Ravlo, a real estate platform. "
        f"Write a concise executive morning briefing for {first_name}. "
        f"Keep it to 4-6 bullet points. Be direct, mission-focused, and end with ONE specific recommendation. "
        f"Tone: warm but strategic. No fluff.\n\n"
        f"Today's data:\n"
        f"- {new_overnight} new accounts created since yesterday\n"
        f"- {active_today} users active today so far\n"
        f"- {saves_today} properties saved today\n"
        f"- {loans_total} total loan files in the system\n"
        f"- {req_waiting} partner connection requests waiting\n\n"
        f"Format: bullet points (use •), then 'Recommendation:' on its own line at the end."
    )

    try:
        client  = OpenAI()
        model   = current_app.config.get("AI_MODEL") or "gpt-4o-mini"
        resp    = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=350,
        )
        briefing = resp.choices[0].message.content.strip()
    except Exception as exc:
        current_app.logger.warning("[ai-briefing] %s", exc)
        briefing = (
            f"• {new_overnight} new accounts joined since yesterday\n"
            f"• {active_today} users active on the platform today\n"
            f"• {saves_today} properties saved by investors today\n"
            f"• {loans_total} total loan files in the system\n"
            f"• {req_waiting} partner connection requests waiting for a match\n\n"
            f"Recommendation: Review open partner requests and assign them before end of day."
        )

    return jsonify({"briefing": briefing, "first_name": first_name})


# ─────────────────────────────────────────────────────────────────────────────
# JAMAINE — CONSTRUCTION COMMAND CENTER
# ─────────────────────────────────────────────────────────────────────────────

@executive_bp.route("/construction")
@login_required
def construction_center():
    access_redirect = _ensure_executive_access()
    if access_redirect:
        return access_redirect

    from datetime import date, timedelta
    from LoanMVP.models.partner_models import PartnerConnectionRequest
    from LoanMVP.models.crm_models import Partner

    now        = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # ── Construction bid pipeline ────────────────────────────────────
    partner = Partner.query.filter_by(
        user_id=current_user.id
    ).first() or Partner.query.filter(
        func.lower(Partner.company) == "caughman mason construction"
    ).first()

    bid_opps   = []
    inbound_jobs = []
    if partner:
        bid_opps = (
            ContractorBidOpportunity.query
            .filter_by(partner_id=partner.id)
            .order_by(ContractorBidOpportunity.created_at.desc())
            .limit(20).all()
        )
        inbound_jobs = (
            PartnerConnectionRequest.query
            .filter_by(partner_id=partner.id)
            .filter(PartnerConnectionRequest.status.in_(["pending", "awaiting_match"]))
            .order_by(PartnerConnectionRequest.created_at.desc())
            .limit(10).all()
        )

    active_bids    = [o for o in bid_opps if o.status in ("reviewing", "bid_submitted")]
    won_bids       = [o for o in bid_opps if o.status == "won"]
    value_in_play  = sum(o.estimated_value or 0 for o in active_bids)

    # ── Finance this month (construction) ───────────────────────────
    month_entries = CMFinanceEntry.query.filter(
        CMFinanceEntry.division == "construction",
        CMFinanceEntry.entry_date >= month_start.date(),
    ).all()
    month_income  = sum(e.amount for e in month_entries if e.entry_type == "income")
    month_expense = sum(e.amount for e in month_entries if e.entry_type == "expense")

    # ── Ravlo OS snapshot (ownership view) ──────────────────────────
    all_users    = _executive_user_query().all()
    scoped_loans = _executive_loan_query()
    total_users  = len(all_users)
    total_loans  = scoped_loans.count()
    req_waiting  = PartnerConnectionRequest.query.filter(
        PartnerConnectionRequest.status.in_(["pending", "awaiting_match"])
    ).count()

    return render_template(
        "executive/construction_center.html",
        partner         = partner,
        bid_opps        = bid_opps,
        active_bids     = active_bids,
        won_bids        = won_bids,
        value_in_play   = value_in_play,
        inbound_jobs    = inbound_jobs,
        month_income    = month_income,
        month_expense   = month_expense,
        month_net       = month_income - month_expense,
        total_users     = total_users,
        total_loans     = total_loans,
        req_waiting     = req_waiting,
        now             = now,
    )


@executive_bp.route("/construction/ai", methods=["POST"])
@login_required
def construction_ai():
    """AI Office Assistant for Jamaine — handles admin so he can stay in the field."""
    from flask import jsonify
    from openai import OpenAI

    access_redirect = _ensure_executive_access()
    if access_redirect:
        return jsonify({"ok": False, "reply": "Access restricted."}), 403

    message = (request.json or {}).get("message", "").strip() if request.is_json \
        else (request.form.get("message") or "").strip()
    if not message:
        return jsonify({"ok": False, "reply": "No message received."})

    system_prompt = (
        "You are the AI Office Assistant for Caughman Mason Construction, "
        "a general contracting company based in Tampa, FL. "
        "Your job is to handle all the office and admin work so the operator can stay focused on field work. "
        "You can help with: drafting invoices, bid follow-up emails, expense logging reminders, "
        "scheduling notes, proposal outlines, subcontractor agreements, permit checklists, "
        "safety notes, client updates, and any other admin task. "
        "Be direct, practical, and field-friendly. No fluff. "
        "When drafting documents, make them professional and ready to use. "
        "Always sign off as 'Caughman Mason Construction' — never use personal names. "
        "If the request is unclear, ask one short clarifying question."
    )

    try:
        client = OpenAI()
        model  = current_app.config.get("AI_MODEL") or "gpt-4o-mini"
        resp   = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": message},
            ],
            temperature=0.55,
            max_tokens=600,
        )
        reply = resp.choices[0].message.content.strip()
        return jsonify({"ok": True, "reply": reply})
    except Exception as exc:
        current_app.logger.warning("[construction-ai] %s", exc)
        return jsonify({"ok": False, "reply": "Office assistant is unavailable right now. Try again in a moment."})


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
