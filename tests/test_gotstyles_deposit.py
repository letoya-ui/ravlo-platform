"""Regression tests for GotStyles' mandatory booking deposit: Aisha can
require clients to pay a deposit through her own connected Stripe account
before an online booking is confirmed ("when they schedule they have to
pay a deposit"). Reuses the existing owner-agnostic PaymentAccount/
PaymentRequest tables (payment_models.py) via payments_service.py --
StylistProfile is already a supported owner_type there -- rather than
inventing a salon-specific payment schema.
"""
import re
from datetime import datetime, time as dtime, timedelta

from LoanMVP.extensions import db, limiter
from LoanMVP.models.admin import Company
from LoanMVP.models.payment_models import PaymentRequest
from LoanMVP.models.salon_models import Appointment, SalonAvailability, SalonClient, StylistProfile
from LoanMVP.models.user_model import User
from LoanMVP.routes.payments_routes import _handle_checkout_completed
from LoanMVP.services.payments_service import get_or_create_payment_account

from tests.conftest import login_as


class _StripeObj(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item)


import pytest


@pytest.fixture(autouse=True)
def _reset_booking_rate_limit():
    limiter.reset()
    yield


def _make_stylist_with_slug(db_session, slug, email, company_name="GotStyles Deposit Co",
                             deposit_required=False, deposit_amount_cents=None):
    company = Company(name=company_name, is_active=True)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role="stylist", is_active=True, company_id=company.id,
                first_name="Aisha", last_name=slug)
    db_session.add(user)
    db_session.commit()

    profile = StylistProfile(
        user_id=user.id,
        company_id=company.id,
        full_name=company_name,
        email=email,
        public_slug=slug,
        deposit_required=deposit_required,
        deposit_amount_cents=deposit_amount_cents,
    )
    db_session.add(profile)
    db_session.commit()
    return user, profile


def _connect_stripe(db_session, profile, account_id="acct_gotstyles_test"):
    account = get_or_create_payment_account("stylist_profile", profile.id)
    account.stripe_connect_account_id = account_id
    account.stripe_connect_charges_enabled = True
    db_session.commit()
    return account


def _add_availability(db_session, profile, day_of_week, start=dtime(10, 0), end=dtime(18, 0), slot_minutes=60):
    slot = SalonAvailability(
        stylist_id=profile.id, day_of_week=day_of_week, start_time=start, end_time=end, slot_minutes=slot_minutes,
    )
    db_session.add(slot)
    db_session.commit()
    return slot


def _first_standard_start(body):
    m = re.search(r'id="standardSlotsWrap".*?data-start="([^"]+)"', body, re.DOTALL)
    return m.group(1) if m else None


# ─── Booking page notice ────────────────────────────────────────────────────

def test_booking_page_shows_deposit_notice_when_required(db_session, client):
    _, profile = _make_stylist_with_slug(
        db_session, "deposit-notice", "notice@example.com", deposit_required=True, deposit_amount_cents=5000,
    )
    upcoming_dow = (datetime.utcnow() + timedelta(days=1)).weekday()
    _add_availability(db_session, profile, day_of_week=upcoming_dow)

    resp = client.get("/salon/deposit-notice/book")
    body = resp.get_data(as_text=True)

    assert "$50.00" in body
    assert "deposit is required" in body


def test_booking_page_no_deposit_notice_when_not_required(db_session, client):
    _, profile = _make_stylist_with_slug(db_session, "no-deposit-notice", "nonotice@example.com")
    upcoming_dow = (datetime.utcnow() + timedelta(days=1)).weekday()
    _add_availability(db_session, profile, day_of_week=upcoming_dow)

    resp = client.get("/salon/no-deposit-notice/book")
    body = resp.get_data(as_text=True)

    assert "deposit is required" not in body


# ─── Submitting a booking that requires a deposit ───────────────────────────

def test_submit_booking_with_deposit_required_holds_slot_and_redirects_to_checkout(db_session, client, monkeypatch):
    _, profile = _make_stylist_with_slug(
        db_session, "deposit-checkout", "checkout@example.com", deposit_required=True, deposit_amount_cents=5000,
    )
    _connect_stripe(db_session, profile)
    upcoming_dow = (datetime.utcnow() + timedelta(days=1)).weekday()
    _add_availability(db_session, profile, day_of_week=upcoming_dow)

    book_resp = client.get("/salon/deposit-checkout/book")
    starts_at = _first_standard_start(book_resp.get_data(as_text=True))
    assert starts_at

    import LoanMVP.services.payments_service as svc
    client.application.config["STRIPE_SECRET_KEY"] = "sk_test_fake"

    captured = {}

    def fake_session_create(**kwargs):
        captured["kwargs"] = kwargs
        return _StripeObj(id="cs_deposit_1", url="https://checkout.stripe.com/deposit-session")

    monkeypatch.setattr(svc.stripe.checkout.Session, "create", fake_session_create)

    resp = client.post("/salon/deposit-checkout/book", data={
        "starts_at": starts_at,
        "service_type": "Silk Press & Blowouts",
        "client_name": "Deposit Client",
        "client_email": "depositclient@example.com",
        "client_phone": "",
    }, follow_redirects=False)

    assert resp.status_code == 303
    assert resp.headers["Location"] == "https://checkout.stripe.com/deposit-session"
    assert captured["kwargs"]["payment_intent_data"]["transfer_data"]["destination"] == "acct_gotstyles_test"
    # Stripe requires expires_at to hold the checkout open only as long as
    # the slot is held, so an abandoned session can't lock it forever.
    assert "expires_at" in captured["kwargs"]

    appt = Appointment.query.filter_by(stylist_id=profile.id).first()
    assert appt is not None
    assert appt.status == "pending_deposit"
    assert appt.payment_request_id is not None

    payment_request = PaymentRequest.query.get(appt.payment_request_id)
    assert payment_request.amount_cents == 5000
    assert payment_request.client_email == "depositclient@example.com"


def test_submit_booking_blocked_when_deposit_required_but_stripe_not_connected(db_session, client):
    _, profile = _make_stylist_with_slug(
        db_session, "deposit-notconnected", "notconnected@example.com",
        deposit_required=True, deposit_amount_cents=5000,
    )
    upcoming_dow = (datetime.utcnow() + timedelta(days=1)).weekday()
    _add_availability(db_session, profile, day_of_week=upcoming_dow)

    book_resp = client.get("/salon/deposit-notconnected/book")
    starts_at = _first_standard_start(book_resp.get_data(as_text=True))
    assert starts_at

    resp = client.post("/salon/deposit-notconnected/book", data={
        "starts_at": starts_at,
        "service_type": "Silk Press & Blowouts",
        "client_name": "Blocked Client",
        "client_email": "blocked@example.com",
    }, follow_redirects=True)

    assert resp.status_code == 200
    assert "set up yet" in resp.get_data(as_text=True)
    assert Appointment.query.filter_by(stylist_id=profile.id).count() == 0
    assert SalonClient.query.filter_by(stylist_id=profile.id).count() == 0


def test_submit_booking_without_deposit_required_is_unaffected(db_session, client):
    _, profile = _make_stylist_with_slug(db_session, "deposit-off", "depositoff@example.com")
    upcoming_dow = (datetime.utcnow() + timedelta(days=1)).weekday()
    _add_availability(db_session, profile, day_of_week=upcoming_dow)

    book_resp = client.get("/salon/deposit-off/book")
    starts_at = _first_standard_start(book_resp.get_data(as_text=True))

    resp = client.post("/salon/deposit-off/book", data={
        "starts_at": starts_at,
        "service_type": "Silk Press & Blowouts",
        "client_name": "Regular Client",
        "client_email": "regular@example.com",
    }, follow_redirects=True)

    assert resp.status_code == 200
    assert "You're Booked" in resp.get_data(as_text=True)

    appt = Appointment.query.filter_by(stylist_id=profile.id).first()
    assert appt.status == "scheduled"
    assert appt.payment_request_id is None


# ─── Slot holding for pending deposits ──────────────────────────────────────

def test_pending_deposit_appointment_blocks_its_slot(db_session, client):
    _, profile = _make_stylist_with_slug(db_session, "deposit-hold", "hold@example.com")
    upcoming_dow = (datetime.utcnow() + timedelta(days=1)).weekday()
    _add_availability(db_session, profile, day_of_week=upcoming_dow)

    book_resp = client.get("/salon/deposit-hold/book")
    starts_at = _first_standard_start(book_resp.get_data(as_text=True))
    assert starts_at

    salon_client = SalonClient(company_id=profile.company_id, stylist_id=profile.id, full_name="Holding Client")
    db_session.add(salon_client)
    db_session.commit()
    db_session.add(Appointment(
        company_id=profile.company_id, stylist_id=profile.id, client_id=salon_client.id,
        service_type="Silk Press & Blowouts", scheduled_at=datetime.fromisoformat(starts_at),
        duration_minutes=60, status="pending_deposit", confirmation_token="hold-token-1",
    ))
    db_session.commit()

    resp = client.get("/salon/deposit-hold/book")
    body = resp.get_data(as_text=True)
    assert starts_at not in body


def test_stale_pending_deposit_appointment_releases_its_slot(db_session, client):
    _, profile = _make_stylist_with_slug(db_session, "deposit-stale", "stale@example.com")
    upcoming_dow = (datetime.utcnow() + timedelta(days=1)).weekday()
    _add_availability(db_session, profile, day_of_week=upcoming_dow)

    book_resp = client.get("/salon/deposit-stale/book")
    starts_at = _first_standard_start(book_resp.get_data(as_text=True))
    assert starts_at

    salon_client = SalonClient(company_id=profile.company_id, stylist_id=profile.id, full_name="Stale Client")
    db_session.add(salon_client)
    db_session.commit()
    stale_appt = Appointment(
        company_id=profile.company_id, stylist_id=profile.id, client_id=salon_client.id,
        service_type="Silk Press & Blowouts", scheduled_at=datetime.fromisoformat(starts_at),
        duration_minutes=60, status="pending_deposit", confirmation_token="stale-token-1",
    )
    db_session.add(stale_appt)
    db_session.commit()
    # Simulate an abandoned Stripe Checkout from over 30 minutes ago.
    stale_appt.created_at = datetime.utcnow() - timedelta(minutes=45)
    db_session.commit()

    resp = client.get("/salon/deposit-stale/book")
    body = resp.get_data(as_text=True)
    assert starts_at in body


# ─── Webhook confirmation ───────────────────────────────────────────────────

def test_webhook_confirms_pending_deposit_appointment(db_session):
    _, profile = _make_stylist_with_slug(db_session, "deposit-webhook", "webhook@example.com")
    account = _connect_stripe(db_session, profile, account_id="acct_webhook_test")

    salon_client = SalonClient(company_id=profile.company_id, stylist_id=profile.id, full_name="Webhook Client",
                                email="webhookclient@example.com")
    db_session.add(salon_client)
    db_session.commit()

    payment_request = PaymentRequest(
        payment_account_id=account.id, title="Deposit -- Silk Press & Blowouts", amount_cents=5000,
        confirmation_token="tok_webhook_deposit_1",
    )
    db_session.add(payment_request)
    db_session.commit()

    appt = Appointment(
        company_id=profile.company_id, stylist_id=profile.id, client_id=salon_client.id,
        service_type="Silk Press & Blowouts", scheduled_at=datetime.utcnow() + timedelta(days=1),
        duration_minutes=60, status="pending_deposit", confirmation_token="webhook-appt-token",
        payment_request_id=payment_request.id,
    )
    db_session.add(appt)
    db_session.commit()

    _handle_checkout_completed({
        "metadata": {"payment_request_id": str(payment_request.id)},
        "payment_intent": "pi_webhook_test",
    })

    db_session.refresh(appt)
    db_session.refresh(payment_request)
    assert appt.status == "scheduled"
    assert payment_request.status == "paid"


def test_webhook_with_unrelated_payment_request_does_not_touch_appointments(db_session):
    # A payment request that isn't gating a salon booking (e.g. a plain
    # invoice) must not be mistaken for one.
    account = get_or_create_payment_account("stylist_profile", 424242)
    payment_request = PaymentRequest(
        payment_account_id=account.id, title="Unrelated Invoice", amount_cents=2000,
        confirmation_token="tok_unrelated_1",
    )
    db_session.add(payment_request)
    db_session.commit()

    _handle_checkout_completed({
        "metadata": {"payment_request_id": str(payment_request.id)},
        "payment_intent": "pi_unrelated",
    })

    db_session.refresh(payment_request)
    assert payment_request.status == "paid"


# ─── Deposit settings dashboard ─────────────────────────────────────────────

def test_stylist_can_enable_deposit_with_valid_amount(db_session, client):
    company = Company(name="Deposit Settings Co", is_active=True)
    db_session.add(company)
    db_session.commit()
    stylist = User(email="settings@example.com", role="stylist", is_active=True, company_id=company.id,
                    first_name="Aisha", last_name="Settings")
    db_session.add(stylist)
    db_session.commit()
    login_as(client, stylist)
    client.get("/stylist/dashboard")
    profile = StylistProfile.query.filter_by(user_id=stylist.id).first()

    resp = client.post("/stylist/availability", data={
        "action_type": "deposit_settings", "deposit_required": "on", "deposit_amount": "75.00",
    }, follow_redirects=False)

    assert resp.status_code == 302
    db_session.refresh(profile)
    assert profile.deposit_required is True
    assert profile.deposit_amount_cents == 7500


def test_stylist_cannot_enable_deposit_without_a_valid_amount(db_session, client):
    company = Company(name="Deposit Bad Settings Co", is_active=True)
    db_session.add(company)
    db_session.commit()
    stylist = User(email="badsettings@example.com", role="stylist", is_active=True, company_id=company.id,
                    first_name="Aisha", last_name="Bad")
    db_session.add(stylist)
    db_session.commit()
    login_as(client, stylist)
    client.get("/stylist/dashboard")
    profile = StylistProfile.query.filter_by(user_id=stylist.id).first()

    client.post("/stylist/availability", data={
        "action_type": "deposit_settings", "deposit_required": "on", "deposit_amount": "0",
    })

    db_session.refresh(profile)
    assert profile.deposit_required is False
    assert profile.deposit_amount_cents is None


def test_stylist_can_turn_off_deposit(db_session, client):
    company = Company(name="Deposit Off Co", is_active=True)
    db_session.add(company)
    db_session.commit()
    stylist = User(email="turnoff@example.com", role="stylist", is_active=True, company_id=company.id,
                    first_name="Aisha", last_name="Off")
    db_session.add(stylist)
    db_session.commit()
    login_as(client, stylist)
    client.get("/stylist/dashboard")
    profile = StylistProfile.query.filter_by(user_id=stylist.id).first()
    profile.deposit_required = True
    profile.deposit_amount_cents = 6000
    db_session.commit()

    client.post("/stylist/availability", data={"action_type": "deposit_settings"})

    db_session.refresh(profile)
    assert profile.deposit_required is False
    assert profile.deposit_amount_cents is None
