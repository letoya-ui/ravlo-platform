"""Regression tests for the Payments capability (Stripe Connect deposits
& invoices). Built as a reusable capability, not a per-vertical feature --
these tests deliberately exercise it from two completely separate model
trees (a VIPProfile realtor and a StylistProfile salon owner) to prove
payments_service.py's owner_type/owner_id design actually works for both,
not just the one it was first wired up for.
"""
from LoanMVP.extensions import db
from LoanMVP.models.admin import Company
from LoanMVP.models.investor_models import InvestorProfile
from LoanMVP.models.payment_models import PaymentAccount, PaymentRequest
from LoanMVP.models.salon_models import StylistProfile
from LoanMVP.models.user_model import User
from LoanMVP.models.vip_models import VIPProfile
from LoanMVP.routes.payments_routes import _handle_account_updated, _handle_checkout_completed
from LoanMVP.services.payments_service import (
    get_or_create_payment_account,
    resolve_current_owner,
)

from tests.conftest import login_as


class _StripeObj(dict):
    """Minimal stand-in for a Stripe SDK object -- real Stripe objects
    support both attribute access (account.id) and dict-style .get()."""

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item)


def _make_company(db_session, name="Test Co"):
    company = Company(name=name, is_active=True)
    db_session.add(company)
    db_session.commit()
    return company


def _make_vip_realtor(db_session, email="realtor@example.com"):
    company = _make_company(db_session, "Realtor Co")
    user = User(email=email, role="partner", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    profile = VIPProfile(
        user_id=user.id, display_name="Test Realtor", business_name="Test Realty",
        role_type="realtor", brand_color="#123456",
    )
    db_session.add(profile)
    db_session.commit()
    return user, profile


def _make_stylist(db_session, email="stylist@example.com"):
    company = _make_company(db_session, "Salon Co")
    user = User(email=email, role="stylist", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    profile = StylistProfile(
        user_id=user.id, company_id=company.id, full_name="Aisha Stylist", brand_color="#B3122A",
    )
    db_session.add(profile)
    db_session.commit()
    return user, profile


def _make_investor(db_session, email="investor@example.com"):
    company = _make_company(db_session, "Investor Co")
    user = User(email=email, role="investor", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    profile = InvestorProfile(user_id=user.id, full_name="Ivy Investor", email=email)
    db_session.add(profile)
    db_session.commit()
    return user, profile


# ─── Owner resolution ───────────────────────────────────────────────────────

def test_resolve_current_owner_for_vip_realtor(db_session, app):
    user, profile = _make_vip_realtor(db_session)
    with app.test_request_context():
        from flask_login import login_user
        login_user(user)
        owner_type, owner_id, display_name, brand_color, logo_url = resolve_current_owner(user)

    assert owner_type == "vip_profile"
    assert owner_id == profile.id
    assert display_name == "Test Realty"


def test_resolve_current_owner_for_stylist(db_session, app):
    user, profile = _make_stylist(db_session)
    with app.test_request_context():
        owner_type, owner_id, display_name, brand_color, logo_url = resolve_current_owner(user)

    assert owner_type == "stylist_profile"
    assert owner_id == profile.id
    assert display_name == "Aisha Stylist"


# ─── PaymentAccount reuse ───────────────────────────────────────────────────

def test_get_or_create_payment_account_reuses_existing_row(db_session):
    account1 = get_or_create_payment_account("stylist_profile", 42)
    account2 = get_or_create_payment_account("stylist_profile", 42)

    assert account1.id == account2.id
    assert PaymentAccount.query.filter_by(owner_type="stylist_profile", owner_id=42).count() == 1


def test_payment_accounts_do_not_bleed_across_owner_types(db_session):
    vip_account = get_or_create_payment_account("vip_profile", 1)
    stylist_account = get_or_create_payment_account("stylist_profile", 1)

    assert vip_account.id != stylist_account.id


# ─── Dashboard ──────────────────────────────────────────────────────────────

def test_dashboard_requires_login(client):
    resp = client.get("/payments/", follow_redirects=False)
    assert resp.status_code in (302, 401)


def test_dashboard_shows_connect_cta_when_not_connected(db_session, client):
    user, _ = _make_stylist(db_session, email="notconnected@example.com")
    login_as(client, user)

    resp = client.get("/payments/")

    assert resp.status_code == 200
    assert "Connect Stripe" in resp.get_data(as_text=True)


def test_dashboard_shows_connected_state(db_session, client):
    user, profile = _make_vip_realtor(db_session, email="connected@example.com")
    account = get_or_create_payment_account("vip_profile", profile.id)
    account.stripe_connect_account_id = "acct_test123"
    account.stripe_connect_charges_enabled = True
    db_session.commit()

    login_as(client, user)
    resp = client.get("/payments/")

    assert resp.status_code == 200
    assert "Stripe connected" in resp.get_data(as_text=True)


def test_dashboard_shows_investor_sidebar_not_partner_workspace_for_investor(db_session, client):
    """resolve_current_owner() learned about investor_profile owners
    (landlords connecting Stripe to collect rent), but _dashboard_chrome()
    still hardcoded portal="vip" for anyone who wasn't a stylist -- so an
    investor visiting their own Payments page got the Partner Workspace
    sidebar instead of their own Investor Portal sidebar."""
    user, _ = _make_investor(db_session, email="investor-chrome@example.com")
    login_as(client, user)

    resp = client.get("/payments/")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Investor Portal" in body
    assert "Partner Workspace" not in body


# ─── Connect onboarding ─────────────────────────────────────────────────────

def test_connect_start_creates_stripe_account_and_redirects(db_session, client, monkeypatch):
    user, profile = _make_stylist(db_session, email="onboard@example.com")
    login_as(client, user)
    client.application.config["STRIPE_SECRET_KEY"] = "sk_test_fake"

    created = {}

    def fake_account_create(**kwargs):
        created["kwargs"] = kwargs
        return _StripeObj(id="acct_new123")

    def fake_account_link_create(**kwargs):
        created["link_kwargs"] = kwargs
        return _StripeObj(url="https://connect.stripe.com/setup/fake")

    import LoanMVP.services.payments_service as svc
    monkeypatch.setattr(svc.stripe.Account, "create", fake_account_create)
    monkeypatch.setattr(svc.stripe.AccountLink, "create", fake_account_link_create)

    resp = client.get("/payments/connect/start", follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers["Location"] == "https://connect.stripe.com/setup/fake"

    account = PaymentAccount.query.filter_by(owner_type="stylist_profile", owner_id=profile.id).first()
    assert account is not None
    assert account.stripe_connect_account_id == "acct_new123"
    assert created["kwargs"]["email"] == "onboard@example.com"


def test_connect_start_surfaces_stripe_error_instead_of_crashing(db_session, client, monkeypatch):
    """A Stripe rejection during onboarding (e.g. Express not enabled on
    the platform's Connect settings) used to bubble up as an unhandled
    exception -- a generic 500 page with no clue what went wrong. It
    should instead redirect back to the dashboard with the real Stripe
    message flashed."""
    import stripe as stripe_sdk

    user, profile = _make_stylist(db_session, email="broken-onboard@example.com")
    login_as(client, user)
    client.application.config["STRIPE_SECRET_KEY"] = "sk_test_fake"

    def fake_account_create(**kwargs):
        raise stripe_sdk.error.InvalidRequestError(
            "Express accounts are not enabled for your platform.", param=None,
        )

    import LoanMVP.services.payments_service as svc
    monkeypatch.setattr(svc.stripe.Account, "create", fake_account_create)

    resp = client.get("/payments/connect/start", follow_redirects=True)

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Express accounts are not enabled" in body

    account = PaymentAccount.query.filter_by(owner_type="stylist_profile", owner_id=profile.id).first()
    assert account.stripe_connect_account_id is None


def test_connect_start_reuses_existing_stripe_account(db_session, client, monkeypatch):
    user, profile = _make_stylist(db_session, email="reuse@example.com")
    account = get_or_create_payment_account("stylist_profile", profile.id)
    account.stripe_connect_account_id = "acct_already123"
    db_session.commit()

    login_as(client, user)

    account_create_called = {"count": 0}

    import LoanMVP.services.payments_service as svc

    def fake_account_create(**kwargs):
        account_create_called["count"] += 1
        return _StripeObj(id="acct_should_not_be_used")

    monkeypatch.setattr(svc.stripe.Account, "create", fake_account_create)
    monkeypatch.setattr(
        svc.stripe.AccountLink, "create", lambda **kw: _StripeObj(url="https://connect.stripe.com/setup/fake2")
    )

    client.get("/payments/connect/start", follow_redirects=False)

    assert account_create_called["count"] == 0


def test_connect_return_syncs_status_from_stripe(db_session, client, monkeypatch):
    user, profile = _make_vip_realtor(db_session, email="return@example.com")
    account = get_or_create_payment_account("vip_profile", profile.id)
    account.stripe_connect_account_id = "acct_sync123"
    db_session.commit()

    login_as(client, user)
    client.application.config["STRIPE_SECRET_KEY"] = "sk_test_fake"

    import LoanMVP.services.payments_service as svc
    monkeypatch.setattr(
        svc.stripe.Account,
        "retrieve",
        lambda account_id: _StripeObj(id=account_id, charges_enabled=True, payouts_enabled=True),
    )

    resp = client.get("/payments/connect/return", follow_redirects=False)
    assert resp.status_code == 302

    db_session.refresh(account)
    assert account.stripe_connect_charges_enabled is True
    assert account.stripe_connect_payouts_enabled is True
    assert account.stripe_connect_onboarded_at is not None


# ─── Payment requests ───────────────────────────────────────────────────────

def test_create_request_blocked_until_connected(db_session, client):
    user, _ = _make_stylist(db_session, email="blocked@example.com")
    login_as(client, user)

    resp = client.post(
        "/payments/requests/new",
        data={"title": "Deposit", "amount": "50.00"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "Connect your Stripe account" in resp.get_data(as_text=True)
    assert PaymentRequest.query.count() == 0


def test_create_request_succeeds_once_connected(db_session, client):
    user, profile = _make_vip_realtor(db_session, email="ready@example.com")
    account = get_or_create_payment_account("vip_profile", profile.id)
    account.stripe_connect_account_id = "acct_ready123"
    account.stripe_connect_charges_enabled = True
    db_session.commit()

    login_as(client, user)

    resp = client.post(
        "/payments/requests/new",
        data={
            "title": "Listing Consult Deposit",
            "amount": "125.50",
            "client_name": "Jamie Client",
            "client_email": "jamie@example.com",
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200
    payment_request = PaymentRequest.query.filter_by(payment_account_id=account.id).first()
    assert payment_request is not None
    assert payment_request.title == "Listing Consult Deposit"
    assert payment_request.amount_cents == 12550
    assert payment_request.client_name == "Jamie Client"
    assert payment_request.confirmation_token


def test_create_request_rejects_invalid_amount(db_session, client):
    user, profile = _make_vip_realtor(db_session, email="badamount@example.com")
    account = get_or_create_payment_account("vip_profile", profile.id)
    account.stripe_connect_account_id = "acct_bad123"
    account.stripe_connect_charges_enabled = True
    db_session.commit()

    login_as(client, user)

    resp = client.post(
        "/payments/requests/new",
        data={"title": "Bad", "amount": "not-a-number"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert PaymentRequest.query.count() == 0


# ─── Public payer page ──────────────────────────────────────────────────────

def test_public_pay_page_renders_for_valid_token(db_session, client):
    _, profile = _make_stylist(db_session, email="publicpage@example.com")
    account = get_or_create_payment_account("stylist_profile", profile.id)
    account.stripe_connect_account_id = "acct_public123"
    account.stripe_connect_charges_enabled = True
    db_session.commit()

    payment_request = PaymentRequest(
        payment_account_id=account.id, title="Color Deposit", amount_cents=7500,
        confirmation_token="tok_public_abc123",
    )
    db_session.add(payment_request)
    db_session.commit()

    resp = client.get("/payments/pay/tok_public_abc123")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Color Deposit" in body
    assert "75.00" in body
    assert "Aisha Stylist" in body


def test_public_pay_page_404s_for_unknown_token(client):
    resp = client.get("/payments/pay/does-not-exist")
    assert resp.status_code == 404


def test_public_pay_checkout_creates_destination_charge_session(db_session, client, monkeypatch):
    _, profile = _make_vip_realtor(db_session, email="checkoutflow@example.com")
    account = get_or_create_payment_account("vip_profile", profile.id)
    account.stripe_connect_account_id = "acct_dest123"
    account.stripe_connect_charges_enabled = True
    db_session.commit()

    payment_request = PaymentRequest(
        payment_account_id=account.id, title="Closing Gift", amount_cents=10000,
        confirmation_token="tok_checkout_xyz",
    )
    db_session.add(payment_request)
    db_session.commit()

    captured = {}
    client.application.config["STRIPE_SECRET_KEY"] = "sk_test_fake"

    import LoanMVP.services.payments_service as svc

    def fake_session_create(**kwargs):
        captured["kwargs"] = kwargs
        return _StripeObj(id="cs_test_1", url="https://checkout.stripe.com/session1")

    monkeypatch.setattr(svc.stripe.checkout.Session, "create", fake_session_create)

    resp = client.post("/payments/pay/tok_checkout_xyz/checkout", follow_redirects=False)

    assert resp.status_code == 303
    assert resp.headers["Location"] == "https://checkout.stripe.com/session1"
    assert captured["kwargs"]["payment_intent_data"]["transfer_data"]["destination"] == "acct_dest123"

    db_session.refresh(payment_request)
    assert payment_request.stripe_checkout_session_id == "cs_test_1"


def test_public_pay_checkout_blocked_if_account_not_ready(db_session, client):
    _, profile = _make_stylist(db_session, email="notready@example.com")
    account = get_or_create_payment_account("stylist_profile", profile.id)
    db_session.commit()

    payment_request = PaymentRequest(
        payment_account_id=account.id, title="Deposit", amount_cents=5000,
        confirmation_token="tok_notready_1",
    )
    db_session.add(payment_request)
    db_session.commit()

    resp = client.post("/payments/pay/tok_notready_1/checkout", follow_redirects=True)

    assert resp.status_code == 200
    db_session.refresh(payment_request)
    assert payment_request.stripe_checkout_session_id is None


# ─── Webhook handlers ───────────────────────────────────────────────────────

def test_handle_checkout_completed_marks_request_paid(db_session):
    account = get_or_create_payment_account("stylist_profile", 999)
    payment_request = PaymentRequest(
        payment_account_id=account.id, title="Webhook Deposit", amount_cents=4000,
        confirmation_token="tok_webhook_1",
    )
    db_session.add(payment_request)
    db_session.commit()

    _handle_checkout_completed({
        "metadata": {"payment_request_id": str(payment_request.id)},
        "payment_intent": "pi_test_999",
    })

    db_session.refresh(payment_request)
    assert payment_request.status == "paid"
    assert payment_request.stripe_payment_intent_id == "pi_test_999"
    assert payment_request.paid_at is not None


def test_handle_checkout_completed_unknown_request_does_not_raise(db_session):
    _handle_checkout_completed({"metadata": {"payment_request_id": "999999"}, "payment_intent": "pi_x"})


def test_handle_account_updated_syncs_charges_and_payouts(db_session):
    account = get_or_create_payment_account("vip_profile", 555)
    account.stripe_connect_account_id = "acct_webhook_555"
    db_session.commit()

    _handle_account_updated({
        "id": "acct_webhook_555", "charges_enabled": True, "payouts_enabled": False,
    })

    db_session.refresh(account)
    assert account.stripe_connect_charges_enabled is True
    assert account.stripe_connect_payouts_enabled is False
    assert account.stripe_connect_onboarded_at is not None


def test_handle_account_updated_unknown_account_does_not_raise(db_session):
    _handle_account_updated({"id": "acct_never_seen", "charges_enabled": True})
