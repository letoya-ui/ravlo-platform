"""Billing-upgrade approval gate regression tests.

partners.confirm_subscription and borrower.subscription both used to apply a
paid tier / an Investor role upgrade the instant a user submitted the form --
no payment step, no admin review. Anyone could grant themselves a paid
partner tier, or a borrower could grant themselves full Investor access, for
free. These tests cover the fix: paid upgrades now queue a pending
SubscriptionRequest that only a full Ravlo admin can approve.
"""
from LoanMVP.models.admin import SubscriptionRequest, Company
from LoanMVP.models.crm_models import Partner
from LoanMVP.models.loan_models import BorrowerProfile
from LoanMVP.models.investor_models import InvestorProfile
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_partner_user(db_session, email="realtor@example.com"):
    user = User(email=email, role="partner", is_active=True)
    db_session.add(user)
    db_session.commit()
    partner = Partner(user_id=user.id, name="Test Partner", subscription_tier=None, featured=False)
    db_session.add(partner)
    db_session.commit()
    return user, partner


def _make_borrower_user(db_session, email="borrower@example.com"):
    user = User(email=email, role="borrower", is_active=True)
    db_session.add(user)
    db_session.commit()
    borrower = BorrowerProfile(user_id=user.id, full_name="Test Borrower", subscription_plan="Basic")
    db_session.add(borrower)
    db_session.commit()
    return user, borrower


def _make_full_admin(db_session, email="admin@ravlohq.com"):
    admin = User(email=email, role="executive", is_active=True)
    db_session.add(admin)
    db_session.commit()
    return admin


def test_confirm_subscription_paid_tier_creates_pending_request_not_instant_upgrade(db_session, client):
    user, partner = _make_partner_user(db_session)
    login_as(client, user)

    resp = client.post("/partners/subscribe/Premium/confirm", follow_redirects=True)

    assert resp.status_code == 200
    assert b"submitted for review" in resp.data

    db_session.refresh(partner)
    assert partner.subscription_tier == "Free"
    assert partner.featured is False

    req = SubscriptionRequest.query.filter_by(user_id=user.id, context="partner_tier").first()
    assert req is not None
    assert req.status == "pending"
    assert req.plan_requested == "Premium"


def test_confirm_subscription_free_tier_applies_immediately(db_session, client):
    user, partner = _make_partner_user(db_session, email="free-partner@example.com")
    login_as(client, user)

    resp = client.post("/partners/subscribe/Free/confirm", follow_redirects=True)

    assert resp.status_code == 200
    db_session.refresh(partner)
    assert partner.subscription_tier == "Free"
    assert SubscriptionRequest.query.filter_by(user_id=user.id, context="partner_tier").first() is None


def test_borrower_investor_upgrade_creates_pending_request_not_instant_role_change(db_session, client):
    user, borrower = _make_borrower_user(db_session)
    login_as(client, user)

    resp = client.post(
        "/borrower/subscription", data={"plan": "investor_upgrade"}, follow_redirects=True
    )

    assert resp.status_code == 200
    assert b"submitted for review" in resp.data

    db_session.refresh(user)
    assert user.role == "borrower"
    assert InvestorProfile.query.filter_by(user_id=user.id).first() is None

    req = SubscriptionRequest.query.filter_by(user_id=user.id, context="borrower_plan").first()
    assert req is not None
    assert req.status == "pending"
    assert req.plan_requested == "investor_upgrade"


def test_admin_approve_partner_tier_request_applies_tier(db_session, client):
    user, partner = _make_partner_user(db_session, email="approve-partner@example.com")
    req = SubscriptionRequest(
        user_id=user.id, plan_requested="Premium", context="partner_tier", status="pending"
    )
    db_session.add(req)
    db_session.commit()

    admin = _make_full_admin(db_session)
    login_as(client, admin)

    resp = client.post(f"/admin/subscription-requests/{req.id}/approve", follow_redirects=True)
    assert resp.status_code == 200

    db_session.refresh(partner)
    db_session.refresh(req)
    assert partner.subscription_tier == "Premium"
    assert partner.featured is True
    assert req.status == "approved"


def test_admin_approve_borrower_investor_upgrade_applies_role_change(db_session, client):
    user, borrower = _make_borrower_user(db_session, email="approve-borrower@example.com")
    req = SubscriptionRequest(
        user_id=user.id, plan_requested="investor_upgrade", context="borrower_plan", status="pending"
    )
    db_session.add(req)
    db_session.commit()

    admin = _make_full_admin(db_session, email="admin2@ravlohq.com")
    login_as(client, admin)

    resp = client.post(f"/admin/subscription-requests/{req.id}/approve", follow_redirects=True)
    assert resp.status_code == 200

    db_session.refresh(user)
    db_session.refresh(req)
    assert user.role == "investor"
    assert InvestorProfile.query.filter_by(user_id=user.id).first() is not None
    assert req.status == "approved"


def test_company_admin_cannot_approve_subscription_request(db_session, client):
    user, partner = _make_partner_user(db_session, email="blocked-partner@example.com")
    req = SubscriptionRequest(
        user_id=user.id, plan_requested="Premium", context="partner_tier", status="pending"
    )
    db_session.add(req)
    db_session.commit()

    company = Company(name="Some Licensed Co", is_active=True)
    db_session.add(company)
    db_session.commit()
    company_admin = User(
        email="company-admin@example.com", role="admin", company_id=company.id, is_active=True
    )
    db_session.add(company_admin)
    db_session.commit()
    login_as(client, company_admin)

    resp = client.post(f"/admin/subscription-requests/{req.id}/approve", follow_redirects=True)
    assert resp.status_code == 200

    db_session.refresh(partner)
    db_session.refresh(req)
    assert partner.subscription_tier == "Free"
    assert req.status == "pending"
