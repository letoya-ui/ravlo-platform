"""Regression tests for the Quote Worksheet (Ravlo Pricing Playbook,
section 4): a discovery form an AE fills out on every deal -- industry,
users, workspaces, branding, implementation complexity, and whether
training is required -- before quoting, so every AE follows the same
repeatable process instead of relying on instinct. The worksheet's
answers also carry forward as sensible defaults into the Quote
Calculator (e.g. a White Label branding answer pre-checks the White
Label flag, which the AE can still override).
"""
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
    user = User(email=email, role="account_executive", is_active=True, company_id=company.id)
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


def _save_worksheet(client, deal_id, **fields):
    form = {"action_type": "save_worksheet"}
    form.update(fields)
    return client.post(f"/account-executive/deals/{deal_id}", data=form, follow_redirects=True)


def test_saving_the_worksheet_persists_every_field(db_session, client):
    ae = _make_ae(db_session)
    deal = _make_deal(db_session, assigned_ae_id=ae.id)
    login_as(client, ae)

    resp = _save_worksheet(
        client,
        deal.id,
        worksheet_industry="Real Estate",
        worksheet_user_count="12",
        worksheet_workspace_count="3",
        worksheet_branding="white_label",
        worksheet_implementation_complexity="advanced",
        worksheet_training_required="yes",
    )

    assert resp.status_code == 200
    refreshed = db.session.get(BusinessInquiry, deal.id)
    assert refreshed.worksheet_industry == "Real Estate"
    assert refreshed.worksheet_user_count == 12
    assert refreshed.worksheet_workspace_count == 3
    assert refreshed.worksheet_branding == "white_label"
    assert refreshed.worksheet_implementation_complexity == "advanced"
    assert refreshed.worksheet_training_required is True


def test_worksheet_training_required_no_is_stored_as_false_not_missing(db_session, client):
    ae = _make_ae(db_session)
    deal = _make_deal(db_session, assigned_ae_id=ae.id)
    login_as(client, ae)

    _save_worksheet(client, deal.id, worksheet_training_required="no")

    refreshed = db.session.get(BusinessInquiry, deal.id)
    assert refreshed.worksheet_training_required is False


def test_invalid_branding_value_is_rejected_not_silently_stored(db_session, client):
    ae = _make_ae(db_session)
    deal = _make_deal(db_session, assigned_ae_id=ae.id)
    login_as(client, ae)

    _save_worksheet(client, deal.id, worksheet_branding="not-a-real-option")

    refreshed = db.session.get(BusinessInquiry, deal.id)
    assert refreshed.worksheet_branding is None


def test_worksheet_user_count_prefills_enterprise_user_count_field(db_session, client):
    ae = _make_ae(db_session)
    deal = _make_deal(db_session, assigned_ae_id=ae.id)
    login_as(client, ae)

    _save_worksheet(client, deal.id, worksheet_user_count="42")

    resp = client.get(f"/account-executive/deals/{deal.id}")
    body = resp.get_data(as_text=True)
    assert 'id="enterprise_user_count" name="enterprise_user_count" type="number" min="1" value="42"' in body


def test_worksheet_white_label_branding_prechecks_white_label_flag(db_session, client):
    ae = _make_ae(db_session)
    deal = _make_deal(db_session, assigned_ae_id=ae.id)
    login_as(client, ae)

    _save_worksheet(client, deal.id, worksheet_branding="white_label")

    resp = client.get(f"/account-executive/deals/{deal.id}")
    body = resp.get_data(as_text=True)
    assert 'name="is_white_label" checked' in body


def test_deal_detail_page_shows_the_worksheet_form(db_session, client):
    ae = _make_ae(db_session)
    deal = _make_deal(db_session, assigned_ae_id=ae.id)
    login_as(client, ae)

    resp = client.get(f"/account-executive/deals/{deal.id}")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Quote Worksheet" in body
    assert "worksheet_industry" in body
    assert "Implementation Complexity" in body
