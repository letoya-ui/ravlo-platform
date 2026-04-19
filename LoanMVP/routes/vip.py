# LoanMVP/routes/vip.py
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash,jsonify
from flask_login import current_user

from LoanMVP.extensions import db

from LoanMVP.models.vip_models import (
    VIPProfile,
    VIPIncome,
    VIPExpense,
    VIPAssistantSuggestion,
)
from LoanMVP.models.vip_models import VIPDesignProject, VIPDesignAnnotation

from LoanMVP.services.vip_ai_pilot import parse_vip_command

from LoanMVP.utils.decorators import role_required

vip_bp = Blueprint("vip", __name__, url_prefix="/vip")

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
            "realtor": "realtor",
            "contractor": "contractor",
            "designer": "designer",
            "lender": "loan_officer",
            "loan_officer": "loan_officer",
            "broker": "partner",
            "vendor": "partner",
            "property_manager": "partner",
            "attorney": "partner",
            "insurance": "partner",
            "title": "partner",
            "inspector": "partner",
            "appraiser": "partner",
            "cleaner": "contractor",
            "janitorial": "contractor",
        }
        default_role_type = role_map.get(raw_category, "partner")

    profile = VIPProfile(
        user_id=current_user.id,
        display_name=getattr(current_user, "name", None)
        or getattr(current_user, "email", "VIP User"),
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
@vip_bp.post("/realtor/market-switch")
@role_required("partner_group", "admin")
def realtor_market_switch():
    selected_market = (request.form.get("market") or "All Markets").strip()
    allowed = {"All Markets", "Hudson Valley", "Sarasota"}

    session["frank_market"] = selected_market if selected_market in allowed else "All Markets"

    next_url = request.form.get("next") or url_for("vip.realtor_dashboard")
    return redirect(next_url)

@vip_bp.app_context_processor
def inject_vip_context():
    if not getattr(current_user, "is_authenticated", False):
        return {
            "vip_profile": None,
            "modules": [],
        }

    profile = get_or_create_vip_profile()

    return {
        "vip_profile": profile,
        "modules": get_enabled_modules(profile),
    }

@vip_bp.get("/")
@role_required("partner_group", "admin")
def index():
    profile = get_or_create_vip_profile()

    # Frank gets his dual-market workspace
    if getattr(profile, "dual_market", False):
        return redirect(url_for("vip.frank_dashboard"))

    role_map = {
        "realtor":      "vip.realtor_dashboard",
        "contractor":   "vip.contractor_dashboard",
        ...
    }
    return redirect(url_for(role_map.get(profile.role_type, "vip.partner_dashboard")))


@vip_bp.get("/realtor")
@role_required("partner_group", "admin")
def realtor_dashboard():
    profile = get_or_create_vip_profile()
    return render_template(
        "vip/realtor/dashboard.html",
        vip_profile=profile,
        modules=get_enabled_modules(profile),
        header_name=get_dashboard_name(profile),
        portal="vip",
        portal_name="VIP",
        portal_home=url_for("vip.realtor_dashboard"),
    )


@vip_bp.get("/contractor")
@role_required("partner_group", "admin")
def contractor_dashboard():
    profile = get_or_create_vip_profile()
    return render_template(
        "vip/contractor/dashboard.html",
        vip_profile=profile,
        modules=get_enabled_modules(profile),
        header_name=get_dashboard_name(profile),
        portal="vip",
        portal_name="VIP",
        portal_home=url_for("vip.contractor_dashboard"),
    )


@vip_bp.get("/designer")
@role_required("partner_group", "admin")
def designer_dashboard():
    profile = get_or_create_vip_profile()
    return render_template(
        "vip/designer/dashboard.html",
        vip_profile=profile,
        modules=get_enabled_modules(profile),
        header_name=get_dashboard_name(profile),
        portal="vip",
        portal_name="VIP",
        portal_home=url_for("vip.designer_dashboard"),
    )


@vip_bp.get("/partner")
@role_required("partner_group", "admin")
def partner_dashboard():
    profile = get_or_create_vip_profile()
    return render_template(
        "vip/partner/dashboard.html",
        vip_profile=profile,
        modules=get_enabled_modules(profile),
        header_name=get_dashboard_name(profile),
        portal="vip",
        portal_name="VIP",
        portal_home=url_for("vip.partner_dashboard"),
    )


@vip_bp.get("/loan-officer")
@role_required("partner_group", "admin")
def loan_officer_dashboard():
    profile = get_or_create_vip_profile()
    return render_template(
        "vip/loan_officer/dashboard.html",
        vip_profile=profile,
        modules=get_enabled_modules(profile),
        header_name=get_dashboard_name(profile),
        portal="vip",
        portal_name="VIP",
        portal_home=url_for("vip.loan_officer_dashboard"),
    )


@vip_bp.get("/finances")
@role_required("partner_group", "admin")
def finances():
    profile = get_or_create_vip_profile()

    incomes = (
        VIPIncome.query.filter_by(vip_profile_id=profile.id)
        .order_by(VIPIncome.created_at.desc())
        .limit(25)
        .all()
    )
    expenses = (
        VIPExpense.query.filter_by(vip_profile_id=profile.id)
        .order_by(VIPExpense.created_at.desc())
        .limit(25)
        .all()
    )

    total_income = sum((item.amount or 0) for item in incomes)
    total_expenses = sum((item.amount or 0) for item in expenses)
    net_profit = total_income - total_expenses

    return render_template(
        "vip/finances.html",
        vip_profile=profile,
        header_name=get_dashboard_name(profile),
        incomes=incomes,
        expenses=expenses,
        total_income=total_income,
        total_expenses=total_expenses,
        net_profit=net_profit,
        portal="vip",
        portal_name="VIP",
        portal_home=url_for("vip.index"),
    )


@vip_bp.get("/ai-pilot")
@role_required("partner_group", "admin")
def ai_pilot():
    profile = get_or_create_vip_profile()

    suggestions = (
        VIPAssistantSuggestion.query.filter_by(vip_profile_id=profile.id)
        .order_by(VIPAssistantSuggestion.created_at.desc())
        .limit(20)
        .all()
    )

    return render_template(
        "vip/ai_pilot.html",
        vip_profile=profile,
        header_name=get_dashboard_name(profile),
        suggestions=suggestions,
        portal="vip",
        portal_name="VIP",
        portal_home=url_for("vip.index"),
    )


@vip_bp.post("/ai-pilot/command")
@role_required("partner_group", "admin")
def ai_pilot_command():
    profile = get_or_create_vip_profile()

    command = (request.form.get("command") or "").strip()
    if not command:
        flash("Please enter a command.", "warning")
        return redirect(url_for("vip.ai_pilot"))

    result = parse_vip_command(command)

    suggestion = VIPAssistantSuggestion(
        vip_profile_id=profile.id,
        suggestion_type=result["suggestion_type"],
        title=result["title"],
        body=result.get("body"),
        source="manual",
    )
    db.session.add(suggestion)
    db.session.commit()

    flash("Assistant suggestion created.", "success")
    return redirect(url_for("vip.ai_pilot"))

@vip_bp.get("/onboarding")
@role_required("partner_group", "admin")
def onboarding():
    profile = get_or_create_vip_profile()

    enabled = set(get_enabled_modules(profile))
    module_pref = {}

    for field_name, module_name in MODULE_FIELD_MAP.items():
        module_pref[field_name] = "yes" if module_name in enabled else "no"

    return render_template(
        "vip/onboarding.html",
        vip_profile=profile,
        module_pref=module_pref,
        header_name=get_dashboard_name(profile),
        portal="vip",
        portal_name="VIP",
        portal_home=url_for("vip.index"),
    )


@vip_bp.post("/onboarding/save")
@role_required("partner_group", "admin")
def onboarding_save():
    profile = get_or_create_vip_profile()

    profile.display_name = (request.form.get("display_name") or profile.display_name or "").strip()
    profile.business_name = (request.form.get("business_name") or "").strip() or None
    profile.dashboard_title = (request.form.get("dashboard_title") or "").strip() or None
    profile.assistant_name = (request.form.get("assistant_name") or "Ravlo").strip()
    profile.role_type = (request.form.get("role_type") or profile.role_type or "partner").strip()
    profile.service_area = (request.form.get("service_area") or "").strip() or None
    profile.headline = (request.form.get("headline") or "").strip() or None
    profile.bio = (request.form.get("bio") or "").strip() or None

    enabled_modules = build_enabled_modules_from_form(request.form)
    profile.enabled_modules = json.dumps(enabled_modules)

    db.session.commit()

    flash("VIP setup saved.", "success")
    return redirect(url_for("vip.index"))

@vip_bp.get("/design-studio")
@role_required("partner_group", "admin")
def design_studio():
    profile = get_or_create_vip_profile()

    project_id = request.args.get("project_id", type=int)
    project = None
    annotations = []

    if project_id:
        project = VIPDesignProject.query.filter_by(
            id=project_id,
            vip_profile_id=profile.id,
        ).first()

        if project:
            annotations = (
                VIPDesignAnnotation.query
                .filter_by(project_id=project.id)
                .order_by(VIPDesignAnnotation.created_at.asc())
                .all()
            )

    return render_template(
        "vip/design_studio.html",
        vip_profile=profile,
        modules=get_enabled_modules(profile),
        header_name=get_dashboard_name(profile),
        project=project,
        annotations=annotations,
        portal="vip",
        portal_name="VIP",
        portal_home=url_for("vip.index"),
    )


@vip_bp.post("/design-studio/create")
@role_required("partner_group", "admin")
def create_design_project():
    profile = get_or_create_vip_profile()

    title = (request.form.get("title") or "").strip()
    source_file = (request.form.get("source_file") or "").strip() or None

    if not title:
        flash("Project title is required.", "warning")
        return redirect(url_for("vip.design_studio"))

    project = VIPDesignProject(
        vip_profile_id=profile.id,
        title=title,
        source_file=source_file,
    )

    db.session.add(project)
    db.session.commit()

    flash("Design project created.", "success")
    return redirect(url_for("vip.design_studio", project_id=project.id))


@vip_bp.post("/design-studio/annotation")
@role_required("partner_group", "admin")
def save_annotation():
    profile = get_or_create_vip_profile()
    data = request.get_json() or {}

    project_id = data.get("project_id")
    project = VIPDesignProject.query.filter_by(
        id=project_id,
        vip_profile_id=profile.id,
    ).first()

    if not project:
        return jsonify({"error": "Project not found"}), 404

    annotation = VIPDesignAnnotation(
        project_id=project.id,
        annotation_type=data.get("type"),
        action_type=data.get("action"),
        label=data.get("label"),
        body=data.get("body"),
        x=data.get("x"),
        y=data.get("y"),
        width=data.get("width"),
        height=data.get("height"),
    )

    db.session.add(annotation)
    db.session.commit()

    return jsonify({
        "status": "ok",
        "annotation_id": annotation.id,
    }), 201

@vip_bp.post("/design-studio/annotation/update")
@role_required("partner_group", "admin")
def update_annotation():
    profile = get_or_create_vip_profile()
    data = request.get_json() or {}

    annotation = VIPDesignAnnotation.query.get(data.get("id"))

    if not annotation:
        return jsonify({"error": "Not found"}), 404

    project = VIPDesignProject.query.filter_by(
        id=annotation.project_id,
        vip_profile_id=profile.id,
    ).first()

    if not project:
        return jsonify({"error": "Unauthorized"}), 403

    annotation.annotation_type = data.get("type")
    annotation.action_type = data.get("action")
    annotation.label = data.get("label")
    annotation.body = data.get("body")

    db.session.commit()

    return jsonify({"status": "updated"})

@vip_bp.post("/design-studio/annotation/delete")
@role_required("partner_group", "admin")
def delete_annotation():
    profile = get_or_create_vip_profile()
    data = request.get_json() or {}

    annotation = VIPDesignAnnotation.query.get(data.get("id"))

    if not annotation:
        return jsonify({"error": "Not found"}), 404

    project = VIPDesignProject.query.filter_by(
        id=annotation.project_id,
        vip_profile_id=profile.id,
    ).first()

    if not project:
        return jsonify({"error": "Unauthorized"}), 403

    db.session.delete(annotation)
    db.session.commit()

    return jsonify({"status": "deleted"})

# ─────────────────────────────────────────────────────────────
# Add these constants near the top of vip.py (already there):
#   FRANK_MARKETS = ["Hudson Valley", "Sarasota"]
#
# Add this helper if not already present:
# ─────────────────────────────────────────────────────────────

def _get_frank_market():
    """Returns Frank's active market filter from session.
    Stored under 'frank_market' — never touches Elena's 'elena_market'."""
    return session.get("frank_market", "All Markets")


# ─────────────────────────────────────────────────────────────
# FRANK — dual-market realtor dashboard
# ─────────────────────────────────────────────────────────────

@vip_bp.post("/frank/market-switch")
@role_required("partner_group", "admin")
def frank_market_switch():
    selected = (request.form.get("market") or "All Markets").strip()
    allowed = {"All Markets", *FRANK_MARKETS}
    session["frank_market"] = selected if selected in allowed else "All Markets"
    next_url = request.form.get("next") or url_for("vip.frank_dashboard")
    return redirect(next_url)


@vip_bp.get("/frank")
@role_required("partner_group", "admin")
def frank_dashboard():
    profile = get_or_create_vip_profile()
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    current_market = _get_frank_market()

    # ── COMBINED summary (always both markets) ──────────────
    total_clients     = ElenaClient.query.count()
    new_leads         = ElenaClient.query.filter(ElenaClient.created_at >= week_ago).count()
    total_listings    = ElenaListing.query.filter_by(status="active").count()
    followups_due     = ElenaInteraction.query.filter(
        ElenaInteraction.due_at.isnot(None),
        ElenaInteraction.due_at >= now,
        ElenaInteraction.due_at <= now + timedelta(days=7),
    ).count()

    summary = {
        "total_clients":  total_clients,
        "new_leads":      new_leads,
        "total_listings": total_listings,
        "followups_due":  followups_due,
    }

    # ── PER-MARKET stats (for the split finance cards) ──────
    market_stats = {}
    for market in FRANK_MARKETS:
        active = ElenaListing.query.filter_by(status="active", market=market).count()
        clients = ElenaClient.query.count()   # extend with market tag if you add one later
        market_stats[market] = {
            "active_listings": active,
            "clients": clients,
        }

    # ── PIPELINE (filtered) ─────────────────────────────────
    pipeline_groups = []
    canonical_keys = {s[0] for s in PIPELINE_STAGES}

    for stage_key, stage_label in PIPELINE_STAGES:
        q = ElenaClient.query.filter_by(pipeline_stage=stage_key)
        pipeline_groups.append({
            "key":     stage_key,
            "label":   stage_label,
            "count":   q.count(),
            "clients": q.order_by(ElenaClient.updated_at.desc()).limit(10).all(),
        })

    unstaged_filter = or_(
        ElenaClient.pipeline_stage.is_(None),
        ~ElenaClient.pipeline_stage.in_(canonical_keys),
    )
    unstaged_total = ElenaClient.query.filter(unstaged_filter).count()
    if unstaged_total:
        pipeline_groups.insert(0, {
            "key":     "unstaged",
            "label":   "Unstaged",
            "count":   unstaged_total,
            "clients": (ElenaClient.query.filter(unstaged_filter)
                        .order_by(ElenaClient.updated_at.desc()).limit(10).all()),
        })

    # ── LISTINGS (respect market filter) ────────────────────
    status_filter = (request.args.get("listing_status") or "").strip().lower()
    listings_q = ElenaListing.query
    if current_market != "All Markets":
        listings_q = listings_q.filter_by(market=current_market)
    if status_filter and status_filter in {s[0] for s in LISTING_STATUSES}:
        listings_q = listings_q.filter_by(status=status_filter)
    listings = listings_q.order_by(ElenaListing.updated_at.desc()).limit(15).all()

    # ── LISTINGS split by market (for side panels) ──────────
    listings_by_market = {}
    for market in FRANK_MARKETS:
        listings_by_market[market] = (
            ElenaListing.query
            .filter_by(market=market, status="active")
            .order_by(ElenaListing.updated_at.desc())
            .limit(6)
            .all()
        )

    # ── FLYERS (respect market filter) ──────────────────────
    flyers_q = ElenaFlyer.query.join(ElenaListing, ElenaFlyer.listing_id == ElenaListing.id)
    if current_market != "All Markets":
        flyers_q = flyers_q.filter(ElenaListing.market == current_market)
    recent_flyers = flyers_q.order_by(ElenaFlyer.created_at.desc()).limit(6).all()

    # ── FLYERS split by market ───────────────────────────────
    flyers_by_market = {}
    for market in FRANK_MARKETS:
        flyers_by_market[market] = (
            ElenaFlyer.query
            .join(ElenaListing, ElenaFlyer.listing_id == ElenaListing.id)
            .filter(ElenaListing.market == market)
            .order_by(ElenaFlyer.created_at.desc())
            .limit(4)
            .all()
        )

    # ── FINANCES — combined + per-market ────────────────────
    all_income   = VIPIncome.query.filter_by(vip_profile_id=profile.id).all()
    all_expenses = VIPExpense.query.filter_by(vip_profile_id=profile.id).all()

    total_income   = sum((i.amount or 0) for i in all_income)
    total_expenses = sum((e.amount or 0) for e in all_expenses)
    net_profit     = total_income - total_expenses

    # Split by market tag (assumes VIPIncome/VIPExpense have a `market` column;
    # fall back gracefully if not — show combined only)
    finances_combined = {
        "income":   total_income,
        "expenses": total_expenses,
        "net":      net_profit,
    }

    finances_by_market = {}
    for market in FRANK_MARKETS:
        try:
            m_income   = sum((i.amount or 0) for i in all_income   if getattr(i, "market", None) == market)
            m_expenses = sum((e.amount or 0) for e in all_expenses if getattr(e, "market", None) == market)
            finances_by_market[market] = {
                "income":   m_income,
                "expenses": m_expenses,
                "net":      m_income - m_expenses,
            }
        except Exception:
            finances_by_market[market] = {"income": 0, "expenses": 0, "net": 0}

    # ── RECENT INTERACTIONS ──────────────────────────────────
    recent_interactions = (
        ElenaInteraction.query
        .order_by(ElenaInteraction.created_at.desc())
        .limit(10)
        .all()
    )

    # ── COPILOT (market-aware) ───────────────────────────────
    copilot_suggestions = (
        VIPAssistantSuggestion.query
        .filter_by(vip_profile_id=profile.id)
        .order_by(VIPAssistantSuggestion.created_at.desc())
        .limit(8)
        .all()
    )

    return render_template(
        "vip/realtor/frank_dashboard.html",
        vip_profile         = profile,
        modules             = get_enabled_modules(profile),
        header_name         = get_dashboard_name(profile),
        # market state
        current_market      = current_market,
        available_markets   = FRANK_MARKETS,
        market_stats        = market_stats,
        # summary
        summary             = summary,
        # pipeline
        pipeline_groups     = pipeline_groups,
        pipeline_stages     = PIPELINE_STAGES,
        # listings
        listings            = listings,
        listings_by_market  = listings_by_market,
        listing_statuses    = LISTING_STATUSES,
        listing_status_filter = status_filter,
        # flyers
        recent_flyers       = recent_flyers,
        flyers_by_market    = flyers_by_market,
        # finances
        finances_combined   = finances_combined,
        finances_by_market  = finances_by_market,
        # activity
        recent_interactions = recent_interactions,
        copilot_suggestions = copilot_suggestions,
        # portal
        portal      = "vip",
        portal_name = "VIP",
        portal_home = url_for("vip.frank_dashboard"),
    )
