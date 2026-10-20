"""Regression tests for using Mashvisor's real comps instead of relying
solely on its single black-box lookup estimate, and for the detail-enrichment
budget covering a full search instead of only its first 8 results.

Previously:
- ProviderBudget.mashvisor_detail defaulted to 8, but api_property_tool_search
  returns up to 25 results per search -- everything past the 8th silently
  fell back to a flat `traditional_rent * 1.55` / 62% occupancy guess in
  dealfinder_service._build_airbnb_strategy_card(), with no indication to
  the user that the number wasn't real data.
- _enrich_with_mashvisor() always called validate_property_with_mashvisor()
  with include_comps=False, so the real nearby-listing comps Mashvisor can
  return were never fetched or used, even though the plan has room for it.
"""
from LoanMVP.services.investor.property_orchestrator import (
    PropertyIntelligenceOrchestrator,
    ProviderBudget,
)


def test_mashvisor_detail_budget_covers_a_full_max_search():
    # api_property_tool_search clamps `limit` to 25 -- the budget must be
    # able to cover every result in the largest search, not just the first 8.
    assert ProviderBudget().mashvisor_detail >= 25


def test_summarize_mashvisor_comps_averages_real_comp_data():
    comps = [
        {"rental_income": 3000, "occupancy_rate": 70, "daily_rate": 150},
        {"rental_income": 3600, "occupancy_rate": 80, "daily_rate": 170},
    ]

    summary = PropertyIntelligenceOrchestrator._summarize_mashvisor_comps(comps)

    assert summary["comp_count"] == 2
    assert summary["avg_revenue"] == 3300
    assert summary["avg_occupancy_rate"] == 75
    assert summary["avg_adr"] == 160


def test_summarize_mashvisor_comps_handles_partial_fields():
    # One comp has revenue but no occupancy/ADR -- averages should only be
    # computed from comps that actually have that field, not treat missing
    # data as zero.
    comps = [
        {"rental_income": 2800},
        {"rental_income": 3200, "occupancy_rate": 65},
    ]

    summary = PropertyIntelligenceOrchestrator._summarize_mashvisor_comps(comps)

    assert summary["comp_count"] == 2
    assert summary["avg_revenue"] == 3000
    assert summary["avg_occupancy_rate"] == 65
    assert summary["avg_adr"] is None


def test_summarize_mashvisor_comps_returns_none_for_empty_or_unparseable():
    assert PropertyIntelligenceOrchestrator._summarize_mashvisor_comps([]) is None
    assert PropertyIntelligenceOrchestrator._summarize_mashvisor_comps(None) is None
    # A non-empty list where nothing matches any known field name should
    # fail safe (None) rather than silently average zeros.
    assert PropertyIntelligenceOrchestrator._summarize_mashvisor_comps(
        [{"unexpected_field": 123}]
    ) is None


def test_enrich_with_mashvisor_requests_comps():
    captured = {}

    class FakeMashvisorClient:
        def validate_property_with_mashvisor(self, **kwargs):
            captured.update(kwargs)
            return {"property": {}, "lookup": {}, "comps": {}, "errors": []}

    class FixedClientOrchestrator(PropertyIntelligenceOrchestrator):
        def _init_mashvisor(self):
            return FakeMashvisorClient()

    orchestrator = FixedClientOrchestrator(
        strategy="airbnb",
        asset_type="any",
        budget=ProviderBudget(
            rentcast_search=0, attom_detail=0, rentcast_detail=0,
            mashvisor_detail=1, realtor_detail=0, rapidapi_real_estate_detail=0,
            deal_architect=0,
        ),
    )

    from LoanMVP.services.investor.property_orchestrator import CanonicalProperty
    prop = CanonicalProperty(address="1 Comp St", city="Austin", state="TX", zip_code="78704")
    orchestrator._enrich_with_mashvisor(prop)

    assert captured.get("include_comps") is True
