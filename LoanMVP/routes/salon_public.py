# LoanMVP/routes/salon_public.py
"""Public landing page + booking calendar for the Salon/Stylist vertical
(GotStyles Beauty and any other salon licensing Ravlo's white-label
platform).

Mirrors two existing patterns in this codebase rather than inventing new
ones:
  - public_pages.py's bespoke realtor landing pages (one hand-built
    template per business, looked up by a slug) -- here looked up by
    StylistProfile.public_slug instead of VIPProfile.public_slug.
  - scheduling.py's in-house demo-booking Calendly: a recurring weekly
    SalonAvailability template, slots computed on the fly (no
    pre-generated per-slot rows), and an unguessable confirmation_token
    for the public confirmation page instead of the sequential id. The
    difference here is bookings land in the real SalonClient/Appointment
    models instead of a parallel one-off table, and everything is scoped
    per-stylist instead of per-Ravlo-staff-host.

Like scheduling.py, times are stored/displayed as naive, stylist-local
datetimes with no per-visitor timezone conversion -- appropriate (more so
than for the Ravlo demo page) since a salon client physically visits the
shop in the stylist's own timezone.
"""
from collections import OrderedDict
from datetime import datetime, timedelta, time as dtime

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_mail import Message as MailMessage

from LoanMVP.app import mail
from LoanMVP.extensions import db, limiter
from LoanMVP.models.salon_models import (
    StylistProfile,
    SalonClient,
    Appointment,
    SalonAvailability,
    SalonReview,
    _new_confirmation_token,
)

salon_public_bp = Blueprint("salon_public", __name__, url_prefix="/salon")

BOOKING_WINDOW_DAYS = 21
DEFAULT_SLOT_MINUTES = 60

# General service categories shown on the landing page and offered in the
# booking form. Deliberately no invented prices here -- unlike Key
# Signature's landing page (an existing, already-priced business), we
# don't have GotStyles' actual service menu/pricing yet, so the public
# form collects free-text "what are you looking for" instead of a priced
# menu. Aisha can attach real pricing when she manages the appointment
# from her own dashboard.
SERVICE_CATEGORIES = [
    {"name": "Cuts & Styling", "description": "Precision cuts, shape-ups, and finished styles."},
    {"name": "Color & Balayage", "description": "Custom color, highlights, and balayage."},
    {"name": "Silk Press & Blowouts", "description": "Sleek, smooth, salon-fresh results."},
    {"name": "Extensions & Install", "description": "Sew-ins, quick weaves, and extension maintenance."},
    {"name": "Treatments", "description": "Deep conditioning and scalp treatments."},
]


def _stylist_or_404(slug):
    return StylistProfile.query.filter(
        db.func.lower(StylistProfile.public_slug) == (slug or "").strip().lower()
    ).first_or_404()


def _generate_available_slots(stylist, days_ahead: int = BOOKING_WINDOW_DAYS):
    templates = SalonAvailability.query.filter_by(stylist_id=stylist.id, is_active=True).all()
    if not templates:
        return []

    now_naive = datetime.utcnow()
    today = now_naive.date()
    end_date = today + timedelta(days=days_ahead)

    existing = Appointment.query.filter(
        Appointment.stylist_id == stylist.id,
        Appointment.status == "scheduled",
        Appointment.scheduled_at >= datetime.combine(today, dtime.min),
        Appointment.scheduled_at < datetime.combine(end_date + timedelta(days=1), dtime.min),
    ).all()
    taken = {a.scheduled_at for a in existing}

    slots = []
    cursor = today
    while cursor <= end_date:
        weekday = cursor.weekday()
        for template in templates:
            if template.day_of_week != weekday:
                continue
            step = timedelta(minutes=template.slot_minutes or DEFAULT_SLOT_MINUTES)
            slot_start = datetime.combine(cursor, template.start_time)
            window_end = datetime.combine(cursor, template.end_time)
            while slot_start + step <= window_end:
                if slot_start > now_naive and slot_start not in taken:
                    slots.append({"start": slot_start, "end": slot_start + step, "slot_minutes": template.slot_minutes})
                slot_start += step
        cursor += timedelta(days=1)

    slots.sort(key=lambda s: s["start"])
    return slots


def _send_booking_confirmation_emails(stylist, appointment) -> None:
    try:
        sender = (
            current_app.config.get("MAIL_DEFAULT_SENDER")
            or current_app.config.get("MAIL_USERNAME")
            or "letoya@ravlohq.com"
        )
        when = appointment.scheduled_at.strftime("%A, %B %d at %I:%M %p")
        confirm_url = url_for(
            "salon_public.booking_confirmed", slug=stylist.public_slug, token=appointment.confirmation_token,
            _external=True,
        )
        client = appointment.client

        if client and client.email:
            mail.send(MailMessage(
                subject=f"Your appointment with {stylist.full_name} is confirmed",
                sender=sender,
                recipients=[client.email],
                body=(
                    f"Hi {client.full_name},\n\n"
                    f"Your {appointment.service_type} appointment is confirmed for {when}.\n\n"
                    f"Details: {confirm_url}\n\n"
                    f"See you then!\n{stylist.full_name}"
                ),
            ))

        if stylist.email:
            mail.send(MailMessage(
                subject=f"New booking: {client.full_name if client else 'a client'}",
                sender=sender,
                recipients=[stylist.email],
                body=(
                    f"{client.full_name if client else 'A client'} booked {appointment.service_type} for {when}.\n\n"
                    f"Phone: {client.phone or '—' if client else '—'}\n"
                    f"Email: {client.email or '—' if client else '—'}\n"
                    f"Notes: {appointment.notes or '—'}\n\n"
                    f"View on your calendar: {url_for('stylist.appointments', _external=True)}"
                ),
            ))
    except Exception as exc:
        current_app.logger.warning("Salon booking confirmation email failed: %s", exc)


# ===============================================================
#   PUBLIC LANDING PAGE
# ===============================================================
@salon_public_bp.route("/<slug>")
def landing(slug):
    stylist = _stylist_or_404(slug)
    reviews = (
        SalonReview.query.filter_by(stylist_id=stylist.id)
        .order_by(SalonReview.created_at.desc())
        .limit(6)
        .all()
    )
    return render_template(
        "public/gotstyles_landing.html",
        stylist=stylist,
        reviews=reviews,
        service_categories=SERVICE_CATEGORIES,
    )


# ===============================================================
#   PUBLIC BOOKING CALENDAR
# ===============================================================
@salon_public_bp.route("/<slug>/book", methods=["GET"])
def book(slug):
    stylist = _stylist_or_404(slug)
    slots = _generate_available_slots(stylist)

    grouped_slots = OrderedDict()
    for slot in slots:
        day_key = slot["start"].strftime("%A, %B %d")
        grouped_slots.setdefault(day_key, []).append(slot)

    return render_template(
        "public/salon_booking.html",
        stylist=stylist,
        grouped_slots=grouped_slots,
        service_categories=SERVICE_CATEGORIES,
    )


@salon_public_bp.route("/<slug>/book", methods=["POST"])
@limiter.limit("5 per minute")
def submit_booking(slug):
    stylist = _stylist_or_404(slug)

    starts_at_raw = (request.form.get("starts_at") or "").strip()
    service_type = (request.form.get("service_type") or "").strip()
    name = (request.form.get("client_name") or "").strip()
    email = (request.form.get("client_email") or "").strip().lower()
    phone = (request.form.get("client_phone") or "").strip()
    notes = (request.form.get("notes") or "").strip() or None

    if not starts_at_raw or not service_type or not name or (not email and not phone):
        flash("Please choose a time, a service, your name, and an email or phone number.", "danger")
        return redirect(url_for("salon_public.book", slug=slug))

    try:
        starts_at = datetime.fromisoformat(starts_at_raw)
    except ValueError:
        flash("That time slot looks invalid. Please pick a time again.", "danger")
        return redirect(url_for("salon_public.book", slug=slug))

    if starts_at <= datetime.utcnow():
        flash("That time has already passed -- please pick another.", "warning")
        return redirect(url_for("salon_public.book", slug=slug))

    already_booked = Appointment.query.filter_by(
        stylist_id=stylist.id, scheduled_at=starts_at, status="scheduled"
    ).first()
    if already_booked:
        flash("That time was just booked -- please pick another.", "warning")
        return redirect(url_for("salon_public.book", slug=slug))

    template = SalonAvailability.query.filter_by(
        stylist_id=stylist.id, day_of_week=starts_at.weekday(), is_active=True
    ).first()
    slot_minutes = template.slot_minutes if template else DEFAULT_SLOT_MINUTES

    client = None
    if email:
        client = SalonClient.query.filter(
            SalonClient.stylist_id == stylist.id, db.func.lower(SalonClient.email) == email
        ).first()
    if not client and phone:
        client = SalonClient.query.filter_by(stylist_id=stylist.id, phone=phone).first()
    if not client:
        client = SalonClient(
            company_id=stylist.company_id,
            stylist_id=stylist.id,
            full_name=name,
            email=email or None,
            phone=phone or None,
        )
        db.session.add(client)
        db.session.flush()

    appointment = Appointment(
        company_id=stylist.company_id,
        stylist_id=stylist.id,
        client_id=client.id,
        service_type=service_type,
        scheduled_at=starts_at,
        duration_minutes=slot_minutes,
        status="scheduled",
        notes=notes,
        confirmation_token=_new_confirmation_token(),
    )
    db.session.add(appointment)
    db.session.commit()

    _send_booking_confirmation_emails(stylist, appointment)

    return redirect(url_for("salon_public.booking_confirmed", slug=slug, token=appointment.confirmation_token))


@salon_public_bp.route("/<slug>/confirmed/<token>")
def booking_confirmed(slug, token):
    stylist = _stylist_or_404(slug)
    appointment = Appointment.query.filter_by(stylist_id=stylist.id, confirmation_token=token).first_or_404()
    return render_template("public/salon_booking_confirmed.html", stylist=stylist, appointment=appointment)
