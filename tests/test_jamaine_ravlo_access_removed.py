"""Regression tests confirming Jamaine's personal Ravlo staff access
(jamaine.caughman@ravlohq.com) was removed from every hardcoded
access-control allowlist, while Caughman Mason Construction -- the
partner business, tied to the separate jamaine.caughman@caughmanmason.com
identity -- is deliberately left untouched for now (a name change for
that business is planned separately, later).
"""
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_user(db_session, email, role="loan_officer"):
    user = User(email=email, role=role, is_active=True)
    db_session.add(user)
    db_session.commit()
    return user


def test_jamaine_ravlohq_email_no_longer_reaches_construction_office(db_session, client):
    user = _make_user(db_session, "jamaine.caughman@ravlohq.com")
    login_as(client, user)

    resp = client.get("/construction-office/packages", follow_redirects=True)

    assert resp.status_code == 200
    assert "You do not have access to construction office tools yet" in resp.get_data(as_text=True)


def test_caughmanmason_email_still_reaches_construction_office(db_session, client):
    user = _make_user(db_session, "jamaine.caughman@caughmanmason.com", role="partner")
    login_as(client, user)

    resp = client.get("/construction-office/packages", follow_redirects=True)

    assert resp.status_code == 200
    assert "You do not have access to construction office tools yet" not in resp.get_data(as_text=True)


def test_jamaine_ravlohq_email_no_longer_reaches_bid_search(db_session, client):
    user = _make_user(db_session, "jamaine.caughman@ravlohq.com")
    login_as(client, user)

    resp = client.get("/construction/bids/search", follow_redirects=True)

    assert resp.status_code == 200
    assert "You do not have access to construction bid tools yet" in resp.get_data(as_text=True)


def test_caughmanmason_email_still_reaches_bid_search(db_session, client):
    user = _make_user(db_session, "jamaine.caughman@caughmanmason.com", role="partner")
    login_as(client, user)

    resp = client.get("/construction/bids/search", follow_redirects=True)

    assert resp.status_code == 200
    assert "You do not have access to construction bid tools yet" not in resp.get_data(as_text=True)


def test_jamaine_ravlohq_email_no_longer_reaches_bid_support_queue(db_session, client):
    # /executive/bid-support unconditionally redirects every GET to the
    # construction office queue (see bid_support_redirect.py), so the
    # meaningful access check happens there.
    user = _make_user(db_session, "jamaine.caughman@ravlohq.com")
    login_as(client, user)

    resp = client.get("/executive/bid-support", follow_redirects=True)

    assert resp.status_code == 200
    assert "You do not have access to construction office tools yet" in resp.get_data(as_text=True)


def test_letoya_still_has_bid_support_and_construction_access(db_session, client):
    user = _make_user(db_session, "letoya@ravlohq.com")
    login_as(client, user)

    bid_support_resp = client.get("/executive/bid-support", follow_redirects=True)
    office_resp = client.get("/construction-office/packages", follow_redirects=True)

    assert bid_support_resp.status_code == 200
    assert "You do not have access to construction office tools yet" not in bid_support_resp.get_data(as_text=True)
    assert "You do not have access to construction office tools yet" not in office_resp.get_data(as_text=True)
