"""Regression tests for the salon vertical's public landing page and
booking calendar (salon_public.py), mirroring scheduling.py's demo-booking
Calendly tests but scoped per-stylist instead of per-Ravlo-staff-host --
and, unlike the single-duration demo page, covering two different
appointment durations (a 30-minute consultation and full-length
appointments) sharing one calendar, which requires real interval-overlap
checking rather than exact-start-time matching.
"""
import re
from datetime import datetime, time as dtime, timedelta

import pytest

from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User
from LoanMVP.models.salon_models import StylistProfile, SalonAvailability, SalonClient, Appointment, SalonReview
from LoanMVP.extensions import db, limiter

from tests.conftest import login_as


@pytest.fixture(autouse=True)
def _reset_booking_rate_limit():
    # submit_booking is rate-limited ("5 per minute") for real visitors,
    # but RATELIMIT_ENABLED=False set post-create_app() in conftest's app
    # fixture doesn't actually disable Flask-Limiter (same class of gotcha
    # as MAIL_SUPPRESS_SEND documented there) -- so with several tests in
    # this file each POSTing to the same rate-limited route, the shared
    # in-memory limiter storage accumulates across tests and a later test
    # gets a bogus 429 that has nothing to do with its own assertions.
    limiter.reset()
    yield


def _make_stylist_with_slug(db_session, slug, email, company_name, address=None):
    company = Company(name=company_name, is_active=True)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role="stylist", is_active=True, company_id=company.id,
                first_name="Stylist", last_name=slug)
    db_session.add(user)
    db_session.commit()

    profile = StylistProfile(
        user_id=user.id,
        company_id=company.id,
        full_name=f"{company_name}",
        email=email,
        public_slug=slug,
        brand_color="#B76E79",
        headline="Beauty. Brand. Business.",
        service_area="Nashville, TN",
        address=address,
    )
    db_session.add(profile)
    db_session.commit()
    return user, profile


def _add_availability(db_session, profile, day_of_week, start=dtime(10, 0), end=dtime(18, 0), slot_minutes=60):
    slot = SalonAvailability(
        stylist_id=profile.id, day_of_week=day_of_week, start_time=start, end_time=end, slot_minutes=slot_minutes,
    )
    db_session.add(slot)
    db_session.commit()
    return slot


def _extract_section(body, div_id):
    match = re.search(rf'id="{div_id}"(.*?)(?=id="\w+SlotsWrap"|</div>\s*</div>\s*<div class="gs-card" id="detailsCard")',
                       body, re.DOTALL)
    return match.group(1) if match else ""


def _first_start(body, div_id):
    section = _extract_section(body, div_id)
    m = re.search(r'data-start="([^"]+)"', section)
    return m.group(1) if m else None


def test_landing_page_renders_for_valid_slug(db_session, client):
    _make_stylist_with_slug(db_session, "gotstyles-test", "stylist-a@example.com", "GotStyles Test")

    resp = client.get("/salon/gotstyles-test")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Beauty. Brand. Business." in body
    assert "/salon/gotstyles-test/book" in body
    assert "30-Minute Consultation" in body
    assert "Dreads &amp; Locs" in body or "Dreads & Locs" in body
    assert "Wigs &amp; Units" in body or "Wigs & Units" in body


def test_landing_page_shows_address_with_directions_link(db_session, client):
    _make_stylist_with_slug(db_session, "gotstyles-addr", "stylist-addr@example.com", "GotStyles Addr",
                             address="1925 Madison Square, Suite 400, LaVergne, TN 37086")

    resp = client.get("/salon/gotstyles-addr")
    body = resp.get_data(as_text=True)
    assert "1925 Madison Square" in body
    assert "maps.google.com" in body


def test_landing_page_unknown_slug_is_404(db_session, client):
    resp = client.get("/salon/no-such-salon")
    assert resp.status_code == 404


def test_landing_page_shows_reviews_when_present(db_session, client):
    _, profile = _make_stylist_with_slug(db_session, "gotstyles-reviews", "stylist-b@example.com", "GotStyles Reviews")
    db_session.add(SalonReview(company_id=profile.company_id, stylist_id=profile.id, client_name="Happy Client",
                                rating=5, comment="Amazing silk press!"))
    db_session.commit()

    resp = client.get("/salon/gotstyles-reviews")
    body = resp.get_data(as_text=True)
    assert "Happy Client" in body
    assert "Amazing silk press!" in body


def test_booking_page_offers_both_consultation_and_standard_tracks(db_session, client):
    _, profile = _make_stylist_with_slug(db_session, "gotstyles-slots", "stylist-c@example.com", "GotStyles Slots")
    upcoming_dow = (datetime.utcnow() + timedelta(days=1)).weekday()
    _add_availability(db_session, profile, day_of_week=upcoming_dow, slot_minutes=60)

    resp = client.get("/salon/gotstyles-slots/book")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "30-Minute Consultation" in body
    assert "Full Appointment" in body
    assert _first_start(body, "consultationSlotsWrap") is not None
    assert _first_start(body, "standardSlotsWrap") is not None


def test_consultation_track_offers_finer_grained_slots_than_standard(db_session, client):
    _, profile = _make_stylist_with_slug(db_session, "gotstyles-fine", "stylist-fine@example.com", "GotStyles Fine")
    upcoming_dow = (datetime.utcnow() + timedelta(days=1)).weekday()
    _add_availability(db_session, profile, day_of_week=upcoming_dow, start=dtime(10, 0), end=dtime(12, 0), slot_minutes=60)

    resp = client.get("/salon/gotstyles-fine/book")
    body = resp.get_data(as_text=True)

    consultation_count = len(re.findall(r'data-start="[^"]+"', _extract_section(body, "consultationSlotsWrap")))
    standard_count = len(re.findall(r'data-start="[^"]+"', _extract_section(body, "standardSlotsWrap")))
    assert consultation_count > standard_count


def test_booking_page_with_no_availability_shows_empty_state(db_session, client):
    _make_stylist_with_slug(db_session, "gotstyles-empty", "stylist-d@example.com", "GotStyles Empty")

    resp = client.get("/salon/gotstyles-empty/book")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "No open times right now" in body


def test_submit_standard_booking_creates_client_and_appointment(db_session, client):
    _, profile = _make_stylist_with_slug(db_session, "gotstyles-book", "stylist-e@example.com", "GotStyles Book")
    upcoming_dow = (datetime.utcnow() + timedelta(days=1)).weekday()
    _add_availability(db_session, profile, day_of_week=upcoming_dow, slot_minutes=60)

    book_resp = client.get("/salon/gotstyles-book/book")
    starts_at = _first_start(book_resp.get_data(as_text=True), "standardSlotsWrap")
    assert starts_at

    resp = client.post("/salon/gotstyles-book/book", data={
        "starts_at": starts_at,
        "service_type": "Silk Press & Blowouts",
        "client_name": "New Client",
        "client_email": "newclient@example.com",
        "client_phone": "",
        "notes": "First visit",
    }, follow_redirects=True)

    assert resp.status_code == 200
    assert "You're Booked" in resp.get_data(as_text=True)

    appt = Appointment.query.filter_by(stylist_id=profile.id).first()
    assert appt is not None
    assert appt.service_type == "Silk Press & Blowouts"
    assert appt.duration_minutes == 60
    assert appt.confirmation_token is not None
    assert appt.status == "scheduled"

    salon_client = SalonClient.query.filter_by(stylist_id=profile.id).first()
    assert salon_client is not None
    assert salon_client.full_name == "New Client"
    assert salon_client.email == "newclient@example.com"


def test_submit_consultation_booking_uses_30_minute_duration(db_session, client):
    _, profile = _make_stylist_with_slug(db_session, "gotstyles-consult", "stylist-consult@example.com", "GotStyles Consult")
    upcoming_dow = (datetime.utcnow() + timedelta(days=1)).weekday()
    _add_availability(db_session, profile, day_of_week=upcoming_dow, slot_minutes=60)

    book_resp = client.get("/salon/gotstyles-consult/book")
    starts_at = _first_start(book_resp.get_data(as_text=True), "consultationSlotsWrap")
    assert starts_at

    resp = client.post("/salon/gotstyles-consult/book", data={
        "starts_at": starts_at,
        "service_type": "30-Minute Consultation",
        "client_name": "Consult Client",
        "client_email": "consult@example.com",
    }, follow_redirects=True)

    assert resp.status_code == 200
    appt = Appointment.query.filter_by(stylist_id=profile.id).first()
    assert appt is not None
    assert appt.service_type == "30-Minute Consultation"
    assert appt.duration_minutes == 30


def test_standard_appointment_blocks_overlapping_consultation(db_session, client):
    _, profile = _make_stylist_with_slug(db_session, "gotstyles-overlap", "stylist-overlap@example.com", "GotStyles Overlap")
    upcoming_dow = (datetime.utcnow() + timedelta(days=1)).weekday()
    _add_availability(db_session, profile, day_of_week=upcoming_dow, start=dtime(10, 0), end=dtime(14, 0), slot_minutes=60)

    book_resp = client.get("/salon/gotstyles-overlap/book")
    body = book_resp.get_data(as_text=True)
    standard_start = _first_start(body, "standardSlotsWrap")
    assert standard_start

    # Book the first standard (60-minute) slot.
    client.post("/salon/gotstyles-overlap/book", data={
        "starts_at": standard_start, "service_type": "Cuts & Styling",
        "client_name": "First Client", "client_email": "first@example.com",
    }, follow_redirects=True)

    # A consultation starting 15 minutes into that same 60-minute window
    # must be rejected -- it overlaps even though it isn't the same exact
    # start time as the standard appointment.
    overlapping_consult_start = (datetime.fromisoformat(standard_start) + timedelta(minutes=15)).isoformat()
    resp = client.post("/salon/gotstyles-overlap/book", data={
        "starts_at": overlapping_consult_start, "service_type": "30-Minute Consultation",
        "client_name": "Second Client", "client_email": "second@example.com",
    }, follow_redirects=True)

    assert Appointment.query.filter_by(stylist_id=profile.id).count() == 1
    assert "no longer available" in resp.get_data(as_text=True)


def test_consultation_immediately_after_standard_appointment_is_allowed(db_session, client):
    # Edge-touching (the consultation starts exactly when the prior
    # appointment ends) should NOT be treated as an overlap.
    _, profile = _make_stylist_with_slug(db_session, "gotstyles-edge", "stylist-edge@example.com", "GotStyles Edge")
    upcoming_dow = (datetime.utcnow() + timedelta(days=1)).weekday()
    _add_availability(db_session, profile, day_of_week=upcoming_dow, start=dtime(10, 0), end=dtime(14, 0), slot_minutes=60)

    book_resp = client.get("/salon/gotstyles-edge/book")
    standard_start = _first_start(book_resp.get_data(as_text=True), "standardSlotsWrap")

    client.post("/salon/gotstyles-edge/book", data={
        "starts_at": standard_start, "service_type": "Cuts & Styling",
        "client_name": "First Client", "client_email": "first@example.com",
    }, follow_redirects=True)

    back_to_back_start = (datetime.fromisoformat(standard_start) + timedelta(minutes=60)).isoformat()
    resp = client.post("/salon/gotstyles-edge/book", data={
        "starts_at": back_to_back_start, "service_type": "30-Minute Consultation",
        "client_name": "Second Client", "client_email": "second@example.com",
    }, follow_redirects=True)

    assert Appointment.query.filter_by(stylist_id=profile.id).count() == 2
    assert "You're Booked" in resp.get_data(as_text=True)


def test_submit_booking_reuses_existing_client_by_email(db_session, client):
    _, profile = _make_stylist_with_slug(db_session, "gotstyles-reuse", "stylist-g@example.com", "GotStyles Reuse")
    upcoming_dow = (datetime.utcnow() + timedelta(days=1)).weekday()
    _add_availability(db_session, profile, day_of_week=upcoming_dow, slot_minutes=60)

    existing_client = SalonClient(company_id=profile.company_id, stylist_id=profile.id,
                                   full_name="Returning Client", email="returning@example.com")
    db_session.add(existing_client)
    db_session.commit()

    book_resp = client.get("/salon/gotstyles-reuse/book")
    starts_at = _first_start(book_resp.get_data(as_text=True), "standardSlotsWrap")

    client.post("/salon/gotstyles-reuse/book", data={
        "starts_at": starts_at, "service_type": "Color & Balayage",
        "client_name": "Returning Client", "client_email": "returning@example.com",
    }, follow_redirects=True)

    assert SalonClient.query.filter_by(stylist_id=profile.id).count() == 1
    appt = Appointment.query.filter_by(stylist_id=profile.id).first()
    assert appt.client_id == existing_client.id


def test_booking_confirmed_page_renders(db_session, client):
    _, profile = _make_stylist_with_slug(db_session, "gotstyles-confirm", "stylist-h@example.com", "GotStyles Confirm",
                                          address="1925 Madison Square, Suite 400, LaVergne, TN 37086")
    salon_client = SalonClient(company_id=profile.company_id, stylist_id=profile.id, full_name="Confirmed Client")
    db_session.add(salon_client)
    db_session.commit()
    appt = Appointment(
        company_id=profile.company_id, stylist_id=profile.id, client_id=salon_client.id,
        service_type="Cuts & Styling", scheduled_at=datetime.utcnow() + timedelta(days=2),
        duration_minutes=60, status="scheduled", confirmation_token="abc123token",
    )
    db_session.add(appt)
    db_session.commit()

    resp = client.get(f"/salon/gotstyles-confirm/confirmed/{appt.confirmation_token}")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Confirmed Client" in body
    assert "1925 Madison Square" in body


def test_booking_confirmed_unknown_token_is_404(db_session, client):
    _make_stylist_with_slug(db_session, "gotstyles-notoken", "stylist-i@example.com", "GotStyles No Token")
    resp = client.get("/salon/gotstyles-notoken/confirmed/does-not-exist")
    assert resp.status_code == 404


def test_stylist_only_sees_own_open_slots(db_session, client):
    # Two different salons, both with availability on the same weekday --
    # confirm one stylist's booking doesn't consume the other's slot.
    _, profile_a = _make_stylist_with_slug(db_session, "gotstyles-iso-a", "stylist-j@example.com", "GotStyles Iso A")
    _, profile_b = _make_stylist_with_slug(db_session, "gotstyles-iso-b", "stylist-k@example.com", "GotStyles Iso B")
    upcoming_dow = (datetime.utcnow() + timedelta(days=1)).weekday()
    _add_availability(db_session, profile_a, day_of_week=upcoming_dow, slot_minutes=60)
    _add_availability(db_session, profile_b, day_of_week=upcoming_dow, slot_minutes=60)

    resp_a = client.get("/salon/gotstyles-iso-a/book")
    starts_at = _first_start(resp_a.get_data(as_text=True), "standardSlotsWrap")

    client.post("/salon/gotstyles-iso-a/book", data={
        "starts_at": starts_at, "service_type": "Cuts & Styling",
        "client_name": "A Client", "client_email": "aclient@example.com",
    }, follow_redirects=True)

    resp_b = client.get("/salon/gotstyles-iso-b/book")
    body_b = _extract_section(resp_b.get_data(as_text=True), "standardSlotsWrap")
    assert starts_at in body_b, "salon B's identical time slot should still be open"
