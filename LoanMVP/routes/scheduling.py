# ===============================================================
#   RAVLO — DEMO SCHEDULING (in-house Calendly replacement)
# ===============================================================
"""Lets prospects self-book a live demo instead of filling out a contact
form and waiting for a callback, and lets Ravlo staff (executives and
account executives) manage their own open hours and see the resulting
bookings on a shared company calendar.

Available slots are computed on the fly from each staff member's
DemoAvailability templates (a recurring weekly window, e.g. "Mon 9am-5pm,
30-minute slots") minus already-booked DemoBooking rows for that host --
there's no pre-generated per-slot row to keep in sync.

All stored/displayed times are company-local (COMPANY_TZ below), not
converted per-visitor timezone -- the booking page labels times with the
company timezone so this stays honest instead of silently wrong for
visitors elsewhere. A future iteration could add real per-visitor
timezone conversion; out of scope for this pass.
"""
from collections import OrderedDict
from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import current_user, login_required
from flask_mail import Message as MailMessage

from LoanMVP.app import mail
from LoanMVP.extensions import db, limiter
from LoanMVP.utils.decorators import role_required
from LoanMVP.models.calendar_models import DemoAvailability, DemoBooking
from LoanMVP.models.user_model import User

scheduling_bp = Blueprint("scheduling", __name__, url_prefix="/")

COMPANY_TZ = ZoneInfo("America/New_York")
COMPANY_TZ_LABEL = "Eastern Time (ET)"
BOOKING_WINDOW_DAYS = 14

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Mirrors account_executive.py's FULL_VISIBILITY_ROLES -- role_required
# already lets platform_admin/master_admin/executive through every check,
# so these are the roles that see the whole company calendar rather than
# just their own bookings.
FULL_VISIBILITY_ROLES = {"platform_admin", "master_admin", "executive"}


def _is_full_visibility(user) -> bool:
    return (getattr(user, "role", "") or "").strip().lower() in FULL_VISIBILITY_ROLES


def _normalize_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _company_now_naive() -> datetime:
    return datetime.now(COMPANY_TZ).replace(tzinfo=None)


def _generate_available_slots(days_ahead: int = BOOKING_WINDOW_DAYS):
    """Returns a list of dicts (host_user_id, host_name, start, end) sorted
    by start time, for every active DemoAvailability template over the next
    `days_ahead` days, excluding times that are already booked or in the past."""
    templates = DemoAvailability.query.filter_by(is_active=True).all()
    if not templates:
        return []

    now_naive = _company_now_naive()
    today = now_naive.date()
    end_date = today + timedelta(days=days_ahead)

    existing = DemoBooking.query.filter(
        DemoBooking.status == "scheduled",
        DemoBooking.starts_at >= datetime.combine(today, dtime.min),
        DemoBooking.starts_at < datetime.combine(end_date + timedelta(days=1), dtime.min),
    ).all()
    taken = {(b.host_user_id, b.starts_at) for b in existing}

    slots = []
    cursor = today
    while cursor <= end_date:
        weekday = cursor.weekday()  # Monday = 0
        for template in templates:
            if template.day_of_week != weekday:
                continue
            step = timedelta(minutes=template.slot_minutes or 30)
            slot_start = datetime.combine(cursor, template.start_time)
            window_end = datetime.combine(cursor, template.end_time)
            while slot_start + step <= window_end:
                if slot_start > now_naive and (template.host_user_id, slot_start) not in taken:
                    host = template.host
                    slots.append({
                        "host_user_id": template.host_user_id,
                        "host_name": (host.full_name if host else None) or "Ravlo Team",
                        "start": slot_start,
                        "end": slot_start + step,
                    })
                slot_start += step
        cursor += timedelta(days=1)

    slots.sort(key=lambda s: s["start"])
    return slots


def _send_booking_confirmation_emails(booking: DemoBooking) -> None:
    try:
        sender = (
            current_app.config.get("MAIL_DEFAULT_SENDER")
            or current_app.config.get("MAIL_USERNAME")
            or "letoya@ravlohq.com"
        )
        when = f"{booking.starts_at.strftime('%A, %B %d at %I:%M %p')} {COMPANY_TZ_LABEL}"
        confirm_url = url_for("scheduling.demo_confirmed", token=booking.confirmation_token, _external=True)

        prospect_msg = MailMessage(
            subject="Your Ravlo demo is scheduled",
            sender=sender,
            recipients=[booking.prospect_email],
            body=(
                f"Hi {booking.prospect_name},\n\n"
                f"Your Ravlo Lending OS demo is confirmed for {when}.\n\n"
                f"Details: {confirm_url}\n\n"
                "See you then!\nRavlo"
            ),
        )
        mail.send(prospect_msg)

        if booking.host and booking.host.email:
            host_msg = MailMessage(
                subject=f"New demo booked: {booking.prospect_name}",
                sender=sender,
                recipients=[booking.host.email],
                body=(
                    f"{booking.prospect_name} ({booking.prospect_email}) booked a demo for {when}.\n\n"
                    f"Company: {booking.prospect_company or '—'}\n"
                    f"Phone: {booking.prospect_phone or '—'}\n"
                    f"Notes: {booking.notes or '—'}\n\n"
                    f"View on your calendar: {url_for('scheduling.company_calendar', _external=True)}"
                ),
            )
            mail.send(host_msg)
    except Exception as exc:
        current_app.logger.warning("Demo booking confirmation email failed: %s", exc)


# ===============================================================
#   PUBLIC BOOKING PAGE
# ===============================================================
@scheduling_bp.route("/demo", methods=["GET"])
def schedule_demo():
    slots = _generate_available_slots()

    grouped_slots = OrderedDict()
    for slot in slots:
        day_key = slot["start"].strftime("%A, %B %d")
        grouped_slots.setdefault(day_key, []).append(slot)

    return render_template(
        "marketing/schedule_demo.html",
        grouped_slots=grouped_slots,
        tz_label=COMPANY_TZ_LABEL,
        page_title="Schedule a Demo | Ravlo",
        meta_description="Pick a time and book a live demo of Ravlo Lending OS -- no back-and-forth required.",
    )


@scheduling_bp.route("/demo/book", methods=["POST"])
@limiter.limit("5 per minute")
def book_demo():
    host_user_id = _normalize_int(request.form.get("host_user_id"))
    starts_at_raw = (request.form.get("starts_at") or "").strip()
    name = (request.form.get("prospect_name") or "").strip()
    email = (request.form.get("prospect_email") or "").strip().lower()
    company_name = (request.form.get("prospect_company") or "").strip() or None
    phone = (request.form.get("prospect_phone") or "").strip() or None
    notes = (request.form.get("notes") or "").strip() or None

    if not host_user_id or not starts_at_raw or not name or not email:
        flash("Please choose a time and fill in your name and email.", "danger")
        return redirect(url_for("scheduling.schedule_demo"))

    try:
        starts_at = datetime.fromisoformat(starts_at_raw)
    except ValueError:
        flash("That time slot looks invalid. Please pick a time again.", "danger")
        return redirect(url_for("scheduling.schedule_demo"))

    host = User.query.get(host_user_id)
    if not host:
        flash("That host is no longer available. Please pick another time.", "danger")
        return redirect(url_for("scheduling.schedule_demo"))

    already_booked = DemoBooking.query.filter_by(
        host_user_id=host_user_id, starts_at=starts_at, status="scheduled"
    ).first()
    if already_booked or starts_at <= _company_now_naive():
        flash("That time was just booked or has already passed -- please pick another.", "warning")
        return redirect(url_for("scheduling.schedule_demo"))

    template = DemoAvailability.query.filter_by(
        host_user_id=host_user_id, day_of_week=starts_at.weekday(), is_active=True
    ).first()
    slot_minutes = template.slot_minutes if template else 30

    booking = DemoBooking(
        host_user_id=host_user_id,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=slot_minutes),
        prospect_name=name,
        prospect_email=email,
        prospect_company=company_name,
        prospect_phone=phone,
        notes=notes,
        status="scheduled",
    )
    db.session.add(booking)
    db.session.commit()

    _send_booking_confirmation_emails(booking)

    return redirect(url_for("scheduling.demo_confirmed", token=booking.confirmation_token))


@scheduling_bp.route("/demo/confirmed/<token>")
def demo_confirmed(token):
    booking = DemoBooking.query.filter_by(confirmation_token=token).first_or_404()
    return render_template(
        "marketing/demo_confirmed.html",
        booking=booking,
        tz_label=COMPANY_TZ_LABEL,
        page_title="Demo Scheduled | Ravlo",
    )


# ===============================================================
#   STAFF: MY AVAILABILITY
# ===============================================================
@scheduling_bp.route("/calendar/availability", methods=["GET", "POST"])
@login_required
@role_required("account_executive")
def availability():
    if request.method == "POST":
        action_type = request.form.get("action_type")

        if action_type == "add":
            day_of_week = _normalize_int(request.form.get("day_of_week"))
            slot_minutes = _normalize_int(request.form.get("slot_minutes")) or 30

            try:
                start_time = datetime.strptime((request.form.get("start_time") or "").strip(), "%H:%M").time()
                end_time = datetime.strptime((request.form.get("end_time") or "").strip(), "%H:%M").time()
            except ValueError:
                flash("Enter valid start and end times.", "danger")
                return redirect(url_for("scheduling.availability"))

            if day_of_week is None or day_of_week not in range(7) or end_time <= start_time:
                flash("Enter a valid day and time range.", "danger")
                return redirect(url_for("scheduling.availability"))

            db.session.add(DemoAvailability(
                host_user_id=current_user.id,
                day_of_week=day_of_week,
                start_time=start_time,
                end_time=end_time,
                slot_minutes=slot_minutes,
            ))
            db.session.commit()
            flash("Availability added.", "success")

        elif action_type == "delete":
            slot_id = _normalize_int(request.form.get("slot_id"))
            slot = DemoAvailability.query.filter_by(id=slot_id, host_user_id=current_user.id).first()
            if slot:
                db.session.delete(slot)
                db.session.commit()
                flash("Availability removed.", "success")

        return redirect(url_for("scheduling.availability"))

    my_slots = (
        DemoAvailability.query
        .filter_by(host_user_id=current_user.id)
        .order_by(DemoAvailability.day_of_week, DemoAvailability.start_time)
        .all()
    )

    return render_template(
        "scheduling/availability.html",
        slots=my_slots,
        weekdays=WEEKDAYS,
        tz_label=COMPANY_TZ_LABEL,
        title="My Availability",
        active_tab="availability",
    )


# ===============================================================
#   STAFF: COMPANY CALENDAR
# ===============================================================
@scheduling_bp.route("/calendar")
@login_required
@role_required("account_executive")
def company_calendar():
    query = DemoBooking.query.filter(DemoBooking.status == "scheduled")
    if not _is_full_visibility(current_user):
        query = query.filter_by(host_user_id=current_user.id)

    bookings = query.order_by(DemoBooking.starts_at).all()

    return render_template(
        "scheduling/company_calendar.html",
        bookings=bookings,
        tz_label=COMPANY_TZ_LABEL,
        is_full_visibility=_is_full_visibility(current_user),
        title="Company Calendar",
        active_tab="calendar",
    )


@scheduling_bp.route("/calendar/bookings/<int:booking_id>/cancel", methods=["POST"])
@login_required
@role_required("account_executive")
def cancel_booking(booking_id):
    booking = DemoBooking.query.get_or_404(booking_id)

    if booking.host_user_id != current_user.id and not _is_full_visibility(current_user):
        flash("You don't have access to that booking.", "warning")
        return redirect(url_for("scheduling.company_calendar"))

    booking.status = "canceled"
    booking.canceled_at = datetime.utcnow()
    db.session.commit()
    flash("Booking canceled.", "success")
    return redirect(url_for("scheduling.company_calendar"))
