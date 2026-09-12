"""The realtor demo listing built to advertise the Partner Network now lives
at /realtors on the public marketing site, so it can be sent to prospective
realtor partners without needing an app login."""


def test_realtors_page_renders(client):
    resp = client.get("/realtors")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "1247 Sycamore Ridge Lane" in body
    assert "Partner with Ravlo" in body


def test_realtors_page_discloses_sample_listing(client):
    resp = client.get("/realtors")

    body = resp.get_data(as_text=True)
    assert "SAMPLE LISTING" in body
    assert "AI-generated" in body
