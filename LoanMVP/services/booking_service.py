# LoanMVP/services/booking_service.py
"""Booking capability: public scheduling for VIP workspaces.

Owner resolution is reused from payments_service.py rather than
duplicated -- resolve_current_owner()/owner_branding() already know how
to turn a logged-in user (or an owner_type/owner_id pair) into the right
VIPProfile/StylistProfile, and that logic shouldn't diverge between the
two capabilities.
"""
from datetime import datetime, timedelta, time as dtime

from LoanMVP.extensions import db
from LoanMVP.models.booking_models import Booking, BookingAvailability

BOOKING_WINDOW_DAYS = 21
DEFAULT_SLOT_MINUTES = 60


def get_availability(owner_type: str, owner_id: int):
    return (
        BookingAvailability.query.filter_by(owner_type=owner_type, owner_id=owner_id)
        .order_by(BookingAvailability.day_of_week.asc(), BookingAvailability.start_time.asc())
        .all()
    )


def add_availability_window(owner_type: str, owner_id: int, day_of_week: int, start_time, end_time, slot_minutes: int = DEFAULT_SLOT_MINUTES) -> BookingAvailability:
    window = BookingAvailability(
        owner_type=owner_type,
        owner_id=owner_id,
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
        slot_minutes=slot_minutes or DEFAULT_SLOT_MINUTES,
    )
    db.session.add(window)
    db.session.commit()
    return window


def delete_availability_window(owner_type: str, owner_id: int, window_id: int) -> bool:
    window = BookingAvailability.query.filter_by(
        id=window_id, owner_type=owner_type, owner_id=owner_id
    ).first()
    if not window:
        return False
    db.session.delete(window)
    db.session.commit()
    return True


def _existing_scheduled_intervals(owner_type: str, owner_id: int, window_start, window_end):
    existing = Booking.query.filter(
        Booking.owner_type == owner_type,
        Booking.owner_id == owner_id,
        Booking.status == "scheduled",
        Booking.starts_at >= window_start,
        Booking.starts_at < window_end,
    ).all()
    return [(b.starts_at, b.ends_at) for b in existing]


def _overlaps(candidate_start, candidate_end, intervals):
    return any(candidate_start < end and start < candidate_end for start, end in intervals)


def generate_available_slots(owner_type: str, owner_id: int, days_ahead: int = BOOKING_WINDOW_DAYS):
    """Slots computed on the fly from the owner's recurring weekly
    BookingAvailability windows minus already-booked Booking rows -- no
    pre-generated per-slot row, same approach as demo/salon scheduling."""
    templates = [w for w in get_availability(owner_type, owner_id) if w.is_active]
    if not templates:
        return []

    now_naive = datetime.utcnow()
    today = now_naive.date()
    end_date = today + timedelta(days=days_ahead)
    window_start = datetime.combine(today, dtime.min)
    window_end = datetime.combine(end_date + timedelta(days=1), dtime.min)
    taken_intervals = _existing_scheduled_intervals(owner_type, owner_id, window_start, window_end)

    slots = []
    cursor = today
    while cursor <= end_date:
        weekday = cursor.weekday()
        for template in templates:
            if template.day_of_week != weekday:
                continue
            duration = template.slot_minutes or DEFAULT_SLOT_MINUTES
            slot_start = datetime.combine(cursor, template.start_time)
            day_end = datetime.combine(cursor, template.end_time)
            while slot_start + timedelta(minutes=duration) <= day_end:
                slot_end = slot_start + timedelta(minutes=duration)
                if slot_start > now_naive and not _overlaps(slot_start, slot_end, taken_intervals):
                    slots.append({"start": slot_start, "end": slot_end, "duration_minutes": duration})
                slot_start += timedelta(minutes=duration)
        cursor += timedelta(days=1)

    slots.sort(key=lambda s: s["start"])
    return slots


def slot_is_valid(owner_type: str, owner_id: int, starts_at: datetime, duration_minutes: int) -> bool:
    """Re-validates a submitted booking server-side against the owner's
    active availability windows and existing bookings."""
    templates = [
        w for w in get_availability(owner_type, owner_id)
        if w.is_active and w.day_of_week == starts_at.weekday()
    ]
    ends_at = starts_at + timedelta(minutes=duration_minutes)

    fits_a_window = any(
        datetime.combine(starts_at.date(), t.start_time) <= starts_at
        and ends_at <= datetime.combine(starts_at.date(), t.end_time)
        for t in templates
    )
    if not fits_a_window:
        return False

    taken_intervals = _existing_scheduled_intervals(
        owner_type, owner_id, starts_at - timedelta(days=1), starts_at + timedelta(days=1)
    )
    return not _overlaps(starts_at, ends_at, taken_intervals)


def create_booking(
    owner_type: str,
    owner_id: int,
    starts_at: datetime,
    duration_minutes: int,
    client_name: str,
    client_email: str = "",
    client_phone: str = "",
    notes: str = "",
    title: str = "",
) -> Booking:
    booking = Booking(
        owner_type=owner_type,
        owner_id=owner_id,
        title=title or None,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=duration_minutes),
        client_name=client_name,
        client_email=client_email or None,
        client_phone=client_phone or None,
        notes=notes or None,
    )
    db.session.add(booking)
    db.session.commit()
    return booking
