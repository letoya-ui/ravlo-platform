"""The /lending-os marketing page used to show an abstract device mockup
("Applications: 124", generic "Workflow"/"Built For" lists) with no
concrete story -- unconvincing next to /realtors' specific sample listing.
Replaced with a Meridian Capital Lending sample pipeline (Danielle Carter,
Marcus Reyes, the Okafors, Priya Nair) walking through a real LO, processor,
and broker-owner scenario, clearly labeled as sample data."""


def test_lending_os_shows_meridian_capital_pipeline(client):
    resp = client.get("/lending-os")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Meridian Capital Lending" in body
    assert "Danielle Carter" in body
    assert "4128 Bayshore Vista Dr" in body


def test_lending_os_walks_through_the_lo_quote_engine_story(client):
    resp = client.get("/lending-os")

    body = resp.get_data(as_text=True)
    assert "Quote Engine" in body
    assert "Best APR" in body
    assert "Pre-Approval" in body


def test_lending_os_shows_processor_and_broker_owner_views(client):
    resp = client.get("/lending-os")

    body = resp.get_data(as_text=True)
    assert "Processor View" in body
    assert "Broker-Owner View" in body
    assert "requested" in body  # open condition item
    assert "Duplicate" in body  # lead dedup


def test_lending_os_discloses_sample_data(client):
    resp = client.get("/lending-os")

    body = resp.get_data(as_text=True)
    assert "Sample data" in body
    assert "fictional" in body
