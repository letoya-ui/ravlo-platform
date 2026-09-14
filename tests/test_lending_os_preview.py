"""/lending-os/preview is a shareable, static mockup of the Lending OS
dashboard -- an AE can send a single link to a prospect and let them see
the product without needing a login or a real demo account. It reuses the
same fictional Meridian Capital pipeline (Danielle Carter, Marcus Reyes,
the Okafors, Priya Nair) already seeded into the real white_label demo
environment, and is clearly labeled as sample data.

Also covers /lending-os itself, which was restored to its previous
abstract-mockup marketing content after this preview page was added."""


def test_lending_os_preview_renders(client):
    resp = client.get("/lending-os/preview")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Meridian Capital" in body
    assert "Lending OS" in body


def test_lending_os_preview_shows_the_meridian_pipeline(client):
    resp = client.get("/lending-os/preview")

    body = resp.get_data(as_text=True)
    assert "Danielle Carter" in body
    assert "Marcus Reyes" in body
    assert "Ade &amp; Lisa Okafor" in body or "Ade & Lisa Okafor" in body
    assert "Priya Nair" in body


def test_lending_os_preview_discloses_sample_data(client):
    resp = client.get("/lending-os/preview")

    body = resp.get_data(as_text=True)
    assert "DEMO PREVIEW" in body
    assert "fictional" in body


def test_lending_os_preview_links_back_to_the_marketing_site(client):
    resp = client.get("/lending-os/preview")

    body = resp.get_data(as_text=True)
    assert 'href="/"' in body
    assert "/lending-os" in body


def test_lending_os_marketing_page_still_renders(client):
    resp = client.get("/lending-os")

    assert resp.status_code == 200
