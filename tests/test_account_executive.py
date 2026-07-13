"""Regression tests for the Account Executive Lending OS licensing system.

Account executives work a deal pipeline (built on the existing
BusinessInquiry "license_application" rows, not a new table) toward
licensing out Ravlo Lending OS to prospective lending companies: pipeline
stage, contract terms, and commission tracking. Marking a deal "signed"
here is deliberately NOT wired to auto-create a Company -- a Ravlo admin
still does that manually via the pre-existing admin.py licensing
applications workflow, and the deal is linked to the resulting Company
afterward for commission/reporting purposes.
"""
from decimal import Decimal

from LoanMVP.models.admin import BusinessInquiry, Company
from LoanMVP.models.user_model import User
from LoanMVP.extensions import db

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


def _make_deal(db_session, assigned_ae_id=None, company_name="Prospect Lending Co"):
    deal = BusinessInquiry(
        inquiry_type="license_application",
        company_name=company_name,
        contact_name="Pat Prospect",
        email="pat@prospectlending.com",
        status="new",
        assigned_ae_id=assigned_ae_id,
        ae_stage="prospect",
    )
    db_session.add(deal)
    db_session.commit()
    return deal


def test_ae_sidebar_shows_deal_pipeline(db_session, client):
    ae = _make_ae(db_session)
    login_as(client, ae)

    resp = client.get("/account-executive/dashboard")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Deal Pipeline" in body
    assert "/account-executive/deals" in body


def test_ae_only_sees_own_deals(db_session, client):
    ae1 = _make_ae(db_session, email="ae1@ravlohq.com")
    ae2 = _make_ae(db_session, email="ae2@ravlohq.com")
    my_deal = _make_deal(db_session, assigned_ae_id=ae1.id, company_name="My Deal Co")
    _make_deal(db_session, assigned_ae_id=ae2.id, company_name="Their Deal Co")

    login_as(client, ae1)
    resp = client.get("/account-executive/deals")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "My Deal Co" in body
    assert "Their Deal Co" not in body


def test_executive_sees_all_ae_deals(db_session, client):
    ae1 = _make_ae(db_session, email="ae1b@ravlohq.com")
    ae2 = _make_ae(db_session, email="ae2b@ravlohq.com")
    _make_deal(db_session, assigned_ae_id=ae1.id, company_name="Deal Alpha")
    _make_deal(db_session, assigned_ae_id=ae2.id, company_name="Deal Beta")
    executive = _make_executive(db_session)

    login_as(client, executive)
    resp = client.get("/account-executive/deals")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Deal Alpha" in body
    assert "Deal Beta" in body


def test_ae_cannot_view_another_aes_deal_directly(db_session, client):
    ae1 = _make_ae(db_session, email="ae1c@ravlohq.com")
    ae2 = _make_ae(db_session, email="ae2c@ravlohq.com")
    their_deal = _make_deal(db_session, assigned_ae_id=ae2.id, company_name="Not Yours Co")

    login_as(client, ae1)
    resp = client.get(f"/account-executive/deals/{their_deal.id}", follow_redirects=False)

    assert resp.status_code == 302
    assert "/account-executive/deals" in resp.headers["Location"]


def test_new_deal_auto_assigns_to_creating_ae(db_session, client):
    ae = _make_ae(db_session, email="ae-new@ravlohq.com")
    login_as(client, ae)

    resp = client.post("/account-executive/deals/new", data={
        "company_name": "New Prospect Co",
        "contact_name": "Casey Contact",
        "email": "casey@newprospect.com",
    }, follow_redirects=False)

    assert resp.status_code == 302
    deal = BusinessInquiry.query.filter_by(company_name="New Prospect Co").first()
    assert deal is not None
    assert deal.assigned_ae_id == ae.id
    assert deal.ae_stage == "prospect"
    assert deal.inquiry_type == "license_application"


def test_claim_unassigned_deal(db_session, client):
    ae = _make_ae(db_session, email="ae-claim@ravlohq.com")
    deal = _make_deal(db_session, assigned_ae_id=None, company_name="Unassigned Co")

    login_as(client, ae)
    client.post(f"/account-executive/deals/{deal.id}", data={"action_type": "claim"})

    updated = BusinessInquiry.query.get(deal.id)
    assert updated.assigned_ae_id == ae.id


def test_mark_signed_computes_commission(db_session, client):
    ae = _make_ae(db_session, email="ae-sign@ravlohq.com")
    deal = _make_deal(db_session, assigned_ae_id=ae.id, company_name="Signing Co")

    login_as(client, ae)
    client.post(f"/account-executive/deals/{deal.id}", data={
        "action_type": "update_stage",
        "ae_stage": "signed",
        "contract_value": "10000",
        "commission_rate": "0.10",
        "billing_cycle": "annual",
    })

    updated = BusinessInquiry.query.get(deal.id)
    assert updated.ae_stage == "signed"
    assert updated.contract_value == Decimal("10000")
    assert updated.commission_amount == Decimal("1000.00")
    assert updated.commission_status == "pending"
    assert updated.signed_at is not None


def test_link_company_requires_full_visibility(db_session, client):
    ae = _make_ae(db_session, email="ae-link@ravlohq.com")
    deal = _make_deal(db_session, assigned_ae_id=ae.id, company_name="Link Me Co")
    company = Company(name="Linked Company LLC", is_active=True)
    db_session.add(company)
    db_session.commit()

    login_as(client, ae)
    resp = client.get(f"/account-executive/deals/{deal.id}")
    assert "Linked Company LLC" not in resp.get_data(as_text=True)

    executive = _make_executive(db_session, email="exec-link@ravlohq.com")
    login_as(client, executive)
    client.post(f"/account-executive/deals/{deal.id}", data={
        "action_type": "link_company",
        "company_id": str(company.id),
    })

    updated = BusinessInquiry.query.get(deal.id)
    assert updated.linked_company_id == company.id


def test_ae_cannot_mark_own_commission_paid(db_session, client):
    ae = _make_ae(db_session, email="ae-paid@ravlohq.com")
    deal = _make_deal(db_session, assigned_ae_id=ae.id, company_name="Paid Co")
    deal.ae_stage = "signed"
    deal.commission_amount = Decimal("500.00")
    deal.commission_status = "pending"
    db_session.commit()

    login_as(client, ae)
    client.post(f"/account-executive/deals/{deal.id}", data={"action_type": "mark_commission_paid"})

    updated = BusinessInquiry.query.get(deal.id)
    assert updated.commission_status == "pending"


def test_executive_can_mark_commission_paid(db_session, client):
    ae = _make_ae(db_session, email="ae-paid2@ravlohq.com")
    deal = _make_deal(db_session, assigned_ae_id=ae.id, company_name="Paid Co 2")
    deal.ae_stage = "signed"
    deal.commission_amount = Decimal("500.00")
    deal.commission_status = "pending"
    db_session.commit()

    executive = _make_executive(db_session, email="exec-paid@ravlohq.com")
    login_as(client, executive)
    client.post(f"/account-executive/deals/{deal.id}", data={"action_type": "mark_commission_paid"})

    updated = BusinessInquiry.query.get(deal.id)
    assert updated.commission_status == "paid"


def test_new_ae_columns_default_safely_for_existing_admin_workflow(db_session, client):
    """The existing admin licensing_applications approve/decline flow only
    ever touches `status` -- confirm the new AE columns don't break that
    row's basic lifecycle (nullable, no NOT NULL surprises)."""
    deal = BusinessInquiry(
        inquiry_type="license_application",
        company_name="Untouched By AE Co",
        contact_name="Original Flow",
        email="original@flow.com",
        status="new",
    )
    db_session.add(deal)
    db_session.commit()

    assert deal.assigned_ae_id is None
    assert deal.linked_company_id is None
    assert deal.commission_amount is None

    deal.status = "approved"
    db_session.commit()
    assert BusinessInquiry.query.get(deal.id).status == "approved"
