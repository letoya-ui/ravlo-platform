from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import current_user
from datetime import datetime
from pathlib import Path
from werkzeug.utils import secure_filename

from LoanMVP.extensions import db, csrf
from LoanMVP.utils.decorators import role_required

from LoanMVP.models.crm_models import Partner, Task, CRMNote
from LoanMVP.models.partner_models import (
    PartnerConnectionRequest,
    PartnerJob,
    PartnerPhoto
)

partners_bp = Blueprint("partners", __name__, url_prefix="/partners")


# ------------------------------------------------
# ACCESS TIERS
# ------------------------------------------------
def partner_has_pro_access(partner) -> bool:
    if current_app.config.get("FREE_PARTNER_MODE", False):
        return bool(partner)

    if not partner or not partner.approved:
        return False

    return partner.subscription_tier in ("Featured", "Premium", "Enterprise") and partner.is_active_listing()


def partner_has_premium_access(partner) -> bool:
    if current_app.config.get("FREE_PARTNER_MODE", False):
        return bool(partner)

    if not partner or not partner.approved:
        return False

    return partner.subscription_tier in ("Premium", "Enterprise") and partner.is_active_listing()


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

    pending_count = PartnerConnectionRequest.query.filter_by(
        partner_id=partner.id,
        status="pending"
    ).count()

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
    }

    template = dashboards.get(
        (partner.category or "").lower(),
        "partners/dashboards/default.html"
    )

    return render_template(
        template,
        partner=partner,
        pending_count=pending_count,
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
        category=category
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
        partner=partner
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
        portal_home=url_for("partners.dashboard")
    )

# ------------------------------------------------
# PARTNER REQUEST INBOX
# ------------------------------------------------

@partners_bp.route("/requests")
@role_required("partner")
def requests_inbox():

    partner = Partner.query.filter_by(user_id=current_user.id).first()

    if not partner:
        flash("Partner profile not found.", "warning")
        return redirect(url_for("partners.register"))

    if not partner_has_pro_access(partner):
        return render_template(
            "partners/upgrade_required.html",
            partner=partner
        ), 403

    requests_q = PartnerConnectionRequest.query.filter_by(
        partner_id=partner.id
    ).order_by(
        PartnerConnectionRequest.created_at.desc()
    ).all()

    return render_template(
        "partners/requests_inbox.html",
        partner=partner,
        requests=requests_q
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
        jobs=jobs
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
        tasks=tasks
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
        portal="partner"
    )

@partners_bp.route("/billing")
@role_required("partner")
def billing():
    partner = Partner.query.filter_by(user_id=current_user.id).first()
    if not partner:
        flash("Partner profile not found.", "warning")
        return redirect(url_for("partners.register"))

    return render_template(
        "partners/billing.html",
        partner=partner,
        portal="partner"
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
        portal="partner"
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
        portal="partner"
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
