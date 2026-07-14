"""Regression test: the login page and its shared auth/public layouts
used to brand themselves "Investor Login" / "INVESTOR OPERATING SYSTEM"
/ "Access your investor command center", excluding partners and lending
professionals who also use Ravlo. Login is now audience-neutral."""


def test_login_page_is_not_investor_exclusive(client):
    resp = client.get("/auth/login")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Investor Login" not in body
    assert "INVESTOR OPERATING SYSTEM" not in body
    assert "Access your investor command center" not in body
    assert "Log In to Ravlo" in body


def test_register_borrower_page_login_link_is_not_investor_exclusive(client):
    resp = client.get("/auth/register_borrower")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Investor Login" not in body
