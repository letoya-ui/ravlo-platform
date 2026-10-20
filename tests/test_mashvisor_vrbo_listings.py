"""Regression tests for nearby VRBO listings on Deal Finder results.

Mashvisor exposes a market-wide search endpoint,
`airbnb-property/newly-listed-vrbo` (state + city), and a single-listing
detail endpoint, `vrbo-property/{listingNumber}`. The search endpoint
returns full VRBO listing objects shaped like:

    {
      "status": "success",
      "content": {
        "items_per_page": ..., "page": ..., "total_pages": ..., "total_items": ...,
        "list": [
          {
            "address": {"city": "Burbank", "stateProvince": "CA", "postalCode": "91506"},
            "bedrooms": 2,
            "bathrooms": {"full": 2, "half": 0, "toiletOnly": 0},
            "priceSummary": {
                "amount": 189, "formattedAmount": "$189",
                "pricePeriodDescription": "per night", "currencySymbol": "$",
            },
            "thumbnailUrl": "https://...",
            "canonicalLink": "https://www.vrbo.com/...",
            "averageRating": 4.8,
            "reviewCount": 32,
            "sleeps": 4,
            "propertyType": "Condo",
            "geoCode": {"latitude": 34.18, "longitude": -118.31},
            "headline": "Cozy Burbank retreat",
            "listingNumber": "1943760",
            "propertyId": "p123",
            "id": "1943760",
            "status": "active",
          },
          ...
        ],
      },
    }

Since this is a market-wide search (state + city), not a per-property
lookup, it should be fetched once per unique city and reused for every
property enriched in that same city -- not re-fetched for every address.
"""
from LoanMVP.services.investor.property_orchestrator import (
    CanonicalProperty,
    PropertyIntelligenceOrchestrator,
    ProviderBudget,
)


def _sample_vrbo_item(**overrides):
    item = {
        "address": {"city": "Burbank", "stateProvince": "CA", "postalCode": "91506"},
        "bedrooms": 2,
        "bathrooms": {"full": 2, "half": 0, "toiletOnly": 0},
        "priceSummary": {
            "amount": 189,
            "formattedAmount": "$189",
            "pricePeriodDescription": "per night",
            "currencySymbol": "$",
        },
        "thumbnailUrl": "https://img.example/thumb.jpg",
        "canonicalLink": "https://www.vrbo.com/1943760",
        "averageRating": 4.8,
        "reviewCount": 32,
        "sleeps": 4,
        "propertyType": "Condo",
        "geoCode": {"latitude": 34.18, "longitude": -118.31},
        "headline": "Cozy Burbank retreat",
        "listingNumber": "1943760",
        "propertyId": "p123",
        "id": "1943760",
        "status": "active",
    }
    item.update(overrides)
    return item


def _fresh_orchestrator(client):
    class FixedClientOrchestrator(PropertyIntelligenceOrchestrator):
        def _init_mashvisor(self):
            return client

    return FixedClientOrchestrator(
        strategy="airbnb",
        asset_type="any",
        budget=ProviderBudget(
            rentcast_search=0, attom_detail=0, rentcast_detail=0,
            mashvisor_detail=1, mashvisor_vrbo=5, realtor_detail=0,
            rapidapi_real_estate_detail=0, deal_architect=0,
        ),
    )


def test_extract_vrbo_listings_returns_individual_listings():
    items = [_sample_vrbo_item()]

    listings = PropertyIntelligenceOrchestrator._extract_vrbo_listings(items)

    assert len(listings) == 1
    listing = listings[0]
    assert listing["address"] == "Burbank, CA, 91506"
    assert listing["beds"] == 2
    assert listing["baths"] == 2
    assert listing["sleeps"] == 4
    assert listing["nightly_rate"] == 189
    assert listing["nightly_rate_formatted"] == "$189"
    assert listing["rating"] == 4.8
    assert listing["review_count"] == 32
    assert listing["url"] == "https://www.vrbo.com/1943760"
    assert listing["listing_number"] == "1943760"


def test_extract_vrbo_listings_sorts_by_nightly_rate_descending():
    items = [
        _sample_vrbo_item(listingNumber="low", priceSummary={"amount": 90}),
        _sample_vrbo_item(listingNumber="high", priceSummary={"amount": 400}),
    ]

    listings = PropertyIntelligenceOrchestrator._extract_vrbo_listings(items)

    assert listings[0]["listing_number"] == "high"
    assert listings[1]["listing_number"] == "low"


def test_extract_vrbo_listings_skips_items_with_no_usable_signal():
    items = [
        {"listingNumber": "empty"},
        _sample_vrbo_item(listingNumber="has-data"),
    ]

    listings = PropertyIntelligenceOrchestrator._extract_vrbo_listings(items)

    assert len(listings) == 1
    assert listings[0]["listing_number"] == "has-data"


def test_extract_vrbo_listings_handles_empty_or_missing_items():
    assert PropertyIntelligenceOrchestrator._extract_vrbo_listings([]) == []
    assert PropertyIntelligenceOrchestrator._extract_vrbo_listings(None) == []


def test_get_vrbo_listings_for_market_caches_by_state_and_city():
    calls = []

    class FakeMashvisorClient:
        def get_newly_listed_vrbo(self, *, state, city):
            calls.append((state, city))
            return {"status": "success", "content": {"list": [_sample_vrbo_item()]}}

    orchestrator = _fresh_orchestrator(FakeMashvisorClient())

    first = orchestrator._get_vrbo_listings_for_market("CA", "Burbank")
    second = orchestrator._get_vrbo_listings_for_market("CA", "Burbank")

    assert len(calls) == 1
    assert first == second
    assert len(first) == 1


def test_get_vrbo_listings_for_market_handles_missing_client_or_location():
    orchestrator = _fresh_orchestrator(None)
    assert orchestrator._get_vrbo_listings_for_market("CA", "Burbank") == []

    class FakeMashvisorClient:
        def get_newly_listed_vrbo(self, *, state, city):
            raise AssertionError("should not be called without state/city")

    orchestrator = _fresh_orchestrator(FakeMashvisorClient())
    assert orchestrator._get_vrbo_listings_for_market(None, "Burbank") == []
    assert orchestrator._get_vrbo_listings_for_market("CA", None) == []


def test_enrich_with_mashvisor_populates_vrbo_nearby_listings_on_property():
    class FakeMashvisorClient:
        def validate_property_with_mashvisor(self, **kwargs):
            return {"property": {}, "lookup": {}, "comps": {}, "errors": []}

        def get_newly_listed_vrbo(self, *, state, city):
            return {"status": "success", "content": {"list": [_sample_vrbo_item()]}}

    orchestrator = _fresh_orchestrator(FakeMashvisorClient())

    prop = CanonicalProperty(address="1 Comp St", city="Burbank", state="CA", zip_code="91506")
    orchestrator._enrich_with_mashvisor(prop)

    assert len(prop.vrbo_nearby_listings) == 1
    assert prop.vrbo_nearby_listings[0]["listing_number"] == "1943760"

    result_dict = prop.to_result_dict()
    assert result_dict["vrbo_nearby_listings"] == prop.vrbo_nearby_listings
