"""Regression tests for the AE prospecting list: a pool of unclaimed
target companies (BusinessInquiry rows with ae_stage="prospect" and no
assigned_ae_id) that any account executive can browse and claim, plus a
CSV bulk-import for Ravlo staff (executive/platform_admin/master_admin)
to seed the pool with real target companies they've sourced (e.g. from
NMLS/MBA directories) instead of adding them one at a time.
"""
import io

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


def _make_deal(db_session, assigned_ae_id=None, company_name="Prospect Lending Co", ae_stage="prospect"):
    deal = BusinessInquiry(
        inquiry_type="license_application",
        company_name=company_name,
        contact_name="Pat Prospect",
        email="pat@prospectlending.com",
        status="new",
        assigned_ae_id=assigned_ae_id,
        ae_stage=ae_stage,
    )
    db_session.add(deal)
    db_session.commit()
    return deal


# ---------------------------------------------------------------------------
# Prospect pool listing
# ---------------------------------------------------------------------------

def test_prospects_page_lists_only_unclaimed_prospect_stage_deals(db_session, client):
    ae = _make_ae(db_session)
    other_ae = _make_ae(db_session, email="other-ae@ravlohq.com")

    unclaimed = _make_deal(db_session, assigned_ae_id=None, company_name="Unclaimed Co")
    _make_deal(db_session, assigned_ae_id=other_ae.id, company_name="Already Claimed Co")
    _make_deal(db_session, assigned_ae_id=None, company_name="Contacted Co", ae_stage="contacted")

    login_as(client, ae)
    resp = client.get("/account-executive/prospects")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Unclaimed Co" in body
    assert "Already Claimed Co" not in body
    assert "Contacted Co" not in body


def test_claiming_from_prospect_pool_assigns_current_user(db_session, client):
    ae = _make_ae(db_session)
    prospect = _make_deal(db_session, assigned_ae_id=None, company_name="Claim Me Lending")

    login_as(client, ae)
    resp = client.post(
        f"/account-executive/deals/{prospect.id}",
        data={"action_type": "claim"},
        follow_redirects=False,
    )

    assert resp.status_code in (302, 200)
    updated = BusinessInquiry.query.get(prospect.id)
    assert updated.assigned_ae_id == ae.id


# ---------------------------------------------------------------------------
# CSV import
# ---------------------------------------------------------------------------

def _csv_upload(csv_text: str):
    return {
        "csv_file": (io.BytesIO(csv_text.encode("utf-8")), "prospects.csv"),
    }


def test_import_creates_prospects_with_placeholder_contact(db_session, client, app):
    executive = _make_executive(db_session)
    login_as(client, executive)

    csv_text = "company_name,website\nAcme Mortgage,acmemortgage.com\nBeta Lending,betalending.com\n"

    app.config["WTF_CSRF_ENABLED"] = False
    resp = client.post(
        "/account-executive/prospects/import",
        data=_csv_upload(csv_text),
        content_type="multipart/form-data",
        follow_redirects=False,
    )

    assert resp.status_code in (302, 200)

    acme = BusinessInquiry.query.filter_by(company_name="Acme Mortgage").first()
    assert acme is not None
    assert acme.ae_stage == "prospect"
    assert acme.assigned_ae_id is None
    assert acme.contact_name == "Unknown Contact"
    assert acme.email.endswith("@prospects.internal")
    assert acme.website == "acmemortgage.com"

    beta = BusinessInquiry.query.filter_by(company_name="Beta Lending").first()
    assert beta is not None


def test_import_skips_duplicate_company_names(db_session, client, app):
    executive = _make_executive(db_session)
    _make_deal(db_session, company_name="Existing Lending Co")

    login_as(client, executive)
    csv_text = "company_name\nExisting Lending Co\nBrand New Co\n"

    app.config["WTF_CSRF_ENABLED"] = False
    client.post(
        "/account-executive/prospects/import",
        data=_csv_upload(csv_text),
        content_type="multipart/form-data",
    )

    assert BusinessInquiry.query.filter_by(company_name="Existing Lending Co").count() == 1
    assert BusinessInquiry.query.filter_by(company_name="Brand New Co").count() == 1


def test_import_requires_company_name_column(db_session, client, app):
    executive = _make_executive(db_session)
    login_as(client, executive)

    csv_text = "contact_name,email\nJane Doe,jane@example.com\n"

    app.config["WTF_CSRF_ENABLED"] = False
    client.post(
        "/account-executive/prospects/import",
        data=_csv_upload(csv_text),
        content_type="multipart/form-data",
    )

    assert BusinessInquiry.query.count() == 0


def test_import_blocked_for_non_full_visibility_ae(db_session, client, app):
    ae = _make_ae(db_session)
    login_as(client, ae)

    csv_text = "company_name\nShould Not Be Created Co\n"

    app.config["WTF_CSRF_ENABLED"] = False
    resp = client.post(
        "/account-executive/prospects/import",
        data=_csv_upload(csv_text),
        content_type="multipart/form-data",
        follow_redirects=False,
    )

    assert resp.status_code in (302, 403)
    assert BusinessInquiry.query.filter_by(company_name="Should Not Be Created Co").count() == 0


# ---------------------------------------------------------------------------
# Editing contact info after claiming (fills in the placeholder)
# ---------------------------------------------------------------------------

def test_update_contact_fills_in_real_contact_info(db_session, client, app):
    ae = _make_ae(db_session)
    deal = _make_deal(db_session, assigned_ae_id=ae.id, company_name="Needs Real Contact Co")
    deal.contact_name = "Unknown Contact"
    deal.email = "no-contact-abc123@prospects.internal"
    db_session.commit()

    login_as(client, ae)
    app.config["WTF_CSRF_ENABLED"] = False
    client.post(
        f"/account-executive/deals/{deal.id}",
        data={
            "action_type": "update_contact",
            "contact_name": "Real Contact",
            "email": "real@lender.com",
            "phone": "555-1234",
            "website": "lender.com",
        },
    )

    updated = BusinessInquiry.query.get(deal.id)
    assert updated.contact_name == "Real Contact"
    assert updated.email == "real@lender.com"
    assert updated.phone == "555-1234"


def test_update_contact_requires_name_and_email(db_session, client, app):
    ae = _make_ae(db_session)
    deal = _make_deal(db_session, assigned_ae_id=ae.id, company_name="Validation Co")

    login_as(client, ae)
    app.config["WTF_CSRF_ENABLED"] = False
    client.post(
        f"/account-executive/deals/{deal.id}",
        data={"action_type": "update_contact", "contact_name": "", "email": ""},
    )

    updated = BusinessInquiry.query.get(deal.id)
    assert updated.contact_name == "Pat Prospect"
    assert updated.email == "pat@prospectlending.com"
