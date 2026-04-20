# LoanMVP/routes/vip.py
import json
from datetime import datetime, timedelta
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, jsonify, session, current_app,
)
from flask_login import current_user

# VIP tiers that unlock the Realtor VIP Workspace.
# Keep tier comparisons case-insensitive.
VIP_ACCESS_TIERS = {"premium", "enterprise"}
from sqlalchemy import or_, func

from LoanMVP.extensions import db

# ── VIP models ────────────────────────────────────────────────────────────────
from LoanMVP.models.vip_models import (
    VIPProfile,
    VIPIncome,
    VIPExpense,
    VIPAssistantSuggestion,
    VIPDesignProject,
    VIPDesignAnnotation,
    VIPTeamMember,
)

# ── Investor / deal models ────────────────────────────────────────────────────
from LoanMVP.models.borrowers import (
    ProjectBudget,
    ProjectExpense,
    Deal,
    PropertyAnalysis,
)
from LoanMVP.models.investor_models import (
    InvestorProfile,
    FundingRequest,
)
from LoanMVP.models.property import SavedProperty

# ── Partner models ────────────────────────────────────────────────────────────
from LoanMVP.models.partner_models import (
    PartnerConnectionRequest,
    PartnerProposal,
    PartnerJob,
)

# ── Lending models ────────────────────────────────────────────────────────────
from LoanMVP.models.loan_models import (
    LoanApplication,
    LoanQuote,
    BorrowerProfile,
    LoanStatusEvent,
)
from LoanMVP.models.loan_officer_model import LoanOfficerProfile

# ── Elena models ──────────────────────────────────────────────────────────────
from LoanMVP.models.elena_models import (
    ElenaClient,
    ElenaListing,
    ElenaFlyer,
    ElenaInteraction,
)

# ── Admin ─────────────────────────────────────────────────────────────────────
from LoanMVP.models.admin import Company

# ── Services / utils ─────────────────────────────────────────────────────────
from LoanMVP.services.vip_ai_pilot import parse_vip_command
from LoanMVP.utils.decorators import role_required
from LoanMVP.utils.company_policy import (
    get_user_lending_policy,
    is_out_of_scope_loan_type,
    INVESTMENT_LOAN_TYPES,
    ALL_LOAN_TYPES,
)
from LoanMVP.utils.lending_utils import calc_payment, get_credit_profile

# ─────────────────────────────────────────────────────────────────────────────
# Blueprint
# ─────────────────────────────────────────────────────────────────────────────
vip_bp = Blueprint("vip", __name__, url_prefix="/vip")

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# Per-user markets now come from `VIPProfile.markets_json` (set during
# onboarding). There is no global fallback — realtors with zero configured
# markets see the shared "All Markets" pool.

VIP_MARKET_SESSION_KEY = "vip_market"
ALL_MARKETS = "All Markets"

PIPELINE_STAGES = [
    ("new",            "New"),
    ("warm",           "Warm"),
    ("active",         "Active"),
    ("under_contract", "Under Contract"),
    ("closed",         "Closed"),
]

LISTING_STATUSES = [
    ("active",    "Active"),
    ("pending",   "Pending"),
    ("sold",      "Sold"),
    ("withdrawn", "Withdrawn"),
]

MODULE_FIELD_MAP = {
    "crm_enabled":            "crm",
    "finances_enabled":       "finances",
    "budget_enabled":         "budget_tracker",
    "ai_pilot_enabled":       "ai_pilot",
    "content_studio_enabled": "content_studio",
    "calendar_sync_enabled":  "calendar_sync",
    "voice_enabled":          "voice_assistant",
    "sms_enabled":            "sms_assistant",
    "email_enabled":          "email_assistant",
    "canva_enabled":          "canva",
    "design_studio_enabled":  "design_studio",
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

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
            "realtor":          "realtor",
            "contractor":       "contractor",
            "designer":         "designer",
            "lender":           "loan_officer",
            "loan_officer":     "loan_officer",
            "broker":           "partner",
            "vendor":           "partner",
            "property_manager": "partner",
            "attorney":         "partner",
            "insurance":        "partner",
            "title":            "partner",
            "inspector":        "partner",
            "appraiser":        "partner",
            "cleaner":          "contractor",
            "janitorial":       "contractor",
        }
        default_role_type = role_map.get(raw_category, "partner")

    profile = VIPProfile(
        user_id=current_user.id,
        display_name=(
            getattr(current_user, "name", None)
            or getattr(current_user, "email", "VIP User")
        ),
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


def get_user_markets(profile):
    """Return this realtor's configured markets as a list of strings.

    Reads from `VIPProfile.markets_json`. Empty list when not configured,
    which the dashboard treats as "no market switcher, single pool".
    """
    if not profile:
        return []
    raw = getattr(profile, "markets_json", None) or "[]"
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        if isinstance(item, str):
            stripped = item.strip()
            if stripped and stripped not in out:
                out.append(stripped)
    return out


def set_user_markets(profile, markets):
    """Persist a list of market names onto the profile."""
    cleaned = []
    for m in markets or []:
        if not isinstance(m, str):
            continue
        m = m.strip()
        if m and m not in cleaned:
            cleaned.append(m)
    profile.markets_json = json.dumps(cleaned)
    db.session.commit()
    return cleaned


def _get_vip_market(profile=None):
    """Return the realtor's currently selected market.

    Defaults to "All Markets". If the session value isn't in the user's
    configured markets (stale state), falls back to "All Markets".
    """
    selected = session.get(VIP_MARKET_SESSION_KEY, ALL_MARKETS)
    if selected == ALL_MARKETS:
        return ALL_MARKETS
    if profile is None:
        return selected
    markets = get_user_markets(profile)
    return selected if selected in markets else ALL_MARKETS


# Kept as an alias for older call sites. New code should use `_get_vip_market`.
def _get_frank_market():
    return _get_vip_market()


# ─────────────────────────────────────────────────────────────────────────────
# VIP access gating
# ─────────────────────────────────────────────────────────────────────────────

def partner_has_vip_access(user) -> bool:
    """True when this user is allowed into the VIP Realtor Workspace.

    Gate is partner.subscription_tier in Premium/Enterprise. Admins and the
    FREE_PARTNER_MODE testing flag bypass the gate.
    """
    if not getattr(user, "is_authenticated", False):
        return False

    if (getattr(user, "role", "") or "").lower() == "admin":
        return True

    if current_app.config.get("FREE_PARTNER_MODE", False):
        return True
    if current_app.config.get("BYPASS_PARTNER_SUBSCRIPTION", False):
        return True

    partner = getattr(user, "partner_profile", None)
    if not partner:
        return False

    tier = (getattr(partner, "subscription_tier", "") or "").strip().lower()
    return tier in VIP_ACCESS_TIERS


def require_vip_access():
    """Return a redirect response if the current user lacks VIP access, else None.

    Use at the top of VIP realtor routes:

        gate = require_vip_access()
        if gate is not None:
            return gate
    """
    if partner_has_vip_access(current_user):
        return None

    partner = getattr(current_user, "partner_profile", None)
    if not partner:
        flash(
            "Create a partner profile first, then upgrade to unlock the VIP Workspace.",
            "warning",
        )
        return redirect(url_for("partners.register"))

    flash(
        "The VIP Realtor Workspace is unlocked on Premium and above. "
        "Upgrade to continue.",
        "warning",
    )
    return redirect(url_for("partners.upgrade"))


# ─────────────────────────────────────────────────────────────────────────────
# Context processor
# ─────────────────────────────────────────────────────────────────────────────

@vip_bp.app_context_processor
def inject_vip_context():
    if not getattr(current_user, "is_authenticated", False):
        return {
            "vip_profile": None,
            "modules": [],
            "partner_has_vip_access": False,
        }
    profile = get_or_create_vip_profile()
    return {
        "vip_profile":            profile,
        "modules":                get_enabled_modules(profile),
        "partner_has_vip_access": partner_has_vip_access(current_user),
    }


# ─────────────────────────────────────────────────────────────────────────────
# INDEX — smart routing
# ─────────────────────────────────────────────────────────────────────────────

@vip_bp.get("/")
@role_required("partner_group", "admin")
def index():
    profile = get_or_create_vip_profile()

    if profile.role_type in ("loan_officer", "lender"):
        policy = get_user_lending_policy(current_user)
        if policy["is_caughman_mason"]:
            return redirect(url_for("vip.loan_officer_dashboard"))
        return redirect(url_for("vip.loan_officer_external_dashboard"))

    # Realtors require a paid VIP tier. Send non-upgraded realtors to the
    # upgrade page so there is a single funnel into the VIP experience.
    if profile.role_type == "realtor" and not partner_has_vip_access(current_user):
        gate = require_vip_access()
        if gate is not None:
            return gate

    role_map = {
        "realtor":    "vip.realtor_dashboard",
        "contractor": "vip.contractor_dashboard",
        "designer":   "vip.designer_dashboard",
        "partner":    "vip.partner_dashboard",
    }
    return redirect(url_for(role_map.get(profile.role_type, "vip.partner_dashboard")))


# ─────────────────────────────────────────────────────────────────────────────
# REALTOR DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────

@vip_bp.post("/realtor/market-switch")
@role_required("partner_group", "admin")
def realtor_market_switch():
    gate = require_vip_access()
    if gate is not None:
        return gate

    profile  = get_or_create_vip_profile()
    markets  = get_user_markets(profile)
    selected = (request.form.get("market") or ALL_MARKETS).strip()
    allowed  = {ALL_MARKETS, *markets}
    session[VIP_MARKET_SESSION_KEY] = selected if selected in allowed else ALL_MARKETS

    next_url = request.form.get("next") or url_for("vip.realtor_dashboard")
    return redirect(next_url)


@vip_bp.get("/realtor")
@role_required("partner_group", "admin")
def realtor_dashboard():
    gate = require_vip_access()
    if gate is not None:
        return gate

    profile           = get_or_create_vip_profile()
    now               = datetime.utcnow()
    week_ago          = now - timedelta(days=7)
    available_markets = get_user_markets(profile)
    current_market    = _get_vip_market(profile)
    multi_market      = len(available_markets) >= 2

    # When the profile has exactly one market, auto-scope everything to it so
    # the dashboard isn't cluttered with a switcher the user doesn't need.
    effective_market = current_market
    if len(available_markets) == 1:
        effective_market = available_markets[0]

    def _scope_listings(q):
        if effective_market != ALL_MARKETS:
            q = q.filter(ElenaListing.market == effective_market)
        return q

    total_clients = ElenaClient.query.count()
    new_leads     = ElenaClient.query.filter(ElenaClient.created_at >= week_ago).count()

    active_listings = _scope_listings(
        ElenaListing.query.filter_by(status="active")
    ).count()

    followups_due = ElenaInteraction.query.filter(
        ElenaInteraction.due_at.isnot(None),
        ElenaInteraction.due_at >= now,
        ElenaInteraction.due_at <= now + timedelta(days=7),
    ).count()

    summary = {
        "total_clients":   total_clients,
        "new_leads":       new_leads,
        "active_listings": active_listings,
        # Combined total across every market this realtor operates in. Used
        # on the "Active Listings" stat card when viewing All Markets so the
        # number isn't artificially filtered.
        "total_listings":  ElenaListing.query.filter_by(status="active").count(),
        "followups_due":   followups_due,
    }

    pipeline_groups = []
    canonical_keys  = {s[0] for s in PIPELINE_STAGES}

    for stage_key, stage_label in PIPELINE_STAGES:
        q = ElenaClient.query.filter_by(pipeline_stage=stage_key)
        pipeline_groups.append({
            "key":     stage_key,
            "label":   stage_label,
            "count":   q.count(),
            "clients": q.order_by(ElenaClient.updated_at.desc()).limit(12).all(),
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
                        .order_by(ElenaClient.updated_at.desc()).limit(12).all()),
        })

    status_filter = (request.args.get("listing_status") or "").strip().lower()
    listings_q    = _scope_listings(ElenaListing.query)
    if status_filter and status_filter in {s[0] for s in LISTING_STATUSES}:
        listings_q = listings_q.filter_by(status=status_filter)
    listings = listings_q.order_by(ElenaListing.updated_at.desc()).limit(12).all()

    recent_interactions = (
        ElenaInteraction.query
        .order_by(ElenaInteraction.created_at.desc())
        .limit(10).all()
    )

    flyers_q = ElenaFlyer.query
    if effective_market != ALL_MARKETS:
        flyers_q = (flyers_q
                    .join(ElenaListing, ElenaFlyer.listing_id == ElenaListing.id)
                    .filter(ElenaListing.market == effective_market))
    recent_flyers = flyers_q.order_by(ElenaFlyer.created_at.desc()).limit(5).all()

    copilot_suggestions = (
        VIPAssistantSuggestion.query
        .filter_by(vip_profile_id=profile.id)
        .order_by(VIPAssistantSuggestion.created_at.desc())
        .limit(5).all()
    )

    # Per-market breakdowns for the dual-market view. Only populated when
    # the realtor has 2+ markets. Empty dicts otherwise — the template uses
    # `multi_market` to decide whether to render these sections.
    market_stats       = {}
    listings_by_market = {}
    flyers_by_market   = {}
    finances_combined  = None
    finances_by_market = {}

    if multi_market:
        for market in available_markets:
            market_stats[market] = {
                "active_listings": (
                    ElenaListing.query
                    .filter_by(status="active", market=market)
                    .count()
                ),
                # Clients aren't market-scoped today (no column on
                # ElenaClient), so this mirrors Frank's prior behavior of
                # showing the combined client total per market card.
                "clients": total_clients,
            }

            listings_by_market[market] = (
                ElenaListing.query
                .filter_by(market=market, status="active")
                .order_by(ElenaListing.updated_at.desc())
                .limit(6).all()
            )

            flyers_by_market[market] = (
                ElenaFlyer.query
                .join(ElenaListing, ElenaFlyer.listing_id == ElenaListing.id)
                .filter(ElenaListing.market == market)
                .order_by(ElenaFlyer.created_at.desc())
                .limit(4).all()
            )

        all_income   = VIPIncome.query.filter_by(vip_profile_id=profile.id).all()
        all_expenses = VIPExpense.query.filter_by(vip_profile_id=profile.id).all()

        total_income   = sum((i.amount or 0) for i in all_income)
        total_expenses = sum((e.amount or 0) for e in all_expenses)
        finances_combined = {
            "income":   total_income,
            "expenses": total_expenses,
            "net":      total_income - total_expenses,
        }

        for market in available_markets:
            m_income   = sum((i.amount or 0) for i in all_income   if getattr(i, "market", None) == market)
            m_expenses = sum((e.amount or 0) for e in all_expenses if getattr(e, "market", None) == market)
            finances_by_market[market] = {
                "income":   m_income,
                "expenses": m_expenses,
                "net":      m_income - m_expenses,
            }

    return render_template(
        "vip/realtor/dashboard.html",
        vip_profile           = profile,
        modules               = get_enabled_modules(profile),
        header_name           = get_dashboard_name(profile),
        summary               = summary,
        pipeline_groups       = pipeline_groups,
        pipeline_stages       = PIPELINE_STAGES,
        recent_interactions   = recent_interactions,
        listings              = listings,
        listing_statuses      = LISTING_STATUSES,
        listing_status_filter = status_filter,
        recent_flyers         = recent_flyers,
        copilot_suggestions   = copilot_suggestions,
        # `effective_market` reflects what the queries were actually
        # scoped to — for a single-market realtor this is their one market
        # even though the session still holds "All Markets".
        current_market        = effective_market,
        available_markets     = available_markets,
        multi_market          = multi_market,
        market_stats          = market_stats,
        listings_by_market    = listings_by_market,
        flyers_by_market      = flyers_by_market,
        finances_combined     = finances_combined,
        finances_by_market    = finances_by_market,
        portal                = "vip",
        portal_name           = "VIP",
        portal_home           = url_for("vip.realtor_dashboard"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# FRANK DUAL-MARKET DASHBOARD (legacy aliases — now unified into realtor_dashboard)
# ─────────────────────────────────────────────────────────────────────────────
# The standalone `/vip/frank` endpoint has been collapsed into the shared
# realtor dashboard. Dual-market behavior now comes from the per-user
# `VIPProfile.markets_json` list. These endpoints stay as redirects so any
# existing bookmarks / links keep working.

@vip_bp.post("/frank/market-switch")
@role_required("partner_group", "admin")
def frank_market_switch():
    return realtor_market_switch()


@vip_bp.get("/frank")
@role_required("partner_group", "admin")
def frank_dashboard():
    return redirect(url_for("vip.realtor_dashboard"))


# ─────────────────────────────────────────────────────────────────────────────
# REALTOR — Investor flow
# ─────────────────────────────────────────────────────────────────────────────

@vip_bp.get("/realtor/investor-flow")
@role_required("partner_group", "admin")
def realtor_investor_flow():
    gate = require_vip_access()
    if gate is not None:
        return gate

    profile           = get_or_create_vip_profile()
    partner           = getattr(current_user, "partner_profile", None)
    available_markets = get_user_markets(profile)
    current_market    = _get_vip_market(profile)

    matched_properties = []

    analyzed_ids = (
        db.session.query(PropertyAnalysis.investor_profile_id)
        .filter(PropertyAnalysis.investor_profile_id.isnot(None))
        .distinct().all()
    )
    analyzed_investor_ids = [row[0] for row in analyzed_ids]

    if analyzed_investor_ids:
        sp_query = SavedProperty.query.filter(
            SavedProperty.investor_profile_id.in_(analyzed_investor_ids)
        )

        market_matches = []
        geo_matches    = []

        if current_market != "All Markets":
            if hasattr(SavedProperty, "market"):
                market_matches = sp_query.filter_by(market=current_market).limit(20).all()

            if not market_matches:
                # Realtors now define their own markets, so we fall back to
                # fuzzy-matching the market label against the saved property
                # city/state instead of hard-coding state codes.
                label_tokens = [
                    t for t in (current_market or "").lower().split() if t
                ]
                if label_tokens:
                    conditions = []
                    for token in label_tokens:
                        like = f"%{token}%"
                        conditions.append(db.func.lower(SavedProperty.city).like(like))
                        if hasattr(SavedProperty, "state"):
                            conditions.append(db.func.lower(SavedProperty.state).like(like))
                    geo_matches = sp_query.filter(or_(*conditions)).limit(20).all()
        else:
            market_matches = sp_query.limit(30).all()

        for sp in (market_matches or geo_matches):
            deal     = Deal.query.filter_by(saved_property_id=sp.id).first()
            analysis = (
                PropertyAnalysis.query
                .filter_by(investor_profile_id=sp.investor_profile_id)
                .order_by(PropertyAnalysis.created_at.desc())
                .first()
            )
            matched_properties.append({
                "property": sp,
                "deal":     deal,
                "analysis": analysis,
                "arv":      float(deal.arv or 0) if deal else float(getattr(analysis, "arv", 0) or 0),
                "rehab":    float(deal.rehab_cost or 0) if deal else float(getattr(analysis, "rehab_cost", 0) or 0),
                "strategy": deal.strategy if deal else None,
                "address":  (getattr(sp, "address", None)
                             or (deal.address if deal else None)
                             or (analysis.address if analysis else "—")),
            })

    realtor_requests = []
    if partner:
        realtor_requests = (
            PartnerConnectionRequest.query
            .filter_by(partner_id=partner.id)
            .filter(PartnerConnectionRequest.category.in_(
                ["realtor", "listing", "comps", "market_analysis", "buyer_agent"]
            ))
            .filter(PartnerConnectionRequest.status.in_(["pending", "accepted"]))
            .order_by(PartnerConnectionRequest.created_at.desc())
            .limit(10).all()
        )

    return render_template(
        "vip/realtor/investor_flow.html",
        vip_profile        = profile,
        modules            = get_enabled_modules(profile),
        header_name        = get_dashboard_name(profile),
        matched_properties = matched_properties,
        realtor_requests   = realtor_requests,
        current_market     = current_market,
        available_markets  = available_markets,
        multi_market       = len(available_markets) >= 2,
        portal             = "vip",
        portal_name        = "VIP",
        portal_home        = url_for("vip.realtor_dashboard"),
    )


@vip_bp.post("/realtor/deal/<int:deal_id>/attach-market-data")
@role_required("partner_group", "admin")
def realtor_attach_market_data(deal_id):
    gate = require_vip_access()
    if gate is not None:
        return gate

    profile = get_or_create_vip_profile()
    partner = getattr(current_user, "partner_profile", None)
    deal    = Deal.query.get_or_404(deal_id)

    suggested_arv  = request.form.get("suggested_arv", type=float)
    comps_note     = (request.form.get("comps_note") or "").strip()
    market_note    = (request.form.get("market_note") or "").strip()
    days_on_market = request.form.get("days_on_market", type=int)
    list_price     = request.form.get("list_price", type=float)

    results = deal.results_json or {}
    results["realtor_market_data"] = {
        "realtor_id":    partner.id if partner else None,
        "realtor_name":  partner.name if partner else profile.display_name,
        "market":        _get_vip_market(profile),
        "suggested_arv": suggested_arv,
        "comps_note":    comps_note,
        "market_note":   market_note,
        "days_on_market": days_on_market,
        "list_price":    list_price,
        "submitted_at":  datetime.utcnow().isoformat(),
    }

    if suggested_arv and deal.arv:
        arv_delta = suggested_arv - float(deal.arv)
        results["realtor_market_data"]["arv_delta"]     = round(arv_delta, 2)
        results["realtor_market_data"]["arv_delta_pct"] = (
            round((arv_delta / float(deal.arv)) * 100, 2) if deal.arv > 0 else None
        )

    deal.results_json = results
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(deal, "results_json")
    db.session.commit()

    flash("Market data attached to deal.", "success")
    return redirect(url_for("vip.realtor_investor_flow"))


# ─────────────────────────────────────────────────────────────────────────────
# CONTRACTOR DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────

@vip_bp.get("/contractor")
@role_required("partner_group", "admin")
def contractor_dashboard():
    profile = get_or_create_vip_profile()
    partner = getattr(current_user, "partner_profile", None)

    requests_with_context = []
    active_jobs = []
    stats = {
        "open_requests":     0,
        "active_jobs":       0,
        "completed_jobs":    0,
        "total_volume":      0.0,
        "ai_estimate_total": 0.0,
        "contractor_total":  0.0,
    }

    if partner:
        raw_requests = (
            PartnerConnectionRequest.query
            .filter_by(partner_id=partner.id)
            .filter(PartnerConnectionRequest.status.in_(["pending", "accepted", "awaiting_match"]))
            .order_by(PartnerConnectionRequest.created_at.desc())
            .limit(20).all()
        )

        for req in raw_requests:
            requests_with_context.append({
                "request": req,
                "context": _build_request_deal_context(req),
            })

        stats["open_requests"] = len(requests_with_context)

        raw_jobs = (
            PartnerJob.query
            .filter_by(partner_id=partner.id)
            .order_by(PartnerJob.created_at.desc())
            .limit(20).all()
        )

        for job in raw_jobs:
            job_data = {"job": job, "budget": None, "ai_estimate": None, "delta": None, "delta_pct": None}

            budget = None
            if job.investor_profile_id:
                budget = (
                    ProjectBudget.query
                    .filter_by(investor_profile_id=job.investor_profile_id)
                    .order_by(ProjectBudget.updated_at.desc())
                    .first()
                )

            if budget:
                job_data["budget"] = budget
                deal = None
                if hasattr(job, "deal_id") and job.deal_id:
                    deal = Deal.query.get(job.deal_id)
                elif budget.deal_id:
                    deal = Deal.query.get(budget.deal_id)

                if deal and deal.rehab_cost:
                    ai_est  = float(deal.rehab_cost or 0)
                    co_cost = float(budget.total_cost or 0)
                    job_data["ai_estimate"] = ai_est
                    job_data["delta"]       = round(co_cost - ai_est, 2)
                    job_data["delta_pct"]   = (
                        round(((co_cost - ai_est) / ai_est) * 100, 1)
                        if ai_est > 0 else None
                    )

            active_jobs.append(job_data)

        stats["active_jobs"]       = sum(1 for j in active_jobs if j["job"].status in ["Open", "in_progress"])
        stats["completed_jobs"]    = sum(1 for j in active_jobs if j["job"].status == "completed")
        stats["total_volume"]      = sum(float(j["budget"].total_cost or 0) for j in active_jobs if j["budget"] and j["job"].status == "completed")
        stats["ai_estimate_total"] = sum(j["ai_estimate"] for j in active_jobs if j["ai_estimate"])
        stats["contractor_total"]  = sum(float(j["budget"].total_cost or 0) for j in active_jobs if j["budget"])

    copilot_suggestions = (
        VIPAssistantSuggestion.query
        .filter_by(vip_profile_id=profile.id)
        .order_by(VIPAssistantSuggestion.created_at.desc())
        .limit(5).all()
    )

    recent_proposals = []
    if partner:
        recent_proposals = (
            PartnerProposal.query
            .filter_by(partner_id=partner.id)
            .order_by(PartnerProposal.created_at.desc())
            .limit(5).all()
        )

    return render_template(
        "vip/contractor/dashboard.html",
        vip_profile           = profile,
        modules               = get_enabled_modules(profile),
        header_name           = get_dashboard_name(profile),
        requests_with_context = requests_with_context,
        active_jobs           = active_jobs,
        recent_proposals      = recent_proposals,
        stats                 = stats,
        copilot_suggestions   = copilot_suggestions,
        portal                = "vip",
        portal_name           = "VIP",
        portal_home           = url_for("vip.contractor_dashboard"),
    )


def _build_request_deal_context(req):
    ctx = {
        "deal": None, "property_analysis": None,
        "ai_rehab_estimate": None, "arv": None,
        "purchase_price": None, "strategy": None,
        "address":   req.related_address(),
        "requester": req.requester_name(),
        "budget":    req.budget,
        "timeline":  req.timeline,
    }

    if req.deal_id:
        deal = Deal.query.get(req.deal_id)
        if deal:
            ctx.update({
                "deal":              deal,
                "ai_rehab_estimate": float(deal.rehab_cost or 0),
                "arv":               float(deal.arv or 0),
                "purchase_price":    float(deal.purchase_price or 0),
                "strategy":          deal.strategy,
                "address":           ctx["address"] or deal.address,
            })
            if deal.rehab_scope_json:
                ctx["rehab_scope"] = deal.rehab_scope_json
            return ctx

    if req.saved_property_id:
        analysis = (
            PropertyAnalysis.query
            .filter_by(investor_profile_id=req.investor_profile_id)
            .order_by(PropertyAnalysis.created_at.desc())
            .first()
        )
        if analysis:
            ctx.update({
                "property_analysis": analysis,
                "ai_rehab_estimate": float(analysis.rehab_cost or 0),
                "arv":               float(analysis.arv or 0),
                "purchase_price":    float(analysis.purchase_price or 0),
                "address":           ctx["address"] or analysis.address,
            })

    return ctx


@vip_bp.post("/contractor/request/<int:req_id>/accept")
@role_required("partner_group", "admin")
def contractor_accept_request(req_id):
    profile = get_or_create_vip_profile()
    partner = getattr(current_user, "partner_profile", None)

    if not partner:
        flash("Partner profile not found.", "danger")
        return redirect(url_for("vip.contractor_dashboard"))

    req        = PartnerConnectionRequest.query.filter_by(id=req_id, partner_id=partner.id).first_or_404()
    req.status = "accepted"
    req.responded_at = datetime.utcnow()

    job = PartnerJob(
        partner_id          = partner.id,
        investor_profile_id = req.investor_profile_id,
        borrower_profile_id = req.borrower_profile_id,
        property_id         = req.property_id,
        title               = req.title or f"{partner.category or 'Contractor'} Job",
        scope               = req.message,
        status              = "Open",
    )
    if hasattr(job, "deal_id") and req.deal_id:
        job.deal_id = req.deal_id

    db.session.add(job)
    db.session.commit()

    flash("Request accepted. Job created.", "success")
    return redirect(url_for("vip.contractor_dashboard"))


@vip_bp.post("/contractor/job/<int:job_id>/submit-scope")
@role_required("partner_group", "admin")
def contractor_submit_scope(job_id):
    profile = get_or_create_vip_profile()
    partner = getattr(current_user, "partner_profile", None)

    if not partner:
        flash("Partner profile not found.", "danger")
        return redirect(url_for("vip.contractor_dashboard"))

    job            = PartnerJob.query.filter_by(id=job_id, partner_id=partner.id).first_or_404()
    labor_cost     = float(request.form.get("labor_cost")     or 0)
    materials_cost = float(request.form.get("materials_cost") or 0)
    other_cost     = float(request.form.get("other_cost")     or 0)
    timeline       = (request.form.get("timeline") or "").strip()
    scope_notes    = (request.form.get("scope_notes") or "").strip()
    total          = labor_cost + materials_cost + other_cost

    deal_id = getattr(job, "deal_id", None)
    budget  = None

    if deal_id:
        budget = ProjectBudget.query.filter_by(deal_id=deal_id).first()
    if not budget and job.investor_profile_id:
        budget = ProjectBudget.query.filter_by(investor_profile_id=job.investor_profile_id).first()
    if not budget:
        budget = ProjectBudget(
            investor_profile_id = job.investor_profile_id,
            borrower_profile_id = job.borrower_profile_id,
            deal_id             = deal_id,
            budget_type         = "rehab",
            name                = job.title or "Contractor Scope",
            project_name        = job.title,
        )
        db.session.add(budget)
        db.session.flush()

    budget.labor_cost     = labor_cost
    budget.materials_cost = materials_cost
    budget.total_cost     = total
    if scope_notes:
        budget.notes = f"[Contractor: {partner.name}]\n{scope_notes}"

    for cat, desc, amt in zip(
        request.form.getlist("line_category[]"),
        request.form.getlist("line_description[]"),
        request.form.getlist("line_amount[]"),
    ):
        if not desc:
            continue
        db.session.add(ProjectExpense(
            budget_id        = budget.id,
            category         = cat or "General",
            description      = desc,
            vendor           = partner.name or partner.company,
            estimated_amount = float(amt or 0),
            status           = "planned",
        ))

    budget.recalculate_totals()

    if deal_id:
        deal = Deal.query.get(deal_id)
        if deal and deal.rehab_cost:
            ai_est  = float(deal.rehab_cost)
            co_cost = float(budget.total_cost)
            delta   = co_cost - ai_est
            results = deal.results_json or {}
            results.setdefault("contractor_feedback", []).append({
                "partner_id":       partner.id,
                "partner_name":     partner.name or partner.company,
                "ai_estimate":      ai_est,
                "contractor_total": co_cost,
                "labor":            labor_cost,
                "materials":        materials_cost,
                "delta":            delta,
                "delta_pct":        round((delta / ai_est) * 100, 2) if ai_est > 0 else 0,
                "timeline":         timeline,
                "submitted_at":     datetime.utcnow().isoformat(),
            })
            deal.results_json = results
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(deal, "results_json")

    proposal = PartnerProposal(
        partner_id         = partner.id,
        title              = job.title or "Scope Submission",
        scope_of_work      = scope_notes,
        labor_cost         = labor_cost,
        materials_cost     = materials_cost,
        other_cost         = other_cost,
        estimated_timeline = timeline,
        status             = "sent",
        sent_at            = datetime.utcnow(),
    )
    proposal.calculate_total()
    db.session.add(proposal)
    db.session.commit()

    flash(f"Scope submitted. Total: ${total:,.0f}", "success")
    return redirect(url_for("vip.contractor_dashboard"))


# ─────────────────────────────────────────────────────────────────────────────
# DESIGNER DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────

@vip_bp.get("/designer")
@role_required("partner_group", "admin")
def designer_dashboard():
    profile = get_or_create_vip_profile()
    partner = getattr(current_user, "partner_profile", None)

    projects = (
        VIPDesignProject.query
        .filter_by(vip_profile_id=profile.id)
        .order_by(VIPDesignProject.created_at.desc())
        .limit(10).all()
    )

    recent_requests = []
    if partner:
        recent_requests = (
            PartnerConnectionRequest.query
            .filter_by(partner_id=partner.id)
            .order_by(PartnerConnectionRequest.created_at.desc())
            .limit(8).all()
        )

    copilot_suggestions = (
        VIPAssistantSuggestion.query
        .filter_by(vip_profile_id=profile.id)
        .order_by(VIPAssistantSuggestion.created_at.desc())
        .limit(5).all()
    )

    return render_template(
        "vip/designer/dashboard.html",
        vip_profile         = profile,
        modules             = get_enabled_modules(profile),
        header_name         = get_dashboard_name(profile),
        projects            = projects,
        recent_requests     = recent_requests,
        copilot_suggestions = copilot_suggestions,
        portal              = "vip",
        portal_name         = "VIP",
        portal_home         = url_for("vip.designer_dashboard"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# PARTNER DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────

@vip_bp.get("/partner")
@role_required("partner_group", "admin")
def partner_dashboard():
    profile = get_or_create_vip_profile()
    partner = getattr(current_user, "partner_profile", None)

    recent_requests = []
    stats = {"pending": 0, "accepted": 0, "completed": 0}

    if partner:
        recent_requests = (
            PartnerConnectionRequest.query
            .filter_by(partner_id=partner.id)
            .order_by(PartnerConnectionRequest.created_at.desc())
            .limit(8).all()
        )
        stats["pending"]   = sum(1 for r in recent_requests if r.status == "pending")
        stats["accepted"]  = sum(1 for r in recent_requests if r.status == "accepted")
        stats["completed"] = sum(1 for r in recent_requests if r.status == "completed")

    copilot_suggestions = (
        VIPAssistantSuggestion.query
        .filter_by(vip_profile_id=profile.id)
        .order_by(VIPAssistantSuggestion.created_at.desc())
        .limit(5).all()
    )

    return render_template(
        "vip/partner/dashboard.html",
        vip_profile         = profile,
        modules             = get_enabled_modules(profile),
        header_name         = get_dashboard_name(profile),
        recent_requests     = recent_requests,
        stats               = stats,
        copilot_suggestions = copilot_suggestions,
        portal              = "vip",
        portal_name         = "VIP",
        portal_home         = url_for("vip.partner_dashboard"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# LOAN OFFICER — Caughman Mason (investment only)
# ─────────────────────────────────────────────────────────────────────────────

@vip_bp.get("/loan-officer")
@role_required("partner_group", "admin")
def loan_officer_dashboard():
    profile    = get_or_create_vip_profile()
    policy     = get_user_lending_policy(current_user)
    lo_profile = LoanOfficerProfile.query.filter_by(user_id=current_user.id).first()

    if not policy["is_caughman_mason"] and not policy["investment_only"]:
        return redirect(url_for("vip.loan_officer_external_dashboard"))

    raw_funding = (
        FundingRequest.query
        .filter(FundingRequest.status.in_(["submitted", "reviewing"]))
        .order_by(FundingRequest.created_at.desc())
        .limit(20).all()
    )

    funding_with_context = []
    for fr in raw_funding:
        deal = Deal.query.get(fr.deal_id) if fr.deal_id else None
        if deal:
            strategy = (getattr(deal, "strategy", "") or "").lower()
            if strategy in {"primary", "owner occupied", "owner_occupied"}:
                continue
        funding_with_context.append({
            "request": fr,
            "deal":    deal,
            "context": _build_funding_context(fr, deal),
        })

    capital_with_context = []
    out_of_scope_loans   = []

    assigned_loans = (
        LoanApplication.query.filter_by(loan_officer_id=lo_profile.id)
        .order_by(LoanApplication.created_at.desc()).all()
    ) if lo_profile else (
        LoanApplication.query
        .filter(LoanApplication.status.in_(["Capital Submitted", "Submitted", "Processing", "Under Review"]))
        .order_by(LoanApplication.created_at.desc()).limit(15).all()
    )

    for loan in assigned_loans:
        if is_out_of_scope_loan_type(loan.loan_type, policy):
            out_of_scope_loans.append(loan)
            continue
        capital_with_context.append({"loan": loan, "context": _build_loan_deal_context(loan)})

    recent_quotes = _get_lo_recent_quotes(lo_profile)

    stats = {
        "funding_requests": len(funding_with_context),
        "capital_loans":    len(capital_with_context),
        "quotes_sent":      len(recent_quotes),
        "pending_review":   sum(1 for i in funding_with_context if i["request"].status == "submitted"),
        "out_of_scope":     len(out_of_scope_loans),
        "total_quoted":     sum(float(getattr(q, "loan_amount", 0) or 0) for q in recent_quotes),
    }

    copilot_suggestions = (
        VIPAssistantSuggestion.query
        .filter_by(vip_profile_id=profile.id)
        .order_by(VIPAssistantSuggestion.created_at.desc())
        .limit(5).all()
    )

    return render_template(
        "vip/loan_officer/dashboard.html",
        vip_profile           = profile,
        modules               = get_enabled_modules(profile),
        header_name           = get_dashboard_name(profile),
        policy                = policy,
        funding_with_context  = funding_with_context,
        capital_with_context  = capital_with_context,
        out_of_scope_loans    = out_of_scope_loans,
        recent_quotes         = recent_quotes,
        stats                 = stats,
        copilot_suggestions   = copilot_suggestions,
        investment_loan_types = INVESTMENT_LOAN_TYPES,
        portal                = "vip",
        portal_name           = "VIP",
        portal_home           = url_for("vip.loan_officer_dashboard"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# LOAN OFFICER — External licensed (all loan types)
# ─────────────────────────────────────────────────────────────────────────────

@vip_bp.get("/loan-officer/workspace")
@role_required("partner_group", "admin")
def loan_officer_external_dashboard():
    profile    = get_or_create_vip_profile()
    policy     = get_user_lending_policy(current_user)
    lo_profile = LoanOfficerProfile.query.filter_by(user_id=current_user.id).first()

    if policy["is_caughman_mason"]:
        return redirect(url_for("vip.loan_officer_dashboard"))

    my_borrowers = (
        BorrowerProfile.query.filter_by(assigned_officer_id=lo_profile.id)
        .order_by(BorrowerProfile.created_at.desc()).limit(20).all()
    ) if lo_profile else []

    my_loans = (
        LoanApplication.query.filter_by(loan_officer_id=lo_profile.id)
        .order_by(LoanApplication.created_at.desc()).limit(30).all()
    ) if lo_profile else []

    def _norm(v):
        return (v or "").strip().lower()

    pipeline = {
        "submitted":      [l for l in my_loans if _norm(l.status) in {"submitted", "application submitted"}],
        "in_review":      [l for l in my_loans if _norm(l.status) in {"in review", "in_review", "processing", "under review"}],
        "approved":       [l for l in my_loans if _norm(l.status) == "approved"],
        "clear_to_close": [l for l in my_loans if _norm(l.status) in {"clear to close", "ctc"}],
        "closed":         [l for l in my_loans if _norm(l.status) == "closed"],
        "declined":       [l for l in my_loans if _norm(l.status) == "declined"],
    }

    loan_type_counts = {}
    for loan in my_loans:
        lt = (loan.loan_type or "Other").title()
        loan_type_counts[lt] = loan_type_counts.get(lt, 0) + 1

    recent_quotes = _get_lo_recent_quotes(lo_profile)

    stats = {
        "total_borrowers": len(my_borrowers),
        "total_loans":     len(my_loans),
        "in_pipeline":     len([l for l in my_loans if _norm(l.status) not in {"closed", "declined"}]),
        "closed":          len(pipeline["closed"]),
        "quotes_sent":     len(recent_quotes),
        "total_volume":    sum(float(l.amount or 0) for l in pipeline["closed"]),
    }

    copilot_suggestions = (
        VIPAssistantSuggestion.query
        .filter_by(vip_profile_id=profile.id)
        .order_by(VIPAssistantSuggestion.created_at.desc())
        .limit(5).all()
    )

    return render_template(
        "vip/loan_officer/external_dashboard.html",
        vip_profile         = profile,
        modules             = get_enabled_modules(profile),
        header_name         = get_dashboard_name(profile),
        policy              = policy,
        my_borrowers        = my_borrowers,
        my_loans            = my_loans,
        pipeline            = pipeline,
        loan_type_counts    = loan_type_counts,
        my_quotes           = recent_quotes,
        stats               = stats,
        copilot_suggestions = copilot_suggestions,
        lo_profile          = lo_profile,
        all_loan_types      = ALL_LOAN_TYPES,
        portal              = "vip",
        portal_name         = "VIP",
        portal_home         = url_for("vip.loan_officer_external_dashboard"),
    )


# ── LO helper functions ───────────────────────────────────────────────────────

def _build_funding_context(fr, deal):
    ctx = {
        "requested_amount":    float(fr.requested_amount or 0),
        "arv":                 None,
        "purchase_price":      None,
        "rehab_cost":          None,
        "strategy":            None,
        "address":             None,
        "deal_score":          None,
        "estimated_profit":    None,
        "estimated_roi":       None,
        "ltv":                 None,
        "contractor_verified": False,
        "contractor_rehab":    None,
        "realtor_arv":         None,
        "arv_confidence":      "single source",
    }
    if not deal:
        return ctx

    ctx.update({
        "arv":              float(deal.arv or 0),
        "purchase_price":   float(deal.purchase_price or 0),
        "rehab_cost":       float(deal.rehab_cost or 0),
        "strategy":         deal.strategy,
        "address":          deal.address,
        "deal_score":       deal.deal_score,
        "estimated_profit": deal.estimated_profit,
        "estimated_roi":    deal.estimated_roi_percent,
    })

    if ctx["arv"] and ctx["requested_amount"]:
        ctx["ltv"] = round(ctx["requested_amount"] / ctx["arv"], 3)

    results = deal.results_json or {}

    feedback = results.get("contractor_feedback", [])
    if feedback:
        ctx["contractor_verified"] = True
        ctx["contractor_rehab"]    = feedback[-1].get("contractor_total")

    rmd = results.get("realtor_market_data", {})
    if rmd.get("suggested_arv"):
        ctx["realtor_arv"]    = rmd["suggested_arv"]
        ctx["arv_confidence"] = "high"

    return ctx


def _build_loan_deal_context(loan):
    from LoanMVP.utils.lending_utils import estimate_rate
    ctx = {
        "arv":                 float(loan.property_value or 0),
        "amount":              float(loan.amount or 0),
        "deal":                None,
        "deal_score":          None,
        "contractor_verified": False,
        "suggested_rate":      None,
        "suggested_payment":   None,
        "ltv":                 None,
    }

    if ctx["arv"] and ctx["amount"]:
        ctx["ltv"] = round(ctx["amount"] / ctx["arv"], 3)

    investor_profile = getattr(loan, "investor_profile", None)
    if investor_profile:
        deal = Deal.query.filter_by(
            investor_profile_id=investor_profile.id
        ).order_by(Deal.updated_at.desc()).first()

        if deal:
            ctx["deal"]       = deal
            ctx["deal_score"] = deal.deal_score
            ctx["arv"]        = float(deal.arv or loan.property_value or 0)
            if (deal.results_json or {}).get("contractor_feedback"):
                ctx["contractor_verified"] = True

    borrower = getattr(loan, "borrower_profile", None)
    if borrower:
        credit = get_credit_profile(borrower)
        score  = getattr(credit, "credit_score", None)
        ctx["suggested_rate"]    = estimate_rate(score, ctx["ltv"], loan.loan_type)
        ctx["suggested_payment"] = calc_payment(ctx["amount"], ctx["suggested_rate"])

    return ctx


def _get_lo_recent_quotes(lo_profile):
    if not lo_profile:
        return []
    try:
        if hasattr(LoanQuote, "loan_officer_id"):
            return (
                LoanQuote.query
                .filter_by(loan_officer_id=lo_profile.id)
                .order_by(LoanQuote.created_at.desc())
                .limit(8).all()
            )
        return (
            LoanQuote.query
            .join(LoanApplication, LoanQuote.loan_application_id == LoanApplication.id)
            .filter(LoanApplication.loan_officer_id == lo_profile.id)
            .order_by(LoanQuote.created_at.desc())
            .limit(8).all()
        )
    except Exception:
        return []


@vip_bp.post("/loan-officer/funding/<int:funding_id>/quote")
@role_required("partner_group", "admin")
def loan_officer_submit_quote(funding_id):
    profile    = get_or_create_vip_profile()
    policy     = get_user_lending_policy(current_user)
    lo_profile = LoanOfficerProfile.query.filter_by(user_id=current_user.id).first()
    fr         = FundingRequest.query.get_or_404(funding_id)
    deal       = Deal.query.get(fr.deal_id) if fr.deal_id else None
    loan_type  = (request.form.get("loan_type") or "").strip()

    if policy["is_caughman_mason"] and is_out_of_scope_loan_type(loan_type, policy):
        flash(f"Caughman Mason is not licensed for '{loan_type}'.", "danger")
        return redirect(url_for("vip.loan_officer_dashboard"))

    quoted_amount = request.form.get("quoted_amount", type=float)
    rate          = request.form.get("rate",          type=float)
    term_months   = request.form.get("term_months",   type=int) or 12
    notes         = (request.form.get("notes") or "").strip()
    decision      = (request.form.get("decision") or "quote").strip()
    points        = request.form.get("points", type=float) or 0.0

    if not quoted_amount or not rate:
        flash("Amount and rate are required.", "warning")
        return redirect(url_for("vip.loan_officer_dashboard"))

    quote = LoanQuote(
        rate          = rate,
        term_months   = term_months,
        loan_amount   = quoted_amount,
        loan_type     = loan_type or "Investor Capital",
        status        = "sent",
        ai_suggestion = notes,
        created_at    = datetime.utcnow(),
    )

    if deal:
        linked_loan = LoanApplication.query.filter(
            LoanApplication.investor_profile_id == deal.investor_profile_id
        ).order_by(LoanApplication.created_at.desc()).first()
        if linked_loan:
            quote.loan_application_id = linked_loan.id
            quote.borrower_profile_id = linked_loan.borrower_profile_id

    db.session.add(quote)
    db.session.flush()

    fr.status     = "reviewing" if decision == "quote" else decision
    fr.updated_at = datetime.utcnow()

    if deal:
        results   = deal.results_json or {}
        requested = float(fr.requested_amount or 0)
        delta     = quoted_amount - requested

        results.setdefault("lo_quotes", []).append({
            "lo_id":           lo_profile.id if lo_profile else None,
            "lo_name":         lo_profile.name if lo_profile else profile.display_name,
            "company":         policy["company_name"],
            "quote_id":        quote.id,
            "requested":       requested,
            "quoted":          quoted_amount,
            "rate":            rate,
            "points":          points,
            "term_months":     term_months,
            "loan_type":       loan_type,
            "monthly_payment": calc_payment(quoted_amount, rate, term=max(term_months // 12, 1)),
            "decision":        decision,
            "delta":           round(delta, 2),
            "delta_pct":       round((delta / requested) * 100, 2) if requested else None,
            "notes":           notes,
            "submitted_at":    datetime.utcnow().isoformat(),
        })

        if decision == "approve":
            results["capital_approved"] = {
                "amount":      quoted_amount,
                "rate":        rate,
                "points":      points,
                "company":     policy["company_name"],
                "approved_at": datetime.utcnow().isoformat(),
            }
            deal.submitted_for_funding = True

        deal.results_json = results
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(deal, "results_json")

    db.session.commit()

    flash(f"Quote submitted — ${quoted_amount:,.0f} at {rate}% for {term_months}mo.", "success")
    return redirect(
        url_for("vip.loan_officer_dashboard")
        if policy["is_caughman_mason"]
        else url_for("vip.loan_officer_external_dashboard")
    )


@vip_bp.post("/loan-officer/funding/<int:funding_id>/decline")
@role_required("partner_group", "admin")
def loan_officer_decline_funding(funding_id):
    policy = get_user_lending_policy(current_user)
    fr     = FundingRequest.query.get_or_404(funding_id)
    reason = (request.form.get("reason") or "").strip()

    fr.status     = "declined"
    fr.updated_at = datetime.utcnow()
    if reason:
        fr.notes = (fr.notes or "") + f"\nDeclined: {reason}"

    if fr.deal_id:
        deal = Deal.query.get(fr.deal_id)
        if deal:
            results = deal.results_json or {}
            results["lo_decline"] = {"reason": reason, "declined_at": datetime.utcnow().isoformat()}
            deal.results_json = results
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(deal, "results_json")

    db.session.commit()
    flash("Funding request declined.", "warning")
    return redirect(
        url_for("vip.loan_officer_dashboard")
        if policy["is_caughman_mason"]
        else url_for("vip.loan_officer_external_dashboard")
    )


@vip_bp.post("/loan-officer/loan/<int:loan_id>/refer-out")
@role_required("partner_group", "admin")
def loan_officer_refer_out(loan_id):
    policy = get_user_lending_policy(current_user)
    loan   = LoanApplication.query.get_or_404(loan_id)
    reason = (request.form.get("reason") or "").strip()

    if not reason:
        reason = (
            "Outside Caughman Mason licensing scope — referred to licensed residential lender."
            if policy["is_caughman_mason"]
            else "Referred out."
        )

    loan.status = "Referred Out"
    db.session.add(LoanStatusEvent(
        loan_id     = loan.id,
        event_name  = "Referred Out",
        description = reason,
    ))
    db.session.commit()

    flash("Loan referred out.", "info")
    return redirect(
        url_for("vip.loan_officer_dashboard")
        if policy["is_caughman_mason"]
        else url_for("vip.loan_officer_external_dashboard")
    )


# ─────────────────────────────────────────────────────────────────────────────
# FINANCES
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_TAX_RATE = 0.28


def _finance_tax_rate(profile):
    raw = getattr(profile, "tax_rate", None) or DEFAULT_TAX_RATE
    try:
        rate = float(raw)
    except (TypeError, ValueError):
        rate = DEFAULT_TAX_RATE
    if rate <= 0:
        return DEFAULT_TAX_RATE
    if rate > 1:
        rate = rate / 100.0
    return min(rate, 0.6)


def _parse_date_input(raw):
    if not raw:
        return None
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt)
        except (TypeError, ValueError):
            continue
    return None


def _parse_money(raw):
    if raw in (None, ""):
        return None
    try:
        cleaned = str(raw).replace(",", "").replace("$", "").strip()
        return int(round(float(cleaned)))
    except (TypeError, ValueError):
        return None


def _sync_projected_closing_income(profile):
    """Auto-create pending commission rows for in-flight listings that belong
    to one of this realtor's configured markets.

    ElenaListing is not currently owned per-user, so we scope by market to
    avoid cross-realtor pollution. Realtors with no configured markets opt
    out of auto-sync — they can always add pending commissions manually.
    """
    user_markets = get_user_markets(profile)
    if not user_markets:
        return

    normalized_markets = {m.strip().lower() for m in user_markets if m}
    if not normalized_markets:
        return

    active_statuses = ("under_contract", "pending", "in_escrow")
    candidate_listings = (
        ElenaListing.query
        .filter(ElenaListing.status.in_(active_statuses))
        .filter(ElenaListing.market.isnot(None))
        .all()
    )
    if not candidate_listings:
        return

    existing_descs = {
        (i.description or "").strip()
        for i in VIPIncome.query.filter_by(
            vip_profile_id=profile.id,
            category="commission",
            status="pending",
        ).all()
    }

    created = 0
    for listing in candidate_listings:
        if not listing.price or listing.price <= 0:
            continue
        listing_market = (listing.market or "").strip().lower()
        if listing_market not in normalized_markets:
            continue
        desc = "Projected commission - " + str(listing.address or ("listing #" + str(listing.id)))
        if desc in existing_descs:
            continue
        projected = int(round(float(listing.price) * 0.03))
        db.session.add(VIPIncome(
            vip_profile_id = profile.id,
            category       = "commission",
            description    = desc,
            amount         = projected,
            income_date    = datetime.utcnow(),
            status         = "pending",
            market         = listing.market,
            notes          = "Auto-added from listing #" + str(listing.id) + " (" + str(listing.status) + ").",
        ))
        created += 1
    if created:
        db.session.commit()


@vip_bp.get("/finances")
@role_required("partner_group", "admin")
def finances():
    profile = get_or_create_vip_profile()
    _sync_projected_closing_income(profile)

    incomes  = (VIPIncome.query.filter_by(vip_profile_id=profile.id)
                .order_by(VIPIncome.created_at.desc()).limit(50).all())
    expenses = (VIPExpense.query.filter_by(vip_profile_id=profile.id)
                .order_by(VIPExpense.created_at.desc()).limit(50).all())

    total_received = int(db.session.query(func.coalesce(func.sum(VIPIncome.amount), 0))
                         .filter(VIPIncome.vip_profile_id == profile.id,
                                 func.coalesce(VIPIncome.status, "received") == "received")
                         .scalar() or 0)
    total_pending  = int(db.session.query(func.coalesce(func.sum(VIPIncome.amount), 0))
                         .filter(VIPIncome.vip_profile_id == profile.id,
                                 VIPIncome.status == "pending")
                         .scalar() or 0)
    total_expenses = int(db.session.query(func.coalesce(func.sum(VIPExpense.amount), 0))
                         .filter(VIPExpense.vip_profile_id == profile.id)
                         .scalar() or 0)

    tax_rate       = _finance_tax_rate(profile)
    taxable_income = max(total_received - total_expenses, 0)
    tax_set_aside  = int(round(taxable_income * tax_rate))
    tax_projected  = int(round(max(total_pending, 0) * tax_rate))

    markets = get_user_markets(profile)

    return render_template(
        "vip/finances.html",
        vip_profile    = profile,
        header_name    = get_dashboard_name(profile),
        incomes        = incomes,
        expenses       = expenses,
        total_received = total_received,
        total_pending  = total_pending,
        total_expenses = total_expenses,
        net_profit     = total_received - total_expenses,
        tax_rate       = tax_rate,
        tax_rate_pct   = int(round(tax_rate * 100)),
        tax_set_aside  = tax_set_aside,
        tax_projected  = tax_projected,
        markets        = markets,
        portal         = "vip",
        portal_name    = "VIP",
        portal_home    = url_for("vip.realtor_dashboard"),
    )


@vip_bp.post("/finances/income/new")
@role_required("partner_group", "admin")
def finances_add_income():
    profile = get_or_create_vip_profile()

    amount = _parse_money(request.form.get("amount"))
    if amount is None or amount <= 0:
        flash("Income amount must be a positive number.", "warning")
        return redirect(url_for("vip.finances"))

    db.session.add(VIPIncome(
        vip_profile_id = profile.id,
        category       = (request.form.get("category") or "commission").strip().lower(),
        description    = (request.form.get("description") or "").strip() or None,
        amount         = amount,
        income_date    = _parse_date_input(request.form.get("income_date")) or datetime.utcnow(),
        status         = (request.form.get("status") or "received").strip().lower(),
        market         = (request.form.get("market") or "").strip() or None,
        notes          = (request.form.get("notes") or "").strip() or None,
    ))
    db.session.commit()
    flash("Income added.", "success")
    return redirect(url_for("vip.finances"))


@vip_bp.post("/finances/expense/new")
@role_required("partner_group", "admin")
def finances_add_expense():
    profile = get_or_create_vip_profile()

    amount = _parse_money(request.form.get("amount"))
    if amount is None or amount <= 0:
        flash("Expense amount must be a positive number.", "warning")
        return redirect(url_for("vip.finances"))

    db.session.add(VIPExpense(
        vip_profile_id = profile.id,
        category       = (request.form.get("category") or "other").strip().lower(),
        description    = (request.form.get("description") or "").strip() or None,
        amount         = amount,
        expense_date   = _parse_date_input(request.form.get("expense_date")) or datetime.utcnow(),
        source         = "manual",
        market         = (request.form.get("market") or "").strip() or None,
        notes          = (request.form.get("notes") or "").strip() or None,
    ))
    db.session.commit()
    flash("Expense added.", "success")
    return redirect(url_for("vip.finances"))


@vip_bp.post("/finances/income/<int:income_id>/delete")
@role_required("partner_group", "admin")
def finances_delete_income(income_id):
    profile = get_or_create_vip_profile()
    income  = VIPIncome.query.filter_by(id=income_id, vip_profile_id=profile.id).first_or_404()
    db.session.delete(income)
    db.session.commit()
    flash("Income entry deleted.", "info")
    return redirect(url_for("vip.finances"))


@vip_bp.post("/finances/expense/<int:expense_id>/delete")
@role_required("partner_group", "admin")
def finances_delete_expense(expense_id):
    profile = get_or_create_vip_profile()
    expense = VIPExpense.query.filter_by(id=expense_id, vip_profile_id=profile.id).first_or_404()
    db.session.delete(expense)
    db.session.commit()
    flash("Expense entry deleted.", "info")
    return redirect(url_for("vip.finances"))


@vip_bp.post("/finances/income/<int:income_id>/mark-received")
@role_required("partner_group", "admin")
def finances_mark_income_received(income_id):
    profile = get_or_create_vip_profile()
    income  = VIPIncome.query.filter_by(id=income_id, vip_profile_id=profile.id).first_or_404()
    income.status = "received"
    income.income_date = income.income_date or datetime.utcnow()
    db.session.commit()
    flash("Income marked as received.", "success")
    return redirect(url_for("vip.finances"))


# ─────────────────────────────────────────────────────────────────────────────
# AI PILOT
# ─────────────────────────────────────────────────────────────────────────────

@vip_bp.get("/ai-pilot")
@role_required("partner_group", "admin")
def ai_pilot():
    profile     = get_or_create_vip_profile()
    suggestions = (
        VIPAssistantSuggestion.query.filter_by(vip_profile_id=profile.id)
        .order_by(VIPAssistantSuggestion.created_at.desc())
        .limit(20).all()
    )
    return render_template(
        "vip/ai_pilot.html",
        vip_profile = profile,
        header_name = get_dashboard_name(profile),
        suggestions = suggestions,
        portal      = "vip",
        portal_name = "VIP",
        portal_home = url_for("vip.index"),
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

    db.session.add(VIPAssistantSuggestion(
        vip_profile_id  = profile.id,
        suggestion_type = result["suggestion_type"],
        title           = result["title"],
        body            = result.get("body"),
        source          = "manual",
    ))
    db.session.commit()

    flash("Assistant suggestion created.", "success")
    return redirect(url_for("vip.ai_pilot"))


def _has_endpoint(name):
    try:
        return name in current_app.view_functions
    except RuntimeError:
        return False


def _dispatch_copilot_intent(profile, result, command):
    intent = result.get("intent") or "note"
    markets = get_user_markets(profile)
    default_market = markets[0] if len(markets) == 1 else None

    summary = ""
    action_url = url_for("vip.ai_pilot")
    executed = False

    if intent == "add_listing":
        address = result.get("address") or "Untitled listing"
        price = result.get("price")
        listing = ElenaListing(
            address     = address,
            city        = "",
            state       = "",
            zip_code    = "",
            price       = price,
            status      = "active",
            market      = default_market,
            description = command,
        )
        db.session.add(listing)
        db.session.flush()
        db.session.commit()
        price_str = " ($" + format(price, ",") + ")" if price else ""
        summary = "Added listing: " + address + price_str
        action_url = url_for("vip.realtor_dashboard")
        executed = True

    elif intent == "add_expense":
        amount = result.get("amount") or 0
        db.session.add(VIPExpense(
            vip_profile_id = profile.id,
            category       = "other",
            description    = command[:240],
            amount         = amount or None,
            expense_date   = datetime.utcnow(),
            source         = "copilot",
            market         = default_market,
        ))
        db.session.commit()
        summary = "Logged expense" + ((" of $" + format(amount, ",")) if amount else "")
        action_url = url_for("vip.finances")
        executed = True

    elif intent == "add_income":
        amount = result.get("amount") or 0
        db.session.add(VIPIncome(
            vip_profile_id = profile.id,
            category       = "commission",
            description    = command[:240],
            amount         = amount or 1,
            income_date    = datetime.utcnow(),
            status         = "received" if amount else "pending",
            market         = default_market,
        ))
        db.session.commit()
        summary = "Logged income" + ((" of $" + format(amount, ",")) if amount else "")
        action_url = url_for("vip.finances")
        executed = True

    elif intent == "make_flyer":
        address = result.get("address")
        listing = None
        if address:
            listing = (ElenaListing.query
                       .filter(ElenaListing.address.ilike("%" + address + "%"))
                       .first())
        if not listing:
            listing = (ElenaListing.query
                       .order_by(ElenaListing.updated_at.desc())
                       .first())
        if listing:
            flyer = ElenaFlyer(
                flyer_type       = "listing",
                property_address = listing.address,
                property_id      = str(listing.id),
                listing_id       = listing.id,
                body             = command,
            )
            db.session.add(flyer)
            db.session.commit()
            summary = "Drafted flyer for " + str(listing.address)
            action_url = url_for("elena.template_studio")
            executed = True
        else:
            summary = "No listing found to attach a flyer to."
            action_url = url_for("elena.template_studio")

    elif intent == "tax_suggestion":
        rate = _finance_tax_rate(profile)
        total_received = sum(
            (i.amount or 0)
            for i in VIPIncome.query.filter_by(vip_profile_id=profile.id).all()
            if (i.status or "pending") == "received"
        )
        set_aside = int(round(total_received * rate))
        summary = ("Set aside $" + format(set_aside, ",")
                   + " for taxes (" + str(int(round(rate * 100)))
                   + "% of $" + format(total_received, ",") + ").")
        action_url = url_for("vip.finances")

    elif intent == "follow_up":
        summary = "Follow-up saved to the copilot queue."
    elif intent == "draft_email":
        summary = "Email draft saved to the copilot queue."
    elif intent == "draft_text":
        summary = "Text draft saved to the copilot queue."
    else:
        summary = "Note saved."

    suggestion = VIPAssistantSuggestion(
        vip_profile_id  = profile.id,
        suggestion_type = result.get("suggestion_type") or "note",
        title           = result.get("title") or "Copilot",
        body            = (summary + "\n\n" + command).strip(),
        source          = "copilot_voice",
    )
    db.session.add(suggestion)
    db.session.commit()

    return {
        "ok":         True,
        "executed":   executed,
        "intent":     intent,
        "title":      result.get("title") or "Copilot",
        "summary":    summary,
        "action_url": action_url,
    }


@vip_bp.post("/ai-pilot/action")
@role_required("partner_group", "admin")
def ai_pilot_action():
    profile = get_or_create_vip_profile()

    if request.is_json:
        data = request.get_json(silent=True) or {}
        command = (data.get("command") or "").strip()
    else:
        command = (request.form.get("command") or "").strip()

    if not command:
        return jsonify({"ok": False, "error": "Empty command."}), 400

    result  = parse_vip_command(command)
    payload = _dispatch_copilot_intent(profile, result, command)
    return jsonify(payload)


# ─────────────────────────────────────────────────────────────────────────────
# TEAM + LEAD DISTRIBUTION
# ─────────────────────────────────────────────────────────────────────────────

TEAM_ROLE_CHOICES = [
    ("buyer_agent",     "Buyer's Agent"),
    ("listing_agent",   "Listing Agent"),
    ("showing_agent",   "Showing Agent"),
    ("transaction_coordinator", "Transaction Coordinator"),
    ("assistant",       "Admin Assistant"),
    ("marketing",       "Marketing"),
    ("other",           "Other"),
]


def _unassigned_leads(profile):
    return (ElenaClient.query
            .filter((ElenaClient.assigned_member_id == None) |  # noqa: E711
                    (ElenaClient.assigned_member_id == 0))
            .order_by(ElenaClient.created_at.desc())
            .limit(50).all())


@vip_bp.get("/team")
@role_required("partner_group", "admin")
def team():
    profile = get_or_create_vip_profile()

    members = (VIPTeamMember.query
               .filter_by(vip_profile_id=profile.id)
               .order_by(VIPTeamMember.active.desc(),
                         VIPTeamMember.name.asc())
               .all())

    member_ids = [m.id for m in members]
    leads_by_member = {}
    if member_ids:
        all_assigned = (ElenaClient.query
                        .filter(ElenaClient.assigned_member_id.in_(member_ids))
                        .order_by(ElenaClient.created_at.desc()).all())
        for lead in all_assigned:
            leads_by_member.setdefault(lead.assigned_member_id, []).append(lead)

    unassigned = _unassigned_leads(profile)

    return render_template(
        "vip/team.html",
        vip_profile     = profile,
        header_name     = get_dashboard_name(profile),
        members         = members,
        role_choices    = TEAM_ROLE_CHOICES,
        leads_by_member = leads_by_member,
        unassigned      = unassigned,
        markets         = get_user_markets(profile),
        portal          = "vip",
        portal_name     = "VIP",
        portal_home     = url_for("vip.realtor_dashboard"),
    )


@vip_bp.post("/team/new")
@role_required("partner_group", "admin")
def team_add():
    profile = get_or_create_vip_profile()

    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Teammate name is required.", "warning")
        return redirect(url_for("vip.team"))

    db.session.add(VIPTeamMember(
        vip_profile_id = profile.id,
        name           = name,
        email          = (request.form.get("email") or "").strip() or None,
        phone          = (request.form.get("phone") or "").strip() or None,
        role           = (request.form.get("role") or "other").strip() or "other",
        market         = (request.form.get("market") or "").strip() or None,
        notes          = (request.form.get("notes") or "").strip() or None,
        active         = True,
    ))
    db.session.commit()
    flash("Teammate added.", "success")
    return redirect(url_for("vip.team"))


@vip_bp.post("/team/<int:member_id>/toggle")
@role_required("partner_group", "admin")
def team_toggle(member_id):
    profile = get_or_create_vip_profile()
    member  = VIPTeamMember.query.filter_by(id=member_id, vip_profile_id=profile.id).first_or_404()
    member.active = not member.active
    db.session.commit()
    flash("Teammate " + ("activated" if member.active else "deactivated") + ".", "info")
    return redirect(url_for("vip.team"))


@vip_bp.post("/team/<int:member_id>/delete")
@role_required("partner_group", "admin")
def team_delete(member_id):
    profile = get_or_create_vip_profile()
    member  = VIPTeamMember.query.filter_by(id=member_id, vip_profile_id=profile.id).first_or_404()

    ElenaClient.query.filter_by(assigned_member_id=member.id).update(
        {"assigned_member_id": None}, synchronize_session=False
    )
    db.session.delete(member)
    db.session.commit()
    flash("Teammate removed and their leads released.", "info")
    return redirect(url_for("vip.team"))


@vip_bp.post("/team/leads/<int:lead_id>/assign")
@role_required("partner_group", "admin")
def team_assign_lead(lead_id):
    profile = get_or_create_vip_profile()
    lead    = ElenaClient.query.get_or_404(lead_id)

    raw = (request.form.get("member_id") or "").strip()
    if raw in ("", "0", "none"):
        lead.assigned_member_id = None
    else:
        try:
            member_id = int(raw)
        except ValueError:
            flash("Invalid teammate.", "warning")
            return redirect(url_for("vip.team"))
        member = VIPTeamMember.query.filter_by(id=member_id, vip_profile_id=profile.id, active=True).first()
        if not member:
            flash("Teammate not found or inactive.", "warning")
            return redirect(url_for("vip.team"))
        lead.assigned_member_id = member.id

    db.session.commit()
    flash("Lead routing updated.", "success")
    return redirect(url_for("vip.team"))


@vip_bp.post("/team/leads/auto-distribute")
@role_required("partner_group", "admin")
def team_auto_distribute():
    """Round-robin unassigned leads across active teammates."""
    profile = get_or_create_vip_profile()

    active_members = (VIPTeamMember.query
                      .filter_by(vip_profile_id=profile.id, active=True)
                      .order_by(VIPTeamMember.id.asc()).all())
    if not active_members:
        flash("Add at least one active teammate before distributing leads.", "warning")
        return redirect(url_for("vip.team"))

    unassigned = _unassigned_leads(profile)
    if not unassigned:
        flash("No unassigned leads to distribute.", "info")
        return redirect(url_for("vip.team"))

    for idx, lead in enumerate(unassigned):
        target = active_members[idx % len(active_members)]
        lead.assigned_member_id = target.id
    db.session.commit()

    flash("Distributed " + str(len(unassigned)) + " lead(s) across " + str(len(active_members)) + " teammate(s).", "success")
    return redirect(url_for("vip.team"))


# ─────────────────────────────────────────────────────────────────────────────
# ONBOARDING
# ─────────────────────────────────────────────────────────────────────────────

@vip_bp.get("/onboarding")
@role_required("partner_group", "admin")
def onboarding():
    profile = get_or_create_vip_profile()
    enabled = set(get_enabled_modules(profile))
    module_pref = {
        field_name: "yes" if module_name in enabled else "no"
        for field_name, module_name in MODULE_FIELD_MAP.items()
    }
    return render_template(
        "vip/onboarding.html",
        vip_profile = profile,
        module_pref = module_pref,
        header_name = get_dashboard_name(profile),
        markets_csv = ", ".join(get_user_markets(profile)),
        portal      = "vip",
        portal_name = "VIP",
        portal_home = url_for("vip.index"),
    )


@vip_bp.post("/onboarding/save")
@role_required("partner_group", "admin")
def onboarding_save():
    profile = get_or_create_vip_profile()

    profile.display_name   = (request.form.get("display_name")   or profile.display_name or "").strip()
    profile.business_name  = (request.form.get("business_name")  or "").strip() or None
    profile.dashboard_title = (request.form.get("dashboard_title") or "").strip() or None
    profile.assistant_name = (request.form.get("assistant_name") or "Ravlo").strip()
    profile.role_type      = (request.form.get("role_type")      or profile.role_type or "partner").strip()
    profile.service_area   = (request.form.get("service_area")   or "").strip() or None
    profile.headline       = (request.form.get("headline")       or "").strip() or None
    profile.bio            = (request.form.get("bio")            or "").strip() or None

    # External LO fields
    if profile.role_type in ("loan_officer", "lender"):
        lo_is_external = request.form.get("lo_is_external", "").strip().lower() == "yes"
        if hasattr(profile, "lo_is_external"):
            profile.lo_is_external = lo_is_external
        if lo_is_external and hasattr(profile, "lo_licensed_residential"):
            profile.lo_licensed_residential = True
            profile.lo_license_number = (request.form.get("lo_license_number") or "").strip() or None
            profile.lo_license_state  = (request.form.get("lo_license_state")  or "").strip() or None
            profile.lo_nmls           = (request.form.get("lo_nmls")           or "").strip() or None

    profile.enabled_modules = json.dumps(build_enabled_modules_from_form(request.form))

    markets_raw = (request.form.get("markets") or "").strip()
    if "markets" in request.form:
        parsed = [m.strip() for m in markets_raw.split(",") if m.strip()]
        profile.markets_json = json.dumps(parsed)

    db.session.commit()

    flash("VIP setup saved.", "success")
    return redirect(url_for("vip.index"))


# ─────────────────────────────────────────────────────────────────────────────
# DESIGN STUDIO
# ─────────────────────────────────────────────────────────────────────────────

@vip_bp.get("/design-studio")
@role_required("partner_group", "admin")
def design_studio():
    profile    = get_or_create_vip_profile()
    project_id = request.args.get("project_id", type=int)
    project    = None
    annotations = []

    if project_id:
        project = VIPDesignProject.query.filter_by(id=project_id, vip_profile_id=profile.id).first()
        if project:
            annotations = (
                VIPDesignAnnotation.query
                .filter_by(project_id=project.id)
                .order_by(VIPDesignAnnotation.created_at.asc())
                .all()
            )

    return render_template(
        "vip/design_studio.html",
        vip_profile = profile,
        modules     = get_enabled_modules(profile),
        header_name = get_dashboard_name(profile),
        project     = project,
        annotations = annotations,
        portal      = "vip",
        portal_name = "VIP",
        portal_home = url_for("vip.index"),
    )


@vip_bp.post("/design-studio/create")
@role_required("partner_group", "admin")
def create_design_project():
    profile     = get_or_create_vip_profile()
    title       = (request.form.get("title") or "").strip()
    source_file = (request.form.get("source_file") or "").strip() or None

    if not title:
        flash("Project title is required.", "warning")
        return redirect(url_for("vip.design_studio"))

    project = VIPDesignProject(vip_profile_id=profile.id, title=title, source_file=source_file)
    db.session.add(project)
    db.session.commit()

    flash("Design project created.", "success")
    return redirect(url_for("vip.design_studio", project_id=project.id))


@vip_bp.post("/design-studio/annotation")
@role_required("partner_group", "admin")
def save_annotation():
    profile = get_or_create_vip_profile()
    data    = request.get_json() or {}

    project = VIPDesignProject.query.filter_by(
        id=data.get("project_id"), vip_profile_id=profile.id
    ).first()

    if not project:
        return jsonify({"error": "Project not found"}), 404

    annotation = VIPDesignAnnotation(
        project_id      = project.id,
        annotation_type = data.get("type"),
        action_type     = data.get("action"),
        label           = data.get("label"),
        body            = data.get("body"),
        x               = data.get("x"),
        y               = data.get("y"),
        width           = data.get("width"),
        height          = data.get("height"),
    )
    db.session.add(annotation)
    db.session.commit()

    return jsonify({"status": "ok", "annotation_id": annotation.id}), 201


@vip_bp.post("/design-studio/annotation/update")
@role_required("partner_group", "admin")
def update_annotation():
    profile    = get_or_create_vip_profile()
    data       = request.get_json() or {}
    annotation = VIPDesignAnnotation.query.get(data.get("id"))

    if not annotation:
        return jsonify({"error": "Not found"}), 404

    project = VIPDesignProject.query.filter_by(
        id=annotation.project_id, vip_profile_id=profile.id
    ).first()

    if not project:
        return jsonify({"error": "Unauthorized"}), 403

    annotation.annotation_type = data.get("type")
    annotation.action_type     = data.get("action")
    annotation.label           = data.get("label")
    annotation.body            = data.get("body")
    db.session.commit()

    return jsonify({"status": "updated"})


@vip_bp.post("/design-studio/annotation/delete")
@role_required("partner_group", "admin")
def delete_annotation():
    profile    = get_or_create_vip_profile()
    data       = request.get_json() or {}
    annotation = VIPDesignAnnotation.query.get(data.get("id"))

    if not annotation:
        return jsonify({"error": "Not found"}), 404

    project = VIPDesignProject.query.filter_by(
        id=annotation.project_id, vip_profile_id=profile.id
    ).first()

    if not project:
        return jsonify({"error": "Unauthorized"}), 403

    db.session.delete(annotation)
    db.session.commit()

    return jsonify({"status": "deleted"})
