from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user
from datetime import datetime
from pathlib import Path
from werkzeug.utils import secure_filename

from LoanMVP.extensions import db
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
    if not partner or not partner.approved:
        return False
    return partner.subscription_tier in ("Featured", "Premium", "Enterprise") and partner.is_active_listing()


def partner_has_premium_access(partner) -> bool:
    if not partner or not partner.approved:
        return False
    return partner.subscription_tier in ("Premium", "Enterprise") and partner.is_active_listing()


# ------------------------------------------------
# DASHBOARD
# ------------------------------------------------

@partners_bp.route("/dashboard")
@role_required("partner")
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

@partners_bp.route("/")
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
        category = request.form.get("category") or request.form.get("role")
        company = request.form.get("company")
        specialty = request.form.get("specialty")
        service_area = request.form.get("service_area")
        bio = request.form.get("bio")

        if partner:
            partner.category = category
            partner.company = company
            partner.specialty = specialty
            partner.service_area = service_area
            partner.bio = bio
        else:
            partner = Partner(
                user_id=current_user.id,
                category=category,
                company=company,
                specialty=specialty,
                service_area=service_area,
                bio=bio
            )
            db.session.add(partner)

        db.session.commit()
        return redirect(url_for("partners.dashboard"))

    return render_template("partners/register.html", partner=partner)

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

    # Create CRM Task
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
            content=f"Accepted partner request (Partner: {partner.company})."
        ))

    if partner_has_premium_access(partner):

        job = PartnerJob(
            partner_id=partner.id,
            borrower_profile_id=req.borrower_profile_id,
            property_id=req.property_id,
            title=f"{req.category or partner.category} Job",
            scope=req.message
        )

        db.session.add(job)
        db.session.flush()

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