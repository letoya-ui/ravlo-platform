# LoanMVP/routes/public_pages.py
"""Public-facing pages for VIP partners (no auth required).

Currently supports realtor landing pages with lead capture forms.
Each realtor gets a public URL at /p/<slug> that displays their
branding, active listings, and a contact form. Submitted leads
are created as ElenaClient records (pipeline_stage='new') and
trigger a VIPNotification so the realtor is alerted immediately.

White-label support: slugs listed in SLUG_TEMPLATES get their own
dedicated template for a fully branded website experience.

Custom domain support: the app.before_request hook in app.py detects
custom domains and calls the _handle_lead_capture, _build_sitemap_xml,
_render_blog_list, and _render_blog_post helpers defined here.
"""

import json
import re
from collections import OrderedDict
from datetime import datetime
from types import SimpleNamespace

from flask import Blueprint, current_app, render_template, request, abort, flash, redirect, url_for, Response
from flask_mail import Message as MailMessage
from sqlalchemy import func

from LoanMVP.extensions import db, csrf, mail
from LoanMVP.models.vip_models import VIPProfile, VIPNotification, VIPTestimonial, VIPBlogPost
from LoanMVP.models.elena_models import ElenaClient, ElenaListing
from LoanMVP.models.user_model import User
from LoanMVP.models.crm_models import Partner, Lead
from LoanMVP.models.booking_models import Booking
from LoanMVP.services.booking_service import (
    DEFAULT_SLOT_MINUTES,
    create_booking,
    generate_available_slots,
    slot_is_valid,
)

public_pages_bp = Blueprint("public_pages", __name__, url_prefix="/p")

# Slug → dedicated white-label template. All other slugs fall back to the
# generic realtor_landing.html.
SLUG_TEMPLATES: dict[str, str] = {
    "bonnie-sells-oc-homes":    "public/bonnie_landing.html",
    "john-headley":             "public/john_headen_landing.html",
    "key-signature-enterprise": "public/key_signature_landing.html",
    "mason-fultz-cleaning":     "public/mason_fultz_landing.html",
}

# Fallback context for white-label pages that don't have a VIPProfile row yet.
# The 'profile' value is a SimpleNamespace so templates can reference
# profile.public_slug for the form action without a DB record.
# User email for the real account that owns each static-context slug.
# Leads submitted through their page are created in the CRM assigned to this user.
SLUG_OWNER_EMAILS: dict[str, str] = {
    "bonnie-sells-oc-homes":    "Bonniesellsochomes@gmail.com",
    "john-headley":             "Jsecond1212@gmail.com",
    "key-signature-enterprise": "keyonahall@icloud.com",
    "mason-fultz-cleaning":     "MasonFultz45cleaningservice@gmail.com",
}

SLUG_STATIC_CONTEXT: dict[str, dict] = {
    "bonnie-sells-oc-homes": {
        "profile":          SimpleNamespace(public_slug="bonnie-sells-oc-homes", business_name="Bonnie Sells OC Homes"),
        "display_name":     "Bonnie Natt",
        "headline":         "Your Orange County & Hudson Valley Real Estate Expert",
        "bio":              (
            "With deep roots in the Hudson Valley and a passion for connecting "
            "people with the right home, Bonnie Natt brings a personal, "
            "results-driven approach to every transaction. Whether you're "
            "buying your first home, selling, or investing across Orange "
            "County and the greater Hudson Valley, she's with you every step "
            "of the way."
        ),
        "service_area":     "Orange County & Hudson Valley, NY",
        "specialties":      "Residential • Buyers & Sellers • Investment",
        "brand_color":      "#C9A878",
        "logo_url":         None,
        "profile_image_url": "/static/images/vip/bonnie_headshot.jpg",
        "cover_image_url":  None,
        "email":            "Bonniesellsochomes@gmail.com",
        "phone":            "914-213-3380",
        "website":          "",
        "listings":         [],
        "testimonials":     [],
        "user":             None,
        "partner":          None,
        "gsc_verification_code": "",
        "ga_measurement_id": "",
    },
    "john-headley": {
        "profile":          SimpleNamespace(public_slug="john-headley"),
        "display_name":     "John Headley",
        "headline":         "Realtor & Contractor — Paid at Closing",
        "bio":              "",
        "service_area":     "Connecticut & New York",
        "specialties":      "Full-service listing packages",
        "brand_color":      "#C9A86C",
        "logo_url":         None,
        "profile_image_url": None,
        "cover_image_url":  None,
        "email":            "Jsecond1212@gmail.com",
        "phone":            "+13479127503",
        "website":          "",
        "listings":         [],
        "testimonials":     [],
        "user":             None,
        "partner":          None,
        "gsc_verification_code": "",
        "ga_measurement_id": "",
    },
    "key-signature-enterprise": {
        "profile":          SimpleNamespace(public_slug="key-signature-enterprise"),
        "display_name":     "Key Signature Enterprise",
        "headline":         "One Company. Multiple Solutions.",
        "bio":              (
            "Real estate. Property management. Insurance. All under one roof. "
            "Your goals. Our priority."
        ),
        "service_area":     "Nashville and Surrounding Areas",
        "specialties":      "Real estate, property management, and insurance solutions",
        "brand_color":      "#B3122A",
        "logo_url":         "/static/images/vip/key_signature_enterprise_logo.jpg",
        "profile_image_url": None,
        "cover_image_url":  None,
        "email":            "Keyona@keysignatureenterprise.com",
        "phone":            "615-818-9438",
        "website":          "https://keysignatureenterprise.setmore.com",
        # Fallback only -- _load_context() recomputes this from her actual
        # live VIPProfile id when one exists, since a hardcoded profile id
        # goes stale the moment her account is ever recreated (the
        # VIPProfile gets a new auto-incremented id).
        "insurance_quote_url": "/vip/insurance/10/get-quote",
        "listings":         [],
        "testimonials":     [],
        "user":             None,
        "partner":          None,
        "gsc_verification_code": "",
        "ga_measurement_id": "",
    },
}


def _load_realtor_context(slug):
    """Look up a VIP profile by public_slug and build page context.

    Despite the name (this module started as realtor-only), it now also
    covers plain "contractor" profiles -- e.g. a commercial cleaning
    business -- so any VIP workspace with a public_slug gets a real,
    DB-driven public page instead of only the hardcoded
    SLUG_STATIC_CONTEXT fallback used for pre-launch accounts.
    """
    profile = VIPProfile.query.filter(
        func.lower(VIPProfile.public_slug) == slug.lower(),
        VIPProfile.role_type.in_(["realtor", "contractor", "contractor_realtor", "insurance_realtor"]),
    ).first()
    if not profile:
        return None

    user = User.query.get(profile.user_id)
    partner = Partner.query.filter_by(user_id=profile.user_id).first() if user else None

    markets = []
    raw_markets = getattr(profile, "markets_json", None) or "[]"
    try:
        markets = json.loads(raw_markets)
        if not isinstance(markets, list):
            markets = []
    except (TypeError, ValueError):
        markets = []

    listings_q = ElenaListing.query.filter_by(status="active", vip_profile_id=profile.id)
    if markets:
        listings_q = listings_q.filter(ElenaListing.market.in_(markets))
    active_listings = (
        listings_q
        .order_by(ElenaListing.created_at.desc())
        .limit(6)
        .all()
    )

    testimonials = VIPTestimonial.query.filter_by(
        vip_profile_id=profile.id,
        approved=True,
    ).order_by(VIPTestimonial.display_order.asc()).all()

    canonical_url = request.url_root.rstrip("/") + f"/p/{profile.public_slug}"

    return {
        "profile": profile,
        "user": user,
        "partner": partner,
        "listings": active_listings,
        "testimonials": testimonials,
        "display_name": profile.display_name or (user.full_name if user else "Realtor"),
        "headline": profile.headline or "Your Trusted Real Estate Partner",
        "bio": profile.bio or "",
        "service_area": profile.service_area or (partner.service_area if partner else ""),
        "specialties": profile.specialties or (partner.specialty if partner else ""),
        "brand_color": profile.brand_color or "#C9A878",
        "logo_url": profile.logo_url or (partner.logo_url if partner else None),
        "profile_image_url": profile.profile_image_url,
        "cover_image_url": profile.cover_image_url,
        "email": user.email if user else "",
        "phone": partner.phone if partner else "",
        "website": partner.website if partner else "",
        "insurance_quote_url": (
            url_for("vip.insurance_public_quote_form", profile_id=profile.id)
            if profile.role_type == "insurance_realtor" else None
        ),
        # SEO / Analytics
        "canonical_url": canonical_url,
        "gsc_verification_code": getattr(profile, "gsc_verification_code", None) or "",
        "ga_measurement_id": getattr(profile, "ga_measurement_id", None) or "",
    }


def _template_for(slug: str) -> str:
    """Return the white-label template for slug, or the generic fallback."""
    return SLUG_TEMPLATES.get(slug.lower(), "public/realtor_landing.html")


def _owner_vip_profile_id(slug: str):
    """The owning account's actual live VIPProfile id, if any -- used to
    recompute links that embed a profile id (e.g. the insurance quote
    form) instead of trusting a hardcoded value that goes stale whenever
    the account/profile is recreated."""
    owner_email = SLUG_OWNER_EMAILS.get(slug.lower())
    if not owner_email:
        return None
    owner_user = User.query.filter(func.lower(User.email) == owner_email.lower()).first()
    if not owner_user:
        return None
    profile = VIPProfile.query.filter_by(user_id=owner_user.id).first()
    return profile.id if profile else None


def _load_context(slug: str) -> dict | None:
    """Load realtor context from DB, falling back to SLUG_STATIC_CONTEXT."""
    ctx = _load_realtor_context(slug)
    if ctx is not None:
        return ctx
    static = SLUG_STATIC_CONTEXT.get(slug.lower())
    if static is not None:
        canonical_url = request.url_root.rstrip("/") + f"/p/{slug}"
        merged = {**static, "canonical_url": canonical_url}
        if "insurance_quote_url" in static:
            profile_id = _owner_vip_profile_id(slug)
            if profile_id:
                merged["insurance_quote_url"] = url_for(
                    "vip.insurance_public_quote_form", profile_id=profile_id
                )
        return merged
    return None


def _send_new_lead_email(recipient, slug: str, client_name: str, client_email: str,
                          client_phone: str, interest: str, message: str) -> None:
    """Email the partner who owns this page about a new lead. Best-effort:
    a delivery failure here must never break lead capture itself."""
    if not recipient or not recipient.email:
        return
    try:
        sender = (
            current_app.config.get("MAIL_DEFAULT_SENDER")
            or current_app.config.get("MAIL_USERNAME")
            or "letoya@ravlohq.com"
        )
        lines = [f"You have a new lead from your Ravlo landing page (/p/{slug}):", ""]
        lines.append(f"Name: {client_name}")
        if client_email:
            lines.append(f"Email: {client_email}")
        if client_phone:
            lines.append(f"Phone: {client_phone}")
        if interest:
            lines.append(f"Interest: {interest}")
        if message:
            lines.append(f"Message: {message}")
        lines.append("")
        lines.append(f"View it in your CRM: {url_for('crm.leads', _external=True)}")

        msg = MailMessage(
            subject=f"New lead: {client_name}",
            sender=sender,
            recipients=[recipient.email],
            body="\n".join(lines),
        )
        mail.send(msg)
    except Exception as exc:
        current_app.logger.warning("New lead email notification failed: %s", exc)


def _handle_lead_capture(slug: str):
    """Process lead capture form and return a rendered response.

    Extracted so it can be called both from the blueprint route and from
    the custom-domain before_request handler in app.py.
    """
    ctx = _load_context(slug)
    if ctx is None:
        abort(404)

    profile = ctx["profile"]

    client_name     = (request.form.get("client_name")     or "").strip()
    client_email    = (request.form.get("client_email")    or "").strip()
    client_phone    = (request.form.get("client_phone")    or "").strip()
    interest        = (request.form.get("interest")        or "").strip()
    message         = (request.form.get("message")        or "").strip()
    preferred_areas = (request.form.get("preferred_areas") or "").strip()
    budget          = (request.form.get("budget")          or "").strip()

    if not client_name:
        return render_template(
            _template_for(slug),
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

    markets = []
    raw_markets = getattr(profile, "markets_json", None) or "[]"
    try:
        markets = json.loads(raw_markets)
        if not isinstance(markets, list):
            markets = []
    except (TypeError, ValueError):
        markets = []
    primary_market = markets[0] if markets else None

    # Resolve the owning realtor for this page. For a live VIPProfile that's
    # the profile itself; for a static-context slug (no DB profile yet) fall
    # back to the configured owner email → their VIPProfile.
    profile_id = getattr(profile, "id", None)
    owner_email = SLUG_OWNER_EMAILS.get(slug.lower())
    owner_user = None
    if owner_email:
        owner_user = User.query.filter(func.lower(User.email) == owner_email.lower()).first()

    owner_profile_id = profile_id
    if owner_profile_id is None and owner_user is not None:
        owner_profile = VIPProfile.query.filter_by(user_id=owner_user.id).first()
        owner_profile_id = owner_profile.id if owner_profile else None

    lead = ElenaClient(
        name=client_name,
        email=client_email or None,
        phone=client_phone or None,
        role=interest or "buyer",
        pipeline_stage="new",
        notes="\n".join(notes_parts),
        preferred_areas=preferred_areas or None,
        budget=budget or None,
        market=primary_market,
        # Owned by the realtor whose page captured it. Left unassigned to a
        # specific teammate (assigned_member_id is a VIPTeamMember FK, not a
        # User id) so the realtor triages it from their pipeline.
        vip_profile_id=owner_profile_id,
        assigned_member_id=None,
    )
    db.session.add(lead)

    # For static-context slugs (no VIPProfile), route the lead to the owner's CRM.
    if owner_user is not None:
        crm_lead = Lead(
            name=client_name,
            email=client_email or None,
            phone=client_phone or None,
            message="\n".join(notes_parts),
            assigned_to=owner_user.id,
            status="New",
        )
        db.session.add(crm_lead)

    if profile_id:
        notification = VIPNotification(
            vip_profile_id=profile_id,
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

    recipient = owner_user or ctx.get("user")
    _send_new_lead_email(recipient, slug, client_name, client_email, client_phone, interest, message)

    return render_template(
        _template_for(slug),
        **ctx,
        submitted=True,
        submitted_name=client_name,
    )


def _build_sitemap_xml(profile: VIPProfile) -> Response:
    """Build sitemap XML for a realtor profile (landing page + blog posts)."""
    base = request.url_root.rstrip("/")
    page_url = f"{base}/p/{profile.public_slug}"
    today = datetime.utcnow().strftime("%Y-%m-%d")

    urls = [
        f"""  <url>
    <loc>{page_url}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>"""
    ]

    blog_posts = VIPBlogPost.query.filter_by(
        vip_profile_id=profile.id,
        is_published=True,
    ).all()
    for post in blog_posts:
        post_date = (post.published_at or post.created_at or datetime.utcnow()).strftime("%Y-%m-%d")
        urls.append(
            f"""  <url>
    <loc>{page_url}/blog/{post.slug}</loc>
    <lastmod>{post_date}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>"""
        )

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += "\n".join(urls) + "\n"
    xml += "</urlset>"

    return Response(xml, mimetype="application/xml")


def _render_blog_list(slug: str):
    """Render the blog post list page for a realtor."""
    profile = VIPProfile.query.filter(
        func.lower(VIPProfile.public_slug) == slug.lower(),
        VIPProfile.marketplace_enabled == "yes",
    ).first()
    if not profile:
        abort(404)

    posts = VIPBlogPost.query.filter_by(
        vip_profile_id=profile.id,
        is_published=True,
    ).order_by(VIPBlogPost.published_at.desc()).all()

    ctx = _load_realtor_context(slug) or {}
    return render_template("public/blog_list.html", posts=posts, **ctx)


def _render_blog_post(slug: str, post_slug: str):
    """Render an individual blog post page."""
    profile = VIPProfile.query.filter(
        func.lower(VIPProfile.public_slug) == slug.lower(),
        VIPProfile.marketplace_enabled == "yes",
    ).first()
    if not profile:
        abort(404)

    post = VIPBlogPost.query.filter_by(
        vip_profile_id=profile.id,
        slug=post_slug,
        is_published=True,
    ).first()
    if not post:
        abort(404)

    ctx = _load_realtor_context(slug) or {}
    return render_template("public/blog_post.html", post=post, **ctx)


# ── Routes ────────────────────────────────────────────────────────────────────

@public_pages_bp.route("/<slug>", methods=["GET"])
def realtor_landing(slug):
    ctx = _load_context(slug)
    if ctx is None:
        abort(404)
    return render_template(_template_for(slug), **ctx)


@public_pages_bp.route("/<slug>/contact", methods=["POST"])
def realtor_lead_capture(slug):
    return _handle_lead_capture(slug)


@public_pages_bp.route("/<slug>/sitemap.xml", methods=["GET"])
def realtor_sitemap(slug):
    profile = VIPProfile.query.filter(
        func.lower(VIPProfile.public_slug) == slug.lower(),
        VIPProfile.role_type.in_(["realtor", "contractor", "contractor_realtor", "insurance_realtor"]),
        VIPProfile.marketplace_enabled == "yes",
    ).first()
    if not profile:
        abort(404)
    return _build_sitemap_xml(profile)


@public_pages_bp.route("/<slug>/blog", methods=["GET"])
def realtor_blog_list(slug):
    return _render_blog_list(slug)


@public_pages_bp.route("/<slug>/blog/<post_slug>", methods=["GET"])
def realtor_blog_post(slug, post_slug):
    return _render_blog_post(slug, post_slug)


# ── Booking capability: public "schedule a visit" calendar ─────────────────
# Only available for slugs backed by a real, live VIPProfile row (the older
# white-label slugs that predate one -- Bonnie/John Headley/Key Signature's
# SLUG_STATIC_CONTEXT fallback -- have no owner_id to attach bookings/leads
# to, so this 404s for those until they have a real profile).

def _booking_owner_profile_id(slug: str):
    ctx = _load_context(slug)
    if ctx is None:
        return None, None
    profile_id = getattr(ctx["profile"], "id", None)
    if not profile_id:
        return ctx, None
    return ctx, profile_id


@public_pages_bp.route("/<slug>/book", methods=["GET"])
def public_booking_page(slug):
    ctx, profile_id = _booking_owner_profile_id(slug)
    if ctx is None or profile_id is None:
        abort(404)

    slots = generate_available_slots("vip_profile", profile_id)
    grouped_slots = OrderedDict()
    for slot in slots:
        day_key = slot["start"].strftime("%A, %B %d")
        grouped_slots.setdefault(day_key, []).append(slot)

    return render_template("public/booking_calendar.html", **ctx, grouped_slots=grouped_slots)


@public_pages_bp.route("/<slug>/book", methods=["POST"])
def public_booking_submit(slug):
    ctx, profile_id = _booking_owner_profile_id(slug)
    if ctx is None or profile_id is None:
        abort(404)

    def _rerender_with_error(message):
        slots = generate_available_slots("vip_profile", profile_id)
        grouped_slots = OrderedDict()
        for slot in slots:
            day_key = slot["start"].strftime("%A, %B %d")
            grouped_slots.setdefault(day_key, []).append(slot)
        return render_template(
            "public/booking_calendar.html", **ctx, grouped_slots=grouped_slots, form_error=message
        )

    client_name = (request.form.get("client_name") or "").strip()
    client_email = (request.form.get("client_email") or "").strip()
    client_phone = (request.form.get("client_phone") or "").strip()
    notes = (request.form.get("notes") or "").strip()
    starts_at_raw = (request.form.get("starts_at") or "").strip()
    duration_minutes = request.form.get("duration_minutes", type=int) or DEFAULT_SLOT_MINUTES

    if not client_name:
        return _rerender_with_error("Name is required.")

    try:
        starts_at = datetime.strptime(starts_at_raw, "%Y-%m-%dT%H:%M")
    except ValueError:
        return _rerender_with_error("Please choose a time slot.")

    if not slot_is_valid("vip_profile", profile_id, starts_at, duration_minutes):
        return _rerender_with_error("That time is no longer available. Please choose another.")

    booking = create_booking(
        "vip_profile",
        profile_id,
        starts_at,
        duration_minutes,
        client_name=client_name,
        client_email=client_email,
        client_phone=client_phone,
        notes=notes,
        title="Quote Visit",
    )

    when_text = booking.starts_at.strftime("%A, %B %d at %I:%M %p")
    owner_user = ctx.get("user")
    if owner_user:
        lead = Lead(
            name=client_name,
            email=client_email or None,
            phone=client_phone or None,
            message=f"Requested a scheduled visit for {when_text}.\n{notes}".strip(),
            assigned_to=owner_user.id,
            status="New",
        )
        db.session.add(lead)

    notification = VIPNotification(
        vip_profile_id=profile_id,
        notification_type="new_booking",
        title=f"New booking: {client_name}",
        body=f"Scheduled for {when_text}. {client_phone or client_email or ''}".strip(),
        action_url="/crm/leads",
    )
    db.session.add(notification)
    db.session.commit()

    return redirect(url_for("public_pages.public_booking_confirmed", slug=slug, token=booking.confirmation_token))


@public_pages_bp.route("/<slug>/book/confirmed/<token>", methods=["GET"])
def public_booking_confirmed(slug, token):
    ctx, profile_id = _booking_owner_profile_id(slug)
    if ctx is None or profile_id is None:
        abort(404)

    booking = Booking.query.filter_by(
        confirmation_token=token, owner_type="vip_profile", owner_id=profile_id
    ).first_or_404()

    return render_template("public/booking_confirmed.html", **ctx, booking=booking)
