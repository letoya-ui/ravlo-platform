"""Regression tests for the orphaned-quote-request recovery tool.

When a VIP partner's account/VIPProfile is deleted and recreated (e.g.
Keyona's), any InsuranceQuoteRequest rows still pointing at the old
vip_profile_id become orphaned -- her account is back, but her quote
history isn't attached to it anymore. This gives staff a way to find
those rows and move them onto her current profile.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User
from LoanMVP.models.vip_models import InsuranceQuoteRequest, VIPProfile
from LoanMVP.extensions import db

from tests.conftest import login_as


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


def _make_partner_with_profile(db_session, email, slug):
    company = Company(name=f"Co {email}", is_active=True)
    db_session.add(company)
    db_session.commit()
    user = User(email=email, role="partner", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    profile = VIPProfile(
        user_id=user.id,
        display_name=slug,
        role_type="insurance_realtor",
        public_slug=slug,
        marketplace_enabled="yes",
    )
    db_session.add(profile)
    db_session.commit()
    return user, profile


def _make_orphaned_quote(db_session, stale_profile_id, client_name="Old Lead"):
    q = InsuranceQuoteRequest(
        vip_profile_id=stale_profile_id,
        client_name=client_name,
        client_email="oldlead@example.com",
        insurance_line="auto",
    )
    db_session.add(q)
    db_session.commit()
    return q


def test_orphaned_quotes_lists_rows_with_no_matching_profile(db_session, client):
    exec_user = _make_executive(db_session)
    _, profile = _make_partner_with_profile(db_session, "keyonahall@icloud.com", "key-signature-enterprise")
    stale_id = profile.id + 999
    _make_orphaned_quote(db_session, stale_id)
    login_as(client, exec_user)

    resp = client.get("/system/orphaned-quotes")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Old Lead" in body
    assert f"#{stale_id}" in body


def test_orphaned_quotes_excludes_rows_with_a_live_profile(db_session, client):
    exec_user = _make_executive(db_session)
    _, profile = _make_partner_with_profile(db_session, "keyonahall@icloud.com", "key-signature-enterprise")
    _make_orphaned_quote(db_session, profile.id, client_name="Current Lead")
    login_as(client, exec_user)

    resp = client.get("/system/orphaned-quotes")

    assert resp.status_code == 200
    assert "Current Lead" not in resp.get_data(as_text=True)


def test_reassign_moves_orphaned_quotes_to_the_new_owners_profile(db_session, client, app):
    exec_user = _make_executive(db_session)
    keyona, new_profile = _make_partner_with_profile(db_session, "keyonahall@icloud.com", "key-signature-enterprise")
    stale_id = new_profile.id + 999
    quote = _make_orphaned_quote(db_session, stale_id)
    login_as(client, exec_user)
    app.config["WTF_CSRF_ENABLED"] = False

    resp = client.post(
        "/system/orphaned-quotes/reassign",
        data={"old_profile_id": stale_id, "new_owner_email": "keyonahall@icloud.com"},
        follow_redirects=False,
    )

    assert resp.status_code == 302
    refreshed = db.session.get(InsuranceQuoteRequest, quote.id)
    assert refreshed.vip_profile_id == new_profile.id


def test_reassign_rejects_unknown_owner_email(db_session, client, app):
    exec_user = _make_executive(db_session)
    _, profile = _make_partner_with_profile(db_session, "keyonahall@icloud.com", "key-signature-enterprise")
    stale_id = profile.id + 999
    quote = _make_orphaned_quote(db_session, stale_id)
    login_as(client, exec_user)
    app.config["WTF_CSRF_ENABLED"] = False

    resp = client.post(
        "/system/orphaned-quotes/reassign",
        data={"old_profile_id": stale_id, "new_owner_email": "nobody@example.com"},
        follow_redirects=False,
    )

    assert resp.status_code == 302
    refreshed = db.session.get(InsuranceQuoteRequest, quote.id)
    assert refreshed.vip_profile_id == stale_id
