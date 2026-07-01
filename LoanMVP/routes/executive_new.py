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
from LoanMVP.models.contractor_models import ContractorBidOpportunity, ConstructionProject
from LoanMVP.models.company_finance_models import CMFinanceEntry, UserEmailConnection
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
        try:
            bid_opps = (
                ContractorBidOpportunity.query
                .filter_by(partner_id=partner.id)
                .order_by(ContractorBidOpportunity.created_at.desc())
                .limit(20).all()
            )
        except Exception as exc:
            db.session.rollback()
            current_app.logger.warning("[construction_center] bid table not ready: %s", exc)
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
    try:
        month_entries = CMFinanceEntry.query.filter(
            CMFinanceEntry.division == "construction",
            CMFinanceEntry.entry_date >= month_start.date(),
        ).all()
        month_income  = sum(e.amount for e in month_entries if e.entry_type == "income")
        month_expense = sum(e.amount for e in month_entries if e.entry_type == "expense")
    except Exception as exc:
        db.session.rollback()
        current_app.logger.warning("[construction_center] finance table not ready: %s", exc)
        month_income = month_expense = 0.0

    # ── Ravlo OS snapshot (ownership view) ──────────────────────────
    all_users    = _executive_user_query().all()
    scoped_loans = _executive_loan_query()
    total_users  = len(all_users)
    total_loans  = scoped_loans.count()
    req_waiting  = PartnerConnectionRequest.query.filter(
        PartnerConnectionRequest.status.in_(["pending", "awaiting_match"])
    ).count()

    # ── Email connection status (table may not exist yet) ──────────
    try:
        email_conn = UserEmailConnection.query.filter_by(user_id=current_user.id).first()
    except Exception:
        db.session.rollback()
        email_conn = None

    # ── Construction projects (needed for morning priorities) ────────
    cc_projects = []
    if partner:
        try:
            cc_projects = ConstructionProject.query.filter_by(partner_id=partner.id).all()
        except Exception as exc:
            db.session.rollback()
            current_app.logger.warning("[construction_center] projects not ready: %s", exc)

    # ── Morning command center priorities ────────────────────────────
    cc_email = (getattr(current_user, "email", "") or "").strip().lower()
    if cc_email == "sandra@ravlohq.com":
        cc_persona  = "sandra"
        cc_greeting = "Sandra"
    elif cc_email == _JAMAINE_EMAIL:
        cc_persona  = "jamaine"
        cc_greeting = "Jamaine"
    else:
        cc_persona  = "letoya"
        cc_greeting = getattr(current_user, "first_name", None) or "Letoya"
    priorities = _morning_priorities(bid_opps, cc_projects, cc_persona)

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
        email_conn      = email_conn,
        now             = now,
        priorities      = priorities,
        greeting        = cc_greeting,
        persona         = cc_persona,
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


@executive_bp.route("/construction/morning-brief", methods=["POST"])
@login_required
def construction_morning_brief():
    """AJAX: AI-generated construction-focused daily briefing with real project data."""
    from flask import jsonify
    from datetime import timedelta
    from openai import OpenAI
    from LoanMVP.models.partner_models import PartnerConnectionRequest
    from LoanMVP.models.crm_models import Partner

    access_redirect = _ensure_executive_access()
    if access_redirect:
        return jsonify({"ok": False, "brief": "Access restricted."}), 403

    now         = datetime.utcnow()
    today       = now.date()
    week_out    = today + timedelta(days=7)
    five_days_ago = now - timedelta(days=5)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    partner = Partner.query.filter_by(user_id=current_user.id).first() \
        or Partner.query.filter(
            func.lower(Partner.company) == "caughman mason construction"
        ).first()

    # Bid data
    upcoming_deadlines = []
    follow_up_needed   = []
    inbound_count      = 0
    if partner:
        bids = ContractorBidOpportunity.query.filter_by(partner_id=partner.id).all()
        for b in bids:
            if b.bid_deadline and b.bid_deadline.date() <= week_out and b.status in ("reviewing",):
                upcoming_deadlines.append(b)
            if b.status == "bid_submitted" and b.updated_at and b.updated_at < five_days_ago:
                follow_up_needed.append(b)
        inbound_count = PartnerConnectionRequest.query.filter_by(partner_id=partner.id).filter(
            PartnerConnectionRequest.status.in_(["pending", "awaiting_match"])
        ).count()

    # Finance snapshot
    month_entries = CMFinanceEntry.query.filter(
        CMFinanceEntry.division == "construction",
        CMFinanceEntry.entry_date >= month_start.date(),
    ).all()
    month_income  = sum(e.amount for e in month_entries if e.entry_type == "income")
    month_expense = sum(e.amount for e in month_entries if e.entry_type == "expense")
    month_net     = month_income - month_expense

    # Build context for AI
    deadline_lines = "\n".join(
        f"  - {b.project_name} (deadline: {b.bid_deadline.strftime('%b %d') if b.bid_deadline else 'soon'}"
        f"{', est $' + '{:,.0f}'.format(b.estimated_value) if b.estimated_value else ''})"
        for b in upcoming_deadlines
    ) or "  None this week"

    followup_lines = "\n".join(
        f"  - {b.project_name} — bid submitted {(now - b.updated_at).days} days ago, no update"
        for b in follow_up_needed
    ) or "  None outstanding"

    day_name = now.strftime("%A")
    date_str = now.strftime("%B %d, %Y")

    prompt = (
        f"You are the AI Office for Caughman Mason Construction based in Tampa, FL. "
        f"Generate a concise, practical morning briefing for today ({day_name}, {date_str}). "
        f"Be direct and construction-focused. Tone: supportive but action-oriented — like a foreman's morning huddle. "
        f"No fluff. Use plain language, not corporate speak.\n\n"
        f"TODAY'S REAL DATA:\n"
        f"Bids with deadlines this week:\n{deadline_lines}\n\n"
        f"Bids needing follow-up (submitted >5 days ago):\n{followup_lines}\n\n"
        f"Inbound job requests from investors: {inbound_count} waiting\n"
        f"Construction P&L this month: income ${month_income:,.0f}, expenses ${month_expense:,.0f}, net ${month_net:,.0f}\n\n"
        f"FORMAT (use exactly this structure):\n"
        f"GOOD MORNING — [one short motivational line specific to today's situation]\n\n"
        f"TODAY'S PRIORITIES:\n"
        f"• [priority 1 — be specific, name actual bids/jobs if relevant]\n"
        f"• [priority 2]\n"
        f"• [priority 3, optional]\n\n"
        f"FOLLOW-UPS TO MAKE:\n"
        f"• [specific follow-up action, naming the project]\n\n"
        f"MEETING SUGGESTION:\n"
        f"[One specific meeting to schedule today and why — subcontractor, client, walk-through, etc.]\n\n"
        f"FINANCIAL NOTE:\n"
        f"[One sentence on the month's P&L and what it means for this week's decisions.]"
    )

    try:
        client  = OpenAI()
        model   = current_app.config.get("AI_MODEL") or "gpt-4o-mini"
        resp    = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=500,
        )
        brief = resp.choices[0].message.content.strip()
    except Exception as exc:
        current_app.logger.warning("[morning-brief] %s", exc)
        brief = (
            f"GOOD MORNING — Let's get Tampa built.\n\n"
            f"TODAY'S PRIORITIES:\n"
            f"• Review any bids with deadlines this week — {len(upcoming_deadlines)} need attention\n"
            f"• Follow up on submitted bids — {len(follow_up_needed)} waiting on a response\n"
            f"• Check inbound job requests — {inbound_count} waiting in your inbox\n\n"
            f"FINANCIAL NOTE:\n"
            f"Construction this month: ${month_income:,.0f} in, ${month_expense:,.0f} out, ${month_net:,.0f} net."
        )

    return jsonify({"ok": True, "brief": brief, "date": date_str})


# ─────────────────────────────────────────────────────────────────────────────
# GMAIL OAUTH — email connection for the AI Office Assistant
# ─────────────────────────────────────────────────────────────────────────────

def _gmail_flow():
    """Build the Google OAuth2 flow — returns None if creds not configured."""
    client_id     = current_app.config.get("GOOGLE_CLIENT_ID") or ""
    client_secret = current_app.config.get("GOOGLE_CLIENT_SECRET") or ""
    if not client_id or not client_secret:
        return None
    try:
        from google_auth_oauthlib.flow import Flow
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id":     client_id,
                    "client_secret": client_secret,
                    "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
                    "token_uri":     "https://oauth2.googleapis.com/token",
                }
            },
            scopes=[
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/userinfo.email",
                "openid",
            ],
        )
        flow.redirect_uri = url_for("executive.email_callback", _external=True)
        return flow
    except ImportError:
        current_app.logger.warning("[gmail-oauth] google-auth-oauthlib not installed")
        return None


@executive_bp.route("/email/connect")
@login_required
def email_connect():
    """Redirect to Google OAuth to connect Gmail."""
    from flask import session as flask_session

    access_redirect = _ensure_executive_access()
    if access_redirect:
        return access_redirect

    flow = _gmail_flow()
    if not flow:
        flash("Gmail OAuth is not configured yet. Contact your admin.", "warning")
        return redirect(url_for("executive.construction_center"))

    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    flask_session["gmail_oauth_state"] = state
    return redirect(auth_url)


@executive_bp.route("/email/callback")
@login_required
def email_callback():
    """Handle Google OAuth callback — store tokens in UserEmailConnection."""
    from flask import session as flask_session, jsonify

    access_redirect = _ensure_executive_access()
    if access_redirect:
        return access_redirect

    flow = _gmail_flow()
    if not flow:
        flash("Gmail OAuth is not configured.", "warning")
        return redirect(url_for("executive.construction_center"))

    try:
        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials

        # Get user's email from Google
        import requests as http_requests
        info_resp = http_requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {creds.token}"},
            timeout=8,
        )
        email_address = info_resp.json().get("email", "") if info_resp.ok else ""

        conn = UserEmailConnection.query.filter_by(user_id=current_user.id).first()
        if not conn:
            conn = UserEmailConnection(user_id=current_user.id)
            db.session.add(conn)

        conn.provider      = "gmail"
        conn.email_address = email_address
        conn.access_token  = creds.token
        conn.refresh_token = creds.refresh_token or conn.refresh_token
        conn.token_expiry  = creds.expiry
        conn.connected_at  = datetime.utcnow()
        db.session.commit()

        flash(f"Gmail connected: {email_address}", "success")
    except Exception as exc:
        current_app.logger.warning("[gmail-callback] %s", exc)
        flash("Could not connect Gmail — please try again.", "danger")

    return redirect(url_for("executive.construction_center"))


@executive_bp.route("/email/disconnect", methods=["POST"])
@login_required
def email_disconnect():
    """Remove stored Gmail tokens."""
    access_redirect = _ensure_executive_access()
    if access_redirect:
        return access_redirect

    conn = UserEmailConnection.query.filter_by(user_id=current_user.id).first()
    if conn:
        db.session.delete(conn)
        db.session.commit()
        flash("Gmail disconnected.", "info")
    return redirect(url_for("executive.construction_center"))


@executive_bp.route("/email/sync", methods=["POST"])
@login_required
def email_sync():
    """AJAX: Read recent Gmail messages and return an AI summary of anything construction-related."""
    from flask import jsonify
    from openai import OpenAI

    access_redirect = _ensure_executive_access()
    if access_redirect:
        return jsonify({"ok": False, "error": "Access restricted."}), 403

    conn = UserEmailConnection.query.filter_by(user_id=current_user.id).first()
    if not conn or not conn.access_token:
        return jsonify({"ok": False, "error": "No Gmail account connected."})

    client_id     = current_app.config.get("GOOGLE_CLIENT_ID") or ""
    client_secret = current_app.config.get("GOOGLE_CLIENT_SECRET") or ""

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request as GRequest
        import requests as http_requests

        creds = Credentials(
            token=conn.access_token,
            refresh_token=conn.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(GRequest())
            conn.access_token = creds.token
            conn.token_expiry = creds.expiry
            db.session.commit()

        # Fetch last 10 messages
        list_resp = http_requests.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages",
            headers={"Authorization": f"Bearer {creds.token}"},
            params={"maxResults": 10, "q": "is:unread"},
            timeout=10,
        )
        messages_raw = list_resp.json().get("messages", []) if list_resp.ok else []

        snippets = []
        for msg in messages_raw[:10]:
            msg_resp = http_requests.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg['id']}",
                headers={"Authorization": f"Bearer {creds.token}"},
                params={"format": "metadata", "metadataHeaders": ["Subject", "From"]},
                timeout=8,
            )
            if not msg_resp.ok:
                continue
            data    = msg_resp.json()
            headers = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])}
            subject = headers.get("Subject", "(no subject)")
            sender  = headers.get("From", "")
            snippet = data.get("snippet", "")
            snippets.append(f"From: {sender}\nSubject: {subject}\nPreview: {snippet}")

        conn.last_synced_at = datetime.utcnow()
        db.session.commit()

        if not snippets:
            return jsonify({"ok": True, "summary": "No unread emails right now. Inbox is clear.", "count": 0})

        inbox_text = "\n\n---\n\n".join(snippets)
        ai_prompt  = (
            "You are the AI Office for Caughman Mason Construction. "
            "Review these recent unread emails and give a SHORT summary of anything that needs attention — "
            "bids, client messages, invoices, supplier quotes, permits, anything construction-related. "
            "Ignore marketing emails or newsletters. "
            "Format: bullet points only. Max 6 bullets. If nothing urgent, say so.\n\n"
            f"EMAILS:\n{inbox_text}"
        )

        client = OpenAI()
        model  = current_app.config.get("AI_MODEL") or "gpt-4o-mini"
        resp   = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": ai_prompt}],
            temperature=0.4,
            max_tokens=300,
        )
        summary = resp.choices[0].message.content.strip()
        return jsonify({"ok": True, "summary": summary, "count": len(snippets)})

    except Exception as exc:
        current_app.logger.warning("[email-sync] %s", exc)
        return jsonify({"ok": False, "error": "Could not read emails right now."})


# ─────────────────────────────────────────────────────────────────────────────
# MORNING COMMAND CENTER — per-persona priority list
# ─────────────────────────────────────────────────────────────────────────────

def _morning_priorities(bids, projects, persona):
    """Build a sorted list of today's action items for the given persona.

    persona: "jamaine" | "sandra" | "letoya"
    Each item: title, stage, next_action, priority (high/medium/low),
               url, deadline (str|None), assigned_to.
    """
    from datetime import timedelta
    now        = datetime.utcnow()
    two_days   = (now + timedelta(days=2)).date()
    seven_days = (now + timedelta(days=7)).date()

    def _dp(bid):
        if not bid.bid_deadline:
            return "low"
        dl = bid.bid_deadline.date()
        if dl <= two_days:
            return "high"
        if dl <= seven_days:
            return "medium"
        return "low"

    def _dl(bid):
        return bid.bid_deadline.strftime("%b %d") if bid.bid_deadline else None

    bid_ids_with_projects = {p.bid_opportunity_id for p in projects if p.bid_opportunity_id}
    items = []

    if persona == "jamaine":
        for b in bids:
            if b.status == "site_visit_needed":
                items.append(dict(title=b.project_name, stage="Site Visit Needed",
                    next_action="Schedule and complete the site visit",
                    priority="high" if (b.bid_deadline and b.bid_deadline.date() <= two_days) else "medium",
                    url=url_for("executive.construction_center"), deadline=_dl(b), assigned_to="Jamaine"))
            elif b.status == "site_visit_scheduled":
                items.append(dict(title=b.project_name, stage="Site Visit Scheduled",
                    next_action="Confirm attendance and capture scope notes",
                    priority="medium", url=url_for("executive.construction_center"),
                    deadline=_dl(b), assigned_to="Jamaine"))
            elif b.status == "jamaine_review_needed":
                items.append(dict(title=b.project_name, stage="Needs Your Review",
                    next_action="Review Sandra's bid package — approve or return with notes",
                    priority="high", url=url_for("executive.bid_support"),
                    deadline=_dl(b), assigned_to="Jamaine"))
            elif b.status == "follow_up_needed":
                items.append(dict(title=b.project_name, stage="Follow-Up Needed",
                    next_action="Follow up with the client or GC on bid status",
                    priority="high", url=url_for("executive.construction_center"),
                    deadline=_dl(b), assigned_to="Jamaine"))
            elif b.status == "bid_submitted":
                items.append(dict(title=b.project_name, stage="Bid Submitted",
                    next_action="Check in with the client — ask for a decision timeline",
                    priority="medium", url=url_for("executive.construction_center"),
                    deadline=_dl(b), assigned_to="Jamaine"))
            elif b.status == "won" and b.id not in bid_ids_with_projects:
                items.append(dict(title=b.project_name, stage="Won — No Project Yet",
                    next_action="Open the Projects page to activate this job",
                    priority="high", url=url_for("construction_projects.project_list"),
                    deadline=None, assigned_to="Jamaine"))
            elif b.status == "saved_opportunity":
                items.append(dict(title=b.project_name, stage="Saved — Needs Decision",
                    next_action="Send to Sandra for bid package or update status",
                    priority=_dp(b), url=url_for("executive.construction_center"),
                    deadline=_dl(b), assigned_to="Jamaine"))
        for p in projects:
            if p.status in ("active", "punch_list"):
                items.append(dict(title=p.project_name,
                    stage="Punch List" if p.status == "punch_list" else "Active",
                    next_action="Check field progress — update project notes",
                    priority="medium",
                    url=url_for("construction_projects.project_detail", project_id=p.id),
                    deadline=p.estimated_completion.strftime("%b %d") if p.estimated_completion else None,
                    assigned_to="Jamaine"))

    elif persona == "sandra":
        for b in bids:
            if b.status == "bid_package_needed":
                items.append(dict(title=b.project_name, stage="Package Needed",
                    next_action="Prepare the full bid package for Jamaine's review",
                    priority=_dp(b), url=url_for("executive.bid_support"),
                    deadline=_dl(b), assigned_to="Sandra"))
            elif b.status == "missing_information":
                items.append(dict(title=b.project_name, stage="Missing Information",
                    next_action="Reach out to client or GC — bid prep is blocked",
                    priority="high", url=url_for("executive.bid_support"),
                    deadline=_dl(b), assigned_to="Sandra"))
            elif b.status == "ready_to_send":
                items.append(dict(title=b.project_name, stage="Ready to Send",
                    next_action="Submit bid to client — Jamaine has approved",
                    priority="high", url=url_for("executive.bid_support"),
                    deadline=_dl(b), assigned_to="Sandra"))
            elif b.status == "draft_bid_prepared":
                items.append(dict(title=b.project_name, stage="Draft Ready",
                    next_action="Send draft to Jamaine for field review",
                    priority="medium", url=url_for("executive.bid_support"),
                    deadline=_dl(b), assigned_to="Sandra"))
            elif b.status == "follow_up_needed":
                items.append(dict(title=b.project_name, stage="Follow-Up Needed",
                    next_action="Contact client for update on submitted bid",
                    priority="medium", url=url_for("executive.bid_support"),
                    deadline=_dl(b), assigned_to="Sandra"))

    else:  # letoya
        for b in bids:
            if b.status == "jamaine_review_needed":
                items.append(dict(title=b.project_name, stage="Jamaine Reviewing",
                    next_action="Check with Jamaine — approve scope or return with notes",
                    priority=_dp(b), url=url_for("executive.bid_support"),
                    deadline=_dl(b), assigned_to="Jamaine"))
            elif b.status == "missing_information":
                items.append(dict(title=b.project_name, stage="Stuck — Missing Info",
                    next_action="Ask Sandra to resolve — bid prep is blocked",
                    priority="high", url=url_for("executive.bid_support"),
                    deadline=_dl(b), assigned_to="Sandra"))
            elif b.status == "won" and b.id not in bid_ids_with_projects:
                items.append(dict(title=b.project_name, stage="Won — No Project",
                    next_action="Project not yet created — confirm with Jamaine",
                    priority="high", url=url_for("construction_projects.project_list"),
                    deadline=None, assigned_to="Jamaine"))
            elif b.status == "bid_submitted":
                items.append(dict(title=b.project_name, stage="Bid Submitted",
                    next_action="Monitor — follow up if no client response within a week",
                    priority="medium", url=url_for("executive.construction_center"),
                    deadline=_dl(b), assigned_to="Sandra"))
        for p in projects:
            if p.status in ("active", "punch_list"):
                items.append(dict(title=p.project_name,
                    stage="Active" if p.status == "active" else "Punch List",
                    next_action="Check field progress with Jamaine",
                    priority="low",
                    url=url_for("construction_projects.project_detail", project_id=p.id),
                    deadline=p.estimated_completion.strftime("%b %d") if p.estimated_completion else None,
                    assigned_to="Jamaine"))

    order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda x: order.get(x["priority"], 3))
    return items


# ─────────────────────────────────────────────────────────────────────────────
# BID SUPPORT QUEUE — Sandra's workflow view
# ─────────────────────────────────────────────────────────────────────────────

# Sandra's preparation stages — a focused slice of ContractorBidOpportunity.status,
# the same field used by the general Bid Pipeline (construction_bids blueprint).
BID_SUPPORT_STATUSES = [
    ("bid_package_needed",   "Package Needed",       "#5FA8FF", "lucide-package"),
    ("missing_information",  "Missing Information",  "#f87171", "lucide-alert-circle"),
    ("draft_bid_prepared",   "Draft Prepared",       "#eab308", "lucide-file-pen-line"),
    ("jamaine_review_needed","Waiting on Jamaine",   "#a78bfa", "lucide-user-clock"),
    ("ready_to_send",        "Ready to Send",        "#2cb67d", "lucide-send"),
    ("follow_up_needed",     "Follow-Up Needed",     "#f97316", "lucide-rotate-ccw"),
]

_BID_SUPPORT_EMAILS: set[str] = {
    "letoya@ravlohq.com",
    "jamaine.caughman@ravlohq.com",
    "sandra@ravlohq.com",
}


def _can_access_bid_support(user) -> bool:
    if _can_access_executive_dashboard(user):
        return True
    email = (getattr(user, "email", "") or "").strip().lower()
    return email in _BID_SUPPORT_EMAILS


def _cm_partner():
    from LoanMVP.models.crm_models import Partner
    return (
        Partner.query.filter(func.lower(Partner.company) == "caughman mason construction").first()
    )


@executive_bp.route("/bid-support")
@login_required
def bid_support():
    if not _can_access_bid_support(current_user):
        flash("Access restricted.", "warning")
        return redirect(url_for("auth.post_login_redirect"))

    partner = _cm_partner()
    bids = []
    if partner:
        try:
            bids = (
                ContractorBidOpportunity.query
                .filter_by(partner_id=partner.id)
                .order_by(ContractorBidOpportunity.created_at.desc())
                .all()
            )
        except Exception as exc:
            db.session.rollback()
            current_app.logger.warning("[bid_support] table not ready: %s", exc)
            flash("Bid table is still setting up — check back shortly.", "info")

    # Sandra's queue is the subset of bids currently in a prep stage —
    # bids not yet handed off (saved_opportunity) or already past prep
    # (bid_submitted, won, lost, etc.) belong on the general Bid Pipeline instead.
    status_keys = [s[0] for s in BID_SUPPORT_STATUSES]
    queue_bids = [b for b in bids if b.status in status_keys]
    by_status = {k: [] for k in status_keys}
    for b in queue_bids:
        by_status[b.status].append(b)

    needs_attention = len(by_status.get("missing_information", [])) + len(by_status.get("follow_up_needed", []))

    # ── Morning priorities for bid support ──────────────────────────
    bs_projects = []
    try:
        cm = _cm_partner()
        if cm:
            bs_projects = ConstructionProject.query.filter_by(partner_id=cm.id).all()
    except Exception:
        db.session.rollback()

    bs_email = (getattr(current_user, "email", "") or "").strip().lower()
    if bs_email == "sandra@ravlohq.com":
        bs_persona  = "sandra"
        bs_greeting = "Sandra"
    elif bs_email == _JAMAINE_EMAIL:
        bs_persona  = "jamaine"
        bs_greeting = "Jamaine"
    else:
        bs_persona  = "letoya"
        bs_greeting = getattr(current_user, "first_name", None) or "Letoya"
    bs_priorities = _morning_priorities(bids, bs_projects, bs_persona)

    return render_template(
        "executive/bid_support.html",
        bids=queue_bids,
        by_status=by_status,
        statuses=BID_SUPPORT_STATUSES,
        needs_attention=needs_attention,
        priorities=bs_priorities,
        greeting=bs_greeting,
        persona=bs_persona,
    )


@executive_bp.route("/bid-support/<int:bid_id>/status", methods=["POST"])
@login_required
def bid_support_update_status(bid_id):
    if not _can_access_bid_support(current_user):
        return redirect(url_for("auth.post_login_redirect"))

    try:
        bid = ContractorBidOpportunity.query.get_or_404(bid_id)
        new_status = (request.form.get("status") or "").strip()
        status_keys = [s[0] for s in BID_SUPPORT_STATUSES]
        if new_status in status_keys:
            bid.status = new_status
        notes = request.form.get("notes")
        if notes is not None:
            bid.notes = notes.strip() or None
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.warning("[bid_support_update] %s", exc)
        flash("Could not update bid status.", "danger")

    return redirect(url_for("executive.bid_support"))


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
