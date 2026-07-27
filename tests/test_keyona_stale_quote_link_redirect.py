"""Regression test for a temporary fix: Keyona's personal website has
"/vip/insurance/10/get-quote" hardcoded into it and she can't update that
link until Saturday -- id=10 belongs to an unrelated demo loan officer
account, so real prospective clients' quote requests were landing on the
demo inbox instead of hers. Rather than renumbering database rows (risky --
would require re-pointing every foreign key referencing either profile),
vip.py's _STALE_QUOTE_LINK_REDIRECTS dict makes the one stale id redirect
straight to her real profile.

Uses monkeypatch to point the redirect dict at freshly-created test
profiles instead of the real hardcoded {10: 18}, since those specific ids
won't exist in the test database.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User
from LoanMVP.models.vip_models import VIPProfile


def _make_insurance_vip(db_session, email, public_slug):
    company = Company(name=f"{public_slug} Co", is_active=True)
    db_session.add(company)
    db_session.commit()
    user = User(email=email, role="partner", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    profile = VIPProfile(
        user_id=user.id, display_name="Test Agency", business_name="Test Agency",
        role_type="insurance", public_slug=public_slug, marketplace_enabled="yes",
    )
    db_session.add(profile)
    db_session.commit()
    return profile


def test_stale_quote_link_redirects_to_real_profile(db_session, client, monkeypatch):
    from LoanMVP.routes import vip as vip_routes

    real_profile = _make_insurance_vip(db_session, "real@example.com", "real-profile")
    stale_profile = _make_insurance_vip(db_session, "stale@example.com", "stale-profile")
    monkeypatch.setitem(vip_routes._STALE_QUOTE_LINK_REDIRECTS, stale_profile.id, real_profile.id)

    resp = client.get(f"/vip/insurance/{stale_profile.id}/get-quote", follow_redirects=False)

    assert resp.status_code == 307
    assert resp.headers["Location"].endswith(f"/vip/insurance/{real_profile.id}/get-quote")


def test_stale_quote_link_redirect_preserves_query_string(db_session, client, monkeypatch):
    from LoanMVP.routes import vip as vip_routes

    real_profile = _make_insurance_vip(db_session, "real2@example.com", "real-profile-2")
    stale_profile = _make_insurance_vip(db_session, "stale2@example.com", "stale-profile-2")
    monkeypatch.setitem(vip_routes._STALE_QUOTE_LINK_REDIRECTS, stale_profile.id, real_profile.id)

    resp = client.get(f"/vip/insurance/{stale_profile.id}/get-quote?line=auto", follow_redirects=False)

    assert "line=auto" in resp.headers["Location"]


def test_stale_quote_link_redirect_applies_to_post_too(db_session, client, monkeypatch):
    from LoanMVP.routes import vip as vip_routes
    from LoanMVP.models.vip_models import InsuranceQuoteRequest

    real_profile = _make_insurance_vip(db_session, "real3@example.com", "real-profile-3")
    stale_profile = _make_insurance_vip(db_session, "stale3@example.com", "stale-profile-3")
    monkeypatch.setitem(vip_routes._STALE_QUOTE_LINK_REDIRECTS, stale_profile.id, real_profile.id)

    resp = client.post(
        f"/vip/insurance/{stale_profile.id}/get-quote",
        data={"client_name": "Redirected Client", "line": "auto"},
        follow_redirects=False,
    )

    assert resp.status_code == 307
    assert resp.headers["Location"].endswith(f"/vip/insurance/{real_profile.id}/get-quote")
    # The redirect itself must not create a quote request under the stale
    # profile -- the client's browser follows the 307 and re-POSTs to the
    # real profile's URL, where the request actually gets saved.
    assert InsuranceQuoteRequest.query.filter_by(vip_profile_id=stale_profile.id).count() == 0


def test_non_redirected_profile_id_renders_normally(db_session, client):
    profile = _make_insurance_vip(db_session, "normal@example.com", "normal-profile")

    resp = client.get(f"/vip/insurance/{profile.id}/get-quote")

    assert resp.status_code == 200
