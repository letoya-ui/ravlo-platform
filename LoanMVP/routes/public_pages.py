# LoanMVP/routes/public_pages.py
"""Public-facing pages for VIP partners (no auth required).

Currently supports realtor landing pages with lead capture forms.
Each realtor gets a public URL at /p/<slug> that displays their
branding, active listings, and a contact form. Submitted leads
are created as ElenaClient records (pipeline_stage='new') and
trigger a VIPNotification so the realtor is alerted immediately.
"""

from datetime import datetime

from flask import Blueprint, render_template, request, abort, flash, redirect, url_for
from sqlalchemy import func

from LoanMVP.extensions import db, csrf
from LoanMVP.models.vip_models import VIPProfile, VIPNotification
from LoanMVP.models.elena_models import ElenaClient, ElenaListing
from LoanMVP.models.user_model import User
from LoanMVP.models.crm_models import Partner

public_pages_bp = Blueprint("public_pages", __name__, url_prefix="/p")


def _load_realtor_context(slug):
    """Look up a VIP realtor profile by public_slug and build page context."""
    profile = VIPProfile.query.filter(
        func.lower(VIPProfile.public_slug) == slug.lower(),
        VIPProfile.role_type.in_(["realtor", "contractor_realtor", "insurance_realtor"]),
    ).first()
    if not profile:
        return None

    user = User.query.get(profile.user_id)
    partner = Partner.query.filter_by(user_id=profile.user_id).first() if user else None

    active_listings = (
        ElenaListing.query
        .filter_by(status="active")
        .order_by(ElenaListing.created_at.desc())
        .limit(6)
        .all()
    )

    return {
        "profile": profile,
        "user": user,
        "partner": partner,
        "listings": active_listings,
        "display_name": profile.display_name or (user.full_name if user else "Realtor"),
        "headline": profile.headline or "Your Trusted Real Estate Partner",
        "bio": profile.bio or "",
        "service_area": profile.service_area or (partner.service_area if partner else ""),
        "specialties": profile.specialties or (partner.specialty if partner else ""),
        "brand_color": profile.brand_color or "#6366f1",
        "logo_url": profile.logo_url or (partner.logo_url if partner else None),
        "profile_image_url": profile.profile_image_url,
        "cover_image_url": profile.cover_image_url,
        "email": user.email if user else "",
        "phone": partner.phone if partner else "",
        "website": partner.website if partner else "",
    }


@public_pages_bp.route("/<slug>", methods=["GET"])
def realtor_landing(slug):
    ctx = _load_realtor_context(slug)
    if ctx is None:
        abort(404)

    return render_template("public/realtor_landing.html", **ctx)


@public_pages_bp.route("/<slug>/contact", methods=["POST"])
@csrf.exempt
def realtor_lead_capture(slug):
    ctx = _load_realtor_context(slug)
    if ctx is None:
        abort(404)

    profile = ctx["profile"]

    client_name = (request.form.get("client_name") or "").strip()
    client_email = (request.form.get("client_email") or "").strip()
    client_phone = (request.form.get("client_phone") or "").strip()
    interest = (request.form.get("interest") or "").strip()
    message = (request.form.get("message") or "").strip()
    preferred_areas = (request.form.get("preferred_areas") or "").strip()
    budget = (request.form.get("budget") or "").strip()

    if not client_name:
        return render_template(
            "public/realtor_landing.html",
            **ctx,
            form_error="Name is required.",
            submitted=False,
        )

    notes_parts = []
    if interest:
        notes_parts.append(f"Interest: {interest}")
    if message:
        notes_parts.append(f"Message: {message}")
    notes_parts.append(f"Source: Public landing page (/p/{slug})")

    lead = ElenaClient(
        name=client_name,
        email=client_email or None,
        phone=client_phone or None,
        role=interest or "buyer",
        pipeline_stage="new",
        notes="\n".join(notes_parts),
        preferred_areas=preferred_areas or None,
        budget=budget or None,
    )
    db.session.add(lead)

    notification = VIPNotification(
        vip_profile_id=profile.id,
        notification_type="new_lead",
        title=f"New lead: {client_name}",
        body=(
            f"{interest or 'Prospect'} via your public page."
            f" {client_phone or client_email or ''}"
        ),
        action_url="/elena/clients",
    )
    db.session.add(notification)
    db.session.commit()

    return render_template(
        "public/realtor_landing.html",
        **ctx,
        submitted=True,
        submitted_name=client_name,
    )
