# LoanMVP/routes/flyers.py
"""Native, brand-driven flyer generation -- no Canva account, no OAuth,
no human-built Canva Brand Template required. See
LoanMVP.services.flyer_pdf for the actual PDF drawing and why this
exists instead of leaning on Canva's Autofill API for this.

Auto-registered by LoanMVP/app.py blueprint scanner.
"""
from datetime import date as _date
from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from LoanMVP.models.elena_models import ElenaListing
from LoanMVP.routes.public_pages import _parse_listing_photos
from LoanMVP.routes.vip import get_or_create_vip_profile
from LoanMVP.services.flyer_ai import FlyerRequestParseError, parse_flyer_request, resolve_event_date
from LoanMVP.services.flyer_pdf import build_business_flyer_pdf, build_listing_flyer_pdf, build_open_house_flyer_pdf

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


def _matching_listing_or_none(profile, address):
    """Best-effort match against the partner's own portfolio so an AI
    flyer request can be enriched with real price/beds/baths/photos --
    the address in a freeform request rarely matches a saved listing
    character-for-character, so this is a substring match, not exact."""
    if not address:
        return None
    return ElenaListing.query.filter(
        ElenaListing.vip_profile_id == profile.id,
        ElenaListing.address.ilike(f"%{address.strip()}%"),
    ).first()


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


@flyers_bp.post("/ai-create")
@login_required
def ai_create():
    """"Ravlo, create me an open house flyer for 123 Main St for Sat at
    12" -- parses a freeform request into flyer fields and shows a
    preview the partner can double-check (and fix) before generating,
    since a misheard address or day is worse coming from an AI than
    from a blank form."""
    profile = get_or_create_vip_profile()
    if not profile:
        flash("Set up your VIP profile first.", "warning")
        return redirect(url_for("vip.onboarding"))

    prompt_text = (request.form.get("prompt") or "").strip()
    if not prompt_text:
        flash('Tell Ravlo what you need, e.g. "open house flyer for 123 Main St, Saturday at 12".', "warning")
        return redirect(url_for("flyers.create"))

    try:
        parsed = parse_flyer_request(prompt_text)
    except FlyerRequestParseError:
        flash('Couldn\'t understand that request -- try something like "open house flyer for 123 Main St, Saturday at 12".', "danger")
        return redirect(url_for("flyers.create"))

    if parsed["flyer_type"] != "open_house" or not parsed["address"]:
        flash("Ravlo can auto-build open house flyers from a request right now -- give it an address and a day or time.", "warning")
        return redirect(url_for("flyers.create"))

    event_date = resolve_event_date(parsed["day_of_week"], parsed["explicit_date"])
    matched = _matching_listing_or_none(profile, parsed["address"])

    return render_template(
        "flyers/create.html",
        profile=profile,
        listing=matched,
        photos=_parse_listing_photos(matched) if matched else [],
        brand_ready=bool(profile.logo_url or profile.brand_color),
        open_house_preview={
            "address": parsed["address"],
            "city": matched.city if matched else (parsed["city"] or ""),
            "state": matched.state if matched else (parsed["state"] or ""),
            "zip": matched.zip_code if matched else (parsed["zip"] or ""),
            "event_date": event_date.isoformat() if event_date else "",
            "event_date_label": event_date.strftime("%A, %B %d") if event_date else "",
            "event_time": parsed["time"] or "",
            "event_time_end": parsed["time_end"] or "",
            "listing_id": matched.id if matched else "",
        },
    )


@flyers_bp.get("/download-open-house")
@login_required
def download_open_house():
    profile = get_or_create_vip_profile()
    if not profile:
        flash("Set up your VIP profile first.", "warning")
        return redirect(url_for("vip.onboarding"))

    address = (request.args.get("address") or "").strip()
    if not address:
        flash("An address is required for an open house flyer.", "warning")
        return redirect(url_for("flyers.create"))

    listing_id = request.args.get("listing_id", type=int)
    listing = _owned_listing_or_none(profile, listing_id)

    event_date = None
    event_date_str = (request.args.get("event_date") or "").strip()
    if event_date_str:
        try:
            event_date = _date.fromisoformat(event_date_str)
        except ValueError:
            event_date = None

    details = {
        "address": address,
        "city": listing.city if listing else (request.args.get("city") or None),
        "state": listing.state if listing else (request.args.get("state") or None),
        "zip": listing.zip_code if listing else (request.args.get("zip") or None),
        "price": listing.price if listing else None,
        "beds": listing.beds if listing else None,
        "baths": listing.baths if listing else None,
        "sqft": listing.sqft if listing else None,
        "description": listing.description if listing else None,
        "event_date": event_date,
        "event_time": request.args.get("event_time") or None,
        "event_time_end": request.args.get("event_time_end") or None,
    }
    photos = _parse_listing_photos(listing) if listing else []
    contact_email, contact_phone = _contact_info()

    try:
        buffer = build_open_house_flyer_pdf(profile, details, photos, contact_email, contact_phone)
    except Exception as exc:
        current_app.logger.error("[flyers] open house generation failed: %s", exc)
        flash("Could not generate your flyer. Please try again.", "danger")
        return redirect(url_for("flyers.create"))

    safe_slug = "".join(ch if ch.isalnum() else "-" for ch in address).strip("-").lower() or "open-house"
    filename = f"ravlo-open-house-{safe_slug}-{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")
