"""Regression test for a production bug: a RentCast listing's description
text ended up as the property's "photo", which the investor Deal Finder
tool then tried to load as an image -- /investor/api/property_tool_image
correctly rejects it as not-a-URL and 400s, so the property fell back to
a placeholder image.

Root cause: normalize_rentcast_sale_listing()'s collect_photos() helper
recurses into several nested keys looking for photo URLs, including
"description" and "location" -- and its string base case appended *any*
non-empty string it found there with no check that it actually looked
like a URL. A listing whose raw payload nests its remarks text under one
of the walked keys would have that whole paragraph treated as a photo.
"""
from unittest.mock import patch

from LoanMVP.services.rentcast_service import (
    get_rentcast_market_stats,
    normalize_rentcast_market_stats,
    normalize_rentcast_sale_listing,
)


def test_description_text_is_not_treated_as_a_photo_url():
    description = (
        "Cash-flowing brick two-family with long-term, tenant-occupied units. "
        "Cash buyers only, tenant occupied-pls do not disturb tenants."
    )
    item = {
        "formattedAddress": "123 Main St, Springfield, IL 62701",
        "photos": {"description": description},
    }

    result = normalize_rentcast_sale_listing(item)

    assert description not in result["photos"]
    assert result["primary_photo"] != description
    assert result["photos"] == []
    assert result["primary_photo"] is None


def test_real_photo_urls_are_still_collected():
    item = {
        "formattedAddress": "123 Main St, Springfield, IL 62701",
        "photos": ["https://cdn.example.com/photo1.jpg", "https://cdn.example.com/photo2.jpg"],
    }

    result = normalize_rentcast_sale_listing(item)

    assert result["photos"] == ["https://cdn.example.com/photo1.jpg", "https://cdn.example.com/photo2.jpg"]
    assert result["primary_photo"] == "https://cdn.example.com/photo1.jpg"


def test_nested_location_text_is_not_treated_as_a_photo_url():
    item = {
        "formattedAddress": "123 Main St, Springfield, IL 62701",
        "photos": {"location": "Springfield, IL near the highway"},
    }

    result = normalize_rentcast_sale_listing(item)

    assert result["photos"] == []


# ─── Zip-level market stats (/markets) ──────────────────────────────────────

def test_get_rentcast_market_stats_calls_markets_endpoint_with_zip():
    with patch("LoanMVP.services.rentcast_service._safe_get") as mock_get:
        mock_get.return_value = {"zipCode": "33607"}

        get_rentcast_market_stats("33607")

        args, kwargs = mock_get.call_args
        assert args[0].endswith("/markets")
        assert args[1] == {"zipCode": "33607"}


def test_normalize_rentcast_market_stats_extracts_sale_and_rental_fields():
    payload = {
        "zipCode": "33607",
        "saleData": {
            "medianPrice": 350000,
            "medianDaysOnMarket": 18,
            "totalListings": 42,
            "newListings": 7,
        },
        "rentalData": {
            "medianRent": 1950,
            "averageDaysOnMarket": 25,
            "totalListings": 30,
            "newListings": 4,
        },
    }

    result = normalize_rentcast_market_stats(payload)

    assert result["zip_code"] == "33607"
    assert result["median_sale_price"] == 350000
    assert result["median_days_on_market"] == 18
    assert result["active_sale_listings"] == 42
    assert result["new_sale_listings"] == 7
    assert result["median_rent"] == 1950
    assert result["median_rent_days_on_market"] == 25
    assert result["active_rental_listings"] == 30
    assert result["new_rental_listings"] == 4


def test_normalize_rentcast_market_stats_handles_missing_data():
    result = normalize_rentcast_market_stats({}, zip_code="99999")

    assert result["zip_code"] == "99999"
    assert result["median_sale_price"] is None
    assert result["median_rent"] is None
