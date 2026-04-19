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

from LoanMVP.models.borrowers import ProjectBudget, ProjectExpense, Deal, PropertyAnalysis
from LoanMVP.models.partner_models import PartnerConnectionRequest, PartnerProposal
from LoanMVP.models.investor_models import InvestorProfile
from LoanMVP.models.property import SavedProperty

from LoanMVP.services.vip_ai_pilot import parse_vip_command

from LoanMVP.utils.decorators import role_required
from LoanMVP.utils.company_policy import (
    get_user_lending_policy,
    is_out_of_scope_loan_type,
    INVESTMENT_LOAN_TYPES,
    ALL_LOAN_TYPES,
)
from LoanMVP.models.admin import Company
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

# ─────────────────────────────────────────────────────────────────────────────
# Updates to vip.py — company-aware LO routing
#
# Required new imports:
#   from LoanMVP.utils.company_policy import (
#       get_user_lending_policy,
#       is_out_of_scope_loan_type,
#       INVESTMENT_LOAN_TYPES,
#       ALL_LOAN_TYPES,
#   )
#   from LoanMVP.models.admin import Company
# ─────────────────────────────────────────────────────────────────────────────


# ── 1. Updated index() — company-aware routing ───────────────────────────────

@vip_bp.get("/")
@role_required("partner_group", "admin")
def index():
    profile = get_or_create_vip_profile()

    if profile.role_type in ("loan_officer", "lender"):
        policy = get_user_lending_policy(current_user)

        if policy["is_caughman_mason"]:
            # Caughman Mason LO — investment only VIP dashboard
            return redirect(url_for("vip.loan_officer_dashboard"))
        else:
            # External licensed LO — their own full workspace
            return redirect(url_for("vip.loan_officer_external_dashboard"))

    role_map = {
        "realtor":    "vip.realtor_dashboard",
        "contractor": "vip.contractor_dashboard",
        "designer":   "vip.designer_dashboard",
        "partner":    "vip.partner_dashboard",
    }
    return redirect(url_for(role_map.get(profile.role_type, "vip.partner_dashboard")))


# ── 2. Updated loan_officer_dashboard() — Caughman Mason VIP ─────────────────
#
# This replaces the current loan_officer/dashboard.html route.
# Caughman Mason LOs now land here instead of loan_officer.dashboard.
# Investment deals only — policy enforced at company level.

@vip_bp.get("/loan-officer")
@role_required("partner_group", "admin")
def loan_officer_dashboard():
    profile    = get_or_create_vip_profile()
    policy     = get_user_lending_policy(current_user)
    lo_profile = LoanOfficerProfile.query.filter_by(user_id=current_user.id).first()

    # If external LO somehow lands here, send them to their workspace
    if not policy["is_caughman_mason"] and not policy["investment_only"]:
        return redirect(url_for("vip.loan_officer_external_dashboard"))

    # ── Funding requests from investors ──────────────────────────────────────
    raw_funding = (
        FundingRequest.query
        .filter(FundingRequest.status.in_(["submitted", "reviewing"]))
        .order_by(FundingRequest.created_at.desc())
        .limit(20)
        .all()
    )

    funding_with_context = []
    for fr in raw_funding:
        deal = Deal.query.get(fr.deal_id) if fr.deal_id else None

        # Skip owner-occupied deals — CM not licensed
        if deal:
            strategy = (getattr(deal, "strategy", "") or "").lower()
            if strategy in {"primary", "owner occupied", "owner_occupied"}:
                continue

        ctx = _build_funding_context(fr, deal)
        funding_with_context.append({"request": fr, "deal": deal, "context": ctx})

    # ── Capital loan applications ─────────────────────────────────────────────
    capital_with_context = []
    out_of_scope_loans   = []

    if lo_profile:
        assigned_loans = (
            LoanApplication.query
            .filter_by(loan_officer_id=lo_profile.id)
            .order_by(LoanApplication.created_at.desc())
            .all()
        )
    else:
        assigned_loans = (
            LoanApplication.query
            .filter(LoanApplication.status.in_(
                ["Capital Submitted", "Submitted", "Processing", "Under Review"]
            ))
            .order_by(LoanApplication.created_at.desc())
            .limit(15)
            .all()
        )

    for loan in assigned_loans:
        if is_out_of_scope_loan_type(loan.loan_type, policy):
            out_of_scope_loans.append(loan)
            continue
        ctx = _build_loan_deal_context(loan)
        capital_with_context.append({"loan": loan, "context": ctx})

    # ── Recent quotes ─────────────────────────────────────────────────────────
    recent_quotes = _get_lo_recent_quotes(lo_profile)

    # ── Stats ─────────────────────────────────────────────────────────────────
    stats = {
        "funding_requests": len(funding_with_context),
        "capital_loans":    len(capital_with_context),
        "quotes_sent":      len(recent_quotes),
        "pending_review":   sum(
            1 for item in funding_with_context
            if item["request"].status == "submitted"
        ),
        "out_of_scope":     len(out_of_scope_loans),
        "total_quoted":     sum(
            float(getattr(q, "loan_amount", 0) or 0)
            for q in recent_quotes
        ),
    }

    copilot_suggestions = (
        VIPAssistantSuggestion.query
        .filter_by(vip_profile_id=profile.id)
        .order_by(VIPAssistantSuggestion.created_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "vip/loan_officer/dashboard.html",
        vip_profile          = profile,
        modules              = get_enabled_modules(profile),
        header_name          = get_dashboard_name(profile),
        policy               = policy,
        funding_with_context = funding_with_context,
        capital_with_context = capital_with_context,
        out_of_scope_loans   = out_of_scope_loans,
        recent_quotes        = recent_quotes,
        stats                = stats,
        copilot_suggestions  = copilot_suggestions,
        investment_loan_types = INVESTMENT_LOAN_TYPES,
        portal      = "vip",
        portal_name = "VIP",
        portal_home = url_for("vip.loan_officer_dashboard"),
    )


# ── 3. Updated external dashboard — non-CM companies ─────────────────────────

@vip_bp.get("/loan-officer/workspace")
@role_required("partner_group", "admin")
def loan_officer_external_dashboard():
    profile    = get_or_create_vip_profile()
    policy     = get_user_lending_policy(current_user)
    lo_profile = LoanOfficerProfile.query.filter_by(user_id=current_user.id).first()

    # Caughman Mason LOs should not be here
    if policy["is_caughman_mason"]:
        return redirect(url_for("vip.loan_officer_dashboard"))

    # ── Their borrowers ───────────────────────────────────────────────────────
    my_borrowers = []
    if lo_profile:
        my_borrowers = (
            BorrowerProfile.query
            .filter_by(assigned_officer_id=lo_profile.id)
            .order_by(BorrowerProfile.created_at.desc())
            .limit(20)
            .all()
        )

    # ── Their pipeline — all types ────────────────────────────────────────────
    my_loans = []
    if lo_profile:
        my_loans = (
            LoanApplication.query
            .filter_by(loan_officer_id=lo_profile.id)
            .order_by(LoanApplication.created_at.desc())
            .limit(30)
            .all()
        )

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
        .limit(5)
        .all()
    )

    return render_template(
        "vip/loan_officer/external_dashboard.html",
        vip_profile       = profile,
        modules           = get_enabled_modules(profile),
        header_name       = get_dashboard_name(profile),
        policy            = policy,
        my_borrowers      = my_borrowers,
        my_loans          = my_loans,
        pipeline          = pipeline,
        loan_type_counts  = loan_type_counts,
        my_quotes         = recent_quotes,
        stats             = stats,
        copilot_suggestions = copilot_suggestions,
        lo_profile        = lo_profile,
        all_loan_types    = ALL_LOAN_TYPES,
        portal      = "vip",
        portal_name = "VIP",
        portal_home = url_for("vip.loan_officer_external_dashboard"),
    )


# ── 4. Updated submit quote — policy-aware ───────────────────────────────────

@vip_bp.post("/loan-officer/funding/<int:funding_id>/quote")
@role_required("partner_group", "admin")
def loan_officer_submit_quote(funding_id):
    profile    = get_or_create_vip_profile()
    policy     = get_user_lending_policy(current_user)
    lo_profile = LoanOfficerProfile.query.filter_by(user_id=current_user.id).first()
    fr         = FundingRequest.query.get_or_404(funding_id)
    deal       = Deal.query.get(fr.deal_id) if fr.deal_id else None

    loan_type = (request.form.get("loan_type") or "").strip()

    # Hard stop for Caughman Mason — no residential
    if policy["is_caughman_mason"] and is_out_of_scope_loan_type(loan_type, policy):
        flash(
            f"Caughman Mason is not licensed for '{loan_type}'. "
            "Refer this to a licensed residential lender.",
            "danger"
        )
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
        rate        = rate,
        term_months = term_months,
        loan_amount = quoted_amount,
        loan_type   = loan_type or "Investor Capital",
        status      = "sent",
        ai_suggestion = notes,
        created_at  = datetime.utcnow(),
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

    # ── Deal Architect feedback loop ──────────────────────────────────────────
    if deal:
        results   = deal.results_json or {}
        lo_quotes = results.setdefault("lo_quotes", [])

        requested   = float(fr.requested_amount or 0)
        delta       = quoted_amount - requested
        delta_pct   = round((delta / requested) * 100, 2) if requested else None
        monthly_pmt = calc_payment(quoted_amount, rate, term=max(term_months // 12, 1))

        lo_quotes.append({
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
            "monthly_payment": monthly_pmt,
            "decision":        decision,
            "delta":           round(delta, 2),
            "delta_pct":       delta_pct,
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

    redirect_target = (
        url_for("vip.loan_officer_dashboard")
        if policy["is_caughman_mason"]
        else url_for("vip.loan_officer_external_dashboard")
    )

    flash(f"Quote submitted — ${quoted_amount:,.0f} at {rate}% for {term_months}mo.", "success")
    return redirect(redirect_target)


# ── 5. Refer out — policy-aware ───────────────────────────────────────────────

@vip_bp.post("/loan-officer/loan/<int:loan_id>/refer-out")
@role_required("partner_group", "admin")
def loan_officer_refer_out(loan_id):
    policy = get_user_lending_policy(current_user)
    loan   = LoanApplication.query.get_or_404(loan_id)
    reason = (request.form.get("reason") or "").strip()

    if not reason:
        if policy["is_caughman_mason"]:
            reason = "Outside Caughman Mason licensing scope — referred to licensed residential lender."
        else:
            reason = "Referred out."

    loan.status = "Referred Out"

    from LoanMVP.models.loan_models import LoanStatusEvent
    event = LoanStatusEvent(
        loan_id     = loan.id,
        event_name  = "Referred Out",
        description = reason,
    )
    db.session.add(event)
    db.session.commit()

    flash("Loan referred out.", "info")

    return redirect(
        url_for("vip.loan_officer_dashboard")
        if policy["is_caughman_mason"]
        else url_for("vip.loan_officer_external_dashboard")
    )



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


# ── CONTRACTOR DASHBOARD ─────────────────────────────────────────

@vip_bp.get("/contractor")
@role_required("partner_group", "admin")
def contractor_dashboard():
    profile = get_or_create_vip_profile()
    partner = getattr(current_user, "partner_profile", None)

    requests_with_context = []
    active_jobs = []
    stats = {
        "open_requests": 0,
        "active_jobs": 0,
        "completed_jobs": 0,
        "total_volume": 0.0,
        "ai_estimate_total": 0.0,
        "contractor_total": 0.0,
    }

    if partner:
        # ── Incoming requests with full deal context ──────────────
        raw_requests = (
            PartnerConnectionRequest.query
            .filter_by(partner_id=partner.id)
            .filter(PartnerConnectionRequest.status.in_(["pending", "accepted", "awaiting_match"]))
            .order_by(PartnerConnectionRequest.created_at.desc())
            .limit(20)
            .all()
        )

        for req in raw_requests:
            context = _build_request_deal_context(req)
            requests_with_context.append({"request": req, "context": context})

        stats["open_requests"] = len(requests_with_context)

        # ── Active jobs with budget comparison ───────────────────
        raw_jobs = (
            PartnerJob.query
            .filter_by(partner_id=partner.id)
            .order_by(PartnerJob.created_at.desc())
            .limit(20)
            .all()
        )

        for job in raw_jobs:
            job_data = {"job": job, "budget": None, "ai_estimate": None, "delta": None}

            # Find linked ProjectBudget via deal or property
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

                # Find the Deal Architect estimate from PropertyAnalysis or Deal
                deal = None
                if hasattr(job, "deal_id") and job.deal_id:
                    deal = Deal.query.get(job.deal_id)
                elif budget.deal_id:
                    deal = Deal.query.get(budget.deal_id)

                if deal and deal.rehab_cost:
                    ai_estimate = float(deal.rehab_cost or 0)
                    contractor_cost = float(budget.total_cost or 0)
                    job_data["ai_estimate"] = ai_estimate
                    job_data["delta"] = round(contractor_cost - ai_estimate, 2)
                    job_data["delta_pct"] = (
                        round(((contractor_cost - ai_estimate) / ai_estimate) * 100, 1)
                        if ai_estimate > 0 else None
                    )

            active_jobs.append(job_data)

        stats["active_jobs"] = sum(1 for j in active_jobs if j["job"].status in ["Open", "in_progress"])
        stats["completed_jobs"] = sum(1 for j in active_jobs if j["job"].status == "completed")
        stats["total_volume"] = sum(
            float(j["budget"].total_cost or 0)
            for j in active_jobs
            if j["budget"] and j["job"].status == "completed"
        )
        stats["ai_estimate_total"] = sum(
            j["ai_estimate"] for j in active_jobs if j["ai_estimate"]
        )
        stats["contractor_total"] = sum(
            float(j["budget"].total_cost or 0)
            for j in active_jobs if j["budget"]
        )

    copilot_suggestions = (
        VIPAssistantSuggestion.query
        .filter_by(vip_profile_id=profile.id)
        .order_by(VIPAssistantSuggestion.created_at.desc())
        .limit(5)
        .all()
    )

    recent_proposals = []
    if partner:
        recent_proposals = (
            PartnerProposal.query
            .filter_by(partner_id=partner.id)
            .order_by(PartnerProposal.created_at.desc())
            .limit(5)
            .all()
        )

    return render_template(
        "vip/contractor/dashboard.html",
        vip_profile=profile,
        modules=get_enabled_modules(profile),
        header_name=get_dashboard_name(profile),
        requests_with_context=requests_with_context,
        active_jobs=active_jobs,
        recent_proposals=recent_proposals,
        stats=stats,
        copilot_suggestions=copilot_suggestions,
        portal="vip",
        portal_name="VIP",
        portal_home=url_for("vip.contractor_dashboard"),
    )


def _build_request_deal_context(req):
    """
    Pull deal context from a PartnerConnectionRequest.
    Returns a dict with whatever deal data is available.
    """
    ctx = {
        "deal": None,
        "property_analysis": None,
        "ai_rehab_estimate": None,
        "arv": None,
        "purchase_price": None,
        "strategy": None,
        "address": req.related_address(),
        "requester": req.requester_name(),
        "budget": req.budget,
        "timeline": req.timeline,
    }

    # Try Deal first (most complete)
    if req.deal_id:
        deal = Deal.query.get(req.deal_id)
        if deal:
            ctx["deal"] = deal
            ctx["ai_rehab_estimate"] = float(deal.rehab_cost or 0)
            ctx["arv"] = float(deal.arv or 0)
            ctx["purchase_price"] = float(deal.purchase_price or 0)
            ctx["strategy"] = deal.strategy
            ctx["address"] = ctx["address"] or deal.address

            # Pull rehab scope if available
            if deal.rehab_scope_json:
                ctx["rehab_scope"] = deal.rehab_scope_json

            return ctx

    # Fall back to SavedProperty → PropertyAnalysis
    if req.saved_property_id:
        analysis = (
            PropertyAnalysis.query
            .filter_by(investor_profile_id=req.investor_profile_id)
            .order_by(PropertyAnalysis.created_at.desc())
            .first()
        )
        if analysis:
            ctx["property_analysis"] = analysis
            ctx["ai_rehab_estimate"] = float(analysis.rehab_cost or 0)
            ctx["arv"] = float(analysis.arv or 0)
            ctx["purchase_price"] = float(analysis.purchase_price or 0)
            ctx["address"] = ctx["address"] or analysis.address

    return ctx


# ── CONTRACTOR: Accept request + create budget ───────────────────

@vip_bp.post("/contractor/request/<int:req_id>/accept")
@role_required("partner_group", "admin")
def contractor_accept_request(req_id):
    profile = get_or_create_vip_profile()
    partner = getattr(current_user, "partner_profile", None)

    if not partner:
        flash("Partner profile not found.", "danger")
        return redirect(url_for("vip.contractor_dashboard"))

    req = PartnerConnectionRequest.query.filter_by(
        id=req_id, partner_id=partner.id
    ).first_or_404()

    req.status = "accepted"
    req.responded_at = datetime.utcnow()

    # Create a PartnerJob linked to the deal
    job = PartnerJob(
        partner_id=partner.id,
        investor_profile_id=req.investor_profile_id,
        borrower_profile_id=req.borrower_profile_id,
        property_id=req.property_id,
        title=req.title or f"{partner.category or 'Contractor'} Job",
        scope=req.message,
        status="Open",
    )

    # Link deal_id if PartnerJob has that column
    if hasattr(job, "deal_id") and req.deal_id:
        job.deal_id = req.deal_id

    db.session.add(job)
    db.session.flush()

    flash("Request accepted. Job created.", "success")
    db.session.commit()
    return redirect(url_for("vip.contractor_dashboard"))


# ── CONTRACTOR: Submit scope back into ProjectBudget ─────────────

@vip_bp.post("/contractor/job/<int:job_id>/submit-scope")
@role_required("partner_group", "admin")
def contractor_submit_scope(job_id):
    """
    Contractor submits actual scope numbers.
    Writes into ProjectBudget — closes the AI feedback loop.
    """
    profile = get_or_create_vip_profile()
    partner = getattr(current_user, "partner_profile", None)

    if not partner:
        flash("Partner profile not found.", "danger")
        return redirect(url_for("vip.contractor_dashboard"))

    job = PartnerJob.query.filter_by(
        id=job_id, partner_id=partner.id
    ).first_or_404()

    labor_cost = float(request.form.get("labor_cost") or 0)
    materials_cost = float(request.form.get("materials_cost") or 0)
    other_cost = float(request.form.get("other_cost") or 0)
    timeline = (request.form.get("timeline") or "").strip()
    scope_notes = (request.form.get("scope_notes") or "").strip()
    total = labor_cost + materials_cost + other_cost

    # Find or create a ProjectBudget for this job/deal
    budget = None
    deal_id = getattr(job, "deal_id", None)

    if deal_id:
        budget = ProjectBudget.query.filter_by(deal_id=deal_id).first()

    if not budget and job.investor_profile_id:
        budget = ProjectBudget.query.filter_by(
            investor_profile_id=job.investor_profile_id
        ).first()

    if not budget:
        budget = ProjectBudget(
            investor_profile_id=job.investor_profile_id,
            borrower_profile_id=job.borrower_profile_id,
            deal_id=deal_id,
            budget_type="rehab",
            name=job.title or "Contractor Scope",
            project_name=job.title,
        )
        db.session.add(budget)
        db.session.flush()

    # Update budget with contractor numbers
    budget.labor_cost = labor_cost
    budget.materials_cost = materials_cost
    budget.total_cost = total
    if scope_notes:
        budget.notes = f"[Contractor: {partner.name}]\n{scope_notes}"

    # Add line-item expenses
    line_items = request.form.getlist("line_category[]")
    line_descs = request.form.getlist("line_description[]")
    line_amounts = request.form.getlist("line_amount[]")

    for cat, desc, amt in zip(line_items, line_descs, line_amounts):
        if not desc:
            continue
        expense = ProjectExpense(
            budget_id=budget.id,
            category=cat or "General",
            description=desc,
            vendor=partner.name or partner.company,
            estimated_amount=float(amt or 0),
            status="planned",
        )
        db.session.add(expense)

    budget.recalculate_totals()

    # ── AI FEEDBACK LOOP ─────────────────────────────────────────
    # Compare contractor total vs Deal Architect estimate
    # Store delta so AI can learn accuracy over time
    if deal_id:
        deal = Deal.query.get(deal_id)
        if deal and deal.rehab_cost:
            ai_estimate = float(deal.rehab_cost)
            contractor_total = float(budget.total_cost)
            delta = contractor_total - ai_estimate
            delta_pct = round((delta / ai_estimate) * 100, 2) if ai_estimate > 0 else 0

            # Store in deal's results_json for Deal Architect to read
            results = deal.results_json or {}
            if "contractor_feedback" not in results:
                results["contractor_feedback"] = []

            results["contractor_feedback"].append({
                "partner_id": partner.id,
                "partner_name": partner.name or partner.company,
                "ai_estimate": ai_estimate,
                "contractor_total": contractor_total,
                "labor": labor_cost,
                "materials": materials_cost,
                "delta": delta,
                "delta_pct": delta_pct,
                "timeline": timeline,
                "submitted_at": datetime.utcnow().isoformat(),
            })

            deal.results_json = results

            # Flag the deal's scope as having a real contractor number
            if hasattr(deal, "inputs_json") and deal.inputs_json:
                inputs = deal.inputs_json or {}
                inputs["contractor_verified_rehab"] = contractor_total
                inputs["contractor_verified_at"] = datetime.utcnow().isoformat()
                deal.inputs_json = inputs

    # Also create a PartnerProposal for the record
    proposal = PartnerProposal(
        partner_id=partner.id,
        title=job.title or "Scope Submission",
        scope_of_work=scope_notes,
        labor_cost=labor_cost,
        materials_cost=materials_cost,
        other_cost=other_cost,
        estimated_timeline=timeline,
        status="sent",
        sent_at=datetime.utcnow(),
    )
    proposal.calculate_total()
    db.session.add(proposal)

    db.session.commit()

    flash(f"Scope submitted. Total: ${total:,.0f}", "success")
    return redirect(url_for("vip.contractor_dashboard"))


# ── REALTOR VIP: Market-matched investor properties ───────────────

@vip_bp.get("/realtor/investor-flow")
@role_required("partner_group", "admin")
def realtor_investor_flow():
    """
    Shows realtor (Frank/Elena) properties investors are actively
    analyzing in their market. Two-way: realtor can attach comps/
    listing data back to the investor's deal.
    """
    profile = get_or_create_vip_profile()
    partner = getattr(current_user, "partner_profile", None)
    current_market = _get_frank_market()

    service_area = getattr(partner, "service_area", "") or ""

    # ── Match SavedProperties to realtor's market ─────────────────
    # Strategy 1: explicit market tag on SavedProperty
    # Strategy 2: geo match on state/city vs service_area
    # Strategy 3: investor explicitly sent a PartnerConnectionRequest
    # to this realtor (category = realtor/listing)

    matched_properties = []

    # Method 1 + 2: market/geo match on active SavedProperties
    # that have been analyzed (have a linked PropertyAnalysis)
    analyzed_ids = (
        db.session.query(PropertyAnalysis.investor_profile_id)
        .filter(PropertyAnalysis.investor_profile_id.isnot(None))
        .distinct()
        .all()
    )
    analyzed_investor_ids = [row[0] for row in analyzed_ids]

    if analyzed_investor_ids:
        sp_query = SavedProperty.query.filter(
            SavedProperty.investor_profile_id.in_(analyzed_investor_ids)
        )

        # Market tag match (Frank's markets)
        market_matches = []
        geo_matches = []

        if current_market != "All Markets":
            # Try market column first
            if hasattr(SavedProperty, "market"):
                market_matches = sp_query.filter_by(market=current_market).limit(20).all()

            # Geo fallback — match state/city
            if not market_matches:
                state_map = {
                    "Hudson Valley": ("NY", ["beacon", "kingston", "poughkeepsie",
                                             "newburgh", "hudson", "rhinebeck",
                                             "woodstock", "catskill"]),
                    "Sarasota": ("FL", ["sarasota", "bradenton", "venice",
                                        "north port", "osprey", "nokomis"]),
                }
                if current_market in state_map:
                    state_code, cities = state_map[current_market]
                    geo_matches = sp_query.filter(
                        db.func.lower(SavedProperty.state) == state_code.lower()
                    ).limit(20).all()
        else:
            # All Markets — show everything analyzed
            market_matches = sp_query.limit(30).all()

        raw_properties = market_matches or geo_matches

        for sp in raw_properties:
            # Get the deal tied to this property if any
            deal = Deal.query.filter_by(saved_property_id=sp.id).first()

            # Get the latest analysis
            analysis = (
                PropertyAnalysis.query
                .filter_by(investor_profile_id=sp.investor_profile_id)
                .order_by(PropertyAnalysis.created_at.desc())
                .first()
            )

            matched_properties.append({
                "property": sp,
                "deal": deal,
                "analysis": analysis,
                "arv": float(deal.arv or 0) if deal else float(getattr(analysis, "arv", 0) or 0),
                "rehab": float(deal.rehab_cost or 0) if deal else float(getattr(analysis, "rehab_cost", 0) or 0),
                "strategy": deal.strategy if deal else None,
                "address": (getattr(sp, "address", None) or
                           (deal.address if deal else None) or
                           (analysis.address if analysis else "—")),
            })

    # Method 3: PartnerConnectionRequests sent TO this realtor
    # (category contains realtor/listing/comps)
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
            .limit(10)
            .all()
        )

    return render_template(
        "vip/realtor/investor_flow.html",
        vip_profile=profile,
        modules=get_enabled_modules(profile),
        header_name=get_dashboard_name(profile),
        matched_properties=matched_properties,
        realtor_requests=realtor_requests,
        current_market=current_market,
        available_markets=FRANK_MARKETS,
        portal="vip",
        portal_name="VIP",
        portal_home=url_for("vip.realtor_dashboard"),
    )


# ── REALTOR: Attach comps/listing data to investor deal ──────────

@vip_bp.post("/realtor/deal/<int:deal_id>/attach-market-data")
@role_required("partner_group", "admin")
def realtor_attach_market_data(deal_id):
    """
    Realtor pushes market context (comps, listing notes, market analysis)
    back into the investor's deal. Feeds Deal Architect accuracy.
    """
    profile = get_or_create_vip_profile()
    partner = getattr(current_user, "partner_profile", None)

    deal = Deal.query.get_or_404(deal_id)

    comps_note = (request.form.get("comps_note") or "").strip()
    suggested_arv = request.form.get("suggested_arv", type=float)
    market_note = (request.form.get("market_note") or "").strip()
    days_on_market = request.form.get("days_on_market", type=int)
    list_price = request.form.get("list_price", type=float)

    # Write realtor's market intelligence into deal's results_json
    results = deal.results_json or {}

    results["realtor_market_data"] = {
        "realtor_id": partner.id if partner else None,
        "realtor_name": partner.name if partner else profile.display_name,
        "market": _get_frank_market(),
        "suggested_arv": suggested_arv,
        "comps_note": comps_note,
        "market_note": market_note,
        "days_on_market": days_on_market,
        "list_price": list_price,
        "submitted_at": datetime.utcnow().isoformat(),
    }

    # If realtor is suggesting a different ARV — flag for Deal Architect
    if suggested_arv and deal.arv:
        arv_delta = suggested_arv - float(deal.arv)
        results["realtor_market_data"]["arv_delta"] = round(arv_delta, 2)
        results["realtor_market_data"]["arv_delta_pct"] = (
            round((arv_delta / float(deal.arv)) * 100, 2)
            if deal.arv > 0 else None
        )

    deal.results_json = results

    # SQLAlchemy JSON mutation tracking
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(deal, "results_json")

    db.session.commit()

    flash("Market data attached to deal.", "success")
    return redirect(url_for("vip.realtor_investor_flow"))



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
