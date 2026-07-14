"""Regression tests for turning /property into a real property
management tool.

The old /property blueprint was a broken admin demo bolted onto
PropertyAnalysis (a loan-deal-underwriting scratchpad): an undefined
`assistant` name crashed every AI route, field names didn't match the
model being queried (after_repair_value/as_is_value don't exist on
PropertyAnalysis), and several routes rendered template filenames that
didn't exist (edit.html/new.html). This rebuilds the same URL space as
an investor-facing rental-portfolio tool: properties -> units -> tenants
/ rent / maintenance, scoped so an investor only sees their own
properties while Ravlo staff see everything.
"""
from datetime import date
from decimal import Decimal

from LoanMVP.models.admin import Company
from LoanMVP.models.investor_models import InvestorProfile
from LoanMVP.models.property import Property, PropertyUnit, Tenant, RentPayment, MaintenanceRequest
from LoanMVP.models.user_model import User
from LoanMVP.extensions import db

from tests.conftest import login_as


def _make_investor(db_session, email="investor@example.com"):
    company = Company.query.filter_by(name="Investor Co").first()
    if not company:
        company = Company(name="Investor Co", is_active=True)
        db_session.add(company)
        db_session.commit()

    user = User(email=email, role="investor", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    profile = InvestorProfile(user_id=user.id, full_name="Ivy Investor", email=email)
    db_session.add(profile)
    db_session.commit()
    return user, profile


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


def _make_property(db_session, owner_investor_id=None, address="123 Main St"):
    prop = Property(address=address, city="Atlanta", state="GA", owner_investor_id=owner_investor_id)
    db_session.add(prop)
    db_session.commit()
    return prop


def _make_unit(db_session, property_id, unit_label="Main Unit", market_rent="1500.00"):
    unit = PropertyUnit(property_id=property_id, unit_label=unit_label, market_rent=Decimal(market_rent))
    db_session.add(unit)
    db_session.commit()
    return unit


def test_new_property_assigns_to_current_investor(db_session, client):
    user, profile = _make_investor(db_session)
    login_as(client, user)

    resp = client.post("/property/new", data={"address": "456 Oak Ave", "city": "Marietta"}, follow_redirects=False)

    assert resp.status_code == 302
    prop = Property.query.filter_by(address="456 Oak Ave").first()
    assert prop is not None
    assert prop.owner_investor_id == profile.id


def test_investor_only_sees_own_properties(db_session, client):
    user1, profile1 = _make_investor(db_session, email="inv1@example.com")
    user2, profile2 = _make_investor(db_session, email="inv2@example.com")
    _make_property(db_session, owner_investor_id=profile1.id, address="My Property Rd")
    _make_property(db_session, owner_investor_id=profile2.id, address="Their Property Rd")

    login_as(client, user1)
    resp = client.get("/property/list")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "My Property Rd" in body
    assert "Their Property Rd" not in body


def test_staff_full_visibility_sees_all_properties(db_session, client):
    user1, profile1 = _make_investor(db_session, email="inv1b@example.com")
    user2, profile2 = _make_investor(db_session, email="inv2b@example.com")
    _make_property(db_session, owner_investor_id=profile1.id, address="Portfolio Alpha")
    _make_property(db_session, owner_investor_id=profile2.id, address="Portfolio Beta")
    executive = _make_executive(db_session)

    login_as(client, executive)
    resp = client.get("/property/list")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Portfolio Alpha" in body
    assert "Portfolio Beta" in body


def test_staff_created_property_appears_on_own_dashboard_and_list(db_session, client):
    """Staff (property/lending_admin/executive) have no InvestorProfile, so a
    property they create via /property/new gets owner_investor_id=None.
    _owned_properties_query() used to exclude NULL owner_investor_id even
    for full-visibility roles, so the property they just created vanished
    from their own dashboard/list right after creation."""
    executive = _make_executive(db_session, email="staff-creator@ravlohq.com")
    login_as(client, executive)

    resp = client.post(
        "/property/new",
        data={"address": "789 Staff Created Way", "city": "Decatur"},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    prop = Property.query.filter_by(address="789 Staff Created Way").first()
    assert prop is not None
    assert prop.owner_investor_id is None

    list_resp = client.get("/property/list")
    assert list_resp.status_code == 200
    assert "789 Staff Created Way" in list_resp.get_data(as_text=True)

    dashboard_resp = client.get("/property/dashboard")
    assert dashboard_resp.status_code == 200
    assert "789 Staff Created Way" in dashboard_resp.get_data(as_text=True)


def test_investor_cannot_view_another_investors_property(db_session, client):
    user1, profile1 = _make_investor(db_session, email="inv1c@example.com")
    user2, profile2 = _make_investor(db_session, email="inv2c@example.com")
    their_prop = _make_property(db_session, owner_investor_id=profile2.id, address="Not Yours Ln")

    login_as(client, user1)
    resp = client.get(f"/property/view/{their_prop.id}")

    assert resp.status_code == 404


def test_add_unit_to_property(db_session, client):
    user, profile = _make_investor(db_session, email="inv-unit@example.com")
    prop = _make_property(db_session, owner_investor_id=profile.id)
    login_as(client, user)

    client.post(f"/property/view/{prop.id}", data={
        "action_type": "add_unit",
        "unit_label": "Unit 1A",
        "bedrooms": "2",
        "bathrooms": "1",
        "market_rent": "1200.00",
    })

    unit = PropertyUnit.query.filter_by(property_id=prop.id).first()
    assert unit is not None
    assert unit.unit_label == "Unit 1A"
    assert unit.market_rent == Decimal("1200.00")
    assert unit.is_occupied is False


def test_add_tenant_marks_unit_occupied(db_session, client):
    user, profile = _make_investor(db_session, email="inv-tenant@example.com")
    prop = _make_property(db_session, owner_investor_id=profile.id)
    unit = _make_unit(db_session, prop.id)
    login_as(client, user)

    client.post(f"/property/unit/{unit.id}", data={
        "action_type": "add_tenant",
        "full_name": "Terry Tenant",
        "email": "terry@example.com",
        "monthly_rent": "1500.00",
        "lease_start": "2026-01-01",
        "lease_end": "2026-12-31",
    })

    updated_unit = PropertyUnit.query.get(unit.id)
    assert updated_unit.is_occupied is True
    assert updated_unit.active_tenant.full_name == "Terry Tenant"


def test_end_tenancy_marks_unit_vacant(db_session, client):
    user, profile = _make_investor(db_session, email="inv-end@example.com")
    prop = _make_property(db_session, owner_investor_id=profile.id)
    unit = _make_unit(db_session, prop.id)
    tenant = Tenant(unit_id=unit.id, full_name="Leaving Tenant", is_active=True)
    db_session.add(tenant)
    db_session.commit()
    login_as(client, user)

    client.post(f"/property/unit/{unit.id}", data={"action_type": "end_tenancy", "tenant_id": str(tenant.id)})

    assert PropertyUnit.query.get(unit.id).is_occupied is False
    assert Tenant.query.get(tenant.id).is_active is False


def test_log_rent_payment_auto_computes_paid_status(db_session, client):
    user, profile = _make_investor(db_session, email="inv-rent@example.com")
    prop = _make_property(db_session, owner_investor_id=profile.id)
    unit = _make_unit(db_session, prop.id)
    login_as(client, user)

    client.post(f"/property/unit/{unit.id}", data={
        "action_type": "log_rent_payment",
        "period_month": "2026-07-01",
        "amount_due": "1500.00",
        "amount_paid": "1500.00",
    })

    payment = RentPayment.query.filter_by(unit_id=unit.id).first()
    assert payment is not None
    assert payment.status == "paid"
    assert payment.amount_paid == Decimal("1500.00")


def test_log_rent_payment_auto_computes_partial_status(db_session, client):
    user, profile = _make_investor(db_session, email="inv-partial@example.com")
    prop = _make_property(db_session, owner_investor_id=profile.id)
    unit = _make_unit(db_session, prop.id)
    login_as(client, user)

    client.post(f"/property/unit/{unit.id}", data={
        "action_type": "log_rent_payment",
        "period_month": "2026-07-01",
        "amount_due": "1500.00",
        "amount_paid": "500.00",
    })

    payment = RentPayment.query.filter_by(unit_id=unit.id).first()
    assert payment.status == "partial"


def test_maintenance_request_resolve_with_cost(db_session, client):
    user, profile = _make_investor(db_session, email="inv-maint@example.com")
    prop = _make_property(db_session, owner_investor_id=profile.id)
    unit = _make_unit(db_session, prop.id)
    login_as(client, user)

    client.post(f"/property/unit/{unit.id}", data={
        "action_type": "add_maintenance_request",
        "title": "Leaky faucet",
        "priority": "high",
        "description": "Kitchen sink is leaking",
    })
    req = MaintenanceRequest.query.filter_by(unit_id=unit.id).first()
    assert req.status == "open"

    client.post(f"/property/unit/{unit.id}", data={
        "action_type": "update_maintenance_status",
        "request_id": str(req.id),
        "status": "resolved",
        "actual_cost": "150.00",
    })

    updated_req = MaintenanceRequest.query.get(req.id)
    assert updated_req.status == "resolved"
    assert updated_req.actual_cost == Decimal("150.00")
    assert updated_req.resolved_at is not None


def test_dashboard_cash_flow_rollup(db_session, client):
    user, profile = _make_investor(db_session, email="inv-dash@example.com")
    prop = _make_property(db_session, owner_investor_id=profile.id)
    unit = _make_unit(db_session, prop.id)

    payment = RentPayment(unit_id=unit.id, period_month=date(2026, 7, 1), amount_due=Decimal("1500.00"), amount_paid=Decimal("1500.00"), status="paid")
    db_session.add(payment)
    req = MaintenanceRequest(unit_id=unit.id, title="Repair", status="resolved", actual_cost=Decimal("200.00"))
    db_session.add(req)
    db_session.commit()

    login_as(client, user)
    resp = client.get("/property/dashboard")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "1500.00" in body
    assert "1300.00" in body  # net cash flow = 1500 - 200


def test_legacy_manage_route_redirects_to_dashboard(db_session, client):
    user, profile = _make_investor(db_session, email="inv-legacy@example.com")
    login_as(client, user)

    resp = client.get("/property/manage", follow_redirects=False)

    assert resp.status_code == 302
    assert "/property/dashboard" in resp.headers["Location"]
