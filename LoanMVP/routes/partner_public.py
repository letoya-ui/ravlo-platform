from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required
from LoanMVP.extensions import db
from LoanMVP.models.crm_models import Partner
from LoanMVP.models.partner_models import PartnerConnectionRequest

partners_public_bp = Blueprint(
    "partners_public",
    __name__,
    url_prefix="/partners/marketplace"
)

@partners_public_bp.route("/")
def marketplace_home():
    role = request.args.get("role")
    q = Partner.query.filter_by(approved=True)

    if role:
        q = q.filter_by(role=role)

    partners = q.all()

    return render_template(
        "partners/public_market.html",
        partners=partners,
        role=role
    )

@partners_public_bp.route("/<int:partner_id>")
def public_profile(partner_id):
    partner = Partner.query.get_or_404(partner_id)

    # Show limited info only
    return render_template(
        "partners/public_profile.html",
        partner=partner,
        show_limited=True  # used by template to blur locked sections
    )

@partners_public_bp.route("/<int:partner_id>/request", methods=["GET", "POST"])
@login_required
def request_partner(partner_id):
    partner = Partner.query.get_or_404(partner_id)

    if request.method == "POST":
        message = request.form.get("message")

        req = PartnerConnectionRequest(
            partner_id=partner.id,
            borrower_profile_id=current_user.borrower_profile.id,
            message=message,
            category=partner.category
        )

        db.session.add(req)
        db.session.commit()

        flash("Your request has been sent!", "success")
        return redirect(url_for("partners_public.public_profile", partner_id=partner.id))

    return render_template(
        "partners/request_form.html",
        partner=partner
    )

@partners_public_bp.route("/<int:partner_id>/add", methods=["GET", "POST"])
@login_required
def add_partner_to_deal(partner_id):
    partner = Partner.query.get_or_404(partner_id)

    # Borrower's deals
    deals = current_user.deals

    if request.method == "POST":
        deal_id = request.form.get("deal_id")
        deal = next((d for d in deals if str(d.id) == deal_id), None)

        if not deal:
            flash("Invalid deal selected.", "danger")
            return redirect(request.url)

        deal.partners.append(partner)
        db.session.commit()

        flash("Partner added to your deal.", "success")
        return redirect(url_for("partners_public.public_profile", partner_id=partner.id))

    return render_template(
        "partners/add_to_deal.html",
        partner=partner,
        deals=deals
    )

@partners_public_bp.route("/<int:partner_id>/message")
@login_required
def message_partner(partner_id):
    partner = Partner.query.get_or_404(partner_id)

    # Redirect to your existing messaging system
    return redirect(url_for(
        "messages.thread_with_partner",
        partner_id=partner.id
    ))

