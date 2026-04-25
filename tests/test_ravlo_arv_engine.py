"""
Tests for the Ravlo ARV Engine
------------------------------
Covers 6 scenarios:
1. Normal single-family home with good comps
2. Vacant lot (land value + finished-home ARV)
3. Provider AVMs disagreeing
4. Active listing used as upper-bound only
5. Weak comp rejection
6. ARV range calculation
"""

import sys
import os
import pytest

# Allow imports from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from LoanMVP.services.ravlo_subject_normalizer import normalize_subject, _detect_vacant_lot
from LoanMVP.services.ravlo_comp_scorer import score_comp, score_all_comps, INCLUSION_THRESHOLD
from LoanMVP.services.ravlo_arv_calculator import calculate_arv, _compute_confidence


# ─────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────

def _make_subject(**overrides):
    base = {
        "address": "123 Main St, Tampa, FL 33601",
        "property_type": "single_family",
        "is_vacant_lot": False,
        "beds": 3,
        "baths": 2.0,
        "living_sqft": 1800,
        "lot_sqft": 7200,
        "year_built": 2005,
        "last_sale_price": 250000,
        "last_sale_date": "2020-06-15",
        "current_listing_price": None,
        "estimated_value_by_source": {"rentcast": 350000, "attom_market": 340000},
        "rent_estimate_by_source": {"rentcast": 2200},
        "latitude": 27.95,
        "longitude": -82.46,
        "data_sources": {"attom": True, "rentcast": True, "mashvisor": False, "listing": False},
    }
    base.update(overrides)
    return base


def _make_comp(**overrides):
    base = {
        "address": "125 Main St, Tampa, FL 33601",
        "formattedAddress": "125 Main St, Tampa, FL 33601",
        "property_type": "single_family",
        "status": "Sold",
        "price": 360000,
        "sqft": 1750,
        "beds": 3,
        "baths": 2,
        "year_built": 2008,
        "lotSize": 7000,
        "distance": 0.2,
        "sold_date": "2024-01-15",
    }
    base.update(overrides)
    return base


# ─────────────────────────────────────────────────
# 1. Normal single-family home with good comps
# ─────────────────────────────────────────────────

class TestNormalSFH:
    def test_base_arv_near_comp_median(self):
        subject = _make_subject()
        comps = [
            _make_comp(address="125 Main St", price=360000, sqft=1750, distance=0.2),
            _make_comp(address="130 Main St", price=370000, sqft=1800, distance=0.3),
            _make_comp(address="135 Main St", price=355000, sqft=1700, distance=0.4),
            _make_comp(address="140 Oak Ave", price=380000, sqft=1850, distance=0.5),
        ]
        included, rejected = score_all_comps(subject, comps)
        assert len(included) >= 3, "Expected at least 3 included comps"

        providers = {
            "rentcast": {"avm": 350000},
            "attom": {"market_value": 340000},
        }
        result = calculate_arv(subject, included, rejected, providers)

        assert result["base"] > 0
        assert result["confidence"] in ("high", "medium")
        assert result["conservative"] < result["base"] < result["aggressive"]

    def test_high_confidence_with_many_sold_comps(self):
        subject = _make_subject()
        comps = [
            _make_comp(address=f"{i} Main St", price=350000 + i * 5000, distance=0.2 + i * 0.1)
            for i in range(6)
        ]
        included, _ = score_all_comps(subject, comps)
        providers = {"rentcast": {"avm": 360000}}
        result = calculate_arv(subject, included, [], providers)
        assert result["confidence_score"] >= 50


# ─────────────────────────────────────────────────
# 2. Vacant lot
# ─────────────────────────────────────────────────

class TestVacantLot:
    def test_detect_vacant_lot_by_type(self):
        assert _detect_vacant_lot("vacant land", None, 10000) is True
        assert _detect_vacant_lot("lot", None, 5000) is True
        assert _detect_vacant_lot("single_family", 1800, 7200) is False

    def test_detect_vacant_lot_by_sqft(self):
        assert _detect_vacant_lot("", 0, 8000) is True
        assert _detect_vacant_lot("", None, 8000) is True

    def test_lot_arv_produces_land_value_and_finished_arv(self):
        subject = _make_subject(
            is_vacant_lot=True,
            property_type="vacant land",
            living_sqft=0,
            lot_sqft=12000,
        )
        # Nearby finished homes as comps
        comps = [
            _make_comp(address="200 Villa Way", price=1625000, sqft=3200, distance=0.3, property_type="single_family"),
            _make_comp(address="210 Villa Way", price=1580000, sqft=3100, distance=0.4, property_type="single_family"),
        ]
        included, rejected = score_all_comps(subject, comps)
        providers = {"attom": {"assessed_value": 450000, "market_value": 450000}}
        result = calculate_arv(subject, included, rejected, providers)

        assert result["land_value"] is not None
        assert result["land_value"] > 0
        assert result["base"] > result["land_value"], "Finished-home ARV should exceed land value"
        assert "Vacant lot" in " ".join(result["warnings"])


# ─────────────────────────────────────────────────
# 3. Provider AVMs disagreeing
# ─────────────────────────────────────────────────

class TestProviderDisagreement:
    def test_web_search_trigger_on_disagreement(self):
        from LoanMVP.services.ravlo_web_search import should_trigger_web_search

        subject = _make_subject()
        arv_result = {"confidence": "medium", "base": 400000}
        included = [_make_comp(status_normalized="sold", comp_score=65)] * 3
        # AVMs disagree by >15%
        providers = {
            "rentcast": {"avm": 350000},
            "attom": {"market_value": 500000},
        }
        assert should_trigger_web_search(subject, arv_result, included, providers) is True

    def test_no_trigger_when_avms_agree(self):
        from LoanMVP.services.ravlo_web_search import should_trigger_web_search

        subject = _make_subject()
        arv_result = {"confidence": "high", "base": 355000}
        included = [
            {**_make_comp(), "status_normalized": "sold", "comp_score": 70}
            for _ in range(4)
        ]
        providers = {
            "rentcast": {"avm": 350000},
            "attom": {"market_value": 360000},
        }
        assert should_trigger_web_search(subject, arv_result, included, providers) is False


# ─────────────────────────────────────────────────
# 4. Active listing used as upper-bound only
# ─────────────────────────────────────────────────

class TestActiveListingUpperBound:
    def test_active_listing_scores_lower_than_sold(self):
        subject = _make_subject()
        sold = _make_comp(status="Sold", price=360000)
        active = _make_comp(address="999 Beach Dr", status="Active", price=500000)

        scored_sold = score_comp(subject, sold)
        scored_active = score_comp(subject, active)

        assert scored_sold["comp_score"] > scored_active["comp_score"], (
            "Sold comp should score higher than active listing"
        )

    def test_active_listing_inflates_aggressive_not_base(self):
        subject = _make_subject()
        sold_comps = [
            _make_comp(address=f"{i} Main St", price=360000, status="Sold", distance=0.3)
            for i in range(3)
        ]
        active_comp = _make_comp(
            address="999 Beach Dr", price=500000, sqft=1800,
            status="Active", distance=0.2,
        )
        all_comps = sold_comps + [active_comp]
        included, rejected = score_all_comps(subject, all_comps)

        providers = {"rentcast": {"avm": 355000}}
        result = calculate_arv(subject, included, rejected, providers)

        # Aggressive should be higher than base due to active listing
        assert result["aggressive"] > result["base"]
        # Base should not be pulled up to the active listing price
        assert result["base"] < 450000, "Base ARV should not be pulled up by active listing"


# ─────────────────────────────────────────────────
# 5. Weak comp rejection
# ─────────────────────────────────────────────────

class TestWeakCompRejection:
    def test_distant_old_comp_rejected(self):
        subject = _make_subject()
        weak_comp = _make_comp(
            address="999 Far Away Rd",
            distance=5.0,
            sold_date="2020-01-01",
            sqft=3500,
            beds=5,
            baths=4,
            property_type="condo",
        )
        scored = score_comp(subject, weak_comp)
        assert scored["comp_score"] < INCLUSION_THRESHOLD
        assert scored["included"] is False
        assert scored["rejection_reason"] is not None

    def test_strong_comp_included(self):
        subject = _make_subject()
        strong_comp = _make_comp(distance=0.15, sold_date="2024-06-01")
        scored = score_comp(subject, strong_comp)
        assert scored["comp_score"] >= INCLUSION_THRESHOLD
        assert scored["included"] is True


# ─────────────────────────────────────────────────
# 6. ARV range calculation
# ─────────────────────────────────────────────────

class TestARVRange:
    def test_conservative_lt_base_lt_aggressive(self):
        subject = _make_subject()
        comps = [
            _make_comp(address=f"{i} Test St", price=340000 + i * 10000, distance=0.3)
            for i in range(4)
        ]
        included, rejected = score_all_comps(subject, comps)
        providers = {"rentcast": {"avm": 360000}}
        result = calculate_arv(subject, included, rejected, providers)

        assert result["conservative"] > 0
        assert result["base"] > 0
        assert result["aggressive"] > 0
        assert result["conservative"] <= result["base"] <= result["aggressive"]

    def test_bands_are_reasonable(self):
        subject = _make_subject()
        comps = [
            _make_comp(address=f"{i} Test St", price=350000 + i * 5000, distance=0.3)
            for i in range(5)
        ]
        included, rejected = score_all_comps(subject, comps)
        providers = {"rentcast": {"avm": 360000}}
        result = calculate_arv(subject, included, rejected, providers)

        base = result["base"]
        cons = result["conservative"]
        agg = result["aggressive"]

        # Conservative should be within 15% below base
        assert cons >= base * 0.85, f"Conservative {cons} too far below base {base}"
        # Aggressive should be within 20% above base
        assert agg <= base * 1.20, f"Aggressive {agg} too far above base {base}"

    def test_no_comps_returns_low_confidence(self):
        subject = _make_subject()
        providers = {"rentcast": {"avm": 360000}}
        result = calculate_arv(subject, [], [], providers)
        assert result["confidence"] in ("low", "medium")


# ─────────────────────────────────────────────────
# Normalizer tests
# ─────────────────────────────────────────────────

class TestNormalizer:
    def test_merges_attom_and_rentcast(self):
        attom = {"address": "123 Main", "beds": 3, "sqft": 1800, "market_value": 350000}
        rentcast = {"bedrooms": 3, "squareFootage": 1850, "price": 360000}
        result = normalize_subject(attom, rentcast)

        assert result["address"] == "123 Main"
        assert result["beds"] == 3
        assert result["estimated_value_by_source"]["attom_market"] == 350000
        assert result["estimated_value_by_source"]["rentcast"] == 360000

    def test_empty_providers(self):
        result = normalize_subject({}, {})
        assert result["address"] is None
        assert result["is_vacant_lot"] is False
        assert result["data_sources"]["attom"] is False
