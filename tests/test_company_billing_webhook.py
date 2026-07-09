"""Company (Lending OS tenant) Stripe billing regression tests.

Company.subscription_tier/max_users/billing_status/grace_period_ends_at
used to be set only by hand (an admin approving onboarding) -- Stripe never
touched the Company model at all, even though a real checkout flow existed
for individual users and partners. These tests cover the fix: a company
Stripe Checkout completing activates the right plan/seats, a failed renewal
starts a grace period, a successful renewal clears it, and a full
cancellation deactivates the company.
"""
from datetime import datetime, timedelta

from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User
from LoanMVP.routes.billing_webhook import (
    _handle_checkout_completed,
    _handle_invoice_payment_failed,
    _handle_invoice_payment_succeeded,
    _handle_subscription_deleted,
    _handle_subscription_updated,
    COMPANY_GRACE_PERIOD_DAYS,
)

from tests.conftest import login_as


def _make_company(db_session, **kwargs):
    defaults = dict(name="Test Lending Co", is_active=True, subscription_tier="team", max_users=10)
    defaults.update(kwargs)
    company = Company(**defaults)
    db_session.add(company)
    db_session.commit()
    return company


def _make_company_admin(db_session, company, email="companyadmin@example.com"):
    user = User(email=email, role="admin", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user


def _make_full_admin(db_session, email="ravlo-admin@ravlohq.com"):
    admin = User(email=email, role="executive", is_active=True)
    db_session.add(admin)
    db_session.commit()
    return admin


def test_checkout_completed_activates_company_plan_and_seats(db_session):
    company = _make_company(db_session, subscription_tier=None, max_users=None, billing_status="active")

    _handle_checkout_completed({
        "metadata": {"company_id": str(company.id), "company_plan": "team"},
        "customer": "cus_test123",
    })

    db_session.refresh(company)
    assert company.subscription_tier == "team"
    assert company.max_users == 10
    assert company.is_active is True
    assert company.billing_status == "active"
    assert company.stripe_customer_id == "cus_test123"


def test_checkout_completed_unknown_company_does_not_raise(db_session):
    # Should log and return quietly, not crash the webhook.
    _handle_checkout_completed({
        "metadata": {"company_id": "999999", "company_plan": "team"},
        "customer": "cus_test999",
    })


def test_invoice_payment_failed_starts_grace_period(db_session):
    company = _make_company(db_session, stripe_customer_id="cus_pastdue1", billing_status="active")

    _handle_invoice_payment_failed({"customer": "cus_pastdue1"})

    db_session.refresh(company)
    assert company.billing_status == "past_due"
    assert company.grace_period_ends_at is not None
    expected = datetime.utcnow() + timedelta(days=COMPANY_GRACE_PERIOD_DAYS)
    assert abs((company.grace_period_ends_at - expected).total_seconds()) < 60
    # Not deactivated immediately -- grace period is still running.
    assert company.is_active is True


def test_invoice_payment_succeeded_clears_past_due_on_renewal(db_session):
    company = _make_company(
        db_session,
        stripe_customer_id="cus_renew1",
        billing_status="past_due",
        grace_period_ends_at=datetime.utcnow() + timedelta(days=2),
        is_active=False,
    )

    _handle_invoice_payment_succeeded({
        "customer": "cus_renew1",
        "billing_reason": "subscription_cycle",
    })

    db_session.refresh(company)
    assert company.billing_status == "active"
    assert company.grace_period_ends_at is None
    assert company.is_active is True


def test_invoice_payment_succeeded_ignores_initial_checkout_invoice(db_session):
    company = _make_company(
        db_session,
        stripe_customer_id="cus_initial1",
        billing_status="past_due",
        grace_period_ends_at=datetime.utcnow() + timedelta(days=2),
    )

    _handle_invoice_payment_succeeded({
        "customer": "cus_initial1",
        "billing_reason": "subscription_create",
    })

    db_session.refresh(company)
    # Untouched -- this handler only acts on renewal invoices.
    assert company.billing_status == "past_due"


def test_subscription_deleted_deactivates_company(db_session):
    company = _make_company(db_session, stripe_customer_id="cus_cancel1", billing_status="past_due")

    _handle_subscription_deleted({"customer": "cus_cancel1", "metadata": {}})

    db_session.refresh(company)
    assert company.billing_status == "canceled"
    assert company.is_active is False
    assert company.grace_period_ends_at is None


def test_subscription_updated_reactivates_after_past_due_renewal(db_session):
    company = _make_company(
        db_session,
        stripe_customer_id="cus_sub_update1",
        billing_status="past_due",
        grace_period_ends_at=datetime.utcnow() + timedelta(days=1),
    )

    _handle_subscription_updated({
        "customer": "cus_sub_update1",
        "status": "active",
        "metadata": {},
    })

    db_session.refresh(company)
    assert company.billing_status == "active"
    assert company.grace_period_ends_at is None


def test_is_billing_current():
    active = Company(name="A", billing_status="active")
    assert active.is_billing_current() is True

    past_due_in_grace = Company(
        name="B", billing_status="past_due",
        grace_period_ends_at=datetime.utcnow() + timedelta(days=1),
    )
    assert past_due_in_grace.is_billing_current() is True

    past_due_expired = Company(
        name="C", billing_status="past_due",
        grace_period_ends_at=datetime.utcnow() - timedelta(days=1),
    )
    assert past_due_expired.is_billing_current() is False

    canceled = Company(name="D", billing_status="canceled")
    assert canceled.is_billing_current() is False


def test_company_billing_page_denies_other_companys_admin(db_session, client):
    company_a = _make_company(db_session, name="Company A")
    company_b = _make_company(db_session, name="Company B")
    outsider_admin = _make_company_admin(db_session, company_b, email="outsider@example.com")
    login_as(client, outsider_admin)

    resp = client.get(f"/admin/company/{company_a.id}/billing", follow_redirects=True)

    assert resp.status_code == 200
    assert b"do not have access" in resp.data


def test_company_billing_page_allows_own_company_admin(db_session, client):
    company = _make_company(db_session)
    admin = _make_company_admin(db_session, company)
    login_as(client, admin)

    resp = client.get(f"/admin/company/{company.id}/billing")

    assert resp.status_code == 200


def test_company_billing_checkout_rejects_custom_quote_plan(db_session, client):
    company = _make_company(db_session, subscription_tier="lender", max_users=50)
    admin = _make_company_admin(db_session, company)
    login_as(client, admin)

    resp = client.get(
        f"/admin/company/{company.id}/billing/checkout/lender", follow_redirects=True
    )

    assert resp.status_code == 200
    assert b"Contact us" in resp.data
