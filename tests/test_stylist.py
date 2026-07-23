"""Regression tests for the Stylist role -- the GotStyles Beauty / salon
vertical's "core dashboard" slice: real StylistProfile/SalonClient/
Appointment/etc. rows, scoped per-stylist the same way LoanOfficerProfile
scopes per-officer.
"""
from datetime import datetime, timedelta
from decimal import Decimal

from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User
from LoanMVP.models.salon_models import (
    StylistProfile,
    SalonClient,
    Appointment,
    ClientFormula,
    ClientPhoto,
    ProductSale,
    SalonReview,
    LoyaltyTransaction,
    SalonAvailability,
)
from LoanMVP.extensions import db

from tests.conftest import login_as


def _make_company(db_session, name):
    company = Company.query.filter_by(name=name).first()
    if not company:
        company = Company(name=name, is_active=True)
        db_session.add(company)
        db_session.commit()
    return company


def _make_stylist(db_session, email="stylist@gotstylesbeauty.com", company_name="GotStyles Beauty"):
    company = _make_company(db_session, company_name)
    user = User(email=email, role="stylist", is_active=True, company_id=company.id,
                first_name="Sam", last_name="Stylist")
    db_session.add(user)
    db_session.commit()
    return user


def _make_client(db_session, profile, full_name="Casey Client"):
    client = SalonClient(company_id=profile.company_id, stylist_id=profile.id, full_name=full_name)
    db_session.add(client)
    db_session.commit()
    return client


def test_dashboard_creates_stylist_profile_and_renders(db_session, client):
    stylist = _make_stylist(db_session)
    login_as(client, stylist)

    resp = client.get("/stylist/dashboard")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Today" in body or "Appointments" in body
    profile = StylistProfile.query.filter_by(user_id=stylist.id).first()
    assert profile is not None
    assert profile.company_id == stylist.company_id


def test_new_client_is_scoped_to_creating_stylist(db_session, client):
    stylist = _make_stylist(db_session, email="stylist-new@gotstylesbeauty.com")
    login_as(client, stylist)
    client.get("/stylist/dashboard")
    profile = StylistProfile.query.filter_by(user_id=stylist.id).first()

    resp = client.post("/stylist/clients", data={
        "full_name": "New Client Co",
        "email": "newclient@example.com",
        "phone": "555-1234",
    }, follow_redirects=False)

    assert resp.status_code == 302
    created = SalonClient.query.filter_by(full_name="New Client Co").first()
    assert created is not None
    assert created.stylist_id == profile.id
    assert created.company_id == profile.company_id


def test_new_appointment_created_for_client(db_session, client):
    stylist = _make_stylist(db_session, email="stylist-appt@gotstylesbeauty.com")
    login_as(client, stylist)
    client.get("/stylist/dashboard")
    profile = StylistProfile.query.filter_by(user_id=stylist.id).first()
    salon_client = _make_client(db_session, profile, full_name="Appt Client")

    scheduled_at = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
    resp = client.post("/stylist/appointments", data={
        "client_id": str(salon_client.id),
        "service_type": "Silk Press",
        "scheduled_at": scheduled_at,
        "duration_minutes": "90",
        "price": "125.00",
    }, follow_redirects=False)

    assert resp.status_code == 302
    appt = Appointment.query.filter_by(client_id=salon_client.id).first()
    assert appt is not None
    assert appt.service_type == "Silk Press"
    assert appt.stylist_id == profile.id
    assert appt.price == Decimal("125.00")


def test_stylist_only_sees_own_clients(db_session, client):
    # NOTE: only one login happens in this test (Flask-Login's per-request
    # user cache lives on `g`, which is bound to the test's outer app
    # context and does not reset between requests within a single test
    # function -- so a second `login_as` call here would not actually
    # switch identity). The other salon's data is created directly via
    # the ORM instead, mirroring test_account_executive.py's
    # test_ae_only_sees_own_deals.
    stylist_a = _make_stylist(db_session, email="stylist-a@salon-a.com", company_name="Salon A")
    stylist_b = _make_stylist(db_session, email="stylist-b@salon-b.com", company_name="Salon B")

    login_as(client, stylist_a)
    client.get("/stylist/dashboard")
    profile_a = StylistProfile.query.filter_by(user_id=stylist_a.id).first()
    _make_client(db_session, profile_a, full_name="Salon A Client")

    profile_b = StylistProfile(user_id=stylist_b.id, company_id=stylist_b.company_id, full_name="B Sty")
    db_session.add(profile_b)
    db_session.commit()
    _make_client(db_session, profile_b, full_name="Salon B Client")

    resp = client.get("/stylist/clients")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Salon A Client" in body
    assert "Salon B Client" not in body


def test_stylist_cannot_view_another_stylists_client_detail(db_session, client):
    stylist_a = _make_stylist(db_session, email="stylist-c@salon-c.com", company_name="Salon C")
    stylist_b = _make_stylist(db_session, email="stylist-d@salon-d.com", company_name="Salon D")

    profile_b = StylistProfile(user_id=stylist_b.id, company_id=stylist_b.company_id, full_name="D Sty")
    db_session.add(profile_b)
    db_session.commit()
    their_client = _make_client(db_session, profile_b, full_name="Not Yours")

    login_as(client, stylist_a)
    client.get("/stylist/dashboard")
    resp = client.get(f"/stylist/clients/{their_client.id}")

    assert resp.status_code == 404


def test_appointment_completion_updates_client_last_visit(db_session, client):
    stylist = _make_stylist(db_session, email="stylist-complete@gotstylesbeauty.com")
    login_as(client, stylist)
    client.get("/stylist/dashboard")
    profile = StylistProfile.query.filter_by(user_id=stylist.id).first()
    salon_client = _make_client(db_session, profile, full_name="Completion Client")
    appt = Appointment(
        company_id=profile.company_id,
        stylist_id=profile.id,
        client_id=salon_client.id,
        service_type="Color",
        scheduled_at=datetime.utcnow() - timedelta(hours=1),
        status="scheduled",
    )
    db_session.add(appt)
    db_session.commit()

    client.post(f"/stylist/appointments/{appt.id}/status", data={"status": "completed"})

    updated = db.session.get(Appointment, appt.id)
    assert updated.status == "completed"
    refreshed_client = db.session.get(SalonClient, salon_client.id)
    assert refreshed_client.last_visit_at == updated.scheduled_at


def test_formula_photo_sale_review_loyalty_flows(db_session, client):
    stylist = _make_stylist(db_session, email="stylist-flows@gotstylesbeauty.com")
    login_as(client, stylist)
    client.get("/stylist/dashboard")
    profile = StylistProfile.query.filter_by(user_id=stylist.id).first()
    salon_client = _make_client(db_session, profile, full_name="Flows Client")

    client.post("/stylist/formulas", data={
        "client_id": str(salon_client.id), "title": "Balayage - Level 8", "notes": "20 vol, 45 min",
    })
    assert ClientFormula.query.filter_by(client_id=salon_client.id).count() == 1

    client.post("/stylist/photos", data={
        "client_id": str(salon_client.id), "photo_type": "after", "image_url": "https://example.com/a.jpg",
    })
    assert ClientPhoto.query.filter_by(client_id=salon_client.id).count() == 1

    client.post("/stylist/product-sales", data={
        "product_name": "Shampoo", "client_id": str(salon_client.id), "quantity": "2", "unit_price": "15.00",
    })
    sale = ProductSale.query.filter_by(client_id=salon_client.id).first()
    assert sale is not None
    assert sale.total == Decimal("30.00")

    client.post("/stylist/reviews", data={
        "client_name": "Flows Client", "rating": "5", "source": "google", "comment": "Great!",
    })
    assert SalonReview.query.filter_by(stylist_id=profile.id).count() == 1

    client.post("/stylist/loyalty", data={
        "client_id": str(salon_client.id), "points": "50", "reason": "Visit",
    })
    refreshed_client = db.session.get(SalonClient, salon_client.id)
    assert refreshed_client.loyalty_points == 50
    assert LoyaltyTransaction.query.filter_by(client_id=salon_client.id).count() == 1


def test_availability_add_and_delete(db_session, client):
    stylist = _make_stylist(db_session, email="stylist-avail@gotstylesbeauty.com")
    login_as(client, stylist)
    client.get("/stylist/dashboard")
    profile = StylistProfile.query.filter_by(user_id=stylist.id).first()

    resp = client.post("/stylist/availability", data={
        "action_type": "add", "day_of_week": "1", "start_time": "10:00", "end_time": "18:00", "slot_minutes": "60",
    }, follow_redirects=False)
    assert resp.status_code == 302

    slot = SalonAvailability.query.filter_by(stylist_id=profile.id).first()
    assert slot is not None
    assert slot.day_of_week == 1
    assert slot.slot_minutes == 60

    client.post("/stylist/availability", data={"action_type": "delete", "slot_id": str(slot.id)})
    assert SalonAvailability.query.filter_by(stylist_id=profile.id).count() == 0


def test_availability_rejects_invalid_time_range(db_session, client):
    stylist = _make_stylist(db_session, email="stylist-avail-bad@gotstylesbeauty.com")
    login_as(client, stylist)
    client.get("/stylist/dashboard")
    profile = StylistProfile.query.filter_by(user_id=stylist.id).first()

    client.post("/stylist/availability", data={
        "action_type": "add", "day_of_week": "1", "start_time": "18:00", "end_time": "10:00", "slot_minutes": "60",
    })
    assert SalonAvailability.query.filter_by(stylist_id=profile.id).count() == 0


def test_stylist_cannot_delete_another_stylists_availability(db_session, client):
    # Only one login in this test -- see test_stylist_only_sees_own_clients
    # above for why a second login_as() call wouldn't actually switch
    # identity within a single test function. Salon B's profile/slot are
    # created directly via the ORM instead.
    stylist_a = _make_stylist(db_session, email="stylist-avail-a@salon-a.com", company_name="Salon Avail A")
    stylist_b = _make_stylist(db_session, email="stylist-avail-b@salon-b.com", company_name="Salon Avail B")

    profile_b = StylistProfile(user_id=stylist_b.id, company_id=stylist_b.company_id, full_name="B Sty")
    db_session.add(profile_b)
    db_session.commit()
    their_slot = SalonAvailability(stylist_id=profile_b.id, day_of_week=2,
                                    start_time=datetime.strptime("10:00", "%H:%M").time(),
                                    end_time=datetime.strptime("18:00", "%H:%M").time(), slot_minutes=60)
    db_session.add(their_slot)
    db_session.commit()

    login_as(client, stylist_a)
    client.get("/stylist/dashboard")
    client.post("/stylist/availability", data={"action_type": "delete", "slot_id": str(their_slot.id)})

    assert SalonAvailability.query.filter_by(stylist_id=profile_b.id).count() == 1
