"""Regression test for the Founders Access price on the Lending OS
marketing page. It previously showed a stale flat $99/month "intro
company access" price that didn't match the platform's real pricing
model (Individual Loan Officer $149/month, Brokerage/Small Team
$799/month -- see lending_pricing.html)."""


def test_founders_access_shows_current_pricing(client):
    resp = client.get("/lending-os")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "$149" in body
    assert "$799" in body
    assert "$99" not in body
