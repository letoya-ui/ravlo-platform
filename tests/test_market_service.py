"""get_market_snapshot()'s zip-only path used to be a hardcoded placeholder
("Zip-only snapshot is a placeholder for now") -- asking about a ZIP with
no address returned an all-None snapshot no matter what. It now calls
RentCast's real /markets endpoint so "is 33607 a fast-moving market"
style questions (see LoanMVP/routes/admin.py's ai_chat()) can be grounded
in live median price/rent/days-on-market data.
"""
from unittest.mock import patch

from LoanMVP.services.market_service import get_market_snapshot
from LoanMVP.services.rentcast_service import RentCastServiceError


def test_zip_only_snapshot_returns_real_market_stats():
    fake_payload = {
        "zipCode": "33607",
        "saleData": {"medianPrice": 350000, "medianDaysOnMarket": 18, "totalListings": 42},
        "rentalData": {"medianRent": 1950},
    }

    with patch("LoanMVP.services.market_service.get_rentcast_market_stats", return_value=fake_payload):
        snapshot = get_market_snapshot(zipcode="33607")

    assert snapshot["name"] == "33607"
    assert snapshot["median_price"] == 350000
    assert snapshot["median_rent"] == 1950
    assert snapshot["inventory"] == 42
    assert snapshot["dom"] == 18
    assert snapshot["trend"] == "Fast-moving"


def test_zip_only_snapshot_classifies_slow_market():
    fake_payload = {"saleData": {"medianDaysOnMarket": 75}}

    with patch("LoanMVP.services.market_service.get_rentcast_market_stats", return_value=fake_payload):
        snapshot = get_market_snapshot(zipcode="10001")

    assert snapshot["trend"] == "Slow-moving"


def test_zip_only_snapshot_degrades_gracefully_on_rentcast_error():
    with patch(
        "LoanMVP.services.market_service.get_rentcast_market_stats",
        side_effect=RentCastServiceError("boom"),
    ):
        snapshot = get_market_snapshot(zipcode="33607")

    assert snapshot["median_price"] is None
    assert snapshot["trend"] is None


def test_no_address_and_no_zip_returns_empty_snapshot():
    snapshot = get_market_snapshot()

    assert snapshot["median_price"] is None
    assert snapshot["name"] is None
