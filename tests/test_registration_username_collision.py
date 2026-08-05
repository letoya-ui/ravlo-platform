"""Regression tests for a production crash: registration writes the
person's full name straight into User.username, which has a unique DB
constraint -- a second person with the same name (e.g. two "Sandra
Fultz"es) hits an unhandled IntegrityError and the request 500s.

username is never used for login/lookup (that's always by email --
confirmed via grep, every User.query.filter_by(email=...) site), it's
only ever displayed as a fallback name, so the fix is twofold:
  1. auth._unique_username() de-duplicates before insert, so two people
     with the same name never collide in the first place.
  2. Each registration commit is wrapped in try/except IntegrityError as
     a defense-in-depth safety net (e.g. a genuine race condition), so
     any residual collision shows a friendly flash instead of a 500.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User
from LoanMVP.routes.auth import _unique_username

from tests.conftest import login_as


def _exit_recovery_mode(db_session):
    """auth._workspace_recovery_mode() is True whenever the DB has zero
    users at all (first-run bootstrap) -- the db_session fixture clears
    every table between tests, so every registration test would otherwise
    hit recovery mode and get redirected into the owner-admin-only flow
    instead of the normal registration path being tested here."""
    company = Company(name="Bootstrap Co", is_active=True)
    db_session.add(company)
    db_session.commit()
    bootstrap_user = User(
        email="bootstrap-admin@example.com", username="Bootstrap Admin",
        is_active=True, company_id=company.id, role="admin",
    )
    db_session.add(bootstrap_user)
    db_session.commit()


# ─── _unique_username() ─────────────────────────────────────────────────────

def test_unique_username_returns_base_when_free(db_session):
    assert _unique_username("Brand New Name") == "Brand New Name"


def test_unique_username_appends_suffix_on_collision(db_session):
    company = Company(name="Co1", is_active=True)
    db_session.add(company)
    db_session.commit()
    existing = User(email="sandra1@example.com", username="Sandra Fultz", is_active=True, company_id=company.id)
    db_session.add(existing)
    db_session.commit()

    assert _unique_username("Sandra Fultz") == "Sandra Fultz 2"


def test_unique_username_keeps_incrementing_past_multiple_collisions(db_session):
    company = Company(name="Co2", is_active=True)
    db_session.add(company)
    db_session.commit()
    for name in ("Sandra Fultz", "Sandra Fultz 2", "Sandra Fultz 3"):
        db_session.add(User(email=f"{name}@example.com", username=name, is_active=True, company_id=company.id))
    db_session.commit()

    assert _unique_username("Sandra Fultz") == "Sandra Fultz 4"


def test_unique_username_falls_back_when_base_empty(db_session):
    assert _unique_username("", fallback="someone@example.com") == "someone@example.com"


def test_unique_username_empty_and_no_fallback_returns_empty(db_session):
    assert _unique_username("") == ""


# ─── /register: two people with the same name ───────────────────────────────

def test_two_users_can_register_with_the_same_full_name(db_session, client):
    _exit_recovery_mode(db_session)

    resp1 = client.post(
        "/auth/register",
        data={
            "full_name": "Sandra Fultz",
            "email": "sandra.a@example.com",
            "password": "password123",
            "confirm_password": "password123",
            "role": "investor",
        },
        follow_redirects=True,
    )
    assert resp1.status_code == 200

    client.get("/auth/logout")
    with client.session_transaction() as sess:
        sess.clear()

    resp2 = client.post(
        "/auth/register",
        data={
            "full_name": "Sandra Fultz",
            "email": "sandra.b@example.com",
            "password": "password123",
            "confirm_password": "password123",
            "role": "investor",
        },
        follow_redirects=True,
    )

    # The historical bug: this second registration 500s with an
    # unhandled IntegrityError instead of succeeding.
    assert resp2.status_code == 200

    user_a = User.query.filter_by(email="sandra.a@example.com").first()
    user_b = User.query.filter_by(email="sandra.b@example.com").first()
    assert user_a is not None
    assert user_b is not None
    assert user_a.username != user_b.username
    assert user_b.username == "Sandra Fultz 2"


def test_two_borrowers_can_register_with_the_same_full_name(db_session, client):
    resp1 = client.post(
        "/auth/register_borrower",
        data={
            "full_name": "Marcus Reed",
            "email": "marcus.a@example.com",
            "password": "password123",
            "confirm_password": "password123",
        },
        follow_redirects=True,
    )
    assert resp1.status_code == 200

    client.get("/auth/logout")
    with client.session_transaction() as sess:
        sess.clear()

    resp2 = client.post(
        "/auth/register_borrower",
        data={
            "full_name": "Marcus Reed",
            "email": "marcus.b@example.com",
            "password": "password123",
            "confirm_password": "password123",
        },
        follow_redirects=True,
    )

    assert resp2.status_code == 200
    user_b = User.query.filter_by(email="marcus.b@example.com").first()
    assert user_b is not None
    assert user_b.username == "Marcus Reed 2"


# ─── Defense-in-depth: a residual collision shows a flash, not a 500 ───────

def test_register_shows_friendly_error_on_integrity_error_instead_of_crashing(db_session, client, monkeypatch):
    """Simulates a residual race condition -- _unique_username() disabled
    so the raw (colliding) name reaches the INSERT -- rather than
    monkeypatching db.session.commit itself, which is a shared object
    other fixtures/teardown also depend on."""
    _exit_recovery_mode(db_session)
    import LoanMVP.routes.auth as auth_module

    monkeypatch.setattr(auth_module, "_unique_username", lambda base, fallback="": base or fallback)

    first = client.post(
        "/auth/register",
        data={
            "full_name": "Race Condition",
            "email": "race1@example.com",
            "password": "password123",
            "confirm_password": "password123",
            "role": "investor",
        },
        follow_redirects=True,
    )
    assert first.status_code == 200
    client.get("/auth/logout")
    with client.session_transaction() as sess:
        sess.clear()

    resp = client.post(
        "/auth/register",
        data={
            "full_name": "Race Condition",
            "email": "race2@example.com",
            "password": "password123",
            "confirm_password": "password123",
            "role": "investor",
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "Something went wrong creating your account" in resp.get_data(as_text=True)
    assert User.query.filter_by(email="race2@example.com").first() is None


def test_register_borrower_shows_friendly_error_on_integrity_error_instead_of_crashing(db_session, client, monkeypatch):
    import LoanMVP.routes.auth as auth_module

    monkeypatch.setattr(auth_module, "_unique_username", lambda base, fallback="": base or fallback)

    first = client.post(
        "/auth/register_borrower",
        data={
            "full_name": "Race Condition",
            "email": "race3@example.com",
            "password": "password123",
            "confirm_password": "password123",
        },
        follow_redirects=True,
    )
    assert first.status_code == 200
    client.get("/auth/logout")
    with client.session_transaction() as sess:
        sess.clear()

    resp = client.post(
        "/auth/register_borrower",
        data={
            "full_name": "Race Condition",
            "email": "race4@example.com",
            "password": "password123",
            "confirm_password": "password123",
        },
        follow_redirects=True,
    )

    # register_borrower.html doesn't render flash messages at all (a
    # pre-existing gap shared by its other validation errors, out of
    # scope here) -- what matters for this regression is that the
    # request no longer 500s and doesn't leave a half-created account.
    assert resp.status_code == 200
    assert User.query.filter_by(email="race4@example.com").first() is None


# ─── complete_profile self-heal path ────────────────────────────────────────

def test_complete_profile_deduplicates_username_for_existing_name(db_session, client):
    company = Company(name="Co3", is_active=True)
    db_session.add(company)
    db_session.commit()

    existing = User(
        email="taken@example.com", username="Jordan Lee", is_active=True,
        company_id=company.id, role="investor",
    )
    db_session.add(existing)

    new_user = User(email="new@example.com", is_active=True, company_id=company.id, role="investor")
    new_user.set_password("password123")
    db_session.add(new_user)
    db_session.commit()

    login_as(client, new_user)

    resp = client.post(
        "/auth/complete-profile",
        data={"first_name": "Jordan", "last_name": "Lee"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    db_session.refresh(new_user)
    assert new_user.username == "Jordan Lee 2"
