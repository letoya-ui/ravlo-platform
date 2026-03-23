from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import current_user
from datetime import datetime
from pathlib import Path
from werkzeug.utils import secure_filename
from sqlalchemy import desc

from LoanMVP.extensions import db, csrf
from LoanMVP.utils.decorators import role_required
from LoanMVP.ai.base_ai import AIAssistant

from LoanMVP.services.partner_search_service import search_external_partners

from LoanMVP.models.crm_models import Partner, Task, CRMNote, Lead
from LoanMVP.models.partner_models import (
    PartnerConnectionRequest,
    PartnerJob,
    PartnerPhoto,
    PartnerProposal,
)

partners_bp = Blueprint("partners", __name__, url_prefix="/partners")


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

# ------------------------------------------------
# DASHBOARD
# ------------------------------------------------


@partners_bp.route("/dashboard")
@role_required("partner", "admin")
def dashboard():
    partner = Partner.query.filter_by(user_id=current_user.id).first()

    if not partner:
        flash("Partner profile not found. Please register.", "warning")
        return redirect(url_for("partners.register"))

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
            "enabled": getattr(partner, "crm_enabled", True),
            "cta": "Open CRM",
            "endpoint": "partners.crm",
            "badge": "Core",
        },
        {
            "key": "deal_visibility",
            "title": "Deal Visibility",
            "description": "See project, deal, and property context tied to requests.",
            "enabled": getattr(partner, "deal_visibility_enabled", False),
            "cta": "View Opportunities",
            "endpoint": "partners.requests",
            "badge": "Growth Tool",
        },
        {
            "key": "proposal_builder",
            "title": "Proposal Builder",
            "description": "Create scopes, service proposals, and branded responses.",
            "enabled": getattr(partner, "proposal_builder_enabled", False),
            "cta": "Build Proposal",
            "endpoint": "partners.proposals",
            "badge": "Premium",
        },
        {
            "key": "instant_quote",
            "title": "Instant Quote",
            "description": "Generate pricing quickly for incoming work opportunities.",
            "enabled": getattr(partner, "instant_quote_enabled", False),
            "cta": "Create Quote",
            "endpoint": "partners.quotes",
            "badge": "Premium",
        },
        {
            "key": "ai_assist",
            "title": "AI Assist",
            "description": "Use AI to help draft responses, estimates, and timelines.",
            "enabled": getattr(partner, "ai_assist_enabled", False),
            "cta": "Open AI",
            "endpoint": "partners.ai",
            "badge": "Premium",
        },
        {
            "key": "priority_placement",
            "title": "Priority Placement",
            "description": "Appear higher in Ravlo search and partner recommendations.",
            "enabled": getattr(partner, "priority_placement_enabled", False),
            "cta": "Boost Visibility",
            "endpoint": "partners.upgrade",
            "badge": "Visibility",
        },
        {
            "key": "smart_notifications",
            "title": "Smart Notifications",
            "description": "Get alerts when new requests match your service area.",
            "enabled": getattr(partner, "smart_notifications_enabled", False),
            "cta": "Manage Alerts",
            "endpoint": "partners.notifications",
            "badge": "Automation",
        },
        {
            "key": "portfolio_showcase",
            "title": "Portfolio Showcase",
            "description": "Display photos and project work to help investors trust faster.",
            "enabled": getattr(partner, "portfolio_showcase_enabled", False),
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

    dashboards = {
        "contractor": "partners/dashboards/contractor.html",
        "designer": "partners/dashboards/designer.html",
        "cleaner": "partners/dashboards/cleaner.html",
        "janitorial": "partners/dashboards/cleaner.html",
        "realtor": "partners/dashboards/realtor.html",
        "inspector": "partners/dashboards/inspector.html",
        "appraiser": "partners/dashboards/appraiser.html",
        "title": "partners/dashboards/title.html",
        "insurance": "partners/dashboards/insurance.html",
        "attorney": "partners/dashboards/attorney.html",
        "property_manager": "partners/dashboards/property_manager.html",
        "lender": "partners/dashboards/lender.html",
        "broker": "partners/dashboards/broker.html",
        "vendor": "partners/dashboards/vendor.html",
    }

    template = dashboards.get(
        (partner.category or "").strip().lower(),
        "partners/dashboards/default.html"
    )

    return render_template(
        template,
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
        portal="partner",
        portal_name="Partner OS",
        portal_home=url_for("partners.dashboard")
    )
# ------------------------------------------------
# PARTNER DIRECTORY (internal)
# ------------------------------------------------

@partners_bp.route("/center")
@role_required("partner")
def center():

    category = request.args.get("category")

    query = Partner.query

    if category:
        query = query.filter_by(category=category)

    partners = query.all()

    return render_template(
        "partners/center.html",
        partners=partners,
        category=category,
        portal="partner",
        portal_name="Partner OS",
        portal_home=url_for("partners.dashboard"),
    )


# ------------------------------------------------
# PARTNER PROFILE
# ------------------------------------------------

@partners_bp.route("/<int:partner_id>")
@role_required("partner")
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
@role_required("partner")
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
@role_required("partner")
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
@role_required("partner", "admin")
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
@role_required("partner")
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
@role_required("partner")
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
@role_required("partner")
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
        return redirect(url_for("partner.request_detail", request_id=req.id))

    req.status = new_status
    req.responded_at = datetime.utcnow()

    db.session.commit()

    flash("Request status updated.", "success")
    return redirect(url_for("partner.request_detail", request_id=req.id))

# ------------------------------------------------
# PREMIUM WORKSPACE
# ------------------------------------------------

@partners_bp.route("/workspace")
@role_required("partner")
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
@role_required("partner")
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
@role_required("partner")
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
@role_required("partner")
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
        partner.featured = "featured" in request.form
        partner.subscription_tier = request.form.get("subscription_tier")

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
@role_required("partner")
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
@role_required("partner")
def leads():
    partner = current_user.partner_profile

    if not partner:
        flash("Please complete your partner profile first.", "warning")
        return redirect(url_for("partners.profile_setup"))

    # Leads linked through your partner_lead_link table
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
@role_required("partner")
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
@role_required("partner")
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
@role_required("partner")
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
@role_required("partner")
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
@role_required("partner")
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
@role_required("partner")
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

    # placeholder subscription logic for testing
    partner.subscription_tier = normalized
    partner.approved = True
    partner.active = True
    partner.status = "Active"

    if normalized in {"Featured", "Premium", "Enterprise"}:
        partner.featured = True
    else:
        partner.featured = False

    db.session.commit()

    flash(f"Your subscription has been updated to {normalized}.", "success")
    return redirect(url_for("partners.billing"))

@partners_bp.route("/billing")
@role_required("partner")
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
            "features": ["Featured listing", "More visibility", "Pro request access"]
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
    
@partners_bp.route("/profile/edit", methods=["GET", "POST"])
@csrf.exempt
@role_required("partner")
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

        # usually these should not be partner-controlled unless you want them to be
        # partner.relationship_level = ...
        # partner.subscription_tier = ...
        # partner.approved = ...
        # partner.featured = ...
        # partner.is_verified = ...

        if not partner.id:
            db.session.add(partner)

        db.session.commit()
        flash("Your partner profile was updated successfully.", "success")
        return redirect(url_for("partners.profile"))

    return render_template("partners/partner_form.html", partner=partner)

@partners_bp.route("/upgrade")
@role_required("partner", "admin")
def upgrade():
    partner = Partner.query.filter_by(user_id=current_user.id).first()

    if not partner:
        flash("Partner profile not found. Please register.", "warning")
        return redirect(url_for("partners.register"))

    locked_feature_count = 0
    feature_flags = [
        getattr(partner, "crm_enabled", True),
        getattr(partner, "deal_visibility_enabled", False),
        getattr(partner, "proposal_builder_enabled", False),
        getattr(partner, "instant_quote_enabled", False),
        getattr(partner, "ai_assist_enabled", False),
        getattr(partner, "priority_placement_enabled", False),
        getattr(partner, "smart_notifications_enabled", False),
        getattr(partner, "portfolio_showcase_enabled", False),
    ]
    locked_feature_count = sum(1 for item in feature_flags if not item)

    return render_template(
        "partners/upgrade.html",
        partner=partner,
        locked_feature_count=locked_feature_count,
        portal="partner",
        portal_name="Partner OS",
        portal_home=url_for("partners.dashboard"),
    )

@partners_bp.route("/proposals")
@role_required("partner", "admin")
def proposals():
    partner = Partner.query.filter_by(user_id=current_user.id).first()

    if not partner:
        flash("Partner profile not found. Please register.", "warning")
        return redirect(url_for("partners.register"))

    if not getattr(partner, "proposal_builder_enabled", False):
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

from datetime import datetime
from flask import render_template, redirect, url_for, flash, request
from flask_login import current_user

from LoanMVP.extensions import db
from LoanMVP.models.partner_models import Partner, PartnerProposal, PartnerConnectionRequest
from LoanMVP.utils.decorators import role_required


@partners_bp.route("/proposals/<int:proposal_id>", methods=["GET", "POST"])
@role_required("partner", "admin")
def proposal_detail(proposal_id):
    partner = Partner.query.filter_by(user_id=current_user.id).first()

    if not partner:
        flash("Partner profile not found. Please register.", "warning")
        return redirect(url_for("partners.register"))

    if not getattr(partner, "proposal_builder_enabled", False):
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
@role_required("partner", "admin")
def create_proposal():

    # --------------------------------------------------
    # Load partner
    # --------------------------------------------------
    partner = Partner.query.filter_by(user_id=current_user.id).first()

    if not partner:
        flash("Partner profile not found. Please register.", "warning")
        return redirect(url_for("partners.register"))

    # --------------------------------------------------
    # Feature gate
    # --------------------------------------------------
    if not getattr(partner, "proposal_builder_enabled", False):
        flash("Proposal Builder is available on an upgraded plan.", "warning")
        return redirect(url_for("partners.upgrade"))

    # --------------------------------------------------
    # Load request (if passed)
    # --------------------------------------------------
    request_id = request.args.get("request_id", type=int)
    linked_request = None

    if request_id:
        linked_request = PartnerConnectionRequest.query.filter_by(
            id=request_id,
            partner_id=partner.id
        ).first()

    # --------------------------------------------------
    # Prefill defaults
    # --------------------------------------------------
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

    # --------------------------------------------------
    # Handle POST
    # --------------------------------------------------
    if request.method == "POST":

        action = (request.form.get("action") or "save").strip().lower()
        form_request_id = request.form.get("request_id", type=int)

        # Load request again safely
        safe_request = None
        if form_request_id:
            safe_request = PartnerConnectionRequest.query.filter_by(
                id=form_request_id,
                partner_id=partner.id
            ).first()

        # --------------------------------------------------
        # Form data
        # --------------------------------------------------
        title = (request.form.get("title") or "").strip()
        proposal_text = (request.form.get("proposal_text") or "").strip()
        scope_of_work = (request.form.get("scope_of_work") or "").strip()
        estimated_timeline = (request.form.get("estimated_timeline") or "").strip()

        labor_cost = request.form.get("labor_cost", type=float) or 0.0
        materials_cost = request.form.get("materials_cost", type=float) or 0.0
        other_cost = request.form.get("other_cost", type=float) or 0.0

        # --------------------------------------------------
        # 🔥 AI GENERATION
        # --------------------------------------------------
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

        # --------------------------------------------------
        # Validate
        # --------------------------------------------------
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

        # --------------------------------------------------
        # Save proposal
        # --------------------------------------------------
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

    # --------------------------------------------------
    # GET request
    # --------------------------------------------------
    return render_template(
        "partners/proposal_builder.html",
        partner=partner,
        linked_request=linked_request,
        prefill=prefill,
        portal="partner",
        portal_name="Partner OS",
        portal_home=url_for("partners.dashboard"),
    )