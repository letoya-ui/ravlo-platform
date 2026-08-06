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

Unlike the single-duration demo page, this vertical offers a short
consultation (fixed 30 minutes) alongside full-length appointments (whose
duration follows the stylist's own per-day availability window length).
Two different durations sharing one calendar means slot availability has
to be checked with real interval overlap (does [start, start+duration)
intersect any existing appointment's [start, start+duration)), not just
"is this exact start time already taken" -- the exact-match check that
sufficed when every appointment was the same length.

Like scheduling.py, times are stored/displayed as naive, stylist-local
datetimes with no per-visitor timezone conversion -- appropriate (more so
than for the Ravlo demo page) since a salon client physically visits the
shop in the stylist's own timezone.
"""
import base64
import io
import time as time_module
from collections import OrderedDict
from datetime import datetime, timedelta, time as dtime

import qrcode
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
from LoanMVP.services.payments_service import (
    PaymentsServiceError,
    create_checkout_session_for_request,
    create_payment_request,
    get_or_create_payment_account,
)

salon_public_bp = Blueprint("salon_public", __name__, url_prefix="/salon")

BOOKING_WINDOW_DAYS = 21
DEFAULT_SLOT_MINUTES = 60

# How long a "pending_deposit" appointment holds its slot while the client
# is on Stripe Checkout. Matched to the Checkout Session's own expires_at
# below so an abandoned checkout can't block the slot forever without
# needing a separate cleanup job.
DEPOSIT_HOLD_MINUTES = 30

CONSULTATION_SERVICE_NAME = "30-Minute Consultation"
CONSULTATION_MINUTES = 30

# GotStyles Beauty's real service menu (from Aisha's own promotional
# flyer), shown on the landing page and offered in the booking form.
# Deliberately no invented prices/durations here beyond the consultation
# (a real, explicit 30 minutes) -- full appointments use whichever slot
# length the stylist has configured for that day in /stylist/availability,
# and Aisha can attach real pricing when she manages the appointment from
# her own dashboard. `icon` keys match the inline SVGs defined in
# gotstyles_landing.html's SERVICE_ICONS.
SERVICE_CATEGORIES = [
    {"name": CONSULTATION_SERVICE_NAME, "icon": "consult",
     "description": "Not sure where to start? A quick chat about your hair goals -- no commitment."},
    {"name": "Silk Press", "icon": "silk_press", "description": "Sleek, smooth, salon-fresh results."},
    {"name": "Sew-Ins", "icon": "sew_ins", "description": "Flawless, natural-looking sew-in installs."},
    {"name": "Quick Weaves", "icon": "quick_weaves", "description": "Fast, seamless quick weave styling."},
    {"name": "Custom Wigs", "icon": "custom_wigs", "description": "Custom wig install, styling, and unit maintenance."},
    {"name": "Color Services", "icon": "color", "description": "Custom color, from subtle to bold."},
    {"name": "Highlights", "icon": "highlights", "description": "Dimension and brightness, done right."},
    {"name": "Natural Hair Care", "icon": "natural_hair", "description": "Healthy, thriving natural hair."},
    {"name": "Treatments", "icon": "treatments", "description": "Deep conditioning and scalp treatments."},
    {"name": "Braids", "icon": "braids", "description": "Clean, long-lasting braid styles."},
    {"name": "Special Occasion Styling", "icon": "occasion", "description": "Red-carpet-ready styling for your big moment."},
]

# Services offered in the "Full Appointment" track of the booking form
# (everything except the consultation, which gets its own track/duration).
FULL_APPOINTMENT_SERVICES = [s for s in SERVICE_CATEGORIES if s["name"] != CONSULTATION_SERVICE_NAME]

# "Why You'll Love GotStyles" -- from Aisha's own flyer.
WHY_YOU_LOVE = [
    "Personalized consultations",
    "Luxury salon experience",
    "Healthy hair is always the priority",
    "Professional products",
    "Relaxing atmosphere",
    "Every client leaves feeling beautiful",
]


def _booking_qr_data_uri(booking_url: str) -> str:
    img = qrcode.make(booking_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _stylist_or_404(slug):
    return StylistProfile.query.filter(
        db.func.lower(StylistProfile.public_slug) == (slug or "").strip().lower()
    ).first_or_404()


def _existing_scheduled_intervals(stylist, window_start, window_end):
    """[(start, end), ...] for every appointment in range that currently
    holds its slot, used for real interval-overlap checks rather than
    exact-start-time matches -- necessary now that appointments can have
    different durations (a 30-minute consultation vs. a full-length
    service). Includes not just confirmed "scheduled" appointments but
    also recent "pending_deposit" ones -- a client mid-Stripe-Checkout for
    a required deposit still holds their slot -- excluding any that are
    older than DEPOSIT_HOLD_MINUTES, since an abandoned checkout should
    release the slot rather than block it forever."""
    deposit_cutoff = datetime.utcnow() - timedelta(minutes=DEPOSIT_HOLD_MINUTES)
    existing = Appointment.query.filter(
        Appointment.stylist_id == stylist.id,
        db.or_(
            Appointment.status == "scheduled",
            db.and_(Appointment.status == "pending_deposit", Appointment.created_at >= deposit_cutoff),
        ),
        Appointment.scheduled_at >= window_start,
        Appointment.scheduled_at < window_end,
    ).all()
    return [
        (a.scheduled_at, a.scheduled_at + timedelta(minutes=a.duration_minutes or DEFAULT_SLOT_MINUTES))
        for a in existing
    ]


def _overlaps(candidate_start, candidate_end, intervals):
    return any(candidate_start < end and start < candidate_end for start, end in intervals)


def _generate_available_slots(stylist, fixed_duration_minutes=None, days_ahead: int = BOOKING_WINDOW_DAYS):
    """Slots for the "Full Appointment" track (fixed_duration_minutes=None,
    each day's own configured slot_minutes) or the fixed-length
    consultation track (fixed_duration_minutes=CONSULTATION_MINUTES)."""
    templates = SalonAvailability.query.filter_by(stylist_id=stylist.id, is_active=True).all()
    if not templates:
        return []

    now_naive = datetime.utcnow()
    today = now_naive.date()
    end_date = today + timedelta(days=days_ahead)
    window_start = datetime.combine(today, dtime.min)
    window_end = datetime.combine(end_date + timedelta(days=1), dtime.min)
    taken_intervals = _existing_scheduled_intervals(stylist, window_start, window_end)

    slots = []
    cursor = today
    while cursor <= end_date:
        weekday = cursor.weekday()
        for template in templates:
            if template.day_of_week != weekday:
                continue
            duration = fixed_duration_minutes or template.slot_minutes or DEFAULT_SLOT_MINUTES
            step = timedelta(minutes=min(duration, template.slot_minutes or DEFAULT_SLOT_MINUTES))
            slot_start = datetime.combine(cursor, template.start_time)
            window_end_dt = datetime.combine(cursor, template.end_time)
            while slot_start + timedelta(minutes=duration) <= window_end_dt:
                slot_end = slot_start + timedelta(minutes=duration)
                if slot_start > now_naive and not _overlaps(slot_start, slot_end, taken_intervals):
                    slots.append({"start": slot_start, "end": slot_end, "duration_minutes": duration})
                slot_start += step
        cursor += timedelta(days=1)

    slots.sort(key=lambda s: s["start"])
    return slots


def _slot_is_valid(stylist, starts_at, duration_minutes) -> bool:
    """Re-validates a submitted booking server-side: does some active
    availability window on that weekday actually cover [starts_at,
    starts_at+duration), and does it avoid overlapping any other
    scheduled appointment."""
    templates = SalonAvailability.query.filter_by(
        stylist_id=stylist.id, day_of_week=starts_at.weekday(), is_active=True
    ).all()
    ends_at = starts_at + timedelta(minutes=duration_minutes)

    fits_a_window = any(
        datetime.combine(starts_at.date(), t.start_time) <= starts_at
        and ends_at <= datetime.combine(starts_at.date(), t.end_time)
        for t in templates
    )
    if not fits_a_window:
        return False

    taken_intervals = _existing_scheduled_intervals(
        stylist, starts_at - timedelta(days=1), starts_at + timedelta(days=1)
    )
    return not _overlaps(starts_at, ends_at, taken_intervals)


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
    booking_url = url_for("salon_public.book", slug=stylist.public_slug, _external=True)
    return render_template(
        "public/gotstyles_landing.html",
        stylist=stylist,
        reviews=reviews,
        service_categories=SERVICE_CATEGORIES,
        why_you_love=WHY_YOU_LOVE,
        booking_url=booking_url,
        booking_qr_data_uri=_booking_qr_data_uri(booking_url),
    )


# ===============================================================
#   PUBLIC BOOKING CALENDAR
# ===============================================================
@salon_public_bp.route("/<slug>/book", methods=["GET"])
def book(slug):
    stylist = _stylist_or_404(slug)

    def _group(slots):
        grouped = OrderedDict()
        for slot in slots:
            grouped.setdefault(slot["start"].strftime("%A, %B %d"), []).append(slot)
        return grouped

    standard_slots = _group(_generate_available_slots(stylist))
    consultation_slots = _group(_generate_available_slots(stylist, fixed_duration_minutes=CONSULTATION_MINUTES))

    return render_template(
        "public/salon_booking.html",
        stylist=stylist,
        standard_slots=standard_slots,
        consultation_slots=consultation_slots,
        full_appointment_services=FULL_APPOINTMENT_SERVICES,
        consultation_service_name=CONSULTATION_SERVICE_NAME,
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

    is_consultation = service_type == CONSULTATION_SERVICE_NAME
    if is_consultation:
        duration_minutes = CONSULTATION_MINUTES
    else:
        template = SalonAvailability.query.filter_by(
            stylist_id=stylist.id, day_of_week=starts_at.weekday(), is_active=True
        ).first()
        duration_minutes = template.slot_minutes if template else DEFAULT_SLOT_MINUTES

    if not _slot_is_valid(stylist, starts_at, duration_minutes):
        flash("That time was just booked or is no longer available -- please pick another.", "warning")
        return redirect(url_for("salon_public.book", slug=slug))

    deposit_account = None
    if stylist.deposit_required:
        deposit_account = get_or_create_payment_account("stylist_profile", stylist.id)
        if not deposit_account.is_ready_for_payments:
            flash(
                "Online booking is temporarily unavailable -- this stylist's deposit payment "
                "isn't set up yet. Please contact them directly to schedule.",
                "danger",
            )
            return redirect(url_for("salon_public.book", slug=slug))

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
        duration_minutes=duration_minutes,
        status="pending_deposit" if deposit_account else "scheduled",
        notes=notes,
        confirmation_token=_new_confirmation_token(),
    )
    db.session.add(appointment)
    db.session.commit()

    if deposit_account:
        try:
            checkout_url = _start_deposit_checkout(stylist, deposit_account, appointment, client)
        except PaymentsServiceError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("salon_public.book", slug=slug))
        return redirect(checkout_url, code=303)

    _send_booking_confirmation_emails(stylist, appointment)

    return redirect(url_for("salon_public.booking_confirmed", slug=slug, token=appointment.confirmation_token))


def _start_deposit_checkout(stylist, deposit_account, appointment, client):
    """Creates the PaymentRequest for this appointment's required deposit
    and returns the Stripe Checkout URL. success_url lands the client back
    on the normal booking-confirmed page (which shows a "confirming your
    deposit" message until the webhook flips the appointment to
    scheduled); cancel_url reuses the Payments capability's own public pay
    page so an abandoned checkout can still be retried without losing the
    held slot."""
    when = appointment.scheduled_at.strftime("%A, %B %d at %I:%M %p")
    payment_request = create_payment_request(
        deposit_account,
        title=f"Deposit -- {appointment.service_type}",
        amount_cents=stylist.deposit_amount_cents,
        description=f"Deposit to confirm your {when} appointment with {stylist.full_name}.",
        client_name=client.full_name,
        client_email=client.email or "",
        client_phone=client.phone or "",
    )
    appointment.payment_request_id = payment_request.id
    db.session.commit()

    success_url = url_for(
        "salon_public.booking_confirmed", slug=stylist.public_slug, token=appointment.confirmation_token,
        _external=True,
    )
    cancel_url = url_for(
        "payments.public_pay_page", token=payment_request.confirmation_token, _external=True
    )
    expires_at = int(time_module.time()) + DEPOSIT_HOLD_MINUTES * 60

    return create_checkout_session_for_request(payment_request, success_url, cancel_url, expires_at=expires_at)


@salon_public_bp.route("/<slug>/confirmed/<token>")
def booking_confirmed(slug, token):
    stylist = _stylist_or_404(slug)
    appointment = Appointment.query.filter_by(stylist_id=stylist.id, confirmation_token=token).first_or_404()
    return render_template("public/salon_booking_confirmed.html", stylist=stylist, appointment=appointment)
