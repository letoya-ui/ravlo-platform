"""Regression tests for comping a specific investor account (currently
letoya.mason@gmail.com, see INVESTOR_COMPED_EMAILS in
LoanMVP/utils/decorators.py) to full access at no charge, independent
of INVESTOR_GRANDFATHERED_CUTOFF.

Three separate gates all had to learn about this:
1. The effective-plan helper in investor_routes.py.
2. check_trial_expiry() in app.py, the before_request hook that
   redirects an expired PREVIEW trial to /trial-expired.
3. inject_trial_popup_data() in app.py, a context processor that shows
   a "Your free trial is over" popup on any ravlo_base.html page
   whenever trial_ends_at has passed and subscription isn't a paid
   plan -- this one fires regardless of subscription == "preview", so
   it caught an account gate #2 didn't (e.g. subscription == "free"
   with a past trial_ends_at), which is exactly how the comped account
   still saw the popup on /partners/register after gate #2 was fixed.
"""
from datetime import datetime, timedelta

from LoanMVP.models.user_model import User
from LoanMVP.routes.investor_routes import _is_investor_grandfathered
from LoanMVP.utils.decorators import is_investor_comped

from tests.conftest import login_as


def _make_investor(db_session, email, created_at=None, subscription="preview", trial_ends_at=None):
    user = User(
        email=email, role="investor", is_active=True,
        subscription=subscription, trial_ends_at=trial_ends_at,
    )
    db_session.add(user)
    db_session.commit()
    if created_at:
        user.created_at = created_at
        db_session.commit()
    return user


def test_is_investor_comped_true_for_comped_email():
    user = User(email="Letoya.Mason@gmail.com", role="investor", is_active=True)
    assert is_investor_comped(user) is True


def test_is_investor_comped_false_for_other_emails():
    user = User(email="someone-else@example.com", role="investor", is_active=True)
    assert is_investor_comped(user) is False


def test_grandfathered_check_true_for_comped_account_regardless_of_signup_date(db_session):
    recent_signup = datetime.utcnow()
    user = _make_investor(db_session, "letoya.mason@gmail.com", created_at=recent_signup)

    assert _is_investor_grandfathered(user) is True


def test_grandfathered_check_false_for_recent_non_comped_account(db_session):
    recent_signup = datetime.utcnow()
    user = _make_investor(db_session, "recent-investor@example.com", created_at=recent_signup)

    assert _is_investor_grandfathered(user) is False


def test_comped_account_is_not_bounced_to_trial_expired_paywall(db_session, client):
    expired_trial = datetime.utcnow() - timedelta(days=1)
    user = _make_investor(
        db_session, "letoya.mason@gmail.com",
        subscription="preview", trial_ends_at=expired_trial,
    )
    login_as(client, user)

    resp = client.get("/investor/dashboard", follow_redirects=False)

    assert resp.status_code != 302 or "trial-expired" not in (resp.headers.get("Location") or "")


def test_non_comped_account_with_expired_trial_still_gets_the_paywall(db_session, client):
    """Confirms the test setup actually reproduces the gate -- otherwise
    the comped-account test above would pass for the wrong reason."""
    expired_trial = datetime.utcnow() - timedelta(days=1)
    user = _make_investor(
        db_session, "expired-trial@example.com",
        subscription="preview", trial_ends_at=expired_trial,
    )
    login_as(client, user)

    resp = client.get("/investor/dashboard", follow_redirects=False)

    assert resp.status_code == 302
    assert "trial-expired" in resp.headers["Location"]


def test_comped_account_does_not_see_the_trial_ended_popup(db_session, client):
    """subscription='free' (not 'preview') with a past trial_ends_at is
    exactly the state that slips past check_trial_expiry() (which only
    checks subscription == 'preview') but still trips the "Your free
    trial is over" popup in inject_trial_popup_data() -- which fires for
    any subscription not in its own paid-plans set."""
    expired_trial = datetime.utcnow() - timedelta(days=1)
    user = _make_investor(
        db_session, "letoya.mason@gmail.com",
        subscription="free", trial_ends_at=expired_trial,
    )
    login_as(client, user)

    resp = client.get("/investor/dashboard")

    assert resp.status_code == 200
    assert "Your free trial is over" not in resp.get_data(as_text=True)


def test_non_comped_account_in_the_same_state_still_sees_the_popup(db_session, client):
    """Confirms the test setup actually reproduces the popup gate."""
    expired_trial = datetime.utcnow() - timedelta(days=1)
    user = _make_investor(
        db_session, "another-free-account@example.com",
        subscription="free", trial_ends_at=expired_trial,
    )
    login_as(client, user)

    resp = client.get("/investor/dashboard")

    assert resp.status_code == 200
    assert "Your free trial is over" in resp.get_data(as_text=True)
