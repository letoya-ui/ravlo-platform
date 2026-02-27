from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from datetime import datetime
from LoanMVP.utils.decorators import role_required
from LoanMVP.extensions import db
from LoanMVP.crm import Partner
from LoanMVP.models.partner_models import PartnerRequest, PartnerConnectionRequest

def partner_tier(partner: Partner) -> str:
    if not partner.approved:
        return "Blocked"
    if partner.subscription_tier in ("Premium", "Enterprise") and partner.is_active_listing():
        return partner.subscription_tier
    if partner.subscription_tier in ("Featured", "Pro") and partner.is_active_listing():
        return "Pro"
    return "Free"
    
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

    template = dashboards.get(partner.role, "partners/dashboards/default.html")
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
@login_required
def profile(partner_id):
    partner = Partner.query.get_or_404(partner_id)
    return render_template("partners/profile.html", partner=partner)

@partners_bp.route("/register", methods=["GET", "POST"])
@login_required
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

@partners_bp.route("/requests")
@role_required("partner")
def requests_inbox():
    partner = Partner.query.filter_by(user_id=current_user.id).first()
    if not partner:
        return redirect(url_for("partners.register"))

    # Gate: only Pro+ can see inbox (or allow Free too; your call)
    if partner.subscription_tier == "Free":
        return render_template("partners/upgrade_required.html", partner=partner), 403

    requests_q = PartnerRequest.query.filter_by(partner_id=partner.id)\
        .order_by(PartnerRequest.created_at.desc()).all()

    return render_template("partners/requests_inbox.html", partner=partner, requests=requests_q)

@partners_bp.route("/requests/<int:req_id>/accept", methods=["POST"])
@role_required("partner")
def accept_request(req_id):
    partner = Partner.query.filter_by(user_id=current_user.id).first()
    req = PartnerRequest.query.get_or_404(req_id)

    if not partner or req.partner_id != partner.id:
        abort(403)

    req.status = "accepted"
    req.responded_at = datetime.utcnow()

    # ✅ Auto-create a Task assigned to the partner user (simple CRM)
    t = Task(
        borrower_id=req.borrower_profile_id,   # your Task expects borrower_profile.id
        title=f"Partner Request: {req.category or partner.category or 'Service'}",
        description=(req.message or "New partner request accepted."),
        assigned_to=current_user.id,
        status="Pending"
    )
    db.session.add(t)
    db.session.commit()

    flash("Accepted. Task created in your Partner CRM.", "success")
    return redirect(url_for("partners.requests_inbox"))
    
@partners_bp.route("/requests/<int:request_id>/decline", methods=["POST"])
@role_required("partner")
def decline_request(request_id):
    partner = Partner.query.filter_by(user_id=current_user.id).first()
    pr = PartnerRequest.query.get_or_404(request_id)

    if not partner or pr.partner_id != partner.id:
        abort(403)

    if pr.status != "pending":
        flash("This request is no longer pending.", "info")
        return redirect(url_for("partners.requests_inbox"))

    pr.status = "declined"
    pr.responded_at = datetime.utcnow()
    db.session.commit()

    flash("Request declined.", "info")
    return redirect(url_for("partners.requests_inbox"))


@partners_bp.route("/requests")
@role_required("partner")
def partner_requests():
    partner = Partner.query.filter_by(user_id=current_user.id).first()
    if not partner:
        flash("Partner profile not found. Please register first.", "warning")
        return redirect(url_for("partners.register"))

    requests_q = PartnerConnectionRequest.query.filter_by(partner_id=partner.id)\
        .order_by(PartnerConnectionRequest.created_at.desc()).all()

    return render_template("partners/requests_inbox.html", partner=partner, requests=requests_q)

@partners_bp.route("/requests/<int:req_id>/accept", methods=["POST"])
@role_required("partner")
def accept_partner_request(req_id):
    partner = Partner.query.filter_by(user_id=current_user.id).first()
    req = PartnerConnectionRequest.query.get_or_404(req_id)

    if not partner or req.partner_id != partner.id:
        abort(403)

    if req.status != "pending":
        flash("This request is no longer pending.", "info")
        return redirect(url_for("partners.partner_requests"))

    req.status = "accepted"
    req.responded_at = datetime.utcnow()
    db.session.commit()

    flash("Request accepted. You’re now connected with this borrower.", "success")
    return redirect(url_for("partners.partner_requests"))

@partners_bp.route("/requests/<int:req_id>/decline", methods=["POST"])
@role_required("partner")
def decline_partner_request(req_id):
    partner = Partner.query.filter_by(user_id=current_user.id).first()
    req = PartnerConnectionRequest.query.get_or_404(req_id)

    if not partner or req.partner_id != partner.id:
        abort(403)

    if req.status != "pending":
        flash("This request is no longer pending.", "info")
        return redirect(url_for("partners.partner_requests"))

    req.status = "declined"
    req.responded_at = datetime.utcnow()
    db.session.commit()

    flash("Request declined.", "info")
    return redirect(url_for("partners.partner_requests"))
