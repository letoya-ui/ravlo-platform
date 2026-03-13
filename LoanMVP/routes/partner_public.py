from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
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
    category = request.args.get("category")
    q = Partner.query.filter_by(approved=True)

    if category:
        q = q.filter_by(category=category)

    partners = q.all()

    return render_template(
        "partners/public_market.html",
        partners=partners,
        category=category
    )


@partners_public_bp.route("/<int:partner_id>")
def public_profile(partner_id):
    partner = Partner.query.filter_by(id=partner_id, approved=True).first_or_404()

    return render_template(
        "partners/public_profile.html",
        partner=partner,
        show_limited=True
    )


@partners_public_bp.route("/<int:partner_id>/request", methods=["GET", "POST"])
@login_required
def request_partner(partner_id):
    partner = Partner.query.filter_by(id=partner_id, approved=True).first_or_404()

    borrower_profile = getattr(current_user, "borrower_profile", None)
    if not borrower_profile:
        flash("You need a borrower profile before sending a request.", "warning")
        return redirect(url_for("borrower.dashboard"))

    if request.method == "POST":
        message = request.form.get("message", "").strip()

        req = PartnerConnectionRequest(
            partner_id=partner.id,
            borrower_profile_id=borrower_profile.id,
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
    partner = Partner.query.filter_by(id=partner_id, approved=True).first_or_404()

    deals = getattr(current_user, "deals", None)
    if deals is None:
        flash("No deals available for this account.", "warning")
        return redirect(url_for("partners_public.public_profile", partner_id=partner.id))

    if request.method == "POST":
        deal_id = request.form.get("deal_id")
        deal = next((d for d in deals if str(d.id) == str(deal_id)), None)

        if not deal:
            flash("Invalid deal selected.", "danger")
            return redirect(request.url)

        if partner not in deal.partners:
            deal.partners.append(partner)
            db.session.commit()
            flash("Partner added to your deal.", "success")
        else:
            flash("This partner is already attached to that deal.", "info")

        return redirect(url_for("partners_public.public_profile", partner_id=partner.id))

    return render_template(
        "partners/add_to_deal.html",
        partner=partner,
        deals=deals
    )


@partners_public_bp.route("/<int:partner_id>/message")
@login_required
def message_partner(partner_id):
    partner = Partner.query.filter_by(id=partner_id, approved=True).first_or_404()

    return redirect(url_for(
        "messages.thread_with_partner",
        partner_id=partner.id
    ))