"""Seat-cap enforcement regression tests.

max_users was set correctly at company-creation time but never actually
checked anywhere before this fix — a company could invite and onboard
unlimited team members regardless of their paid seat count. These tests
cover the hard enforcement gate (accepting an invite past the cap) and the
softer pre-check (inviting a new member past the cap).
"""
from LoanMVP.models.admin import Company, UserInvite
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_invite(db_session, company, email, role="loan_officer"):
    invite = UserInvite(
        company_id=company.id,
        email=email,
        role=role,
        token=UserInvite.generate_token(),
        expires_at=UserInvite.default_expiration(days=7),
        status="pending",
    )
    db_session.add(invite)
    db_session.commit()
    return invite


def test_seat_cap_blocks_accepting_invite_past_limit(db_session, client):
    company = Company(name="Full Co", is_active=True, subscription_tier="individual", max_users=1)
    db_session.add(company)
    db_session.commit()

    # Company already has its one paid seat filled.
    existing = User(email="existing@example.com", role="loan_officer", company_id=company.id)
    db_session.add(existing)
    db_session.commit()

    invite = _make_invite(db_session, company, "newhire@example.com")

    resp = client.get(f"/auth/register/invite/{invite.token}", follow_redirects=True)

    assert resp.status_code == 200
    assert b"reached its plan" in resp.data
    assert User.query.filter_by(email="newhire@example.com").first() is None


def test_seat_cap_allows_accepting_invite_under_limit(db_session, client):
    company = Company(name="Roomy Co", is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()

    invite = _make_invite(db_session, company, "newhire2@example.com")

    resp = client.get(f"/auth/register/invite/{invite.token}", follow_redirects=True)

    assert resp.status_code == 200
    assert b"reached its plan" not in resp.data


def test_uncapped_company_always_has_seat_available(db_session):
    company = Company(name="Enterprise Co", is_active=True, subscription_tier="white_label", max_users=None)
    db_session.add(company)
    db_session.commit()

    for i in range(20):
        db_session.add(User(email=f"user{i}@example.com", role="loan_officer", company_id=company.id))
    db_session.commit()

    assert company.has_seat_available() is True


def test_company_admin_cannot_invite_past_seat_cap(db_session, client):
    company = Company(name="Cap Co", is_active=True, subscription_tier="individual", max_users=1)
    db_session.add(company)
    db_session.commit()

    admin = User(email="cap-admin@example.com", role="admin", company_id=company.id, is_active=True)
    db_session.add(admin)
    db_session.commit()

    login_as(client, admin)
    resp = client.post(
        f"/admin/company/{company.id}/team/invite",
        data={"first_name": "New", "last_name": "Hire", "email": "blocked@example.com", "role": "loan_officer"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert b"reached its plan" in resp.data
    assert UserInvite.query.filter_by(email="blocked@example.com").first() is None
