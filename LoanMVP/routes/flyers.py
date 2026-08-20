# LoanMVP/routes/flyers.py
"""Native, brand-driven flyer generation -- no Canva account, no OAuth,
no human-built Canva Brand Template required. See
LoanMVP.services.flyer_pdf for the actual PDF drawing and why this
exists instead of leaning on Canva's Autofill API for this.

Auto-registered by LoanMVP/app.py blueprint scanner.
"""
from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from LoanMVP.models.elena_models import ElenaListing
from LoanMVP.routes.public_pages import _parse_listing_photos
from LoanMVP.routes.vip import get_or_create_vip_profile
from LoanMVP.services.flyer_pdf import build_business_flyer_pdf, build_listing_flyer_pdf

flyers_bp = Blueprint("flyers", __name__, url_prefix="/flyers")


def _contact_info():
    partner = getattr(current_user, "partner_profile", None)
    email = (getattr(partner, "email", None) or current_user.email or "").strip() or None
    phone = (getattr(partner, "phone", None) or "").strip() or None
    return email, phone


def _owned_listing_or_none(profile, listing_id):
    if not listing_id:
        return None
    return ElenaListing.query.filter_by(id=listing_id, vip_profile_id=profile.id).first()


@flyers_bp.get("/create")
@login_required
def create():
    profile = get_or_create_vip_profile()
    if not profile:
        flash("Set up your VIP profile first.", "warning")
        return redirect(url_for("vip.onboarding"))

    listing_id = request.args.get("listing_id", type=int)
    listing = _owned_listing_or_none(profile, listing_id)
    if listing_id and not listing:
        flash("That listing wasn't found.", "warning")

    brand_ready = bool(profile.logo_url or profile.brand_color)

    return render_template(
        "flyers/create.html",
        profile=profile,
        listing=listing,
        photos=_parse_listing_photos(listing) if listing else [],
        brand_ready=brand_ready,
    )


@flyers_bp.get("/download")
@login_required
def download():
    profile = get_or_create_vip_profile()
    if not profile:
        flash("Set up your VIP profile first.", "warning")
        return redirect(url_for("vip.onboarding"))

    listing_id = request.args.get("listing_id", type=int)
    listing = _owned_listing_or_none(profile, listing_id)
    contact_email, contact_phone = _contact_info()

    try:
        if listing:
            photos = _parse_listing_photos(listing)
            buffer = build_listing_flyer_pdf(profile, listing, photos, contact_email, contact_phone)
            slug_bit = listing.address or f"listing-{listing.id}"
        else:
            buffer = build_business_flyer_pdf(profile, contact_email, contact_phone)
            slug_bit = profile.business_name or profile.display_name or "flyer"
    except Exception as exc:
        current_app.logger.error("[flyers] generation failed: %s", exc)
        flash("Could not generate your flyer. Please try again.", "danger")
        return redirect(url_for("flyers.create", listing_id=listing_id) if listing_id else url_for("flyers.create"))

    safe_slug = "".join(ch if ch.isalnum() else "-" for ch in str(slug_bit)).strip("-").lower() or "flyer"
    filename = f"ravlo-flyer-{safe_slug}-{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")
