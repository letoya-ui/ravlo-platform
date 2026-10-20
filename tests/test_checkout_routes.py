"""Regression tests for the universal Stripe Checkout route
(checkout.subscribe). Written after a production report of 503s on
/checkout/subscribe/operator -- the route slug/price wiring was correct,
but STRIPE_BILLING_ENABLED defaults to False (LoanMVP/config.py) unless
explicitly turned on in the environment, and that check gates every
plan the route serves, not just operator.
"""
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_user(db_session, email="checkout-user@example.com"):
    user = User(email=email, role="investor", is_active=True)
    db_session.add(user)
    db_session.commit()
    return user


def test_subscribe_redirects_to_register_when_unauthenticated(client):
    resp = client.get("/checkout/subscribe/operator", follow_redirects=False)

    assert resp.status_code == 302
    assert "/auth/register" in resp.headers["Location"]


def test_subscribe_unknown_plan_404s(db_session, client):
    user = _make_user(db_session)
    login_as(client, user)

    resp = client.get("/checkout/subscribe/not-a-real-plan")

    assert resp.status_code == 404


def test_subscribe_returns_503_when_billing_disabled(db_session, client):
    user = _make_user(db_session, email="billing-off@example.com")
    login_as(client, user)
    client.application.config["STRIPE_BILLING_ENABLED"] = False

    resp = client.get("/checkout/subscribe/operator")

    assert resp.status_code == 503
    assert "Billing is not enabled" in resp.get_data(as_text=True)


def test_subscribe_returns_503_when_price_not_configured(db_session, client):
    user = _make_user(db_session, email="no-price@example.com")
    login_as(client, user)
    client.application.config["STRIPE_BILLING_ENABLED"] = True
    client.application.config["STRIPE_PRICE_OPERATOR"] = ""

    resp = client.get("/checkout/subscribe/operator")

    assert resp.status_code == 503
    assert "not currently available" in resp.get_data(as_text=True)


def test_subscribe_creates_checkout_session_when_configured(db_session, client, monkeypatch):
    user = _make_user(db_session, email="works@example.com")
    login_as(client, user)
    client.application.config["STRIPE_BILLING_ENABLED"] = True
    client.application.config["STRIPE_PRICE_OPERATOR"] = "price_test123"
    client.application.config["STRIPE_SECRET_KEY"] = "sk_test_fake"

    import LoanMVP.routes.checkout_routes as routes

    class _FakeSession:
        url = "https://checkout.stripe.com/pay/fake_session"

    def fake_session_create(**kwargs):
        assert kwargs["line_items"] == [{"price": "price_test123", "quantity": 1}]
        return _FakeSession()

    monkeypatch.setattr(routes.stripe.checkout.Session, "create", fake_session_create)

    resp = client.get("/checkout/subscribe/operator", follow_redirects=False)

    assert resp.status_code == 303
    assert resp.headers["Location"] == "https://checkout.stripe.com/pay/fake_session"
