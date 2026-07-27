"""Regression test for a production outage: a Postgres connection blip made
`handle_custom_domain` (LoanMVP/app.py) raise on every single request across
the whole platform, since it's a before_request hook with no error handling
around its DB lookup.

This hook has to run on every request (it's how custom realtor domains like
bonniesellsochomes.com get routed to the right page instead of the marketing
homepage), so any DB hiccup here doesn't just affect custom-domain traffic --
it 500s every route for every user. The fix makes the lookup fail open
instead: on a DB error, skip custom-domain handling and let normal routing
continue.
"""
from sqlalchemy.exc import OperationalError


def test_custom_domain_lookup_failure_falls_through_instead_of_500ing(app, client, monkeypatch):
    from LoanMVP.models.vip_models import VIPProfile

    class _RaisingQuery:
        def filter(self, *args, **kwargs):
            raise OperationalError("connection to server failed", {}, Exception("connection refused"))

    # Scoped to VIPProfile.query only, so no other model/query in the
    # request lifecycle (discovery tracking, trial/billing checks, the
    # marketing homepage view itself) is affected -- this isolates the
    # failure to exactly the lookup handle_custom_domain performs.
    monkeypatch.setattr(VIPProfile, "query", _RaisingQuery())

    resp = client.get("/", headers={"Host": "some-realtor-custom-domain.com"})

    assert resp.status_code != 500


def test_custom_domain_lookup_still_works_when_db_is_healthy(db_session, client):
    from LoanMVP.models.vip_models import VIPProfile

    profile = VIPProfile.query.filter_by(custom_domain="healthy-domain.com").first()
    assert profile is None  # sanity: no stray row from a prior test

    resp = client.get("/", headers={"Host": "healthy-domain.com"})

    # No VIPProfile registered for this host -> falls through to the normal
    # marketing homepage rather than a VIP landing page, and must not error.
    assert resp.status_code != 500


def test_custom_domain_with_missing_public_slug_falls_through_instead_of_500ing(db_session, client):
    """A VIPProfile can have custom_domain set without public_slug (e.g. an
    account whose onboarding-set fields were lost when it got recreated,
    the exact bug found on Keyona's account) -- every helper
    handle_custom_domain calls looks content up by slug, and
    _load_realtor_context(None) would raise (`None.lower()`) rather than
    just finding nothing. Must fail open like every other unservable case."""
    from LoanMVP.models.admin import Company
    from LoanMVP.models.user_model import User
    from LoanMVP.models.vip_models import VIPProfile

    company = Company(name="No Slug Co", is_active=True)
    db_session.add(company)
    db_session.commit()
    user = User(email="noslug@example.com", role="partner", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    db_session.add(VIPProfile(
        user_id=user.id, display_name="No Slug Realtor", role_type="realtor",
        public_slug=None, custom_domain="noslug-domain.com", marketplace_enabled="yes",
    ))
    db_session.commit()

    resp = client.get("/", headers={"Host": "noslug-domain.com"})

    assert resp.status_code != 500
