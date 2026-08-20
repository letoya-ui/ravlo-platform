"""Regression tests for the renter portal: invite acceptance, dashboard,
maintenance requests, and paying rent through the landlord's own Stripe
Connect account. Mirrors the ownership-scoping discipline established in
test_listing_ownership_scoping.py/test_flyers_routes.py: a renter must
never be able to see or pay another tenant's rent by guessing an id.
"""
from datetime import date
from decimal import Decimal

from LoanMVP.extensions import db
from LoanMVP.models.investor_models import InvestorProfile
from LoanMVP.models.payment_models import PaymentAccount, PaymentRequest
from LoanMVP.models.property import MaintenanceRequest, Property, PropertyUnit, RentPayment, Tenant
from LoanMVP.models.user_model import User
from LoanMVP.routes.payments_routes import _handle_checkout_completed
from LoanMVP.services.payments_service import get_or_create_payment_account, resolve_current_owner
from LoanMVP.services.renter_invite_service import build_invite_token

from tests.conftest import login_as


def _make_investor(db_session, email="landlord@example.com", full_name="Larry Landlord"):
    user = User(email=email, role="investor", is_active=True)
    db_session.add(user)
    db_session.commit()
    profile = InvestorProfile(user_id=user.id, full_name=full_name, email=email)
    db_session.add(profile)
    db_session.commit()
    return user, profile


def _make_unit_with_tenant(db_session, investor_profile, tenant_name="Rita Renter", tenant_email="rita@example.com", monthly_rent="1500"):
    prop = Property(address="1 Main St", owner_investor_id=investor_profile.id)
    db_session.add(prop)
    db_session.commit()
    unit = PropertyUnit(property_id=prop.id, unit_label="Unit A", market_rent=Decimal(monthly_rent))
    db_session.add(unit)
    db_session.commit()
    tenant = Tenant(
        unit_id=unit.id, full_name=tenant_name, email=tenant_email,
        monthly_rent=Decimal(monthly_rent), is_active=True,
    )
    db_session.add(tenant)
    db_session.commit()
    return prop, unit, tenant


def _make_renter_user(db_session, tenant, email, password="testpass123"):
    user = User(email=email, role="renter", is_active=True, onboarding_complete=True)
    user.set_password(password)
    db_session.add(user)
    db_session.commit()
    tenant.user_id = user.id
    db_session.commit()
    return user


def _connect_landlord_stripe(db_session, investor_profile, account_id="acct_landlord_ready"):
    account = get_or_create_payment_account("investor_profile", investor_profile.id)
    account.stripe_connect_account_id = account_id
    account.stripe_connect_charges_enabled = True
    db_session.commit()
    return account


class _StripeObj(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item)


# ─── Owner resolution ───────────────────────────────────────────────────────

def test_resolve_current_owner_for_investor(db_session, app):
    user, profile = _make_investor(db_session)
    with app.test_request_context():
        owner_type, owner_id, display_name, brand_color, logo_url = resolve_current_owner(user)

    assert owner_type == "investor_profile"
    assert owner_id == profile.id
    assert display_name == "Larry Landlord"


# ─── Invite acceptance ──────────────────────────────────────────────────────

def test_accept_invite_get_renders_form(db_session, client):
    _, profile = _make_investor(db_session)
    _, unit, tenant = _make_unit_with_tenant(db_session, profile)

    with client.application.test_request_context():
        token = build_invite_token(tenant.id)

    resp = client.get(f"/renter/invite/{token}")

    assert resp.status_code == 200
    assert "Rita Renter" in resp.get_data(as_text=True)


def test_accept_invite_bad_token_redirects_to_login(client):
    resp = client.get("/renter/invite/not-a-real-token", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_accept_invite_post_creates_account_links_tenant_and_logs_in(db_session, client):
    _, profile = _make_investor(db_session)
    _, unit, tenant = _make_unit_with_tenant(db_session, profile)

    with client.application.test_request_context():
        token = build_invite_token(tenant.id)

    resp = client.post(
        f"/renter/invite/{token}",
        data={
            "email": "rita@example.com",
            "password": "supersecret1",
            "confirm_password": "supersecret1",
        },
        follow_redirects=False,
    )

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/renter/dashboard")

    db_session.refresh(tenant)
    assert tenant.user_id is not None
    user = User.query.get(tenant.user_id)
    assert user.email == "rita@example.com"
    assert user.role == "renter"
    assert user.check_password("supersecret1")


def test_accept_invite_post_rejects_mismatched_passwords(db_session, client):
    _, profile = _make_investor(db_session)
    _, unit, tenant = _make_unit_with_tenant(db_session, profile)

    with client.application.test_request_context():
        token = build_invite_token(tenant.id)

    resp = client.post(
        f"/renter/invite/{token}",
        data={"email": "rita@example.com", "password": "supersecret1", "confirm_password": "different"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "do not match" in resp.get_data(as_text=True)
    db_session.refresh(tenant)
    assert tenant.user_id is None


def test_accept_invite_cannot_be_reused(db_session, client):
    _, profile = _make_investor(db_session)
    _, unit, tenant = _make_unit_with_tenant(db_session, profile)
    _make_renter_user(db_session, tenant, "rita@example.com")

    with client.application.test_request_context():
        token = build_invite_token(tenant.id)

    resp = client.get(f"/renter/invite/{token}", follow_redirects=False)

    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


# ─── Dashboard: ownership scoping ───────────────────────────────────────────

def test_dashboard_requires_login(client):
    resp = client.get("/renter/dashboard", follow_redirects=False)
    assert resp.status_code in (302, 401)


def test_dashboard_shows_only_this_tenants_rent_history(db_session, client):
    _, profile = _make_investor(db_session)
    _, unit, tenant = _make_unit_with_tenant(db_session, profile)
    renter = _make_renter_user(db_session, tenant, "rita@example.com")

    payment = RentPayment(
        unit_id=unit.id, tenant_id=tenant.id, period_month=date(2026, 8, 1),
        amount_due=Decimal("1500"), amount_paid=Decimal("0"), status="unpaid",
    )
    db_session.add(payment)
    db_session.commit()

    login_as(client, renter)
    resp = client.get("/renter/dashboard")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "August 2026" in body
    assert "1,500.00" in body or "1500.00" in body


def test_dashboard_links_to_the_ravlo_network(db_session, client):
    _, profile = _make_investor(db_session)
    _, unit, tenant = _make_unit_with_tenant(db_session, profile)
    renter = _make_renter_user(db_session, tenant, "nadia@example.com")

    login_as(client, renter)
    resp = client.get("/renter/dashboard")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert '/network/real-estate' in body


def test_dashboard_auto_posts_current_months_rent_when_none_logged(db_session, client):
    """A PM who never manually logs a charge would otherwise leave the
    tenant with nothing to pay -- the first dashboard visit should post
    the current month from the lease's monthly_rent."""
    _, profile = _make_investor(db_session)
    _, unit, tenant = _make_unit_with_tenant(db_session, profile, monthly_rent="1800")
    renter = _make_renter_user(db_session, tenant, "priya@example.com")

    login_as(client, renter)
    resp = client.get("/renter/dashboard")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "1,800.00" in body or "1800.00" in body
    assert "Pay Now" in body

    payments = RentPayment.query.filter_by(tenant_id=tenant.id).all()
    assert len(payments) == 1
    assert payments[0].period_month == date.today().replace(day=1)
    assert payments[0].amount_due == Decimal("1800")


def test_dashboard_does_not_duplicate_an_already_posted_current_month(db_session, client):
    _, profile = _make_investor(db_session)
    _, unit, tenant = _make_unit_with_tenant(db_session, profile)
    renter = _make_renter_user(db_session, tenant, "quinn@example.com")

    existing = RentPayment(
        unit_id=unit.id, tenant_id=tenant.id, period_month=date.today().replace(day=1),
        amount_due=Decimal("1500"), amount_paid=Decimal("500"), status="partial",
    )
    db_session.add(existing)
    db_session.commit()

    login_as(client, renter)
    client.get("/renter/dashboard")
    client.get("/renter/dashboard")

    payments = RentPayment.query.filter_by(tenant_id=tenant.id).all()
    assert len(payments) == 1
    assert payments[0].id == existing.id
    assert payments[0].status == "partial"


def test_dashboard_does_not_auto_post_before_lease_start(db_session, client):
    _, profile = _make_investor(db_session)
    _, unit, tenant = _make_unit_with_tenant(db_session, profile)
    tenant.lease_start = date.today().replace(year=date.today().year + 1)
    db_session.commit()
    renter = _make_renter_user(db_session, tenant, "sam@example.com")

    login_as(client, renter)
    resp = client.get("/renter/dashboard")

    assert resp.status_code == 200
    assert RentPayment.query.filter_by(tenant_id=tenant.id).count() == 0
    assert "lease starts" in resp.get_data(as_text=True)


def test_dashboard_does_not_auto_post_after_lease_end(db_session, client):
    _, profile = _make_investor(db_session)
    _, unit, tenant = _make_unit_with_tenant(db_session, profile)
    tenant.lease_end = date.today().replace(year=date.today().year - 1)
    tenant.is_active = False
    db_session.commit()
    renter = _make_renter_user(db_session, tenant, "tara@example.com")

    login_as(client, renter)
    resp = client.get("/renter/dashboard")

    assert resp.status_code == 200
    assert RentPayment.query.filter_by(tenant_id=tenant.id).count() == 0


def test_dashboard_does_not_leak_a_prior_tenants_rent_history(db_session, client):
    """The unit had a previous tenant before this one moved in -- their
    old rent payments live on the same unit_id and must not show up for
    the new tenant, who only owns their own tenant_id-scoped rows."""
    _, profile = _make_investor(db_session)
    prop, unit, old_tenant = _make_unit_with_tenant(
        db_session, profile, tenant_name="Old Tenant", tenant_email="old@example.com"
    )
    old_tenant.is_active = False
    db_session.commit()

    old_payment = RentPayment(
        unit_id=unit.id, tenant_id=old_tenant.id, period_month=date(2026, 1, 1),
        amount_due=Decimal("1400"), amount_paid=Decimal("1400"), status="paid",
    )
    db_session.add(old_payment)
    db_session.commit()

    new_tenant = Tenant(
        unit_id=unit.id, full_name="New Tenant", email="new@example.com",
        monthly_rent=Decimal("1500"), is_active=True,
    )
    db_session.add(new_tenant)
    db_session.commit()
    renter = _make_renter_user(db_session, new_tenant, "new@example.com")

    login_as(client, renter)
    resp = client.get("/renter/dashboard")

    assert resp.status_code == 200
    assert "January 2026" not in resp.get_data(as_text=True)


def test_renter_without_a_tenant_record_gets_404(db_session, client):
    user = User(email="notenant@example.com", role="renter", is_active=True, onboarding_complete=True)
    user.set_password("testpass123")
    db_session.add(user)
    db_session.commit()

    login_as(client, user)
    resp = client.get("/renter/dashboard")

    assert resp.status_code == 404


# ─── Maintenance requests ───────────────────────────────────────────────────

def test_maintenance_new_creates_a_request_scoped_to_this_tenant(db_session, client):
    _, profile = _make_investor(db_session)
    _, unit, tenant = _make_unit_with_tenant(db_session, profile)
    renter = _make_renter_user(db_session, tenant, "rita@example.com")
    login_as(client, renter)

    resp = client.post(
        "/renter/maintenance/new",
        data={"title": "Leaky faucet", "priority": "high", "description": "Kitchen sink drips."},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    req = MaintenanceRequest.query.filter_by(unit_id=unit.id).first()
    assert req is not None
    assert req.title == "Leaky faucet"
    assert req.priority == "high"
    assert req.reported_by_user_id == renter.id
    assert req.status == "open"


def test_dashboard_does_not_show_another_renters_maintenance_request(db_session, client):
    _, profile = _make_investor(db_session)
    _, unit_a, tenant_a = _make_unit_with_tenant(db_session, profile, tenant_name="A", tenant_email="a@example.com")
    _, unit_b, tenant_b = _make_unit_with_tenant(db_session, profile, tenant_name="B", tenant_email="b@example.com")
    renter_a = _make_renter_user(db_session, tenant_a, "a@example.com")
    renter_b = _make_renter_user(db_session, tenant_b, "b@example.com")

    req_b = MaintenanceRequest(
        unit_id=unit_b.id, reported_by_user_id=renter_b.id, title="B's Broken Window",
        priority="medium", status="open",
    )
    db_session.add(req_b)
    db_session.commit()

    login_as(client, renter_a)
    resp = client.get("/renter/dashboard")

    assert resp.status_code == 200
    assert "B's Broken Window" not in resp.get_data(as_text=True)


# ─── Pay rent ────────────────────────────────────────────────────────────────

def test_pay_rent_blocked_if_landlord_not_connected(db_session, client):
    _, profile = _make_investor(db_session)
    _, unit, tenant = _make_unit_with_tenant(db_session, profile)
    renter = _make_renter_user(db_session, tenant, "rita@example.com")

    payment = RentPayment(
        unit_id=unit.id, tenant_id=tenant.id, period_month=date(2026, 8, 1),
        amount_due=Decimal("1500"), amount_paid=Decimal("0"), status="unpaid",
    )
    db_session.add(payment)
    db_session.commit()

    login_as(client, renter)
    resp = client.post(f"/renter/pay/{payment.id}", follow_redirects=True)

    assert resp.status_code == 200
    assert "finished connecting their Stripe account" in resp.get_data(as_text=True)
    assert payment.payment_request_id is None


def test_pay_rent_creates_checkout_session_via_landlords_connect_account(db_session, client, monkeypatch):
    _, profile = _make_investor(db_session)
    _, unit, tenant = _make_unit_with_tenant(db_session, profile)
    renter = _make_renter_user(db_session, tenant, "rita@example.com")
    _connect_landlord_stripe(db_session, profile)

    payment = RentPayment(
        unit_id=unit.id, tenant_id=tenant.id, period_month=date(2026, 8, 1),
        amount_due=Decimal("1500"), amount_paid=Decimal("0"), status="unpaid",
    )
    db_session.add(payment)
    db_session.commit()

    client.application.config["STRIPE_SECRET_KEY"] = "sk_test_fake"
    captured = {}

    import LoanMVP.services.payments_service as svc

    def fake_session_create(**kwargs):
        captured["kwargs"] = kwargs
        return _StripeObj(id="cs_rent_1", url="https://checkout.stripe.com/rent1")

    monkeypatch.setattr(svc.stripe.checkout.Session, "create", fake_session_create)

    login_as(client, renter)
    resp = client.post(f"/renter/pay/{payment.id}", follow_redirects=False)

    assert resp.status_code == 303
    assert resp.headers["Location"] == "https://checkout.stripe.com/rent1"
    assert captured["kwargs"]["payment_intent_data"]["transfer_data"]["destination"] == "acct_landlord_ready"
    assert captured["kwargs"]["line_items"][0]["price_data"]["unit_amount"] == 150000

    db_session.refresh(payment)
    assert payment.payment_request_id is not None


def test_pay_rent_rejects_another_tenants_rent_payment(db_session, client):
    """IDOR guard: renter A must not be able to pay (or even trigger
    checkout creation for) renter B's rent period by guessing its id."""
    _, profile = _make_investor(db_session)
    _, unit_a, tenant_a = _make_unit_with_tenant(db_session, profile, tenant_name="A", tenant_email="a@example.com")
    _, unit_b, tenant_b = _make_unit_with_tenant(db_session, profile, tenant_name="B", tenant_email="b@example.com")
    renter_a = _make_renter_user(db_session, tenant_a, "a@example.com")
    _make_renter_user(db_session, tenant_b, "b@example.com")
    _connect_landlord_stripe(db_session, profile)

    payment_b = RentPayment(
        unit_id=unit_b.id, tenant_id=tenant_b.id, period_month=date(2026, 8, 1),
        amount_due=Decimal("1500"), amount_paid=Decimal("0"), status="unpaid",
    )
    db_session.add(payment_b)
    db_session.commit()

    login_as(client, renter_a)
    resp = client.post(f"/renter/pay/{payment_b.id}")

    assert resp.status_code == 404
    db_session.refresh(payment_b)
    assert payment_b.payment_request_id is None


def test_pay_rent_already_paid_is_a_no_op(db_session, client):
    _, profile = _make_investor(db_session)
    _, unit, tenant = _make_unit_with_tenant(db_session, profile)
    renter = _make_renter_user(db_session, tenant, "rita@example.com")
    _connect_landlord_stripe(db_session, profile)

    payment = RentPayment(
        unit_id=unit.id, tenant_id=tenant.id, period_month=date(2026, 8, 1),
        amount_due=Decimal("1500"), amount_paid=Decimal("1500"), status="paid",
    )
    db_session.add(payment)
    db_session.commit()

    login_as(client, renter)
    resp = client.post(f"/renter/pay/{payment.id}", follow_redirects=True)

    assert resp.status_code == 200
    assert "already paid" in resp.get_data(as_text=True)


# ─── Webhook confirmation ────────────────────────────────────────────────────

def test_checkout_completed_marks_rent_payment_paid(db_session):
    _, profile = _make_investor(db_session, email="webhooklandlord@example.com")
    _, unit, tenant = _make_unit_with_tenant(db_session, profile, tenant_email="webhookrenter@example.com")
    account = get_or_create_payment_account("investor_profile", profile.id)

    payment_request = PaymentRequest(
        payment_account_id=account.id, title="Rent — August 2026", amount_cents=150000,
        confirmation_token="tok_rent_webhook_1",
    )
    db_session.add(payment_request)
    db_session.commit()

    rent_payment = RentPayment(
        unit_id=unit.id, tenant_id=tenant.id, period_month=date(2026, 8, 1),
        amount_due=Decimal("1500"), amount_paid=Decimal("0"), status="unpaid",
        payment_request_id=payment_request.id,
    )
    db_session.add(rent_payment)
    db_session.commit()

    _handle_checkout_completed({
        "metadata": {"payment_request_id": str(payment_request.id)},
        "payment_intent": "pi_rent_test",
    })

    db_session.refresh(rent_payment)
    assert rent_payment.status == "paid"
    assert rent_payment.amount_paid == Decimal("1500")
    assert rent_payment.paid_date == date.today()
