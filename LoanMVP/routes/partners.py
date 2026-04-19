# LoanMVP/routes/vip.py
import json
from datetime import datetime, timedelta
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, jsonify, session
)
from flask_login import current_user
from sqlalchemy import or_

from LoanMVP.extensions import db
from LoanMVP.models.vip_models import (
    VIPProfile, VIPIncome, VIPExpense,
    VIPAssistantSuggestion, VIPDesignProject, VIPDesignAnnotation,
)
from LoanMVP.models.elena_models import (
    ElenaClient, ElenaListing, ElenaFlyer, ElenaInteraction,
)
from LoanMVP.models.partner_models import PartnerJob, PartnerConnectionRequest
from LoanMVP.services.vip_ai_pilot import parse_vip_command
from LoanMVP.utils.decorators import role_required

vip_bp = Blueprint("vip", __name__, url_prefix="/vip")

PIPELINE_STAGES = [
    ("new", "New"), ("warm", "Warm"), ("active", "Active"),
    ("under_contract", "Under Contract"), ("closed", "Closed"),
]
LISTING_STATUSES = [
    ("active", "Active"), ("pending", "Pending"),
    ("sold", "Sold"), ("withdrawn", "Withdrawn"),
]
FRANK_MARKETS = ["Hudson Valley", "Sarasota"]

MODULE_FIELD_MAP = {
    "crm_enabled": "crm",
    "finances_enabled": "finances",
    "budget_enabled": "budget_tracker",
    "ai_pilot_enabled": "ai_pilot",
    "content_studio_enabled": "content_studio",
    "calendar_sync_enabled": "calendar_sync",
    "voice_enabled": "voice_assistant",
    "sms_enabled": "sms_assistant",
    "email_enabled": "email_assistant",
    "canva_enabled": "canva",
    "design_studio_enabled": "design_studio",
}


# ── helpers ──────────────────────────────────────────────

def get_enabled_modules(profile):
    raw = profile.enabled_modules or "[]"
    try:
        value = json.loads(raw)
        return value if isinstance(value, list) else []
    except (TypeError, ValueError):
        return []


def has_module(profile, module_name):
    return module_name in get_enabled_modules(profile)


def build_enabled_modules_from_form(form):
    modules = []
    for field_name, module_name in MODULE_FIELD_MAP.items():
        if (form.get(field_name) or "").strip().lower() == "yes":
            modules.append(module_name)
    return modules


def get_or_create_vip_profile():
    if not getattr(current_user, "is_authenticated", False):
        return None

    profile = VIPProfile.query.filter_by(user_id=current_user.id).first()
    if profile:
        return profile

    partner = getattr(current_user, "partner_profile", None)
    default_role_type = "partner"
    if partner and getattr(partner, "category", None):
        raw_category = (partner.category or "").strip().lower()
        role_map = {
            "realtor": "realtor", "contractor": "contractor",
            "designer": "designer", "lender": "loan_officer",
            "loan_officer": "loan_officer",
        }
        default_role_type = role_map.get(raw_category, "partner")

    profile = VIPProfile(
        user_id=current_user.id,
        display_name=(getattr(current_user, "name", None)
                      or getattr(current_user, "email", "VIP User")),
        business_name=getattr(partner, "company", None) if partner else None,
        role_type=default_role_type,
        assistant_name="Ravlo",
    )
    db.session.add(profile)
    db.session.commit()
    return profile


def get_dashboard_name(profile):
    return (
        profile.dashboard_title
        or profile.business_name
        or profile.display_name
        or "VIP Workspace"
    )


def _get_frank_market():
    return session.get("frank_market", "All Markets")


# ── context processor ────────────────────────────────────

@vip_bp.app_context_processor
def inject_vip_context():
    if not getattr(current_user, "is_authenticated", False):
        return {"vip_profile": None, "modules": []}
    profile = get_or_create_vip_profile()
    return {"vip_profile": profile, "modules": get_enabled_modules(profile)}


# ── index (smart redirect) ───────────────────────────────

@vip_bp.get("/")
@role_required("partner_group", "admin")
def index():
    profile = get_or_create_vip_profile()
    role_map = {
        "realtor":      "vip.realtor_dashboard",
        "contractor":   "vip.contractor_dashboard",
        "designer":     "vip.designer_dashboard",
        "partner":      "vip.partner_dashboard",
        "loan_officer": "vip.loan_officer_dashboard",
        "lender":       "vip.loan_officer_dashboard",
    }
    return redirect(url_for(role_map.get(profile.role_type, "vip.partner_dashboard")))


# ── market switch ────────────────────────────────────────

@vip_bp.post("/realtor/market-switch")
@role_required("partner_group", "admin")
def realtor_market_switch():
    selected = (request.form.get("market") or "All Markets").strip()
    allowed = {"All Markets", *FRANK_MARKETS}
    session["frank_market"] = selected if selected in allowed else "All Markets"
    next_url = request.form.get("next") or url_for("vip.realtor_dashboard")
    return redirect(next_url)


# ── REALTOR dashboard (Elena-quality data) ───────────────

@vip_bp.get("/realtor")
@role_required("partner_group", "admin")
def realtor_dashboard():
    profile = get_or_create_vip_profile()
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    current_market = _get_frank_market()

    # — summary stats —
    total_clients = ElenaClient.query.count()
    new_leads = ElenaClient.query.filter(ElenaClient.created_at >= week_ago).count()

    listing_q = ElenaListing.query.filter_by(status="active")
    if current_market != "All Markets":
        listing_q = listing_q.filter_by(market=current_market)
    active_listings = listing_q.count()

    followups_due = ElenaInteraction.query.filter(
        ElenaInteraction.due_at.isnot(None),
        ElenaInteraction.due_at >= now,
        ElenaInteraction.due_at <= now + timedelta(days=7),
    ).count()

    summary = {
        "total_clients": total_clients,
        "new_leads": new_leads,
        "active_listings": active_listings,
        "followups_due": followups_due,
    }

    # — pipeline —
    pipeline_groups = []
    canonical_keys = {s[0] for s in PIPELINE_STAGES}
    for stage_key, stage_label in PIPELINE_STAGES:
        q = ElenaClient.query.filter_by(pipeline_stage=stage_key)
        pipeline_groups.append({
            "key": stage_key,
            "label": stage_label,
            "count": q.count(),
            "clients": q.order_by(ElenaClient.updated_at.desc()).limit(12).all(),
        })

    unstaged_filter = or_(
        ElenaClient.pipeline_stage.is_(None),
        ~ElenaClient.pipeline_stage.in_(canonical_keys),
    )
    unstaged_total = ElenaClient.query.filter(unstaged_filter).count()
    if unstaged_total:
        pipeline_groups.insert(0, {
            "key": "unstaged", "label": "Unstaged",
            "count": unstaged_total,
            "clients": (ElenaClient.query.filter(unstaged_filter)
                        .order_by(ElenaClient.updated_at.desc()).limit(12).all()),
        })

    # — listings —
    status_filter = (request.args.get("listing_status") or "").strip().lower()
    listings_q = ElenaListing.query
    if current_market != "All Markets":
        listings_q = listings_q.filter_by(market=current_market)
    if status_filter and status_filter in {s[0] for s in LISTING_STATUSES}:
        listings_q = listings_q.filter_by(status=status_filter)
    listings = listings_q.order_by(ElenaListing.updated_at.desc()).limit(12).all()

    # — recent activity —
    recent_interactions = (ElenaInteraction.query
                           .order_by(ElenaInteraction.created_at.desc()).limit(10).all())

    flyers_q = ElenaFlyer.query
    if current_market != "All Markets":
        flyers_q = (flyers_q
                    .join(ElenaListing, ElenaFlyer.listing_id == ElenaListing.id)
                    .filter(ElenaListing.market == current_market))
    recent_flyers = flyers_q.order_by(ElenaFlyer.created_at.desc()).limit(5).all()

    copilot_suggestions = (VIPAssistantSuggestion.query
                           .filter_by(vip_profile_id=profile.id)
                           .order_by(VIPAssistantSuggestion.created_at.desc())
                           .limit(5).all())

    return render_template(
        "vip/realtor/dashboard.html",
        vip_profile=profile,
        modules=get_enabled_modules(profile),
        header_name=get_dashboard_name(profile),
        summary=summary,
        pipeline_groups=pipeline_groups,
        pipeline_stages=PIPELINE_STAGES,
        recent_interactions=recent_interactions,
        listings=listings,
        listing_statuses=LISTING_STATUSES,
        listing_status_filter=status_filter,
        recent_flyers=recent_flyers,
        copilot_suggestions=copilot_suggestions,
        current_market=current_market,
        available_markets=FRANK_MARKETS,
        portal="vip",
        portal_name="VIP",
        portal_home=url_for("vip.realtor_dashboard"),
    )


# ── CONTRACTOR dashboard ─────────────────────────────────

@vip_bp.get("/contractor")
@role_required("partner_group", "admin")
def contractor_dashboard():
    profile = get_or_create_vip_profile()
    partner = getattr(current_user, "partner_profile", None)

    jobs = []
    stats = {"open": 0, "in_progress": 0, "completed": 0, "total_volume": 0.0}

    if partner:
        jobs = (PartnerJob.query
                .filter_by(partner_id=partner.id)
                .order_by(PartnerJob.created_at.desc())
                .limit(20).all())
        stats["open"] = sum(1 for j in jobs if j.status == "Open")
        stats["in_progress"] = sum(1 for j in jobs if j.status == "in_progress")
        stats["completed"] = sum(1 for j in jobs if j.status == "completed")
        stats["total_volume"] = sum(
            (j.total_cost or 0) for j in jobs if j.status == "completed"
        )

    copilot_suggestions = (VIPAssistantSuggestion.query
                           .filter_by(vip_profile_id=profile.id)
                           .order_by(VIPAssistantSuggestion.created_at.desc())
                           .limit(5).all())

    return render_template(
        "vip/contractor/dashboard.html",
        vip_profile=profile,
        modules=get_enabled_modules(profile),
        header_name=get_dashboard_name(profile),
        jobs=jobs,
        stats=stats,
        copilot_suggestions=copilot_suggestions,
        portal="vip",
        portal_name="VIP",
        portal_home=url_for("vip.contractor_dashboard"),
    )


# ── DESIGNER dashboard ───────────────────────────────────

@vip_bp.get("/designer")
@role_required("partner_group", "admin")
def designer_dashboard():
    profile = get_or_create_vip_profile()
    partner = getattr(current_user, "partner_profile", None)

    projects = (VIPDesignProject.query
                .filter_by(vip_profile_id=profile.id)
                .order_by(VIPDesignProject.created_at.desc())
                .limit(10).all())

    recent_requests = []
    if partner:
        recent_requests = (PartnerConnectionRequest.query
                           .filter_by(partner_id=partner.id)
                           .order_by(PartnerConnectionRequest.created_at.desc())
                           .limit(8).all())

    copilot_suggestions = (VIPAssistantSuggestion.query
                           .filter_by(vip_profile_id=profile.id)
                           .order_by(VIPAssistantSuggestion.created_at.desc())
                           .limit(5).all())

    return render_template(
        "vip/designer/dashboard.html",
        vip_profile=profile,
        modules=get_enabled_modules(profile),
        header_name=get_dashboard_name(profile),
        projects=projects,
        recent_requests=recent_requests,
        copilot_suggestions=copilot_suggestions,
        portal="vip",
        portal_name="VIP",
        portal_home=url_for("vip.designer_dashboard"),
    )


# ── LOAN OFFICER dashboard ───────────────────────────────

@vip_bp.get("/loan-officer")
@role_required("partner_group", "admin")
def loan_officer_dashboard():
    profile = get_or_create_vip_profile()
    partner = getattr(current_user, "partner_profile", None)

    recent_requests = []
    stats = {"pending": 0, "accepted": 0, "completed": 0}

    if partner:
        recent_requests = (PartnerConnectionRequest.query
                           .filter_by(partner_id=partner.id)
                           .order_by(PartnerConnectionRequest.created_at.desc())
                           .limit(10).all())
        stats["pending"] = sum(1 for r in recent_requests if r.status == "pending")
        stats["accepted"] = sum(1 for r in recent_requests if r.status == "accepted")
        stats["completed"] = sum(1 for r in recent_requests if r.status == "completed")

    copilot_suggestions = (VIPAssistantSuggestion.query
                           .filter_by(vip_profile_id=profile.id)
                           .order_by(VIPAssistantSuggestion.created_at.desc())
                           .limit(5).all())

    return render_template(
        "vip/loan_officer/dashboard.html",
        vip_profile=profile,
        modules=get_enabled_modules(profile),
        header_name=get_dashboard_name(profile),
        recent_requests=recent_requests,
        stats=stats,
        copilot_suggestions=copilot_suggestions,
        portal="vip",
        portal_name="VIP",
        portal_home=url_for("vip.loan_officer_dashboard"),
    )


# ── PARTNER dashboard ────────────────────────────────────

@vip_bp.get("/partner")
@role_required("partner_group", "admin")
def partner_dashboard():
    profile = get_or_create_vip_profile()
    partner = getattr(current_user, "partner_profile", None)

    recent_requests = []
    stats = {"pending": 0, "accepted": 0, "completed": 0}

    if partner:
        recent_requests = (PartnerConnectionRequest.query
                           .filter_by(partner_id=partner.id)
                           .order_by(PartnerConnectionRequest.created_at.desc())
                           .limit(8).all())
        stats["pending"] = sum(1 for r in recent_requests if r.status == "pending")
        stats["accepted"] = sum(1 for r in recent_requests if r.status == "accepted")
        stats["completed"] = sum(1 for r in recent_requests if r.status == "completed")

    copilot_suggestions = (VIPAssistantSuggestion.query
                           .filter_by(vip_profile_id=profile.id)
                           .order_by(VIPAssistantSuggestion.created_at.desc())
                           .limit(5).all())

    return render_template(
        "vip/partner/dashboard.html",
        vip_profile=profile,
        modules=get_enabled_modules(profile),
        header_name=get_dashboard_name(profile),
        recent_requests=recent_requests,
        stats=stats,
        copilot_suggestions=copilot_suggestions,
        portal="vip",
        portal_name="VIP",
        portal_home=url_for("vip.partner_dashboard"),
    )
