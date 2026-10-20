"""The realtor demo listing built to advertise the Partner Network now lives
at /realtors on the public marketing site, so it can be sent to prospective
realtor partners without needing an app login.

Also regression-covers two bugs an automated review caught on the first cut:
the "Request a Showing" form used to fake a success message without sending
the lead anywhere, and the whole form was hidden (with no fallback) on
mobile widths even though the "Schedule a Showing" nav link still pointed
at it."""
from LoanMVP.models.admin import BusinessInquiry


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


def test_realtors_page_does_not_hide_showing_form_on_mobile(client):
    resp = client.get("/realtors")

    body = resp.get_data(as_text=True)
    assert ".hero-overlay{display:none;}" not in body
    assert "showFormError" in body


def test_realtors_page_links_home_to_the_main_ravlo_site(client):
    """Visitors are scrolling a sample listing, not the real site -- the
    logo and "Home" nav link should take them to the actual Ravlo
    marketing homepage, not just scroll them back up this page."""
    resp = client.get("/realtors")

    body = resp.get_data(as_text=True)
    assert body.count('href="/"') >= 2


def test_realtors_showing_request_saves_a_lead(db_session, client):
    resp = client.post(
        "/realtors/request-showing",
        json={"name": "Jordan Blake", "email": "jordan@example.com", "phone": "6155550100", "date": "2026-09-20"},
    )

    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True

    lead = BusinessInquiry.query.filter_by(email="jordan@example.com").first()
    assert lead is not None
    assert lead.inquiry_type == "realtor_partner_lead"
    assert lead.contact_name == "Jordan Blake"


def test_realtors_showing_request_requires_name_and_email(db_session, client):
    resp = client.post("/realtors/request-showing", json={"name": "", "email": ""})

    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False
    assert BusinessInquiry.query.filter_by(inquiry_type="realtor_partner_lead").count() == 0
