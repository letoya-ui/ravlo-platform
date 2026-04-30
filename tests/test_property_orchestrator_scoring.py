from LoanMVP.services.investor.property_orchestrator import (
    CanonicalProperty,
    ProviderBudget,
    PropertyIntelligenceOrchestrator,
)


class NoMashvisorOrchestrator(PropertyIntelligenceOrchestrator):
    def _init_mashvisor(self):
        return None


def make_orchestrator(strategy="all", asset_type="any"):
    return NoMashvisorOrchestrator(
        strategy=strategy,
        asset_type=asset_type,
        budget=ProviderBudget(
            rentcast_search=0,
            attom_detail=0,
            rentcast_detail=0,
            mashvisor_detail=0,
            realtor_detail=0,
            rapidapi_real_estate_detail=0,
            deal_architect=4,
        ),
    )


def test_non_land_property_does_not_default_to_land_exit():
    orchestrator = make_orchestrator()
    prop = CanonicalProperty(
        address="12 Main St",
        city="Goshen",
        state="NY",
        zip_code="10924",
        listing_price=320000,
        purchase_price=320000,
        market_value=335000,
        monthly_rent_estimate=2400,
        square_feet=1800,
        property_type="Single Family",
        year_built=1988,
    )

    scored = orchestrator._recommend_exit_strategy(prop)

    assert scored.property_classification != "land"
    assert scored.best_exit_strategy != "land"


def test_deal_score_rewards_value_gap_and_rent_support():
    orchestrator = make_orchestrator(strategy="rental")
    strong = CanonicalProperty(
        address="7 Value Ave",
        listing_price=180000,
        purchase_price=180000,
        market_value=245000,
        monthly_rent_estimate=2100,
        square_feet=1500,
        property_type="Single Family",
        year_built=1995,
        days_on_market=74,
    )
    weak = CanonicalProperty(
        address="9 Retail Rd",
        listing_price=310000,
        purchase_price=310000,
        market_value=295000,
        monthly_rent_estimate=1450,
        square_feet=1450,
        property_type="Single Family",
        year_built=1995,
        days_on_market=8,
    )

    strong = orchestrator._recommend_exit_strategy(strong)
    weak = orchestrator._recommend_exit_strategy(weak)

    strong_score, strong_reasons, _ = orchestrator._score_candidate(strong)
    weak_score, _, weak_risks = orchestrator._score_candidate(weak)

    assert strong_score > weak_score
    assert any("below the current value signal" in reason for reason in strong_reasons)
    assert any("above the current value signal" in risk for risk in weak_risks)


def test_pre_rank_prefers_discounted_price_per_square_foot():
    orchestrator = make_orchestrator(strategy="flip")
    high_ppsf = CanonicalProperty(
        address="1 Expensive Way",
        listing_price=420000,
        purchase_price=420000,
        square_feet=1400,
        property_type="Single Family",
        year_built=2002,
    )
    low_ppsf = CanonicalProperty(
        address="2 Opportunity Ln",
        listing_price=255000,
        purchase_price=255000,
        square_feet=1900,
        property_type="Single Family",
        year_built=1972,
        days_on_market=92,
    )

    ranked = orchestrator._pre_rank_candidates([high_ppsf, low_ppsf])

    assert ranked[0].address == "2 Opportunity Ln"
    assert ranked[0].raw["deal_finder"]["pre_rank_score"] > ranked[1].raw["deal_finder"]["pre_rank_score"]
