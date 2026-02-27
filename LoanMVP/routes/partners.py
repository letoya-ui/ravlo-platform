from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from datetime import datetime
from LoanMVP.utils.decorators import role_required
from LoanMVP.extensions import db
from LoanMVP.crm import Partner
from LoanMVP.models.partner_models import PartnerRequest

@partners_bp.route("/dashboard")
@role_required("partner")
def dashboard():
    partner = Partner.query.filter_by(user_id=current_user.id).first()

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
    return render_template(template, partner=partner)

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
        flash("Partner profile not found. Please register first.", "warning")
        return redirect(url_for("partners.register"))

    requests_q = PartnerRequest.query.filter_by(partner_id=partner.id)\
        .order_by(PartnerRequest.created_at.desc()).all()

    return render_template("partners/requests_inbox.html", partner=partner, requests=requests_q)

@partners_bp.route("/requests/<int:request_id>/accept", methods=["POST"])
@role_required("partner")
def accept_request(request_id):
    partner = Partner.query.filter_by(user_id=current_user.id).first()
    pr = PartnerRequest.query.get_or_404(request_id)

    if not partner or pr.partner_id != partner.id:
        abort(403)

    if pr.status != "pending":
        flash("This request is no longer pending.", "info")
        return redirect(url_for("partners.requests_inbox"))

    pr.status = "accepted"
    pr.responded_at = datetime.utcnow()
    db.session.commit()

    flash("Request accepted. You’re now connected with the borrower.", "success")
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
