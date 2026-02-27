from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from datetime import datetime
from LoanMVP.utils.decorators import role_required
from LoanMVP.extensions import db
from LoanMVP.models.crm_models import Partner, Task, CRMNote
from LoanMVP.models.partner_models import PartnerConnectionRequest, PartnerJob

def partner_tier(partner: Partner) -> str:
    if not partner.approved:
        return "Blocked"
    if partner.subscription_tier in ("Premium", "Enterprise") and partner.is_active_listing():
        return partner.subscription_tier
    if partner.subscription_tier in ("Featured", "Pro") and partner.is_active_listing():
        return "Pro"
    return "Free"

def _require_pro(partner):
    # You can tweak this rule anytime
    if partner.subscription_tier in ("Free", None):
        return False
    return partner.is_active_listing()

def partner_has_pro_access(partner) -> bool:
    # Pro = Featured/Premium AND active paid listing AND approved
    if not partner or not partner.approved:
        return False
    if partner.subscription_tier in ("Featured", "Premium", "Enterprise") and partner.is_active_listing():
        return True
    return False

def partner_has_premium_access(partner) -> bool:
    if not partner or not partner.approved:
        return False
    if partner.subscription_tier in ("Premium", "Enterprise") and partner.is_active_listing():
        return True
    return False
    
@partners_bp.route("/dashboard")
@role_required("partner")
def dashboard():
    partner = Partner.query.filter_by(user_id=current_user.id).first()

    pending_count = 0
    if partner:
        pending_count = PartnerRequest.query.filter_by(partner_id=partner.id, status="pending").count()

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

    template = dashboards.get((partner.category or "").lower(), "partners/dashboards/default.html")
    return render_template(template, partner=partner, pending_count=pending_count)

@partners_bp.route("/")
@role_required("partner")
def center():
    role_filter = request.args.get("role")
    query = Partner.query

    if role_filter:
        query = query.filter_by(role=role_filter)

    partners = query.all()

    return render_template(
        "partners/center.html",
        partners=partners,
        role_filter=role_filter
    )

@partners_bp.route("/<int:partner_id>")
@role_required("partner")
def profile(partner_id):
    partner = Partner.query.get_or_404(partner_id)
    return render_template("partners/profile.html", partner=partner)

@partners_bp.route("/register", methods=["GET", "POST"])
@role_required("partner")
def register():
    if request.method == "POST":
        role = request.form.get("role")
        company = request.form.get("company")
        specialty = request.form.get("specialty")
        service_area = request.form.get("service_area")
        bio = request.form.get("bio")

        partner = Partner(
            user_id=current_user.id,
            role=role,
            company=company,
            specialty=specialty,
            service_area=service_area,
            bio=bio
        )
        db.session.add(partner)
        db.session.commit()

        return redirect(url_for("partners.dashboard"))

    return render_template("partners/register.html")



# ============================
# PARTNER REQUESTS INBOX
# ============================

@partners_bp.route("/requests")
@role_required("partner")
def requests_inbox():
    partner = Partner.query.filter_by(user_id=current_user.id).first()
    if not partner:
        flash("Partner profile not found. Please register.", "warning")
        return redirect(url_for("partners.register"))

    # Tier gate: Pro+ only
    if not partner_has_pro_access(partner):
        return render_template("partners/upgrade_required.html", partner=partner), 403

    requests_q = PartnerConnectionRequest.query.filter_by(partner_id=partner.id) \
        .order_by(PartnerConnectionRequest.created_at.desc()).all()

    return render_template("partners/requests_inbox.html", partner=partner, requests=requests_q)


@partners_bp.route("/requests/<int:req_id>/accept", methods=["POST"])
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

    # ✅ Tier 1: always create a Task in CRM
    t = Task(
        borrower_id=req.borrower_profile_id,  # borrower_profile.id (nullable ok)
        title=f"{req.category or partner.category or 'Service'} • New Request",
        description=req.message or "Partner request accepted.",
        assigned_to=current_user.id,
        status="Pending",
        priority="Normal"
    )
    db.session.add(t)

    # ✅ Optional: create CRM note
    if req.borrower_profile_id:
        db.session.add(CRMNote(
            borrower_id=req.borrower_profile_id,
            user_id=current_user.id,
            content=f"Accepted partner request (Partner: {partner.name})."
        ))

    # ✅ Tier 2: Premium → create PartnerJob + link task
    if partner_has_premium_access(partner):
        job = PartnerJob(
            partner_id=partner.id,
            borrower_profile_id=req.borrower_profile_id,
            property_id=req.property_id,
            title=f"{req.category or partner.category or 'Service'} Job",
            scope=req.message
        )
        db.session.add(job)
        db.session.flush()  # get job.id
        t.partner_job_id = job.id  # requires Task.partner_job_id column

    db.session.commit()

    flash("Accepted. Added to your CRM (and Workspace if Premium).", "success")
    return redirect(url_for("partners.requests_inbox"))


@partners_bp.route("/requests/<int:req_id>/decline", methods=["POST"])
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

    flash("Declined.", "info")
    return redirect(url_for("partners.requests_inbox"))


# ============================
# PREMIUM WORKSPACE
# ============================

@partners_bp.route("/workspace")
@role_required("partner")
def workspace_home():
    partner = Partner.query.filter_by(user_id=current_user.id).first()
    if not partner or not partner_has_premium_access(partner):
        return render_template("partners/upgrade_required.html", partner=partner), 403

    jobs = PartnerJob.query.filter_by(partner_id=partner.id)\
        .order_by(PartnerJob.created_at.desc()).all()

    return render_template("partners/workspace/home.html", partner=partner, jobs=jobs)


@partners_bp.route("/workspace/jobs/<int:job_id>")
@role_required("partner")
def workspace_job(job_id):
    partner = Partner.query.filter_by(user_id=current_user.id).first()
    job = PartnerJob.query.get_or_404(job_id)

    if not partner or not partner_has_premium_access(partner) or job.partner_id != partner.id:
        abort(403)

    tasks = Task.query.filter_by(partner_job_id=job.id)\
        .order_by(Task.created_at.desc()).all()

    return render_template("partners/workspace/job.html", partner=partner, job=job, tasks=tasks)
