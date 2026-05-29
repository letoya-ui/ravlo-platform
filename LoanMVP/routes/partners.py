from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app, jsonify
from flask_login import current_user, login_required
from datetime import datetime
from pathlib import Path
from werkzeug.utils import secure_filename
from sqlalchemy import desc

from LoanMVP.extensions import db, csrf, stripe
from LoanMVP.utils.decorators import role_required
from LoanMVP.ai.base_ai import AIAssistant

from LoanMVP.services.partner_search_service import search_external_partners

from LoanMVP.models.crm_models import Partner, Task, CRMNote, Lead
from LoanMVP.models.vip_models import VIPProfile
from LoanMVP.models.partner_models import (
    PartnerConnectionRequest,
    PartnerJob,
    PartnerPhoto,
    PartnerProposal,
    PartnerLeadCharge,
)

partners_bp = Blueprint("partners", __name__, url_prefix="/partners")


def _partner_testing_enabled() -> bool:
    return bool(
        current_app.config.get("FREE_PARTNER_MODE", False)
        or current_app.config.get("BYPASS_PARTNER_SUBSCRIPTION", False)
    )


def _partner_tier_features(partner) -> set[str]:
    tier = ((getattr(partner, "subscription_tier", "") or "").strip().lower())

    features_by_tier = {
        "free": {"crm_enabled"},
        "featured": {
            "crm_enabled",
            "deal_visibility_enabled",
            "priority_placement_enabled",
            "smart_notifications_enabled",
            "portfolio_showcase_enabled",
        },
        "premium": {
            "crm_enabled",
            "deal_visibility_enabled",
            "priority_placement_enabled",
            "smart_notifications_enabled",
            "portfolio_showcase_enabled",
            "proposal_builder_enabled",
            "instant_quote_enabled",
            "ai_assist_enabled",
        },
        "enterprise": {
            "crm_enabled",
            "deal_visibility_enabled",
            "priority_placement_enabled",
            "smart_notifications_enabled",
            "portfolio_showcase_enabled",
            "proposal_builder_enabled",
            "instant_quote_enabled",
            "ai_assist_enabled",
        },
    }

    return features_by_tier.get(tier, set())


def partner_feature_enabled(partner, feature_attr: str, default: bool = False) -> bool:
    if _partner_testing_enabled():
        return bool(partner)

    if not partner:
        return False

    if getattr(partner, feature_attr, default):
        return True

    return feature_attr in _partner_tier_features(partner)


def partner_effective_feature_access(partner) -> dict[str, bool]:
    feature_defaults = {
        "crm_enabled": True,
        "deal_visibility_enabled": False,
        "proposal_builder_enabled": False,
        "instant_quote_enabled": False,
        "ai_assist_enabled": False,
        "priority_placement_enabled": False,
        "smart_notifications_enabled": False,
        "portfolio_showcase_enabled": False,
    }

    return {
        feature_name: partner_feature_enabled(partner, feature_name, default)
        for feature_name, default in feature_defaults.items()
    }


def partner_has_pro_access(partner) -> bool:
    if current_app.config.get("FREE_PARTNER_MODE", False):
        return bool(partner)

    if not partner or not partner.approved:
        return False

    tier = (partner.subscription_tier or "").strip()
    return tier in ("Featured", "Premium", "Enterprise") and partner.is_active_listing()


def partner_has_premium_access(partner) -> bool:
    if current_app.config.get("FREE_PARTNER_MODE", False):
        return bool(partner)

    if not partner or not partner.approved:
        return False

    tier = (partner.subscription_tier or "").strip()
    return tier in ("Premium", "Enterprise") and partner.is_active_listing()


# Tiers that unlock the VIP Realtor Workspace. Matches
# LoanMVP.routes.vip.VIP_ACCESS_TIERS (kept local to avoid import cycle).
_VIP_ACCESS_TIERS = {"featured", "premium", "enterprise"}


def _partner_role_text(partner) -> str:
    if not partner:
        return ""

    fields = [
        getattr(partner, "category", ""),
        getattr(partner, "type", ""),
    ]
    return " ".join(str(value or "").strip().lower() for value in fields)


def partner_is_realtor(partner) -> bool:
    if not partner:
        return False
    role_text = _partner_role_text(partner)
    return any(term in role_text for term in ("realtor", "real estate", "real-estate", "realty"))


def partner_is_contractor(partner) -> bool:
    if not partner:
        return False
    role_text = _partner_role_text(partner)
    return any(term in role_text for term in ("contractor", "construction", "builder", "general contractor"))


def partner_is_insurance(partner) -> bool:
    if not partner:
        return False
    role_text = _partner_role_text(partner)
    return any(term in role_text for term in ("insurance", "insurer"))


def partner_vip_tier_unlocked(partner) -> bool:
    """True if this partner's current tier already unlocks VIP."""
    if not partner:
        return False

    if current_app.config.get("FREE_PARTNER_MODE", False):
        return True
    if current_app.config.get("BYPASS_PARTNER_SUBSCRIPTION", False):
        return True

    tier = (getattr(partner, "subscription_tier", "") or "").strip().lower()
    return tier in _VIP_ACCESS_TIERS


# ------------------------------------------------
# DASHBOARD
# ------------------------------------------------

@partners_bp.route("/dashboard")
@role_required("partner_group", "admin")
def dashboard():
    partner = Partner.query.filter_by(user_id=current_user.id).first()

    if not partner:
        flash("Partner profile not found. Please register.", "warning")
        return redirect(url_for("partners.register"))

    vip_profile = VIPProfile.query.filter_by(user_id=current_user.id).first()
    vip_role = ((getattr(vip_profile, "role_type", "") or "").strip().lower())

    if partner_vip_tier_unlocked(partner) and vip_role in {"contractor", "contractor_realtor"}:
        return redirect(url_for("vip.contractor_dashboard"))

    # VIP contractor/realtor partners use the Build Studio-style contractor
    # dashboard so field and property workflows stay together.
    if (
        partner_vip_tier_unlocked(partner)
        and partner_is_realtor(partner)
        and partner_is_contractor(partner)
    ):
        return redirect(url_for("vip.contractor_dashboard"))

    # VIP realtors use the unified VIP dashboard — redirect so they never
    # see a separate partner space.
    if partner_vip_tier_unlocked(partner) and partner_is_realtor(partner):
        return redirect(url_for("vip.realtor_dashboard"))

    # VIP insurance partners use the unified insurance dashboard.
    if partner_vip_tier_unlocked(partner) and partner_is_insurance(partner):
        return redirect(url_for("vip.insurance_dashboard"))

    base_query = PartnerConnectionRequest.query.filter_by(partner_id=partner.id)

    pending_count = base_query.filter_by(status="pending").count()
    accepted_count = base_query.filter_by(status="accepted").count()
    completed_count = base_query.filter_by(status="completed").count()
    awaiting_match_count = base_query.filter_by(status="awaiting_match").count()
    declined_count = base_query.filter_by(status="declined").count()

    recent_requests = (
        base_query.order_by(desc(PartnerConnectionRequest.created_at))
        .limit(8)
        .all()
    )

    feature_cards = [
        {
            "key": "crm",
            "title": "CRM",
            "description": "Manage contacts, follow-up, and lead activity inside Ravlo.",
            "enabled": partner_feature_enabled(partner, "crm_enabled", True),
            "cta": "Open CRM",
            "endpoint": "partners.crm",
            "badge": "Core",
        },
        {
            "key": "deal_visibility",
            "title": "Deal Visibility",
            "description": "See project, deal, and property context tied to requests.",
            "enabled": partner_feature_enabled(partner, "deal_visibility_enabled", False),
            "cta": "View Opportunities",
            "endpoint": "partners.requests",
            "badge": "Growth Tool",
        },
        {
            "key": "proposal_builder",
            "title": "Proposal Builder",
            "description": "Create scopes, service proposals, and branded responses.",
            "enabled": partner_feature_enabled(partner, "proposal_builder_enabled", False),
            "cta": "Build Proposal",
            "endpoint": "partners.proposals",
            "badge": "Premium",
        },
        {
            "key": "instant_quote",
            "title": "Instant Quote",
            "description": "Generate pricing quickly for incoming work opportunities.",
            "enabled": partner_feature_enabled(partner, "instant_quote_enabled", False),
            "cta": "Create Quote",
            "endpoint": "partners.quotes",
            "badge": "Premium",
        },
        {
            "key": "ai_assist",
            "title": "AI Assist",
            "description": "Use AI to help draft responses, estimates, and timelines.",
            "enabled": partner_feature_enabled(partner, "ai_assist_enabled", False),
            "cta": "Open AI",
            "endpoint": "partners.ai",
            "badge": "Premium",
        },
        {
            "key": "priority_placement",
            "title": "Priority Placement",
            "description": "Appear higher in Ravlo search and partner recommendations.",
            "enabled": partner_feature_enabled(partner, "priority_placement_enabled", False),
            "cta": "Boost Visibility",
            "endpoint": "partners.upgrade",
            "badge": "Visibility",
        },
        {
            "key": "smart_notifications",
            "title": "Smart Notifications",
            "description": "Get alerts when new requests match your service area.",
            "enabled": partner_feature_enabled(partner, "smart_notifications_enabled", False),
            "cta": "Manage Alerts",
            "endpoint": "partners.notifications",
            "badge": "Automation",
        },
        {
            "key": "portfolio_showcase",
            "title": "Portfolio Showcase",
            "description": "Display photos and project work to help investors trust faster.",
            "enabled": partner_feature_enabled(partner, "portfolio_showcase_enabled", False),
            "cta": "Manage Portfolio",
            "endpoint": "partners.portfolio",
            "badge": "Brand",
        },
    ]

    locked_feature_count = sum(1 for item in feature_cards if not item["enabled"])

    stats = {
        "pending": pending_count,
        "accepted": accepted_count,
        "completed": completed_count,
        "awaiting_match": awaiting_match_count,
        "declined": declined_count,
        "deals": partner.deals or 0,
        "volume": partner.volume or 0.0,
        "rating": partner.rating or 0.0,
        "review_count": partner.review_count or 0,
        "profile_completion": partner.profile_completion() if hasattr(partner, "profile_completion") else 0,
    }

    is_realtor = partner_is_realtor(partner)
    vip_unlocked = partner_vip_tier_unlocked(partner)

    return render_template(
        "partners/dashboards/home.html",
        partner=partner,
        pending_count=pending_count,
        accepted_count=accepted_count,
        completed_count=completed_count,
        awaiting_match_count=awaiting_match_count,
        declined_count=declined_count,
        recent_requests=recent_requests,
        feature_cards=feature_cards,
        locked_feature_count=locked_feature_count,
        stats=stats,
        is_realtor=is_realtor,
        vip_unlocked=vip_unlocked,
        portal="partner",
        portal_name="Partner OS",
        portal_home=url_for("partners.dashboard")
    )


# ------------------------------------------------
# PARTNER DIRECTORY (internal)
# ------------------------------------------------

@partners_bp.route("/center")
@role_required("partner_group")
def center():
    partner = Partner.query.filter_by(user_id=current_user.id).first()

    jobs = []
    connections = []
    stats = {
        "active_jobs": 0,
        "completed_jobs": 0,
        "connection_requests": 0,
    }

    if partner:
        jobs = (
            PartnerJob.query
            .filter_by(partner_id=partner.id)
            .order_by(PartnerJob.created_at.desc())
            .limit(10)
            .all()
        )

        stats["active_jobs"] = len([j for j in jobs if j.status in ["new", "in_progress"]])
        stats["completed_jobs"] = len([j for j in jobs if j.status == "completed"])

        connections = (
            PartnerConnectionRequest.query
            .filter_by(partner_id=partner.id)
            .order_by(PartnerConnectionRequest.created_at.desc())
            .limit(10)
            .all()
        )

        stats["connection_requests"] = len(connections)

    return render_template(
        "partners/center.html",
        partner=partner,
        jobs=jobs,
        connections=connections,
        stats=stats,
        active_tab="center",
    )


# ------------------------------------------------
# PARTNER PROFILE
# ------------------------------------------------

@partners_bp.route("/<int:partner_id>")
@role_required("partner_group")
def profile(partner_id):
    partner = Partner.query.get_or_404(partner_id)

    return render_template(
        "partners/profile.html",
        partner=partner,
        portal="partner",
        portal_name="Partner OS",
        portal_home=url_for("partners.dashboard"),
    )


# ------------------------------------------------
# PARTNER REGISTRATION
# ------------------------------------------------

@partners_bp.route("/register", methods=["GET", "POST"])
@csrf.exempt
@role_required("partner_group")
def register():
    partner = Partner.query.filter_by(user_id=current_user.id).first()

    if request.method == "POST":
        name = (request.form.get("name") or request.form.get("company") or "").strip() or None
        category = (request.form.get("category") or request.form.get("role") or "").strip() or None
        company = request.form.get("company", "").strip() or None
        service_area = request.form.get("service_area", "").strip() or None
        specialty = request.form.get("specialty", "").strip() or None
        bio = request.form.get("bio", "").strip() or None

        if not name:
            flash("Please enter a contact name or company name.", "danger")
            return render_template("partners/register.html", partner=partner)

        if partner:
            partner.name = name
            partner.category = category
            partner.company = company
            partner.service_area = service_area
            partner.specialty = specialty
            partner.bio = bio
        else:
            partner = Partner(
                user_id=current_user.id,
                name=name,
                category=category,
                company=company,
                service_area=service_area,
                specialty=specialty,
                bio=bio,
                active=True,
                status="Active",
                approved=True,
                featured=True,
                subscription_tier="Premium",
            )
            db.session.add(partner)

        db.session.commit()
        flash("Partner profile saved.", "success")
        return redirect(url_for("partners.dashboard"))

    return render_template(
        "partners/register.html",
        partner=partner,
        portal="partner",
        portal_name="Partner OS",
        portal_home=url_for("partners.dashboard"),
    )


@partners_bp.route("/requests/<int:request_id>", methods=["GET"])
@role_required("partner_group")
def request_detail(request_id):
    partner = Partner.query.filter_by(user_id=current_user.id).first()

    if not partner:
        flash("Partner profile not found.", "danger")
        return redirect(url_for("auth.login"))

    req = PartnerConnectionRequest.query.filter_by(
        id=request_id,
        partner_id=partner.id
    ).first_or_404()

    return render_template(
        "partners/request_detail.html",
        partner=partner,
        req=req,
        page_title="Request Detail",
        page_subline="Review opportunity details and next steps.",
        portal="partner",
        portal_name="Partner OS",
        portal_home=url_for("partners.dashboard"),
    )


# ------------------------------------------------
# PARTNER REQUEST INBOX
# ------------------------------------------------

@partners_bp.route("/requests")
@role_required("partner_group", "admin")
def requests_inbox():
    partner = Partner.query.filter_by(user_id=current_user.id).first()

    if not partner:
        flash("Partner profile not found.", "warning")
        return redirect(url_for("partners.register"))

    if not partner_has_pro_access(partner):
        return render_template(
            "partners/upgrade_required.html",
            partner=partner,
            portal="partner",
            portal_name="Partner OS",
            portal_home=url_for("partners.dashboard"),
        ), 403

    selected_status = (request.args.get("status") or "").strip()
    selected_source = (request.args.get("source") or "").strip()

    query = PartnerConnectionRequest.query.filter_by(partner_id=partner.id)

    if selected_status:
        query = query.filter(PartnerConnectionRequest.status == selected_status)

    if selected_source:
        query = query.filter(PartnerConnectionRequest.source == selected_source)

    requests_list = query.order_by(
        PartnerConnectionRequest.created_at.desc()
    ).all()

    return render_template(
        "partners/requests.html",
        partner=partner,
        requests_list=requests_list,
        selected_status=selected_status,
        selected_source=selected_source,
        portal="partner",
        portal_name="Partner OS",
        portal_home=url_for("partners.dashboard"),
    )


# ------------------------------------------------
# ACCEPT REQUEST
# ------------------------------------------------

@partners_bp.route("/requests/<int:req_id>/accept", methods=["POST"])
@csrf.exempt
@role_required("partner_group")
def accept_request(req_id):
    partner = Partner.query.filter_by(user_id=current_user.id).first()
    req = PartnerConnectionRequest.query.get_or_404(req_id)

    if not partner or req.partner_id != partner.id:
        abort(403)

    if req.status != "pending":
        flash("This request is no longer pending.", "info")
        return redirect(url_for("partners.requests_inbox"))

    req.status = "accepted"
    req.responded_at = datetime.utcnow()

    task = Task(
        borrower_id=req.borrower_profile_id,
        title=f"{req.category or partner.category} • New Request",
        description=req.message,
        assigned_to=current_user.id,
        status="Pending",
        priority="Normal"
    )
    db.session.add(task)

    if req.borrower_profile_id:
        db.session.add(CRMNote(
            borrower_id=req.borrower_profile_id,
            user_id=current_user.id,
            content=f"Accepted partner request (Partner: {partner.company or partner.name})."
        ))

    if partner_has_premium_access(partner):
        job = PartnerJob(
            partner_id=partner.id,
            borrower_profile_id=req.borrower_profile_id,
            investor_profile_id=req.investor_profile_id,
            property_id=req.property_id,
            title=f"{req.category or partner.category} Job",
            scope=req.message,
            status="Open"
        )

        db.session.add(job)
        db.session.flush()

        if hasattr(task, "partner_job_id"):
            task.partner_job_id = job.id

    db.session.commit()

    flash("Request accepted.", "success")
    return redirect(url_for("partners.requests_inbox"))


# ------------------------------------------------
# DECLINE REQUEST
# ------------------------------------------------

@partners_bp.route("/requests/<int:req_id>/decline", methods=["POST"])
@csrf.exempt
@role_required("partner_group")
def decline_request(req_id):
    partner = Partner.query.filter_by(user_id=current_user.id).first()
    req = PartnerConnectionRequest.query.get_or_404(req_id)

    if not partner or req.partner_id != partner.id:
        abort(403)

    if req.status != "pending":
        flash("This request is no longer pending.", "info")
        return redirect(url_for("partners.requests_inbox"))

    req.status = "declined"
    req.responded_at = datetime.utcnow()

    db.session.commit()

    flash("Request declined.", "info")
    return redirect(url_for("partners.requests_inbox"))


@partners_bp.route("/requests/<int:request_id>/status", methods=["POST"])
@csrf.exempt
@role_required("partner_group")
def update_request_status(request_id):
    partner = Partner.query.filter_by(user_id=current_user.id).first()

    if not partner:
        flash("Partner profile not found.", "danger")
        return redirect(url_for("auth.login"))

    req = PartnerConnectionRequest.query.filter_by(
        id=request_id,
        partner_id=partner.id
    ).first_or_404()

    new_status = (request.form.get("status") or "").strip().lower()
    allowed = {"pending", "accepted", "declined", "canceled", "completed", "awaiting_match"}

    if new_status not in allowed:
        flash("Invalid request status.", "danger")
        return redirect(url_for("partners.request_detail", request_id=req.id))

    req.status = new_status
    req.responded_at = datetime.utcnow()

    db.session.commit()

    flash("Request status updated.", "success")
    return redirect(url_for("partners.request_detail", request_id=req.id))


# ------------------------------------------------
# PREMIUM WORKSPACE
# ------------------------------------------------

@partners_bp.route("/workspace")
@role_required("partner_group")
def workspace_home():
    partner = Partner.query.filter_by(user_id=current_user.id).first()

    if not partner or not partner_has_premium_access(partner):
        return render_template(
            "partners/upgrade_required.html",
            partner=partner
        ), 403

    jobs = PartnerJob.query.filter_by(
        partner_id=partner.id
    ).order_by(
        PartnerJob.created_at.desc()
    ).all()

    return render_template(
        "partners/workspace/home.html",
        partner=partner,
        jobs=jobs,
        portal="partner",
        portal_name="Partner OS",
        portal_home=url_for("partners.dashboard"),
    )


@partners_bp.route("/workspace/jobs/<int:job_id>")
@role_required("partner_group")
def workspace_job(job_id):
    partner = Partner.query.filter_by(user_id=current_user.id).first()
    job = PartnerJob.query.get_or_404(job_id)

    if not partner or job.partner_id != partner.id:
        abort(403)

    tasks = Task.query.filter_by(
        partner_job_id=job.id
    ).order_by(
        Task.created_at.desc()
    ).all()

    return render_template(
        "partners/workspace/job.html",
        partner=partner,
        job=job,
        tasks=tasks,
        portal="partner",
        portal_name="Partner OS",
        portal_home=url_for("partners.dashboard"),
    )


# ------------------------------------------------
# PHOTO UPLOAD
# ------------------------------------------------

@partners_bp.route("/photos/upload", methods=["POST"])
@csrf.exempt
@role_required("partner_group")
def upload_photo():
    partner = Partner.query.filter_by(user_id=current_user.id).first()

    if not partner:
        flash("Partner profile not found.", "danger")
        return redirect(request.referrer)

    file = request.files.get("photo")

    if not file:
        flash("No file uploaded.", "danger")
        return redirect(request.referrer)

    filename = secure_filename(file.filename)
    upload_dir = Path("static/uploads/partners") / str(partner.id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    filepath = upload_dir / filename
    file.save(filepath)

    photo = PartnerPhoto(
        partner_id=partner.id,
        url=f"/static/uploads/partners/{partner.id}/{filename}"
    )

    db.session.add(photo)
    db.session.commit()

    flash("Photo uploaded successfully.", "success")
    return redirect(request.referrer)


@partners_bp.route("/listing", methods=["GET", "POST"])
@csrf.exempt
@role_required("partner_group")
def listing():
    partner = current_user.partner_profile

    if not partner:
        flash("Please complete your partner profile first.", "warning")
        return redirect(url_for("partners.profile_setup"))

    if request.method == "POST":
        partner.listing_description = request.form.get("listing_description")
        partner.bio = request.form.get("bio")
        partner.specialty = request.form.get("specialty")
        partner.service_area = request.form.get("service_area")
        partner.logo_url = request.form.get("logo_url")
        # subscription_tier and featured are billing/admin fields — never accept from user input

        db.session.commit()
        flash("Your marketplace listing has been updated.", "success")
        return redirect(url_for("partners.listing"))

    return render_template(
        "partners/listing.html",
        partner=partner,
        portal="partner",
        page_title="Marketplace Listing",
        page_subline="Manage how you appear in the Ravlo Partner Marketplace."
    )


# ------------------------------------------------
# DELETE PHOTO
# ------------------------------------------------

@partners_bp.route("/photos/<int:photo_id>/delete", methods=["POST"])
@csrf.exempt
@role_required("partner_group")
def delete_photo(photo_id):
    partner = Partner.query.filter_by(user_id=current_user.id).first()
    photo = PartnerPhoto.query.get_or_404(photo_id)

    if photo.partner_id != partner.id:
        abort(403)

    db.session.delete(photo)
    db.session.commit()

    flash("Photo removed.", "success")
    return redirect(request.referrer)


@partners_bp.route("/leads")
@role_required("partner_group")
def leads():
    partner = current_user.partner_profile

    if not partner:
        flash("Please complete your partner profile first.", "warning")
        return redirect(url_for("partners.profile_setup"))

    leads = partner.leads.order_by(Lead.created_at.desc()).all()

    return render_template(
        "partners/leads.html",
        partner=partner,
        leads=leads,
        portal="partner",
        page_title="Leads",
        page_subline="Your incoming opportunities from the Ravlo ecosystem."
    )


@partners_bp.route("/lead/<int:lead_id>")
@role_required("partner_group")
def lead_detail(lead_id):
    lead = Lead.query.get_or_404(lead_id)

    if current_user.partner_profile not in lead.partners:
        abort(403)

    return render_template(
        "partners/lead_detail.html",
        lead=lead,
        portal="partner",
        page_title=lead.name,
        page_subline="Lead details and activity"
    )


@partners_bp.route("/settings", methods=["GET", "POST"])
@role_required("partner_group")
def settings():
    partner = Partner.query.filter_by(user_id=current_user.id).first()

    if not partner:
        flash("Partner profile not found.", "warning")
        return redirect(url_for("partners.register"))

    if request.method == "POST":
        company = request.form.get("company")
        category = request.form.get("category") or request.form.get("role")
        service_area = request.form.get("service_area")
        bio = request.form.get("bio")

        partner.company = company
        partner.category = category
        partner.service_area = service_area
        partner.bio = bio

        db.session.commit()
        flash("Settings updated.", "success")
        return redirect(url_for("partners.settings"))

    return render_template(
        "partners/settings.html",
        partner=partner,
        portal="partner",
        portal_name="Partner OS",
        portal_home=url_for("partners.dashboard"),
    )


@partners_bp.route("/deals")
@role_required("partner_group")
def deals():
    partner = Partner.query.filter_by(user_id=current_user.id).first()
    if not partner:
        flash("Partner profile not found.", "warning")
        return redirect(url_for("partners.register"))

    jobs = PartnerJob.query.filter_by(partner_id=partner.id)\
        .order_by(PartnerJob.created_at.desc()).all()

    return render_template(
        "partners/deals.html",
        partner=partner,
        jobs=jobs,
        portal="partner",
        portal_name="Partner OS",
        portal_home=url_for("partners.dashboard"),
    )


@partners_bp.route("/resources")
@role_required("partner_group")
def resources():
    partner = Partner.query.filter_by(user_id=current_user.id).first()
    if not partner:
        flash("Partner profile not found.", "warning")
        return redirect(url_for("partners.register"))

    return render_template(
        "partners/resources.html",
        partner=partner,
        portal="partner",
        portal_name="Partner OS",
        portal_home=url_for("partners.dashboard"),
    )


@partners_bp.route("/subscribe/<tier>")
@role_required("partner_group")
def subscribe(tier):
    partner = Partner.query.filter_by(user_id=current_user.id).first()
    if not partner:
        flash("Partner profile not found.", "warning")
        return redirect(url_for("partners.register"))

    allowed_tiers = {"Free", "Featured", "Premium", "Enterprise"}
    normalized = tier.strip().title()

    if normalized not in allowed_tiers:
        flash("Invalid subscription tier.", "danger")
        return redirect(url_for("partners.billing"))

    return render_template(
        "partners/subscribe.html",
        partner=partner,
        selected_tier=normalized,
        portal="partner",
        page_title="Choose Plan",
        page_subline="Confirm your Ravlo Partner subscription tier."
    )


@partners_bp.route("/subscribe/<tier>/confirm", methods=["POST"])
@csrf.exempt
@role_required("partner_group")
def confirm_subscription(tier):
    partner = Partner.query.filter_by(user_id=current_user.id).first()
    if not partner:
        flash("Partner profile not found.", "warning")
        return redirect(url_for("partners.register"))

    allowed_tiers = {"Free", "Featured", "Premium", "Enterprise"}
    normalized = tier.strip().title()

    if normalized not in allowed_tiers:
        flash("Invalid subscription tier.", "danger")
        return redirect(url_for("partners.billing"))

    partner.subscription_tier = normalized
    partner.approved = True
    partner.active = True
    partner.status = "Active"

    if normalized in {"Featured", "Premium", "Enterprise"}:
        partner.featured = True
    else:
        partner.featured = False

    db.session.commit()

    # When a realtor upgrades into a VIP-unlocking tier, send them straight
    # into the VIP Realtor Workspace so the upgrade is immediately tangible.
    if partner_is_realtor(partner) and normalized.lower() in _VIP_ACCESS_TIERS:
        flash(
            f"Your VIP Realtor Workspace is unlocked — welcome to {normalized}.",
            "success",
        )
        return redirect(url_for("vip.realtor_dashboard"))

    flash(f"Your subscription has been updated to {normalized}.", "success")
    return redirect(url_for("partners.billing"))


@partners_bp.route("/billing")
@role_required("partner_group")
def billing():
    partner = Partner.query.filter_by(user_id=current_user.id).first()
    if not partner:
        flash("Partner profile not found.", "warning")
        return redirect(url_for("partners.register"))

    plans = [
        {
            "name": "Free",
            "price": "$0",
            "features": ["Basic profile", "Limited visibility", "Starter access"]
        },
        {
            "name": "Featured",
            "price": "$49/mo",
            "features": ["Featured listing", "More visibility", "Pro request access", "VIP Dashboard access"]
        },
        {
            "name": "Premium",
            "price": "$99/mo",
            "features": ["Workspace access", "Priority visibility", "Advanced tools"]
        },
        {
            "name": "Enterprise",
            "price": "Custom",
            "features": ["Full suite", "Priority support", "Custom partner setup"]
        },
    ]

    return render_template(
        "partners/billing.html",
        partner=partner,
        plans=plans,
        portal="partner",
        page_title="Billing",
        page_subline="Manage your Ravlo Partner plan."
    )


@partners_bp.route("/billing/setup-intent", methods=["POST"])
@login_required
@role_required("partner_group")
def partner_billing_setup_intent():
    if not current_app.config.get("STRIPE_BILLING_ENABLED"):
        return jsonify({"error": "Billing not enabled."}), 400
    tier = (request.get_json(silent=True) or {}).get("tier") or request.form.get("tier", "")
    try:
        customers = stripe.Customer.list(email=current_user.email, limit=1)
        if customers.data:
            customer_id = customers.data[0].id
        else:
            customer_id = stripe.Customer.create(
                email=current_user.email,
                metadata={"user_id": str(current_user.id)},
            ).id
        intent = stripe.SetupIntent.create(
            customer=customer_id,
            payment_method_types=["card"],
            metadata={"user_id": str(current_user.id), "partner_tier": tier},
        )
        return jsonify({"client_secret": intent.client_secret})
    except Exception:
        current_app.logger.exception("Stripe SetupIntent creation failed for partner")
        return jsonify({"error": "Unable to initialize payment. Please try again."}), 500


_PARTNER_STRIPE_PRICE_MAP = {
    "featured": "STRIPE_PRICE_FEATURED_PARTNER",
    "premium":  "STRIPE_PRICE_PREFERRED_PARTNER",
    "enterprise": "STRIPE_PRICE_ENTERPRISE",
}


@partners_bp.route("/billing/subscribe-checkout/<tier>", methods=["POST"])
@login_required
@role_required("partner_group")
def partner_subscription_checkout(tier):
    if not current_app.config.get("STRIPE_BILLING_ENABLED"):
        flash("Stripe billing is not enabled yet.", "warning")
        return redirect(url_for("partners.billing"))

    normalized = tier.strip().lower()
    price_key = _PARTNER_STRIPE_PRICE_MAP.get(normalized)
    price_id = current_app.config.get(price_key, "") if price_key else ""

    if not price_id:
        flash("That plan is not yet configured for checkout.", "warning")
        return redirect(url_for("partners.billing"))

    try:
        session_obj = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=url_for("partners.partner_subscription_success", _external=True)
                        + "?session_id={CHECKOUT_SESSION_ID}&tier=" + normalized,
            cancel_url=url_for("partners.billing", _external=True),
            customer_email=current_user.email,
            metadata={
                "user_id": str(current_user.id),
                "partner_tier": normalized,
            },
            subscription_data={
                "metadata": {
                    "user_id": str(current_user.id),
                    "partner_tier": normalized,
                },
            },
        )
        return redirect(session_obj.url, code=303)
    except Exception:
        current_app.logger.exception("Stripe Checkout creation failed for partner")
        flash("Unable to start checkout. Please try again.", "danger")
        return redirect(url_for("partners.billing"))


@partners_bp.route("/billing/subscribe-success")
@login_required
@role_required("partner_group")
def partner_subscription_success():
    session_id = request.args.get("session_id")
    tier = (request.args.get("tier") or "").strip().lower()

    if session_id:
        try:
            session_obj = stripe.checkout.Session.retrieve(session_id)
            if session_obj.payment_status in ("paid", "no_payment_required"):
                tier = tier or (session_obj.metadata or {}).get("partner_tier", "")
        except Exception:
            current_app.logger.exception("Stripe Checkout verification failed for partner")

    allowed = {"featured", "premium", "enterprise"}
    if tier in allowed:
        partner = Partner.query.filter_by(user_id=current_user.id).first()
        if partner:
            partner.subscription_tier = tier.title()
            partner.approved = True
            partner.active = True
            partner.status = "Active"
            partner.featured = tier in {"featured", "premium", "enterprise"}
            db.session.commit()
            flash(f"Subscription activated — welcome to {tier.title()}!", "success")
            if tier in _VIP_ACCESS_TIERS:
                return redirect(url_for("vip.realtor_dashboard"))
    else:
        flash("Subscription checkout completed.", "success")

    return redirect(url_for("partners.billing"))


# ─── Pay-Per-Lead ─────────────────────────────────────────────────────────────

def _charge_partner_for_lead(partner, connection_request=None):
    """
    Attempt a Stripe off-session charge for one lead delivery.
    Returns the PartnerLeadCharge record (status may be 'paid' or 'failed').
    """
    from datetime import datetime as _dt
    amount = float(partner.lead_price or 35.00)
    charge = PartnerLeadCharge(
        partner_id=partner.id,
        connection_request_id=getattr(connection_request, "id", None),
        amount=amount,
        stripe_customer_id=partner.stripe_customer_id,
    )
    db.session.add(charge)
    db.session.flush()  # get charge.id before Stripe call

    if not partner.stripe_customer_id or not partner.stripe_payment_method_id:
        charge.status = "pending"  # awaiting card on file
        return charge

    try:
        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),
            currency="usd",
            customer=partner.stripe_customer_id,
            payment_method=partner.stripe_payment_method_id,
            off_session=True,
            confirm=True,
            description=f"Lead delivery — partner {partner.id}",
            metadata={
                "partner_id": str(partner.id),
                "lead_charge_id": str(charge.id),
            },
        )
        charge.stripe_payment_intent = intent.id
        charge.status = "paid"
        charge.paid_at = _dt.utcnow()
    except stripe.error.CardError as exc:
        charge.status = "failed"
        charge.failure_reason = exc.user_message or str(exc)
    except Exception as exc:
        charge.status = "failed"
        charge.failure_reason = str(exc)

    return charge


@partners_bp.route("/billing/lead-price", methods=["POST"])
@login_required
@role_required("partner_group")
def update_lead_price():
    """Partner sets their per-lead price and toggles pay-per-lead on/off."""
    partner = Partner.query.filter_by(user_id=current_user.id).first()
    if not partner:
        flash("Partner profile not found.", "warning")
        return redirect(url_for("partners.billing"))

    pay_per_lead = request.form.get("pay_per_lead_enabled") == "1"
    raw_price = request.form.get("lead_price", "").strip()
    try:
        price = round(float(raw_price), 2) if raw_price else 35.00
        price = max(1.00, price)
    except ValueError:
        flash("Invalid lead price.", "warning")
        return redirect(url_for("partners.billing"))

    partner.pay_per_lead_enabled = pay_per_lead
    partner.lead_price = price
    db.session.commit()
    flash("Lead pricing updated.", "success")
    return redirect(url_for("partners.billing"))


@partners_bp.route("/billing/save-payment-method", methods=["POST"])
@login_required
@role_required("partner_group")
def save_partner_payment_method():
    """Store a Stripe PaymentMethod ID on the partner after SetupIntent confirms."""
    partner = Partner.query.filter_by(user_id=current_user.id).first()
    if not partner:
        return jsonify({"error": "Partner not found."}), 404

    pm_id = (request.json or {}).get("payment_method_id") or request.form.get("payment_method_id")
    if not pm_id:
        return jsonify({"error": "Missing payment_method_id."}), 400

    try:
        # Ensure/create Stripe Customer
        if not partner.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                metadata={"partner_id": str(partner.id), "user_id": str(current_user.id)},
            )
            partner.stripe_customer_id = customer.id

        # Attach the PaymentMethod to the customer
        stripe.PaymentMethod.attach(pm_id, customer=partner.stripe_customer_id)
        stripe.Customer.modify(
            partner.stripe_customer_id,
            invoice_settings={"default_payment_method": pm_id},
        )
        partner.stripe_payment_method_id = pm_id
        db.session.commit()
        return jsonify({"ok": True})
    except Exception as exc:
        current_app.logger.exception("Failed to save partner payment method")
        return jsonify({"error": str(exc)}), 500


@partners_bp.route("/billing/lead-charges")
@login_required
@role_required("partner_group")
def lead_charge_history():
    partner = Partner.query.filter_by(user_id=current_user.id).first()
    if not partner:
        flash("Partner profile not found.", "warning")
        return redirect(url_for("partners.billing"))

    charges = (
        PartnerLeadCharge.query
        .filter_by(partner_id=partner.id)
        .order_by(PartnerLeadCharge.created_at.desc())
        .limit(50)
        .all()
    )
    return render_template(
        "partners/lead_charges.html",
        partner=partner,
        charges=charges,
        portal="partner",
        page_title="Lead Charge History",
    )


@partners_bp.route("/profile/edit", methods=["GET", "POST"])
@csrf.exempt
@role_required("partner_group")
def edit_profile():
    partner = Partner.query.filter_by(user_id=current_user.id).first()

    if not partner:
        partner = Partner(user_id=current_user.id, name=current_user.name or "Partner")

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Contact name is required.", "warning")
            return render_template("partner/partner_form.html", partner=partner)

        partner.name = name
        partner.company = (request.form.get("company") or "").strip() or None
        partner.email = (request.form.get("email") or "").strip() or None
        partner.phone = (request.form.get("phone") or "").strip() or None
        partner.website = (request.form.get("website") or "").strip() or None
        partner.category = (request.form.get("category") or "").strip() or None
        partner.type = (request.form.get("type") or "").strip() or None
        partner.specialty = (request.form.get("specialty") or "").strip() or None
        partner.service_area = (request.form.get("service_area") or "").strip() or None
        partner.address = (request.form.get("address") or "").strip() or None
        partner.city = (request.form.get("city") or "").strip() or None
        partner.state = (request.form.get("state") or "").strip() or None
        partner.zip_code = (request.form.get("zip_code") or "").strip() or None
        partner.listing_description = (request.form.get("listing_description") or "").strip() or None
        partner.bio = (request.form.get("bio") or "").strip() or None

        if not partner.id:
            db.session.add(partner)

        db.session.commit()
        flash("Your partner profile was updated successfully.", "success")
        return redirect(url_for("partners.profile", partner_id=partner.id))

    return render_template("partners/partner_form.html", partner=partner)


@partners_bp.route("/upgrade")
@role_required("partner_group", "admin")
def upgrade():
    partner = Partner.query.filter_by(user_id=current_user.id).first()

    if not partner:
        flash("Partner profile not found. Please register.", "warning")
        return redirect(url_for("partners.register"))

    feature_access = partner_effective_feature_access(partner)
    locked_feature_count = sum(1 for item in feature_access.values() if not item)

    is_realtor = partner_is_realtor(partner)
    vip_unlocked = partner_vip_tier_unlocked(partner)

    return render_template(
        "partners/upgrade.html",
        partner=partner,
        feature_access=feature_access,
        locked_feature_count=locked_feature_count,
        testing_unlocks_enabled=_partner_testing_enabled(),
        is_realtor=is_realtor,
        vip_unlocked=vip_unlocked,
        portal="partner",
        portal_name="Partner OS",
        portal_home=url_for("partners.dashboard"),
    )


@partners_bp.route("/proposals")
@role_required("partner_group", "admin")
def proposals():
    partner = Partner.query.filter_by(user_id=current_user.id).first()

    if not partner:
        flash("Partner profile not found. Please register.", "warning")
        return redirect(url_for("partners.register"))

    if not partner_feature_enabled(partner, "proposal_builder_enabled", False):
        flash("Proposal Builder is available on an upgraded plan.", "warning")
        return redirect(url_for("partners.upgrade"))

    proposals_list = (
        PartnerProposal.query
        .filter_by(partner_id=partner.id)
        .order_by(desc(PartnerProposal.created_at))
        .all()
    )

    return render_template(
        "partners/proposals.html",
        partner=partner,
        proposals_list=proposals_list,
        portal="partner",
        portal_name="Partner OS",
        portal_home=url_for("partners.dashboard"),
    )


@partners_bp.route("/proposals/<int:proposal_id>", methods=["GET", "POST"])
@role_required("partner_group", "admin")
def proposal_detail(proposal_id):
    partner = Partner.query.filter_by(user_id=current_user.id).first()

    if not partner:
        flash("Partner profile not found. Please register.", "warning")
        return redirect(url_for("partners.register"))

    if not partner_feature_enabled(partner, "proposal_builder_enabled", False):
        flash("Proposal Builder is available on an upgraded plan.", "warning")
        return redirect(url_for("partners.upgrade"))

    proposal = PartnerProposal.query.filter_by(
        id=proposal_id,
        partner_id=partner.id
    ).first_or_404()

    linked_request = proposal.request

    if request.method == "POST":
        proposal.title = (request.form.get("title") or "").strip()
        proposal.proposal_text = (request.form.get("proposal_text") or "").strip()
        proposal.scope_of_work = (request.form.get("scope_of_work") or "").strip()
        proposal.estimated_timeline = (request.form.get("estimated_timeline") or "").strip()

        proposal.labor_cost = request.form.get("labor_cost", type=float) or 0.0
        proposal.materials_cost = request.form.get("materials_cost", type=float) or 0.0
        proposal.other_cost = request.form.get("other_cost", type=float) or 0.0
        proposal.calculate_total()

        action = (request.form.get("action") or "save").strip().lower()

        if action == "send":
            proposal.status = "sent"
            proposal.sent_at = datetime.utcnow()

            if linked_request:
                linked_request.status = "accepted"
                linked_request.responded_at = datetime.utcnow()

            db.session.commit()
            flash("Proposal sent and request updated.", "success")

            if linked_request:
                return redirect(url_for("partners.request_detail", request_id=linked_request.id))
            return redirect(url_for("partners.proposal_detail", proposal_id=proposal.id))

        elif action == "accept":
            proposal.status = "accepted"
            db.session.commit()
            flash("Proposal marked accepted.", "success")
            return redirect(url_for("partners.proposal_detail", proposal_id=proposal.id))

        elif action == "decline":
            proposal.status = "declined"
            db.session.commit()
            flash("Proposal marked declined.", "warning")
            return redirect(url_for("partners.proposal_detail", proposal_id=proposal.id))

        else:
            db.session.commit()
            flash("Proposal saved.", "success")
            return redirect(url_for("partners.proposal_detail", proposal_id=proposal.id))

    return render_template(
        "partners/proposal_detail.html",
        partner=partner,
        proposal=proposal,
        portal="partner",
        portal_name="Partner OS",
        portal_home=url_for("partners.dashboard"),
    )


@partners_bp.route("/proposals/new", methods=["GET", "POST"])
@role_required("partner_group", "admin")
def create_proposal():
    partner = Partner.query.filter_by(user_id=current_user.id).first()

    if not partner:
        flash("Partner profile not found. Please register.", "warning")
        return redirect(url_for("partners.register"))

    if not partner_feature_enabled(partner, "proposal_builder_enabled", False):
        flash("Proposal Builder is available on an upgraded plan.", "warning")
        return redirect(url_for("partners.upgrade"))

    request_id = request.args.get("request_id", type=int)
    linked_request = None

    if request_id:
        linked_request = PartnerConnectionRequest.query.filter_by(
            id=request_id,
            partner_id=partner.id
        ).first()

    prefill = {
        "title": "",
        "estimated_timeline": "",
        "proposal_text": "",
        "scope_of_work": "",
        "labor_cost": "",
        "materials_cost": "",
        "other_cost": "",
    }

    if linked_request:
        prefill["title"] = linked_request.title or linked_request.category or "Service Proposal"
        prefill["estimated_timeline"] = linked_request.timeline or ""
        prefill["scope_of_work"] = linked_request.message or ""

    if request.method == "POST":
        action = (request.form.get("action") or "save").strip().lower()
        form_request_id = request.form.get("request_id", type=int)

        safe_request = None
        if form_request_id:
            safe_request = PartnerConnectionRequest.query.filter_by(
                id=form_request_id,
                partner_id=partner.id
            ).first()

        title = (request.form.get("title") or "").strip()
        proposal_text = (request.form.get("proposal_text") or "").strip()
        scope_of_work = (request.form.get("scope_of_work") or "").strip()
        estimated_timeline = (request.form.get("estimated_timeline") or "").strip()

        labor_cost = request.form.get("labor_cost", type=float) or 0.0
        materials_cost = request.form.get("materials_cost", type=float) or 0.0
        other_cost = request.form.get("other_cost", type=float) or 0.0

        if action == "generate_ai":
            ai = AIAssistant()

            ai_input = f"""
You are a professional contractor preparing a proposal for a real estate investor.

Partner: {partner.display_name()}
Category: {partner.category or partner.type}

Request Title: {safe_request.title if safe_request else title}
Request Details: {safe_request.message if safe_request else scope_of_work}
Budget: {safe_request.budget if safe_request else ''}
Timeline: {safe_request.timeline if safe_request else estimated_timeline}

Write:

1. Proposal Summary
2. Scope of Work
3. Timeline & Execution
4. Closing Statement

Keep it clear, confident, and investor-friendly.
"""

            generated_text = ai.generate_reply(ai_input, role="general")

            prefill = {
                "title": title or (safe_request.title if safe_request else "Service Proposal"),
                "estimated_timeline": estimated_timeline or (safe_request.timeline if safe_request else ""),
                "proposal_text": generated_text,
                "scope_of_work": scope_of_work or (safe_request.message if safe_request else ""),
                "labor_cost": labor_cost,
                "materials_cost": materials_cost,
                "other_cost": other_cost,
            }

            return render_template(
                "partners/proposal_builder.html",
                partner=partner,
                linked_request=safe_request,
                prefill=prefill,
                portal="partner",
                portal_name="Partner OS",
                portal_home=url_for("partners.dashboard"),
            )

        if not title:
            flash("Proposal title is required.", "danger")

            prefill = {
                "title": title,
                "estimated_timeline": estimated_timeline,
                "proposal_text": proposal_text,
                "scope_of_work": scope_of_work,
                "labor_cost": labor_cost,
                "materials_cost": materials_cost,
                "other_cost": other_cost,
            }

            return render_template(
                "partners/proposal_builder.html",
                partner=partner,
                linked_request=safe_request,
                prefill=prefill,
                portal="partner",
                portal_name="Partner OS",
                portal_home=url_for("partners.dashboard"),
            )

        proposal = PartnerProposal(
            partner_id=partner.id,
            request_id=safe_request.id if safe_request else None,
            title=title,
            proposal_text=proposal_text,
            scope_of_work=scope_of_work,
            labor_cost=labor_cost,
            materials_cost=materials_cost,
            other_cost=other_cost,
            estimated_timeline=estimated_timeline,
            status="draft",
            created_at=datetime.utcnow()
        )

        proposal.calculate_total()

        db.session.add(proposal)
        db.session.commit()

        flash("Proposal saved as draft.", "success")
        return redirect(url_for("partners.proposal_detail", proposal_id=proposal.id))

    return render_template(
        "partners/proposal_builder.html",
        partner=partner,
        linked_request=linked_request,
        prefill=prefill,
        portal="partner",
        portal_name="Partner OS",
        portal_home=url_for("partners.dashboard"),
    )
