"""Regression tests for Ravlo's in-house demo scheduling tool (built
instead of integrating third-party Calendly, per explicit request).

Staff (executives and account executives) set a recurring weekly
DemoAvailability window; the public /demo page computes actual open
slots on the fly (template minus already-booked DemoBooking rows) so
there's no per-slot row to keep in sync. Booking creates a DemoBooking
and redirects to a confirmation page looked up by an unguessable token
rather than the sequential id, to avoid one prospect enumerating
another's booking details.
"""
from datetime import time as dtime, timedelta

from LoanMVP.models.admin import Company
from LoanMVP.models.calendar_models import DemoAvailability, DemoBooking
from LoanMVP.models.user_model import User
from LoanMVP.extensions import db
from LoanMVP.routes.scheduling import _generate_available_slots, _company_now_naive

from tests.conftest import login_as


def _make_ae(db_session, email="ae@ravlohq.com"):
    company = Company.query.filter_by(name="Ravlo").first()
    if not company:
        company = Company(name="Ravlo", is_active=True)
        db_session.add(company)
        db_session.commit()
    user = User(email=email, role="account_executive", is_active=True, company_id=company.id,
                first_name="Alex", last_name="Exec")
    db_session.add(user)
    db_session.commit()
    return user


def _make_executive(db_session, email="exec@ravlohq.com"):
    company = Company.query.filter_by(name="Ravlo").first()
    if not company:
        company = Company(name="Ravlo", is_active=True)
        db_session.add(company)
        db_session.commit()
    user = User(email=email, role="executive", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user


def _make_all_week_availability(db_session, host):
    """Wide-open availability every day of the week, so tests don't
    depend on which real-world weekday they happen to run on."""
    for day in range(7):
        db_session.add(DemoAvailability(
            host_user_id=host.id,
            day_of_week=day,
            start_time=dtime(0, 0),
            end_time=dtime(23, 45),
            slot_minutes=30,
        ))
    db_session.commit()


# ---------------------------------------------------------------------------
# Slot generation
# ---------------------------------------------------------------------------

def test_generate_available_slots_returns_slots_from_active_availability(db_session):
    host = _make_ae(db_session)
    _make_all_week_availability(db_session, host)

    slots = _generate_available_slots(days_ahead=14)

    assert len(slots) > 0
    assert all(slot["host_user_id"] == host.id for slot in slots)
    assert all(slot["start"] > _company_now_naive() for slot in slots)


def test_generate_available_slots_excludes_booked_times(db_session):
    host = _make_ae(db_session)
    _make_all_week_availability(db_session, host)

    slots_before = _generate_available_slots(days_ahead=14)
    first_slot = slots_before[0]

    db.session.add(DemoBooking(
        host_user_id=host.id,
        starts_at=first_slot["start"],
        ends_at=first_slot["end"],
        prospect_name="Existing Prospect",
        prospect_email="existing@example.com",
        status="scheduled",
    ))
    db.session.commit()

    slots_after = _generate_available_slots(days_ahead=14)
    assert first_slot["start"] not in {s["start"] for s in slots_after if s["host_user_id"] == host.id}


def test_generate_available_slots_empty_with_no_availability(db_session):
    assert _generate_available_slots(days_ahead=14) == []


# ---------------------------------------------------------------------------
# Public booking page
# ---------------------------------------------------------------------------

def test_schedule_demo_page_renders(db_session, client):
    host = _make_ae(db_session)
    _make_all_week_availability(db_session, host)

    resp = client.get("/demo")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Confirm Demo" in body


def test_book_demo_creates_booking_and_redirects_to_confirmation(db_session, client, app):
    host = _make_ae(db_session)
    _make_all_week_availability(db_session, host)
    slot = _generate_available_slots(days_ahead=14)[0]

    app.config["WTF_CSRF_ENABLED"] = False
    resp = client.post("/demo/book", data={
        "host_user_id": str(slot["host_user_id"]),
        "starts_at": slot["start"].isoformat(),
        "prospect_name": "Jamie Prospect",
        "prospect_email": "jamie@prospect.com",
        "prospect_company": "Prospect Lending",
    }, follow_redirects=False)

    assert resp.status_code == 302
    assert "/demo/confirmed/" in resp.headers["Location"]

    booking = DemoBooking.query.filter_by(prospect_email="jamie@prospect.com").first()
    assert booking is not None
    assert booking.host_user_id == host.id
    assert booking.status == "scheduled"


def test_book_demo_rejects_already_booked_slot(db_session, client, app):
    host = _make_ae(db_session)
    _make_all_week_availability(db_session, host)
    slot = _generate_available_slots(days_ahead=14)[0]

    app.config["WTF_CSRF_ENABLED"] = False
    data = {
        "host_user_id": str(slot["host_user_id"]),
        "starts_at": slot["start"].isoformat(),
        "prospect_name": "First Prospect",
        "prospect_email": "first@prospect.com",
    }
    client.post("/demo/book", data=data)

    data2 = dict(data, prospect_name="Second Prospect", prospect_email="second@prospect.com")
    client.post("/demo/book", data=data2, follow_redirects=False)

    assert DemoBooking.query.filter_by(status="scheduled").count() == 1
    assert DemoBooking.query.filter_by(prospect_email="second@prospect.com").count() == 0


def test_demo_confirmed_page_shows_booking_and_invalid_token_404s(db_session, client, app):
    host = _make_ae(db_session)
    _make_all_week_availability(db_session, host)
    slot = _generate_available_slots(days_ahead=14)[0]

    app.config["WTF_CSRF_ENABLED"] = False
    client.post("/demo/book", data={
        "host_user_id": str(slot["host_user_id"]),
        "starts_at": slot["start"].isoformat(),
        "prospect_name": "Jordan Prospect",
        "prospect_email": "jordan@prospect.com",
    })

    booking = DemoBooking.query.filter_by(prospect_email="jordan@prospect.com").first()
    resp = client.get(f"/demo/confirmed/{booking.confirmation_token}")
    assert resp.status_code == 200
    assert "Jordan Prospect" in resp.get_data(as_text=True)

    resp_bad = client.get("/demo/confirmed/not-a-real-token")
    assert resp_bad.status_code == 404


# ---------------------------------------------------------------------------
# Staff availability management
# ---------------------------------------------------------------------------

def test_ae_can_add_and_remove_own_availability(db_session, client, app):
    ae = _make_ae(db_session)
    login_as(client, ae)

    app.config["WTF_CSRF_ENABLED"] = False
    client.post("/calendar/availability", data={
        "action_type": "add",
        "day_of_week": "1",
        "start_time": "09:00",
        "end_time": "17:00",
        "slot_minutes": "30",
    })

    slot = DemoAvailability.query.filter_by(host_user_id=ae.id).first()
    assert slot is not None
    assert slot.day_of_week == 1

    client.post("/calendar/availability", data={"action_type": "delete", "slot_id": str(slot.id)})
    assert DemoAvailability.query.filter_by(id=slot.id).first() is None


def test_ae_cannot_delete_another_hosts_availability(db_session, client, app):
    ae = _make_ae(db_session)
    other_ae = _make_ae(db_session, email="other@ravlohq.com")
    _make_all_week_availability(db_session, other_ae)
    other_slot = DemoAvailability.query.filter_by(host_user_id=other_ae.id).first()

    login_as(client, ae)
    app.config["WTF_CSRF_ENABLED"] = False
    client.post("/calendar/availability", data={"action_type": "delete", "slot_id": str(other_slot.id)})

    assert DemoAvailability.query.filter_by(id=other_slot.id).first() is not None


# ---------------------------------------------------------------------------
# Company calendar visibility + cancellation
# ---------------------------------------------------------------------------

def test_company_calendar_scopes_ae_to_own_bookings(db_session, client):
    ae = _make_ae(db_session)
    other_ae = _make_ae(db_session, email="other2@ravlohq.com")

    db.session.add(DemoBooking(
        host_user_id=ae.id, starts_at=_company_now_naive() + timedelta(days=1),
        ends_at=_company_now_naive() + timedelta(days=1, minutes=30),
        prospect_name="My Prospect", prospect_email="mine@example.com", status="scheduled",
    ))
    db.session.add(DemoBooking(
        host_user_id=other_ae.id, starts_at=_company_now_naive() + timedelta(days=1),
        ends_at=_company_now_naive() + timedelta(days=1, minutes=30),
        prospect_name="Someone Elses Prospect", prospect_email="theirs@example.com", status="scheduled",
    ))
    db.session.commit()

    login_as(client, ae)
    resp = client.get("/calendar")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "My Prospect" in body
    assert "Someone Elses Prospect" not in body


def test_company_calendar_shows_all_bookings_for_executive(db_session, client):
    ae = _make_ae(db_session)
    executive = _make_executive(db_session)

    db.session.add(DemoBooking(
        host_user_id=ae.id, starts_at=_company_now_naive() + timedelta(days=1),
        ends_at=_company_now_naive() + timedelta(days=1, minutes=30),
        prospect_name="AE Prospect", prospect_email="aes@example.com", status="scheduled",
    ))
    db.session.commit()

    login_as(client, executive)
    resp = client.get("/calendar")

    assert resp.status_code == 200
    assert "AE Prospect" in resp.get_data(as_text=True)


def test_ae_cannot_cancel_another_hosts_booking(db_session, client, app):
    ae = _make_ae(db_session)
    other_ae = _make_ae(db_session, email="other3@ravlohq.com")

    booking = DemoBooking(
        host_user_id=other_ae.id, starts_at=_company_now_naive() + timedelta(days=1),
        ends_at=_company_now_naive() + timedelta(days=1, minutes=30),
        prospect_name="Protected Prospect", prospect_email="protected@example.com", status="scheduled",
    )
    db.session.add(booking)
    db.session.commit()

    login_as(client, ae)
    app.config["WTF_CSRF_ENABLED"] = False
    client.post(f"/calendar/bookings/{booking.id}/cancel")

    assert DemoBooking.query.get(booking.id).status == "scheduled"


# ---------------------------------------------------------------------------
# Discoverability: linked from the marketing site (learned from /refer)
# ---------------------------------------------------------------------------

def test_marketing_footer_links_to_schedule_demo(client):
    resp = client.get("/lending-os")
    assert resp.status_code == 200
    assert "/demo" in resp.get_data(as_text=True)


def test_lending_os_page_has_its_own_schedule_demo_cta(client):
    """Beyond the sitewide footer link, the Lending OS page itself should
    have a direct 'Schedule a Demo' call to action -- the page's own closing
    CTA copy already promised one ("request a demo") without an actual
    button pointing there."""
    resp = client.get("/lending-os")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Schedule a Demo" in body
