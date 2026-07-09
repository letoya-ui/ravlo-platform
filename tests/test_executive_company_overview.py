"""Regression tests for the combined executive Company Overview page.

/executive/dashboard used to be a Ravlo-only view. This MR makes it a
combined Ravlo + Caughman Mason Construction overview instead, moves the
old Ravlo-only view to /executive/ravlo, and pulls in real P&L numbers
from CMFinanceEntry (the same ledger the Financial Hub already uses).
Jamaine still lands on his construction-only command center.
"""
from datetime import date

from LoanMVP.models.company_finance_models import CMFinanceEntry
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_executive(db_session, email="letoya@ravlohq.com"):
    user = User(email=email, role="executive", is_active=True)
    db_session.add(user)
    db_session.commit()
    return user


def _make_jamaine(db_session):
    user = User(email="jamaine.caughman@ravlohq.com", role="executive", is_active=True)
    db_session.add(user)
    db_session.commit()
    return user


def test_dashboard_renders_combined_overview_for_executive(db_session, client):
    exec_user = _make_executive(db_session)
    login_as(client, exec_user)

    resp = client.get("/executive/dashboard")

    assert resp.status_code == 200
    assert b"Company Overview" in resp.data
    assert b"Ravlo" in resp.data
    assert b"Caughman Mason Construction" in resp.data


def test_jamaine_still_redirected_to_construction_center(db_session, client):
    jamaine = _make_jamaine(db_session)
    login_as(client, jamaine)

    resp = client.get("/executive/dashboard", follow_redirects=False)

    assert resp.status_code == 302
    assert "/executive/construction" in resp.headers["Location"]


def test_ravlo_overview_route_serves_old_ravlo_only_view(db_session, client):
    exec_user = _make_executive(db_session)
    login_as(client, exec_user)

    resp = client.get("/executive/ravlo")

    assert resp.status_code == 200
    assert b"Mission Control" in resp.data


def test_combined_pnl_sums_ravlo_and_construction_divisions(db_session, client):
    exec_user = _make_executive(db_session)
    today = date.today().replace(day=1)

    db_session.add(CMFinanceEntry(division="lending", entry_type="income", amount=1000, entry_date=today))
    db_session.add(CMFinanceEntry(division="lending", entry_type="expense", amount=200, entry_date=today))
    db_session.add(CMFinanceEntry(division="construction", entry_type="income", amount=5000, entry_date=today))
    db_session.add(CMFinanceEntry(division="construction", entry_type="expense", amount=3000, entry_date=today))
    db_session.commit()

    login_as(client, exec_user)
    resp = client.get("/executive/dashboard")

    assert resp.status_code == 200
    # Ravlo: $1,000 income / Construction: $5,000 income / Combined: $6,000
    assert b"1,000" in resp.data
    assert b"5,000" in resp.data
    assert b"6,000" in resp.data
