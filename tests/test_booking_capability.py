"""Regression tests for the Booking capability: a public "schedule a
visit" calendar for VIPProfile-owned workspaces (realtor/insurance/
contractor) that had no booking system at all before this -- starting
with Mason-Fultz's quote-visit scheduling. Deliberately separate from
the Salon/Stylist vertical's own existing Appointment system.
"""
from datetime import datetime, timedelta, time as dtime

from LoanMVP.models.admin import Company
from LoanMVP.models.booking_models import Booking, BookingAvailability
from LoanMVP.models.crm_models import Lead
from LoanMVP.models.user_model import User
from LoanMVP.models.vip_models import VIPProfile, VIPNotification
from LoanMVP.services.booking_service import (
    add_availability_window,
    create_booking,
    generate_available_slots,
    slot_is_valid,
)

from tests.conftest import login_as


def _make_contractor(db_session, email="quotebiz@example.com", public_slug="quote-biz"):
    company = Company(name="Quote Biz Co", is_active=True)
    db_session.add(company)
    db_session.commit()
    user = User(email=email, role="partner", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    profile = VIPProfile(
        user_id=user.id,
        display_name="Quote Biz",
        business_name="Quote Biz",
        role_type="contractor",
        public_slug=public_slug,
        marketplace_enabled="yes",
    )
    db_session.add(profile)
    db_session.commit()
    return user, profile


# ─── booking_service ────────────────────────────────────────────────────────

def test_generate_available_slots_empty_without_any_window(db_session):
    assert generate_available_slots("vip_profile", 999) == []


def test_generate_available_slots_respects_configured_window(db_session):
    _, profile = _make_contractor(db_session)
    weekday = (datetime.utcnow() + timedelta(days=1)).weekday()
    add_availability_window(
        "vip_profile", profile.id, weekday, dtime(9, 0), dtime(11, 0), slot_minutes=60
    )

    slots = generate_available_slots("vip_profile", profile.id)

    assert len(slots) > 0
    assert all(s["duration_minutes"] == 60 for s in slots)


def test_generate_available_slots_excludes_already_booked_time(db_session):
    _, profile = _make_contractor(db_session)
    tomorrow = datetime.utcnow() + timedelta(days=1)
    weekday = tomorrow.weekday()
    # Single one-hour window on this weekday -> exactly one slot per
    # occurrence of that weekday inside the 21-day booking window.
    add_availability_window("vip_profile", profile.id, weekday, dtime(9, 0), dtime(10, 0), slot_minutes=60)

    slots_before = generate_available_slots("vip_profile", profile.id)
    count_before = len(slots_before)
    assert count_before >= 1
    booked_start = slots_before[0]["start"]

    create_booking("vip_profile", profile.id, booked_start, 60, client_name="Existing Client")

    slots_after = generate_available_slots("vip_profile", profile.id)
    assert len(slots_after) == count_before - 1
    assert booked_start not in [s["start"] for s in slots_after]


def test_slot_is_valid_rejects_time_outside_any_window(db_session):
    _, profile = _make_contractor(db_session)
    weekday = (datetime.utcnow() + timedelta(days=1)).weekday()
    add_availability_window("vip_profile", profile.id, weekday, dtime(9, 0), dtime(10, 0), slot_minutes=60)

    far_future_wrong_time = datetime.utcnow() + timedelta(days=30)
    assert slot_is_valid("vip_profile", profile.id, far_future_wrong_time.replace(hour=23, minute=0), 60) is False


def test_slot_is_valid_rejects_double_booking(db_session):
    _, profile = _make_contractor(db_session)
    weekday = (datetime.utcnow() + timedelta(days=1)).weekday()
    add_availability_window("vip_profile", profile.id, weekday, dtime(9, 0), dtime(11, 0), slot_minutes=60)

    slots = generate_available_slots("vip_profile", profile.id)
    starts_at = slots[0]["start"]
    create_booking("vip_profile", profile.id, starts_at, 60, client_name="First Client")

    assert slot_is_valid("vip_profile", profile.id, starts_at, 60) is False


# ─── Dashboard: availability settings ──────────────────────────────────────

def test_availability_dashboard_requires_login(client):
    resp = client.get("/booking/availability", follow_redirects=False)
    assert resp.status_code in (302, 401)


def test_owner_can_add_and_remove_availability_window(db_session, client):
    user, profile = _make_contractor(db_session, email="owner@example.com")
    login_as(client, user)

    resp = client.post(
        "/booking/availability",
        data={"action_type": "add", "day_of_week": "1", "start_time": "09:00", "end_time": "17:00", "slot_minutes": "60"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    window = BookingAvailability.query.filter_by(owner_type="vip_profile", owner_id=profile.id).first()
    assert window is not None
    assert window.day_of_week == 1

    resp2 = client.post(
        "/booking/availability",
        data={"action_type": "delete", "window_id": window.id},
        follow_redirects=True,
    )
    assert resp2.status_code == 200
    assert BookingAvailability.query.filter_by(id=window.id).first() is None


# ─── Public calendar + booking ──────────────────────────────────────────────

def test_public_booking_page_shows_open_slots(db_session, client):
    _, profile = _make_contractor(db_session, email="visible@example.com", public_slug="visible-biz")
    weekday = (datetime.utcnow() + timedelta(days=1)).weekday()
    add_availability_window("vip_profile", profile.id, weekday, dtime(9, 0), dtime(11, 0), slot_minutes=60)

    resp = client.get("/p/visible-biz/book")

    assert resp.status_code == 200
    assert "Schedule a Visit" in resp.get_data(as_text=True)


def test_public_booking_page_404s_for_slug_without_live_profile(client):
    resp = client.get("/p/not-a-real-business/book")
    assert resp.status_code == 404


def test_submitting_a_booking_creates_lead_and_notification(db_session, client):
    owner, profile = _make_contractor(db_session, email="bookme@example.com", public_slug="book-me")
    weekday = (datetime.utcnow() + timedelta(days=1)).weekday()
    add_availability_window("vip_profile", profile.id, weekday, dtime(9, 0), dtime(11, 0), slot_minutes=60)

    slots = generate_available_slots("vip_profile", profile.id)
    starts_at = slots[0]["start"]

    resp = client.post(
        "/p/book-me/book",
        data={
            "client_name": "Prospective Client",
            "client_email": "prospect@example.com",
            "client_phone": "615-555-0000",
            "notes": "Need a quote for a 3,000 sqft office.",
            "starts_at": starts_at.strftime("%Y-%m-%dT%H:%M"),
            "duration_minutes": "60",
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "You're Confirmed!" in body

    booking = Booking.query.filter_by(owner_type="vip_profile", owner_id=profile.id).first()
    assert booking is not None
    assert booking.client_name == "Prospective Client"

    lead = Lead.query.filter_by(email="prospect@example.com").first()
    assert lead is not None
    assert lead.assigned_to == owner.id

    notification = VIPNotification.query.filter_by(vip_profile_id=profile.id).first()
    assert notification is not None


def test_submitting_a_booking_requires_name(db_session, client):
    _, profile = _make_contractor(db_session, email="needsname@example.com", public_slug="needs-name")
    weekday = (datetime.utcnow() + timedelta(days=1)).weekday()
    add_availability_window("vip_profile", profile.id, weekday, dtime(9, 0), dtime(11, 0), slot_minutes=60)
    slots = generate_available_slots("vip_profile", profile.id)

    resp = client.post(
        "/p/needs-name/book",
        data={"starts_at": slots[0]["start"].strftime("%Y-%m-%dT%H:%M"), "duration_minutes": "60"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "Name is required" in resp.get_data(as_text=True)
    assert Booking.query.count() == 0


def test_submitting_a_booking_rejects_already_taken_slot(db_session, client):
    _, profile = _make_contractor(db_session, email="raceslot@example.com", public_slug="race-slot")
    weekday = (datetime.utcnow() + timedelta(days=1)).weekday()
    add_availability_window("vip_profile", profile.id, weekday, dtime(9, 0), dtime(10, 0), slot_minutes=60)
    slots = generate_available_slots("vip_profile", profile.id)
    starts_at = slots[0]["start"]

    create_booking("vip_profile", profile.id, starts_at, 60, client_name="First Client")

    resp = client.post(
        "/p/race-slot/book",
        data={
            "client_name": "Second Client",
            "starts_at": starts_at.strftime("%Y-%m-%dT%H:%M"),
            "duration_minutes": "60",
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "no longer available" in resp.get_data(as_text=True)
    assert Booking.query.filter_by(client_name="Second Client").count() == 0


def test_booking_confirmation_page_renders(db_session, client):
    _, profile = _make_contractor(db_session, email="confirm@example.com", public_slug="confirm-biz")
    booking = create_booking(
        "vip_profile", profile.id, datetime.utcnow() + timedelta(days=2), 60, client_name="Confirmed Client",
    )

    resp = client.get(f"/p/confirm-biz/book/confirmed/{booking.confirmation_token}")

    assert resp.status_code == 200
    assert "Confirmed Client" in resp.get_data(as_text=True)
