"""Shared fixtures for real Flask app + DB integration tests.

Existing tests in this suite mock everything with SimpleNamespace and never
touch a real app/DB. Tenant-isolation regressions live in the SQLAlchemy
queries themselves, so catching them needs a real app, a real (file-backed)
SQLite DB, and real HTTP requests through the test client — that's what
these fixtures provide.
"""
import os
import tempfile
import uuid

# Must be set before any LoanMVP import: Config resolves these once at
# class-body evaluation time.
os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("OPENAI_API_KEY", "dummy")
os.environ.setdefault("SECRET_KEY", "dummy-test-secret")

import pytest

_DB_PATH = os.path.join(tempfile.gettempdir(), f"test_tenant_isolation_{uuid.uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"

from LoanMVP.app import create_app
from LoanMVP.extensions import db as _db


@pytest.fixture(scope="session")
def app():
    application = create_app()
    application.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        RATELIMIT_ENABLED=False,
        SERVER_NAME="localhost",
    )
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()
    if os.path.exists(_DB_PATH):
        os.remove(_DB_PATH)


@pytest.fixture
def db_session(app):
    with app.app_context():
        yield _db.session
        _db.session.rollback()
        # Clean every table between tests so each test starts from empty.
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()


@pytest.fixture
def client(app):
    return app.test_client()


def login_as(client, user):
    """Log the test client in as `user` via Flask-Login's session convention."""
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True
