"""Tenant-isolation regression tests.

These exist so a future change can't silently reintroduce the class of bug
found and fixed across underwriter.py, processor.py, loan_officer.py,
admin.py, mobile_api.py, and vip.py this session: a user at Company A
reading or writing a record that belongs to Company B.

Every existing test in this suite mocks everything with SimpleNamespace and
never touches a real app/DB/route — none of them would have caught any of
these bugs. These tests hit real routes through the Flask test client
against a real (file-backed) SQLite DB, with two real companies, so they
exercise the actual SQLAlchemy queries the bugs lived in.

Not exhaustive: this covers one representative, previously-broken
write-IDOR per file (the most severe class — one company mutating another
company's data), plus the shared root-cause helper. It is not a full
route-by-route re-test of every fix made this session.
"""
import pytest

from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User
from LoanMVP.models.loan_models import LoanApplication

from tests.conftest import login_as


@pytest.fixture
def two_companies(db_session):
    company_a = Company(name="Company A", is_active=True)
    company_b = Company(name="Company B", is_active=True)
    db_session.add_all([company_a, company_b])
    db_session.commit()
    return company_a, company_b


def _make_user(db_session, company, role, email):
    user = User(email=email, role=role, company_id=company.id, is_active=True)
    db_session.add(user)
    db_session.commit()
    return user


def _make_loan(db_session, company, **extra):
    extra.setdefault("status", "Pending")
    loan = LoanApplication(company_id=company.id, amount=100000, **extra)
    db_session.add(loan)
    db_session.commit()
    return loan


# ---------------------------------------------------------------------------
# processor.py — assign_loan() write-IDOR (fixed this session)
# ---------------------------------------------------------------------------

def test_processor_cannot_assign_another_companys_loan(db_session, client, two_companies):
    company_a, company_b = two_companies
    processor_a = _make_user(db_session, company_a, "processor", "processor-a@example.com")
    loan_b = _make_loan(db_session, company_b)

    login_as(client, processor_a)
    resp = client.get(f"/processor/assign/{loan_b.id}", follow_redirects=False)

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# underwriter.py — decision() write-IDOR (fixed this session)
# ---------------------------------------------------------------------------

def test_underwriter_cannot_decide_another_companys_loan(db_session, client, two_companies):
    company_a, company_b = two_companies
    uw_a = _make_user(db_session, company_a, "underwriter", "uw-a@example.com")
    loan_b = _make_loan(db_session, company_b, status="Under Review")

    login_as(client, uw_a)
    resp = client.post(
        f"/underwriter/decision/{loan_b.id}",
        data={"decision": "Approved", "notes": "should not apply"},
        follow_redirects=False,
    )

    assert resp.status_code == 404
    db_session.refresh(loan_b)
    assert loan_b.status == "Under Review"  # unchanged


def test_underwriter_can_decide_own_companys_loan(db_session, client, two_companies):
    """Positive control: the fix must not have blocked legitimate same-company use."""
    company_a, _ = two_companies
    uw_a = _make_user(db_session, company_a, "underwriter", "uw-a2@example.com")
    loan_a = _make_loan(db_session, company_a, status="Under Review")

    login_as(client, uw_a)
    resp = client.post(
        f"/underwriter/decision/{loan_a.id}",
        data={"decision": "Approved", "notes": "fine"},
        follow_redirects=False,
    )

    assert resp.status_code in (302, 303)
    db_session.refresh(loan_a)
    assert loan_a.status == "Approved"


# ---------------------------------------------------------------------------
# admin.py — block_company() cross-tenant privilege escalation (fixed this session)
# ---------------------------------------------------------------------------

def test_company_admin_cannot_block_another_company(db_session, client, two_companies):
    company_a, company_b = two_companies
    admin_a = _make_user(db_session, company_a, "admin", "admin-a@example.com")

    login_as(client, admin_a)
    resp = client.post(f"/admin/companies/{company_b.id}/block", data={"reason": "non_payment"})

    assert resp.status_code == 403
    db_session.refresh(company_b)
    assert company_b.is_blocked is False


def test_full_admin_can_block_any_company(db_session, client, two_companies):
    """Positive control: full admins retain the ability the fix must not remove."""
    company_a, company_b = two_companies
    platform_admin = _make_user(db_session, company_a, "platform_admin", "platform-admin@example.com")

    login_as(client, platform_admin)
    resp = client.post(
        f"/admin/companies/{company_b.id}/block",
        data={"reason": "non_payment"},
        follow_redirects=False,
    )

    assert resp.status_code in (302, 303)
    db_session.refresh(company_b)
    assert company_b.is_blocked is True


# ---------------------------------------------------------------------------
# vip.py — loan_officer_refer_out() write-IDOR (fixed this session)
# ---------------------------------------------------------------------------

def test_partner_cannot_refer_out_another_companys_loan(db_session, client, two_companies):
    company_a, company_b = two_companies
    admin_a = _make_user(db_session, company_a, "admin", "vip-admin-a@example.com")
    loan_b = _make_loan(db_session, company_b, status="Pending")

    login_as(client, admin_a)
    resp = client.post(f"/vip/loan-officer/loan/{loan_b.id}/refer-out", data={"reason": "test"})

    assert resp.status_code == 404
    db_session.refresh(loan_b)
    assert loan_b.status == "Pending"  # unchanged


# ---------------------------------------------------------------------------
# mobile_api.py — underwriter_decision() write-IDOR (fixed this session)
# ---------------------------------------------------------------------------

def test_mobile_underwriter_cannot_decide_another_companys_loan(db_session, client, two_companies, app):
    from LoanMVP.routes.mobile_api import _encode_token

    company_a, company_b = two_companies
    uw_a = _make_user(db_session, company_a, "underwriter", "mobile-uw-a@example.com")
    loan_b = _make_loan(db_session, company_b, status="Under Review")

    with app.app_context():
        token = _encode_token(uw_a.id)

    resp = client.post(
        f"/mobile/lending/underwriter/loan/{loan_b.id}/decision",
        json={"decision": "approved", "notes": "should not apply"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 404
    db_session.refresh(loan_b)
    assert loan_b.status == "Under Review"  # unchanged


def test_mobile_user_cannot_complete_another_users_task(db_session, client, two_companies, app):
    from LoanMVP.routes.mobile_api import _encode_token
    from LoanMVP.models.crm_models import Task

    company_a, company_b = two_companies
    user_a = _make_user(db_session, company_a, "loan_officer", "mobile-task-a@example.com")
    user_b = _make_user(db_session, company_b, "loan_officer", "mobile-task-b@example.com")
    task_b = Task(title="Follow up", assigned_to=user_b.id, completed=False)
    db_session.add(task_b)
    db_session.commit()

    with app.app_context():
        token = _encode_token(user_a.id)

    resp = client.post(
        f"/mobile/lending/tasks/{task_b.id}/complete",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 404
    db_session.refresh(task_b)
    assert task_b.completed is False  # unchanged
