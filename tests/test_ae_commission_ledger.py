"""Regression tests for the AE commission ledger: setup-fee commission
pays out once at signing (rewards closing new business), monthly
commission accrues for the first 12 months only (recurring revenue is
not committed to indefinitely at the same rate), and an optional renewal
rate can be added on for as long as the customer keeps renewing. See
LoanMVP/services/ae_pricing.py's build_commission_schedule() /
next_renewal_commission_entry() and the "signed" branch of
account_executive.deal_detail().
"""
from decimal import Decimal

from flask import g

from LoanMVP.models.admin import AECommissionEntry, BusinessInquiry, Company
from LoanMVP.models.user_model import User
from LoanMVP.extensions import db
from LoanMVP.services import ae_pricing

from tests.conftest import login_as


def _switch_to(client, user):
    """login_as() plus clearing Flask-Login's per-app-context user cache
    (see tests/test_ae_pricing_guardrails.py's _switch_to for why this is
    needed for any mid-test identity switch that follows a real request)."""
    login_as(client, user)
    g.pop("_login_user", None)


def _make_ae(db_session, email="ae@ravlohq.com"):
    company = Company.query.filter_by(name="Ravlo").first()
    if not company:
        company = Company(name="Ravlo", is_active=True)
        db_session.add(company)
        db_session.commit()
    user = User(email=email, role="account_executive", is_active=True, company_id=company.id)
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


def _make_deal(db_session, assigned_ae_id, company_name="Prospect Lending Co"):
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


def _sign(client, deal_id, **overrides):
    form = {
        "action_type": "update_stage",
        "ae_stage": "signed",
        "signed_setup_fee": "10000",
        "signed_monthly_fee": "2500",
        "setup_commission_rate": "0.15",
        "monthly_commission_rate": "0.08",
    }
    form.update(overrides)
    return client.post(f"/account-executive/deals/{deal_id}", data=form, follow_redirects=True)


# ----------------------------------------------------------------
#   ae_pricing.py -- pure schedule-building unit tests
# ----------------------------------------------------------------

def test_build_commission_schedule_matches_the_playbooks_worked_example():
    entries = ae_pricing.build_commission_schedule(
        setup_fee=Decimal("10000"), monthly_fee=Decimal("2500"),
        setup_commission_rate=Decimal("0.15"), monthly_commission_rate=Decimal("0.08"),
    )
    assert len(entries) == 13
    setup = entries[0]
    assert setup == {"entry_type": "setup", "period_number": None, "amount": Decimal("1500.00")}
    monthly = entries[1:]
    assert len(monthly) == 12
    assert all(e["amount"] == Decimal("200.00") for e in monthly)
    assert [e["period_number"] for e in monthly] == list(range(1, 13))

    total_first_year = setup["amount"] + sum(e["amount"] for e in monthly)
    assert total_first_year == Decimal("3900.00")  # matches the proposal's own worked example


def test_next_renewal_commission_entry_continues_period_numbering():
    entry = ae_pricing.next_renewal_commission_entry(
        monthly_fee=Decimal("2500"), renewal_commission_rate=Decimal("0.02"), existing_renewal_count=0
    )
    assert entry == {"entry_type": "renewal", "period_number": 13, "amount": Decimal("50.00")}

    second_entry = ae_pricing.next_renewal_commission_entry(
        monthly_fee=Decimal("2500"), renewal_commission_rate=Decimal("0.02"), existing_renewal_count=1
    )
    assert second_entry["period_number"] == 14


# ----------------------------------------------------------------
#   Wired into the deal tool
# ----------------------------------------------------------------

def test_deal_commission_amount_totals_across_the_whole_ledger(db_session, client):
    ae = _make_ae(db_session)
    deal = _make_deal(db_session, assigned_ae_id=ae.id)
    login_as(client, ae)

    _sign(client, deal.id)

    refreshed = db.session.get(BusinessInquiry, deal.id)
    assert refreshed.commission_amount == Decimal("3900.00")
    assert refreshed.commission_status == "pending"


def test_commission_status_is_partial_once_some_entries_are_paid(db_session, client):
    ae = _make_ae(db_session)
    executive = _make_executive(db_session)
    deal = _make_deal(db_session, assigned_ae_id=ae.id)
    login_as(client, ae)
    _sign(client, deal.id)

    setup_entry = AECommissionEntry.query.filter_by(deal_id=deal.id, entry_type="setup").first()
    _switch_to(client, executive)
    client.post(f"/account-executive/deals/{deal.id}", data={
        "action_type": "mark_ledger_entry_paid", "entry_id": str(setup_entry.id),
    })

    refreshed = db.session.get(BusinessInquiry, deal.id)
    assert refreshed.commission_status == "partial"


def test_commission_status_is_paid_once_every_entry_is_paid(db_session, client):
    ae = _make_ae(db_session)
    executive = _make_executive(db_session)
    deal = _make_deal(db_session, assigned_ae_id=ae.id)
    login_as(client, ae)
    _sign(client, deal.id)

    _switch_to(client, executive)
    for entry in AECommissionEntry.query.filter_by(deal_id=deal.id).all():
        client.post(f"/account-executive/deals/{deal.id}", data={
            "action_type": "mark_ledger_entry_paid", "entry_id": str(entry.id),
        })

    refreshed = db.session.get(BusinessInquiry, deal.id)
    assert refreshed.commission_status == "paid"


def test_no_renewal_rate_means_no_renewal_action_available(db_session, client):
    ae = _make_ae(db_session)
    executive = _make_executive(db_session)
    deal = _make_deal(db_session, assigned_ae_id=ae.id)
    login_as(client, ae)
    _sign(client, deal.id)  # no renewal_commission_rate provided

    _switch_to(client, executive)
    client.post(f"/account-executive/deals/{deal.id}", data={"action_type": "record_renewal_commission"})

    assert AECommissionEntry.query.filter_by(deal_id=deal.id, entry_type="renewal").count() == 0


def test_recording_renewal_commission_adds_one_entry_each_time(db_session, client):
    ae = _make_ae(db_session)
    executive = _make_executive(db_session)
    deal = _make_deal(db_session, assigned_ae_id=ae.id)
    login_as(client, ae)
    _sign(client, deal.id, renewal_commission_rate="0.02")

    _switch_to(client, executive)
    client.post(f"/account-executive/deals/{deal.id}", data={"action_type": "record_renewal_commission"})
    client.post(f"/account-executive/deals/{deal.id}", data={"action_type": "record_renewal_commission"})

    renewals = AECommissionEntry.query.filter_by(deal_id=deal.id, entry_type="renewal").order_by(
        AECommissionEntry.period_number
    ).all()
    assert len(renewals) == 2
    assert [r.period_number for r in renewals] == [13, 14]
    assert all(r.amount == Decimal("50.00") for r in renewals)  # 2% of 2500


def test_ae_cannot_record_renewal_commission(db_session, client):
    ae = _make_ae(db_session)
    deal = _make_deal(db_session, assigned_ae_id=ae.id)
    login_as(client, ae)
    _sign(client, deal.id, renewal_commission_rate="0.02")

    client.post(f"/account-executive/deals/{deal.id}", data={"action_type": "record_renewal_commission"})

    assert AECommissionEntry.query.filter_by(deal_id=deal.id, entry_type="renewal").count() == 0


def test_dashboard_sums_pending_and_paid_commission_from_the_ledger(db_session, client):
    ae = _make_ae(db_session)
    executive = _make_executive(db_session)
    deal = _make_deal(db_session, assigned_ae_id=ae.id)
    login_as(client, ae)
    _sign(client, deal.id)

    setup_entry = AECommissionEntry.query.filter_by(deal_id=deal.id, entry_type="setup").first()
    _switch_to(client, executive)
    client.post(f"/account-executive/deals/{deal.id}", data={
        "action_type": "mark_ledger_entry_paid", "entry_id": str(setup_entry.id),
    })

    _switch_to(client, ae)
    resp = client.get("/account-executive/dashboard")
    body = resp.get_data(as_text=True)

    assert "$1500.00" in body  # setup entry (15% of 10000), now paid
    assert "$2400.00" in body  # 12 monthly entries (8% of 2500 each), still pending
