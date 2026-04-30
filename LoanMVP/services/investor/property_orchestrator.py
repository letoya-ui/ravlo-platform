from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

_log = logging.getLogger(__name__)


def _normalize_address_text(value: str) -> str:
    """Lowercase, strip punctuation, and collapse whitespace for fuzzy matching."""
    text = re.sub(r"[^a-z0-9\s]", "", str(value or "").lower())
    return " ".join(text.split())

from LoanMVP.services.attom_service import build_attom_dealfinder_profile, AttomServiceError
from LoanMVP.services.rentcast_service import (
    get_rentcast_rent_estimate,
    get_rentcast_value_estimate,
    get_rentcast_sale_listings,
    find_rentcast_sale_listing,
    normalize_rentcast_sale_listing,
    RentCastServiceError,
)
from LoanMVP.services.mashvisor_client import MashvisorClient, MashvisorError
from LoanMVP.services.mashvisor_service import normalize_mashvisor_validation
from LoanMVP.services.realtor_provider import (
    fetch_realtor_data,
    fetch_realtor_photos,
    search_realtor_for_sale,
)

from LoanMVP.services.investor.investor_route_helpers import (
    _normalize_asset_type,
    _asset_type_label,
    _property_matches_asset_type,
    _annotate_deal_finder_opportunity,
)
from LoanMVP.services.investor.investor_media_helpers import (
    _normalize_photo_urls,
    _resolve_photo,
)

try:
    from LoanMVP.services.rapidapi_real_estate_provider import (
        fetch_rapidapi_real_estate_photos,
    )
except Exception:
    fetch_rapidapi_real_estate_photos = None

@dataclass
class ProviderBudget:
    rentcast_search: int = 1
    attom_detail: int = 4
    rentcast_detail: int = 4
    mashvisor_detail: int = 4
    realtor_detail: int = 4
    rapidapi_real_estate_detail: int = 4
    deal_architect: int = 4

    def use(self, key: str, amount: int = 1) -> bool:
        current = getattr(self, key, 0)
        if current < amount:
            return False
        setattr(self, key, current - amount)
        return True


@dataclass
class CanonicalProperty:
    provider_ids: Dict[str, Any] = field(default_factory=dict)

    address: Optional[str] = None
    address_line1: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None

    listing_price: Optional[float] = None
    purchase_price: Optional[float] = None
    market_value: Optional[float] = None
    assessed_value: Optional[float] = None
    last_sale_price: Optional[float] = None
    last_sale_date: Optional[str] = None
    tax_amount: Optional[float] = None

    beds: Optional[float] = None
    baths: Optional[float] = None
    square_feet: Optional[int] = None
    lot_size_sqft: Optional[int] = None
    year_built: Optional[int] = None
    property_type: Optional[str] = None

    monthly_rent_estimate: Optional[float] = None
    arv: Optional[float] = None

    primary_photo: Optional[str] = None
    photos: List[str] = field(default_factory=list)

    status: Optional[str] = None
    days_on_market: Optional[int] = None
    description: Optional[str] = None

    latitude: Optional[float] = None
    longitude: Optional[float] = None

    strategy: Optional[str] = None
    strategy_tag: Optional[str] = None
    recommended_strategy: Optional[str] = None
    estimated_best_use: Optional[str] = None

    deal_score: Optional[int] = None
    opportunity_tier: Optional[str] = None
    deal_finder_signal: Optional[str] = None
    next_step: Optional[str] = None
    comp_confidence: Optional[str] = None
    buyer_demand_score: Optional[int] = None
    buy_box_fit_score: Optional[int] = None
    spread_to_arv_pct: Optional[float] = None
    equity_spread: Optional[float] = None
    deal_velocity: Optional[str] = None
    rank_reason: Optional[str] = None

    primary_strengths: List[str] = field(default_factory=list)
    primary_risks: List[str] = field(default_factory=list)
    risk_notes: List[str] = field(default_factory=list)
    why_it_made_list: List[str] = field(default_factory=list)

    traditional_cap_rate: Optional[float] = None
    traditional_cash_on_cash: Optional[float] = None
    airbnb_rent_estimate: Optional[float] = None
    airbnb_cap_rate: Optional[float] = None
    airbnb_cash_on_cash: Optional[float] = None
    airbnb_nightly_rate: Optional[float] = None
    airbnb_cash_flow: Optional[float] = None
    occupancy_rate: Optional[float] = None

    property_classification: Optional[str] = None
    best_exit_strategy: Optional[str] = None
    best_exit_reason: Optional[str] = None
    ai_recommendation: Dict[str, Any] = field(default_factory=dict)
    exit_strategy_cards: List[Dict[str, Any]] = field(default_factory=list)

    value_sources: Dict[str, str] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_result_dict(self) -> Dict[str, Any]:
        return {
            "property_id": self.provider_ids.get("realtor") or self.provider_ids.get("rentcast"),
            "attom_id": self.provider_ids.get("attom"),
            "address": self.address,
            "address_line1": self.address_line1 or self.address,
            "city": self.city,
            "state": self.state,
            "zip_code": self.zip_code,
            "price": self.listing_price,
            "listing_price": self.listing_price,
            "purchase_price": self.purchase_price,
            "market_value": self.market_value,
            "assessed_value": self.assessed_value,
            "last_sale_price": self.last_sale_price,
            "last_sale_date": self.last_sale_date,
            "tax_amount": self.tax_amount,
            "beds": self.beds,
            "baths": self.baths,
            "square_feet": self.square_feet,
            "sqft": self.square_feet,
            "lot_size_sqft": self.lot_size_sqft,
            "year_built": self.year_built,
            "property_type": self.property_type,
            "traditional_rent": self.monthly_rent_estimate,
            "monthly_rent_estimate": self.monthly_rent_estimate,
            "arv": self.arv,
            "primary_photo": self.primary_photo,
            "image_url": self.primary_photo,
            "photos": self.photos,
            "listing_photos": self.photos,
            "status": self.status,
            "days_on_market": self.days_on_market,
            "description": self.description,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "strategy": self.strategy,
            "strategy_tag": self.strategy_tag,
            "recommended_strategy": self.recommended_strategy,
            "estimated_best_use": self.estimated_best_use,
            "deal_score": self.deal_score,
            "opportunity_tier": self.opportunity_tier,
            "deal_finder_signal": self.deal_finder_signal,
            "next_step": self.next_step,
            "comp_confidence": self.comp_confidence,
            "buyer_demand_score": self.buyer_demand_score,
            "buy_box_fit_score": self.buy_box_fit_score,
            "spread_to_arv_pct": self.spread_to_arv_pct,
            "equity_spread": self.equity_spread,
            "deal_velocity": self.deal_velocity,
            "rank_reason": self.rank_reason,
            "primary_strengths": self.primary_strengths,
            "primary_risks": self.primary_risks,
            "risk_notes": self.risk_notes,
            "why_it_made_list": self.why_it_made_list,
            "traditional_cap_rate": self.traditional_cap_rate,
            "traditional_cash_on_cash": self.traditional_cash_on_cash,
            "airbnb_rent_estimate": self.airbnb_rent_estimate,
            "airbnb_revenue": self.airbnb_rent_estimate,
            "airbnb_cap_rate": self.airbnb_cap_rate,
            "airbnb_cash_on_cash": self.airbnb_cash_on_cash,
            "airbnb_nightly_rate": self.airbnb_nightly_rate,
            "daily_rate": self.airbnb_nightly_rate,
            "airbnb_cash_flow": self.airbnb_cash_flow,
            "cash_flow": self.airbnb_cash_flow,
            "occupancy_rate": self.occupancy_rate,
            "property_classification": self.property_classification,
            "best_exit_strategy": self.best_exit_strategy,
            "best_exit_reason": self.best_exit_reason,
            "ai_recommendation": self.ai_recommendation,
            "exit_strategy_cards": self.exit_strategy_cards,
            "value_sources": self.value_sources,
            "raw": self.raw,
        }


class PropertyIntelligenceOrchestrator:
    def __init__(self, strategy: str, asset_type: str, budget: Optional[ProviderBudget] = None):
        self.strategy = (strategy or "flip").strip().lower()
        self.asset_type = _normalize_asset_type(asset_type)
        self.budget = budget or ProviderBudget()
        self._mashvisor = self._init_mashvisor()

    def _init_mashvisor(self):
        try:
            client = MashvisorClient()
            _log.info("[mashvisor] client initialised")
            return client
        except Exception as exc:
            _log.warning("[mashvisor] client init failed: %s", exc)
            return None

    @staticmethod
    def _as_float(v):
        try:
            if v in (None, "", "None"):
                return None
            if isinstance(v, (int, float)):
                return float(v)
            return float(str(v).replace("$", "").replace(",", "").strip())
        except Exception:
            return None

    @staticmethod
    def _as_int(v):
        try:
            n = PropertyIntelligenceOrchestrator._as_float(v)
            return int(round(n)) if n is not None else None
        except Exception:
            return None

    @staticmethod
    def _first_truthy(*vals):
        for v in vals:
            if v not in (None, "", [], {}):
                return v
        return None

    @staticmethod
    def _normalize_photo_candidates(*sources):
        return _normalize_photo_urls(*sources)

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    @staticmethod
    def _median(values: List[float]) -> Optional[float]:
        clean = sorted(v for v in values if v is not None and v > 0)
        if not clean:
            return None
        mid = len(clean) // 2
        if len(clean) % 2:
            return clean[mid]
        return (clean[mid - 1] + clean[mid]) / 2.0

    def _occupancy_percent(self, value: Any) -> float:
        occupancy = self._as_float(value) or 0.0
        if 0 < occupancy <= 1:
            return occupancy * 100.0
        return occupancy

    def _extract_mashvisor_photos(
        self,
        normalized: Dict[str, Any],
        raw_result: Dict[str, Any] | None = None,
    ) -> List[str]:
        raw_result = raw_result or {}

        # raw_result is the validate dict with keys: property, lookup, comps, errors.
        # Extract the nested "content" dicts from property and lookup responses.
        prop_resp = raw_result.get("property") or {}
        prop_content = prop_resp.get("content") if isinstance(prop_resp, dict) else {}
        if not isinstance(prop_content, dict):
            prop_content = {}

        lookup_resp = raw_result.get("lookup") or {}
        lookup_content = lookup_resp.get("content") if isinstance(lookup_resp, dict) else {}
        if not isinstance(lookup_content, dict):
            lookup_content = {}

        photos = self._normalize_photo_candidates(
            normalized.get("photos"),
            normalized.get("images"),
            normalized.get("image"),
            normalized.get("extra_images"),
            prop_content.get("photos"),
            prop_content.get("images"),
            prop_content.get("image"),
            prop_content.get("extra_images"),
            lookup_content.get("photos"),
            lookup_content.get("images"),
            lookup_content.get("image"),
            lookup_content.get("extra_images"),
        )

        return photos

    def _classify_property(self, cp: CanonicalProperty) -> str:
        prop_type = (cp.property_type or "").lower()
        has_structure = bool(cp.square_feet or cp.beds or cp.baths)
        lot_size = cp.lot_size_sqft or 0

        looks_like_land = any(x in prop_type for x in ["land", "lot", "vacant", "acre", "parcel"])
        fixer_signal = bool(cp.year_built and cp.year_built < 1980)

        if looks_like_land or (lot_size > 0 and not has_structure):
            return "land"

        if cp.airbnb_rent_estimate and self._occupancy_percent(cp.occupancy_rate) >= 45:
            return "str_candidate"

        if cp.monthly_rent_estimate and (cp.market_value or cp.listing_price):
            return "rental_candidate"

        if fixer_signal or (cp.assessed_value and cp.market_value and cp.assessed_value < cp.market_value):
            return "fixer_upper"

        return "general_opportunity"

    def _estimate_rehab_cost(self, cp: CanonicalProperty) -> float:
        if self._classify_property(cp) == "land":
            return 0.0

        sqft = self._as_float(cp.square_feet) or 0.0
        year_built = self._as_int(cp.year_built)

        if year_built and year_built < 1950:
            floor, per_sqft = 65000.0, 42.0
        elif year_built and year_built < 1980:
            floor, per_sqft = 42000.0, 30.0
        elif year_built and year_built < 2005:
            floor, per_sqft = 22000.0, 18.0
        else:
            floor, per_sqft = 12000.0, 10.0

        if sqft <= 0:
            return floor

        return min(max(sqft * per_sqft, floor), 180000.0)

    def _pre_rank_candidates(self, candidates: List[CanonicalProperty]) -> List[CanonicalProperty]:
        price_per_sqft_values: List[float] = []
        for cp in candidates:
            price = self._as_float(cp.listing_price or cp.purchase_price)
            sqft = self._as_float(cp.square_feet)
            if price and sqft:
                price_per_sqft_values.append(price / sqft)

        market_ppsf = self._median(price_per_sqft_values)

        def score(cp: CanonicalProperty) -> float:
            value = 50.0
            price = self._as_float(cp.listing_price or cp.purchase_price)
            sqft = self._as_float(cp.square_feet)
            ppsf = (price / sqft) if price and sqft else None
            classification = self._classify_property(cp)

            if ppsf and market_ppsf:
                ratio = ppsf / market_ppsf
                if ratio <= 0.72:
                    value += 18
                elif ratio <= 0.86:
                    value += 12
                elif ratio <= 0.95:
                    value += 6
                elif ratio >= 1.25:
                    value -= 10

            if cp.days_on_market is not None:
                dom = cp.days_on_market
                if 21 <= dom <= 120:
                    value += 5
                elif 121 <= dom <= 240:
                    value += 8
                elif dom > 240:
                    value += 4

            if self.strategy == "flip" and cp.year_built and cp.year_built < 1980:
                value += 5
            elif self.strategy in {"rental", "airbnb"} and cp.year_built and cp.year_built < 1950:
                value -= 4

            if self.strategy == "land":
                value += 14 if classification == "land" else -16
            elif classification == "land":
                value -= 12

            if cp.photos or cp.primary_photo:
                value += 3
            if cp.address and (cp.city or cp.zip_code):
                value += 2
            if cp.beds or cp.baths:
                value += 2
            if sqft:
                value += 2

            return value

        for cp in candidates:
            cp.raw.setdefault("deal_finder", {})
            cp.raw["deal_finder"]["pre_rank_score"] = round(score(cp), 2)

        return sorted(candidates, key=score, reverse=True)

    def _build_exit_strategy_cards(self, cp: CanonicalProperty) -> List[Dict[str, Any]]:
        purchase_price = self._as_float(cp.purchase_price) or self._as_float(cp.listing_price) or 0.0
        rehab_cost = self._estimate_rehab_cost(cp)
        arv = self._as_float(cp.arv) or self._as_float(cp.market_value) or 0.0
        monthly_rent = self._as_float(cp.monthly_rent_estimate) or 0.0
        airbnb_monthly = self._as_float(cp.airbnb_rent_estimate) or 0.0
        occupancy = self._occupancy_percent(cp.occupancy_rate)

        flip_basis = purchase_price + rehab_cost
        holding_cost = flip_basis * 0.06 if flip_basis > 0 else 0.0
        selling_cost = arv * 0.08 if arv > 0 else 0.0
        flip_total = flip_basis + holding_cost + selling_cost
        flip_profit = (arv - flip_total) if arv > 0 and flip_basis > 0 else 0.0
        flip_roi = (flip_profit / flip_basis * 100.0) if flip_basis > 0 else 0.0

        monthly_taxes = (self._as_float(cp.tax_amount) or 0.0) / 12.0
        insurance = max(purchase_price * 0.004 / 12.0, 100.0) if purchase_price > 0 else 150.0
        operating_reserve = monthly_rent * 0.28 if monthly_rent > 0 else 0.0
        rental_expenses = operating_reserve + monthly_taxes + insurance
        rental_noi = monthly_rent - rental_expenses if monthly_rent > 0 else 0.0
        monthly_debt = purchase_price * 0.0075 if purchase_price > 0 else 0.0
        rental_cashflow = rental_noi - monthly_debt if monthly_rent > 0 else 0.0
        annual_noi = rental_noi * 12.0
        rental_cap = (annual_noi / purchase_price * 100.0) if purchase_price > 0 else 0.0
        rental_dscr = (rental_noi / max(monthly_debt, 1.0)) if purchase_price > 0 else 0.0

        airbnb_expense_ratio = 0.42 if occupancy >= 55 else 0.48
        airbnb_net = airbnb_monthly * (1.0 - airbnb_expense_ratio) if airbnb_monthly > 0 else 0.0
        airbnb_cashflow = airbnb_net - monthly_debt if airbnb_monthly > 0 else 0.0
        airbnb_roi = ((airbnb_net * 12.0) / purchase_price * 100.0) if purchase_price > 0 else 0.0

        is_land = self._classify_property(cp) == "land"
        land_score = 70.0 if is_land else 0.0
        land_upside = ((cp.market_value or 0) - purchase_price) if (cp.market_value and purchase_price) else 0.0

        return [
            {
                "key": "flip",
                "label": "Flip",
                "headline_label": "Projected Profit",
                "headline_value": flip_profit,
                "score": flip_roi,
                "summary": "Resale-driven value-add path.",
                "metrics": {
                    "purchase_price": purchase_price,
                    "rehab_cost": rehab_cost,
                    "holding_cost": holding_cost,
                    "selling_cost": selling_cost,
                    "arv": arv,
                    "profit": flip_profit,
                    "roi": flip_roi,
                    "total_investment": flip_total,
                },
            },
            {
                "key": "rental",
                "label": "Rental",
                "headline_label": "Monthly Cash Flow",
                "headline_value": rental_cashflow,
                "score": rental_cap,
                "summary": "Long-term hold and income path.",
                "metrics": {
                    "monthly_rent": monthly_rent,
                    "monthly_noi": rental_noi,
                    "monthly_debt": monthly_debt,
                    "net_cashflow": rental_cashflow,
                    "annual_noi": annual_noi,
                    "cap_rate": rental_cap,
                    "dscr": rental_dscr,
                },
            },
            {
                "key": "airbnb",
                "label": "Airbnb",
                "headline_label": "Net Monthly",
                "headline_value": airbnb_net,
                "score": airbnb_roi,
                "summary": "Short-term rental revenue path.",
                "metrics": {
                    "gross_monthly": airbnb_monthly,
                    "net_monthly": airbnb_net,
                    "monthly_cash_flow": airbnb_cashflow,
                    "occupancy_rate": occupancy,
                    "annualized_roi": airbnb_roi,
                },
            },
            {
                "key": "land",
                "label": "Land / Build",
                "headline_label": "Optionality Score",
                "headline_value": land_score,
                "score": land_score,
                "summary": "Land optionality or build-out path.",
                "metrics": {
                    "land_value": purchase_price,
                    "projected_upside": land_upside,
                    "score": land_score,
                    "lot_size_sqft": cp.lot_size_sqft,
                },
            },
        ]

    def _recommend_exit_strategy(self, cp: CanonicalProperty) -> CanonicalProperty:
        cards = self._build_exit_strategy_cards(cp)
        property_classification = self._classify_property(cp)

        by_key = {card["key"]: card for card in cards}
        flip_metrics = by_key.get("flip", {}).get("metrics", {})
        rental_metrics = by_key.get("rental", {}).get("metrics", {})
        airbnb_metrics = by_key.get("airbnb", {}).get("metrics", {})

        scores = {
            "flip": (
                (self._as_float(flip_metrics.get("roi")) or 0.0) * 1.2
                + self._clamp((self._as_float(flip_metrics.get("profit")) or 0.0) / 5000.0, -18.0, 22.0)
            ),
            "rental": (
                (self._as_float(rental_metrics.get("cap_rate")) or 0.0) * 2.0
                + self._clamp((self._as_float(rental_metrics.get("net_cashflow")) or 0.0) / 100.0, -12.0, 16.0)
                + self._clamp(((self._as_float(rental_metrics.get("dscr")) or 0.0) - 1.0) * 10.0, -8.0, 10.0)
            ),
            "airbnb": (
                (self._as_float(airbnb_metrics.get("annualized_roi")) or 0.0) * 1.25
                + self._clamp((self._as_float(airbnb_metrics.get("monthly_cash_flow")) or 0.0) / 150.0, -12.0, 16.0)
                + self._clamp(self._occupancy_percent(airbnb_metrics.get("occupancy_rate")) / 10.0, 0.0, 8.0)
            ),
            "land": (self._as_float(by_key.get("land", {}).get("score")) or 0.0),
        }

        if property_classification == "land":
            scores["land"] += 20
            scores["flip"] -= 20
            scores["rental"] -= 20
            scores["airbnb"] -= 20
        else:
            scores["land"] = -999.0

        if self.strategy in scores and self.strategy != "all":
            scores[self.strategy] += 8

        if property_classification == "fixer_upper":
            scores["flip"] += 10
        elif property_classification == "rental_candidate":
            scores["rental"] += 10
        elif property_classification == "str_candidate":
            scores["airbnb"] += 10

        best = max(scores, key=scores.get) if scores else "flip"

        reasons = {
            "flip": "Flip shows the strongest spread between basis and resale value.",
            "rental": "Rental shows the strongest risk-adjusted hold profile with recurring income support.",
            "airbnb": "Short-term rental shows the strongest revenue upside under current assumptions.",
            "land": "This opportunity reads more like land optionality or a build-oriented play than a standard residential hold.",
        }

        why_map = {
            "flip": [
                "Projected resale spread is competitive.",
                "This looks more like a value-add execution path than a stabilized hold.",
                "Current value signals support a resale thesis.",
            ],
            "rental": [
                "Long-term rent support is present.",
                "The hold profile appears more stable than the resale spread.",
                "This asset fits a recurring-income strategy.",
            ],
            "airbnb": [
                "Short-term revenue appears stronger than long-term rent.",
                "Hospitality upside may justify deeper underwriting.",
                "Revenue concentration is stronger under an STR path.",
            ],
            "land": [
                "Lot and site profile matter more than in-place operations.",
                "This appears better suited to land optionality or build-out.",
                "Traditional residential income assumptions are weaker here.",
            ],
        }

        watch_map = {
            "flip": [
                "Verify rehab scope and resale timeline.",
                "Stress-test ARV against conservative comps.",
            ],
            "rental": [
                "Confirm taxes, insurance, and maintenance assumptions.",
                "Validate rent support with fresh comps.",
            ],
            "airbnb": [
                "Validate STR regulations and seasonality.",
                "Pressure-test occupancy and nightly assumptions.",
            ],
            "land": [
                "Verify zoning and entitlement path.",
                "Confirm utility access and frontage.",
            ],
        }

        cp.property_classification = property_classification
        cp.best_exit_strategy = best
        cp.best_exit_reason = reasons[best]
        cp.exit_strategy_cards = cards
        cp.ai_recommendation = {
            "confidence": "high" if scores.get(best, 0) >= 12 else "moderate",
            "why": why_map[best],
            "watch_items": watch_map[best],
        }
        return cp

    def _score_candidate(self, cp: CanonicalProperty) -> Tuple[int, List[str], List[str]]:
        cards = cp.exit_strategy_cards or self._build_exit_strategy_cards(cp)
        by_key = {card["key"]: card for card in cards}
        flip = by_key.get("flip", {}).get("metrics", {})
        rental = by_key.get("rental", {}).get("metrics", {})
        airbnb = by_key.get("airbnb", {}).get("metrics", {})

        score = 44.0
        why: List[str] = []
        risks: List[str] = []

        price = self._as_float(cp.purchase_price or cp.listing_price)
        value = self._as_float(cp.arv or cp.market_value)
        rent = self._as_float(cp.monthly_rent_estimate)

        if price and value:
            discount = (value - price) / value
            if discount >= 0.20:
                score += 24
                why.append("Price is at least 20% below the current value signal.")
            elif discount >= 0.12:
                score += 17
                why.append("Price is meaningfully below the current value signal.")
            elif discount >= 0.06:
                score += 10
                why.append("There is a modest value gap to validate.")
            elif discount <= -0.05:
                score -= 14
                risks.append("Asking price is above the current value signal.")
        elif not value:
            score -= 8
            risks.append("Value signal still needs validation.")

        flip_profit = self._as_float(flip.get("profit")) or 0.0
        flip_roi = self._as_float(flip.get("roi")) or 0.0
        if flip_profit >= 75000:
            score += 15
            why.append("Flip spread clears a strong profit threshold.")
        elif flip_profit >= 40000:
            score += 10
            why.append("Flip spread is worth deeper underwriting.")
        elif flip_profit < 0 and (self.strategy == "flip" or cp.best_exit_strategy == "flip"):
            score -= 10
            risks.append("Conservative flip math is currently negative.")

        if flip_roi >= 25:
            score += 10
        elif flip_roi >= 16:
            score += 6

        if price and rent:
            rent_to_price = (rent * 12.0) / price
            if rent_to_price >= 0.12:
                score += 16
                why.append("Rent-to-price ratio clears the 1% rule.")
            elif rent_to_price >= 0.10:
                score += 12
                why.append("Rent-to-price ratio is strong for a hold review.")
            elif rent_to_price >= 0.08:
                score += 8
                why.append("Rental income support is present.")
            elif self.strategy == "rental":
                score -= 8
                risks.append("Rent-to-price ratio is light for a rental-first search.")
        elif self.strategy == "rental":
            score -= 10
            risks.append("Rental strategy needs a rent estimate.")

        cap_rate = self._as_float(rental.get("cap_rate")) or 0.0
        dscr = self._as_float(rental.get("dscr")) or 0.0
        if cap_rate >= 8:
            score += 10
        elif cap_rate >= 6:
            score += 6
        if dscr >= 1.25:
            score += 6
        elif self.strategy == "rental" and dscr and dscr < 1.0:
            score -= 6
            risks.append("Debt-service coverage looks tight.")

        airbnb_cashflow = self._as_float(airbnb.get("monthly_cash_flow")) or 0.0
        airbnb_roi = self._as_float(airbnb.get("annualized_roi")) or 0.0
        if self.strategy == "airbnb":
            if cp.airbnb_rent_estimate:
                score += 6
                why.append("Short-term rental revenue support is available.")
            else:
                score -= 10
                risks.append("Short-term rental strategy needs stronger STR data.")
            if airbnb_cashflow > 350:
                score += 8
            if airbnb_roi >= 10:
                score += 6

        if self.strategy != "all" and cp.best_exit_strategy and cp.best_exit_strategy != self.strategy:
            score -= 5
            risks.append(f"Best current exit reads as {cp.best_exit_strategy}, not {self.strategy}.")
        elif self.strategy != "all" and cp.best_exit_strategy == self.strategy:
            score += 5

        if cp.days_on_market is not None:
            if 45 <= cp.days_on_market <= 180:
                score += 5
                why.append("Days on market may create negotiation room.")
            elif cp.days_on_market > 240:
                score += 2
                risks.append("Stale listing; verify condition and seller motivation.")

        if cp.year_built and cp.year_built < 1950:
            score -= 6
            risks.append("Older property may require heavier systems review.")
        elif cp.year_built and cp.year_built < 1980 and self.strategy == "flip":
            score += 3
            why.append("Older property profile can support a value-add plan.")

        classification = self._classify_property(cp)
        if classification == "land" and self.strategy not in {"land", "all"} and self.asset_type != "land":
            score -= 12
            risks.append("This reads as land/build optionality, not an in-place income deal.")
        if classification != "land" and self.strategy == "land":
            score -= 14
            risks.append("Selected land strategy does not match this property type.")

        if cp.photos or cp.primary_photo:
            score += 2
        if cp.square_feet:
            score += 2
        if cp.market_value and cp.monthly_rent_estimate:
            score += 4

        clean_score = int(round(self._clamp(score, 1, 99)))
        return clean_score, why[:4], risks[:3]

    def _apply_marketplace_signals(self, cp: CanonicalProperty) -> CanonicalProperty:
        """Add deal-marketplace style signals for faster ranking and review."""
        price = self._as_float(cp.purchase_price or cp.listing_price)
        value = self._as_float(cp.arv or cp.market_value)
        rent = self._as_float(cp.monthly_rent_estimate)
        score = self._as_float(cp.deal_score) or 0.0
        photo_count = len(self._normalize_photo_candidates(cp.photos, cp.primary_photo))

        equity_spread = None
        spread_pct = None
        if price and value:
            equity_spread = value - price
            spread_pct = (equity_spread / value) * 100.0 if value > 0 else None

        demand = 40.0
        if photo_count >= 4:
            demand += 10
        elif photo_count:
            demand += 5
        if cp.days_on_market is not None:
            if cp.days_on_market <= 21:
                demand += 8
            elif cp.days_on_market <= 90:
                demand += 12
            elif cp.days_on_market <= 180:
                demand += 6
            else:
                demand -= 4
        if rent and price and (rent * 12.0 / price) >= 0.10:
            demand += 12
        if spread_pct is not None:
            if spread_pct >= 20:
                demand += 16
            elif spread_pct >= 12:
                demand += 10
            elif spread_pct < 0:
                demand -= 10
        if cp.best_exit_strategy == self.strategy or self.strategy == "all":
            demand += 6

        buy_box = score * 0.55
        if spread_pct is not None:
            buy_box += self._clamp(spread_pct, -10.0, 30.0) * 0.75
        if cp.best_exit_strategy == self.strategy or self.strategy == "all":
            buy_box += 12
        if cp.property_type:
            buy_box += 4
        if cp.square_feet or cp.lot_size_sqft:
            buy_box += 4
        if rent:
            buy_box += 4

        cp.equity_spread = round(equity_spread, 2) if equity_spread is not None else None
        cp.spread_to_arv_pct = round(spread_pct, 1) if spread_pct is not None else None
        cp.buyer_demand_score = int(round(self._clamp(demand, 1, 99)))
        cp.buy_box_fit_score = int(round(self._clamp(buy_box, 1, 99)))

        if cp.deal_score and cp.deal_score >= 78 and (cp.days_on_market is None or cp.days_on_market <= 45):
            cp.deal_velocity = "Move fast"
        elif cp.days_on_market is not None and 45 <= cp.days_on_market <= 180:
            cp.deal_velocity = "Negotiation window"
        elif cp.deal_score and cp.deal_score >= 60:
            cp.deal_velocity = "Validate fast"
        else:
            cp.deal_velocity = "Watch list"

        reason_parts: List[str] = []
        if cp.spread_to_arv_pct is not None:
            reason_parts.append(f"{cp.spread_to_arv_pct:.1f}% spread to value signal")
        if cp.buy_box_fit_score is not None:
            reason_parts.append(f"{cp.buy_box_fit_score}/99 buy-box fit")
        if cp.buyer_demand_score is not None:
            reason_parts.append(f"{cp.buyer_demand_score}/99 demand proxy")
        if cp.best_exit_strategy:
            reason_parts.append(f"best exit: {cp.best_exit_strategy}")
        cp.rank_reason = "; ".join(reason_parts[:4]) or "Ranked by Ravlo deal score and data completeness."

        existing_why = cp.why_it_made_list or []
        if cp.rank_reason and cp.rank_reason not in existing_why:
            cp.why_it_made_list = [cp.rank_reason] + existing_why
            cp.why_it_made_list = cp.why_it_made_list[:4]

        return cp

    def search_candidates(
        self,
        *,
        address: str = "",
        city: str = "",
        state: str = "",
        zip_code: str = "",
        limit: int = 12,
    ) -> List[CanonicalProperty]:
        if not self.budget.use("rentcast_search", 1):
            return []

        # If an address is provided with city+state, try exact match first
        if address and (city or state or zip_code):
            try:
                matched = find_rentcast_sale_listing(
                    address=address,
                    city=city,
                    state=state,
                    zip_code=zip_code,
                    limit=min(max(limit, 5), 25),
                ) or {}
            except Exception:
                matched = {}

            if matched:
                normalized = normalize_rentcast_sale_listing(matched)
                if _property_matches_asset_type(normalized, self.asset_type):
                    return [self._from_rentcast_listing(normalized)]

        # Broad listing search by city/state or ZIP
        try:
            listings = get_rentcast_sale_listings(
                city=city,
                state=state,
                zip_code=zip_code,
                status="Active",
                limit=min(limit, 25),
            )
        except Exception:
            listings = []

        results: List[CanonicalProperty] = []
        for item in listings:
            normalized = normalize_rentcast_sale_listing(item)
            if _property_matches_asset_type(normalized, self.asset_type):
                results.append(self._from_rentcast_listing(normalized))

        return results

    def _from_rentcast_listing(self, item: Dict[str, Any]) -> CanonicalProperty:
        raw = item.get("raw") or {}
        photos = self._normalize_photo_candidates(
            item.get("photos"),
            item.get("primary_photo"),
            raw.get("imgSrc"),
            raw.get("photos"),
            raw.get("images"),
            raw.get("primaryPhoto"),
            raw,
        )

        primary_photo = _resolve_photo(item.get("primary_photo"), photos)

        return CanonicalProperty(
            provider_ids={"rentcast": item.get("property_id")},
            address=item.get("address"),
            address_line1=item.get("address"),
            city=item.get("city"),
            state=item.get("state"),
            zip_code=item.get("zip_code"),
            listing_price=self._as_float(item.get("price")),
            purchase_price=self._as_float(item.get("price")),
            beds=self._as_float(item.get("beds")),
            baths=self._as_float(item.get("baths")),
            square_feet=self._as_int(item.get("square_feet")),
            lot_size_sqft=self._as_int(item.get("lot_size_sqft")),
            year_built=self._as_int(item.get("year_built")),
            property_type=item.get("property_type"),
            primary_photo=primary_photo,
            photos=photos,
            status=item.get("status"),
            days_on_market=self._as_int(item.get("days_on_market")),
            latitude=self._as_float(item.get("latitude")),
            longitude=self._as_float(item.get("longitude")),
            strategy=self.strategy,
            recommended_strategy=self.strategy,
            value_sources={
                "listing_price": "rentcast",
                "photos": "rentcast" if primary_photo else "",
            },
            raw=item.get("raw") or item,
        )

    def enrich_top_candidates(self, results: List[CanonicalProperty], top_n: int = 4) -> List[CanonicalProperty]:
        enriched: List[CanonicalProperty] = []

        for idx, cp in enumerate(results):
            if idx >= top_n:
                enriched.append(cp)
                continue

            cp = self._enrich_with_attom(cp)
            cp = self._enrich_with_rentcast(cp)

            cp = self._enrich_with_mashvisor(cp)

            cp = self._enrich_with_realtor(cp)

            cp = self._enrich_with_rapidapi_real_estate(cp)

            if len(self._normalize_photo_candidates(cp.photos, cp.primary_photo)) < 4:
                cp = self._recover_gallery_depth(cp)

            if not cp.photos and not cp.primary_photo:
                cp = self._recover_photos(cp)

            enriched.append(cp)

        return enriched

    def _enrich_with_attom(self, cp: CanonicalProperty) -> CanonicalProperty:
        if not self.budget.use("attom_detail", 1):
            return cp

        try:
            profile = build_attom_dealfinder_profile(
                address=cp.address or cp.address_line1 or "",
                city=cp.city or "",
                state=cp.state or "",
                zip_code=cp.zip_code or "",
            )
        except AttomServiceError:
            return cp
        except Exception:
            return cp

        cp.provider_ids["attom"] = profile.get("attom_id") or cp.provider_ids.get("attom")
        cp.market_value = self._first_truthy(self._as_float(profile.get("market_value")), cp.market_value)
        cp.assessed_value = self._first_truthy(self._as_float(profile.get("assessed_value")), cp.assessed_value)
        cp.last_sale_price = self._first_truthy(self._as_float(profile.get("last_sale_price")), cp.last_sale_price)
        cp.last_sale_date = self._first_truthy(profile.get("last_sale_date"), cp.last_sale_date)
        cp.tax_amount = self._first_truthy(self._as_float(profile.get("tax_amount")), cp.tax_amount)
        cp.square_feet = self._first_truthy(self._as_int(profile.get("sqft")), cp.square_feet)
        cp.lot_size_sqft = self._first_truthy(self._as_int(profile.get("lot_sqft")), cp.lot_size_sqft)
        cp.year_built = self._first_truthy(self._as_int(profile.get("year_built")), cp.year_built)
        cp.beds = self._first_truthy(self._as_float(profile.get("beds")), cp.beds)
        cp.baths = self._first_truthy(self._as_float(profile.get("baths")), cp.baths)
        cp.property_type = self._first_truthy(profile.get("property_type"), cp.property_type)
        cp.latitude = self._first_truthy(self._as_float(profile.get("latitude")), cp.latitude)
        cp.longitude = self._first_truthy(self._as_float(profile.get("longitude")), cp.longitude)

        cp.value_sources.update({
            "assessed_value": "attom",
            "last_sale_price": "attom",
            "square_feet": "attom",
        })

        if profile.get("distressed"):
            cp.primary_strengths.append("Distress signal detected.")
        if profile.get("ravlo_score") and cp.deal_score is None:
            cp.deal_score = self._as_int(profile.get("ravlo_score"))
        if profile.get("recommended_strategy") and not cp.recommended_strategy:
            cp.recommended_strategy = profile.get("recommended_strategy")

        # ATTOM may include image URLs in some plans/responses.
        attom_raw = profile.get("raw") or {}
        attom_photos = self._normalize_photo_candidates(
            attom_raw.get("photos"),
            attom_raw.get("images"),
            attom_raw.get("image"),
            attom_raw.get("media"),
            attom_raw.get("imgSrc"),
            attom_raw.get("primaryPhoto"),
        )
        if attom_photos:
            _log.info("[attom] extracted %d photos from raw response", len(attom_photos))
            cp.photos = self._normalize_photo_candidates(cp.photos, attom_photos)
            cp.primary_photo = _resolve_photo(cp.primary_photo, cp.photos)
            cp.value_sources["photos"] = "attom"

        return cp

    def _enrich_with_rapidapi_real_estate(self, cp: CanonicalProperty) -> CanonicalProperty:
        if not self.budget.use("rapidapi_real_estate_detail", 1):
            return cp

        if fetch_rapidapi_real_estate_photos is None:
            return cp

        # Only use this as a fallback. Do not spend calls when we already have photos.
        if cp.photos or cp.primary_photo:
            return cp

        try:
            payload = {
                "address": cp.address or cp.address_line1,
                "address_line1": cp.address_line1 or cp.address,
                "city": cp.city,
                "state": cp.state,
                "zip_code": cp.zip_code,
                "zpid": cp.provider_ids.get("zillow"),
                "zillow_id": cp.provider_ids.get("zillow"),
            }

            photos = fetch_rapidapi_real_estate_photos(payload)

        except Exception as exc:
            _log.warning("[rapidapi-real-estate] photo fallback failed: %s", exc)
            return cp

        if photos:
            cp.photos = self._normalize_photo_candidates(cp.photos, photos)
            cp.primary_photo = _resolve_photo(cp.primary_photo, cp.photos)
            cp.value_sources["photos"] = "rapidapi_real_estate"

            cp.raw.setdefault("rapidapi_real_estate", {})
            cp.raw["rapidapi_real_estate"]["photo_count"] = len(photos)

            _log.info(
                "[rapidapi-real-estate] extracted %d photos for %s",
                len(photos),
                cp.address or cp.address_line1 or "unknown",
            )

        return cp

    def _enrich_with_rentcast(self, cp: CanonicalProperty) -> CanonicalProperty:
        if not self.budget.use("rentcast_detail", 1):
            return cp

        property_type = cp.property_type or "single_family"

        try:
            rent_data = get_rentcast_rent_estimate(
                address=cp.address or cp.address_line1 or "",
                city=cp.city or "",
                state=cp.state or "",
                zip_code=cp.zip_code or "",
                property_type=property_type,
            )
        except RentCastServiceError:
            rent_data = {}
        except Exception:
            rent_data = {}

        try:
            value_data = get_rentcast_value_estimate(
                address=cp.address or cp.address_line1 or "",
                city=cp.city or "",
                state=cp.state or "",
                zip_code=cp.zip_code or "",
                property_type=property_type,
            )
        except RentCastServiceError:
            value_data = {}
        except Exception:
            value_data = {}

        try:
            sale_listing = find_rentcast_sale_listing(
                address=cp.address or cp.address_line1 or "",
                city=cp.city or "",
                state=cp.state or "",
                zip_code=cp.zip_code or "",
                limit=25,
            )
            sale_listing = normalize_rentcast_sale_listing(sale_listing) if sale_listing else {}
        except RentCastServiceError:
            sale_listing = {}
        except Exception:
            sale_listing = {}

        rent_estimate = self._first_truthy(
            self._as_float(rent_data.get("rent")),
            self._as_float(rent_data.get("price")),
            self._as_float(rent_data.get("estimate")),
            self._as_float(rent_data.get("monthlyRent")),
        )

        value_estimate = self._first_truthy(
            self._as_float(value_data.get("price")),
            self._as_float(value_data.get("value")),
            self._as_float(value_data.get("estimate")),
            self._as_float(value_data.get("avm")),
        )

        cp.provider_ids["rentcast"] = sale_listing.get("property_id") or cp.provider_ids.get("rentcast")
        cp.market_value = self._first_truthy(value_estimate, cp.market_value)
        cp.monthly_rent_estimate = self._first_truthy(rent_estimate, cp.monthly_rent_estimate)
        cp.arv = self._first_truthy(cp.market_value, cp.arv)

        cp.listing_price = self._first_truthy(cp.listing_price, self._as_float(sale_listing.get("price")))
        cp.purchase_price = self._first_truthy(cp.purchase_price, cp.listing_price)
        cp.beds = self._first_truthy(cp.beds, self._as_float(sale_listing.get("beds")))
        cp.baths = self._first_truthy(cp.baths, self._as_float(sale_listing.get("baths")))
        cp.square_feet = self._first_truthy(cp.square_feet, self._as_int(sale_listing.get("square_feet")))
        cp.lot_size_sqft = self._first_truthy(cp.lot_size_sqft, self._as_int(sale_listing.get("lot_size_sqft")))
        cp.year_built = self._first_truthy(cp.year_built, self._as_int(sale_listing.get("year_built")))
        cp.property_type = self._first_truthy(cp.property_type, sale_listing.get("property_type"))
        cp.status = self._first_truthy(cp.status, sale_listing.get("status"))
        cp.days_on_market = self._first_truthy(cp.days_on_market, self._as_int(sale_listing.get("days_on_market")))
        cp.latitude = self._first_truthy(cp.latitude, self._as_float(sale_listing.get("latitude")))
        cp.longitude = self._first_truthy(cp.longitude, self._as_float(sale_listing.get("longitude")))

        # Extract photos from ALL RentCast responses (sale listing, rent,
        # and value endpoints may each carry image data).
        sale_raw = sale_listing.get("raw") or {}
        rentcast_photos = self._normalize_photo_candidates(
            cp.photos,
            sale_listing.get("primary_photo"),
            sale_listing.get("photos"),
            sale_raw.get("imgSrc"),
            sale_raw.get("photos"),
            sale_raw.get("images"),
            sale_raw.get("primaryPhoto"),
            rent_data.get("imgSrc") if isinstance(rent_data, dict) else None,
            rent_data.get("photos") if isinstance(rent_data, dict) else None,
            value_data.get("imgSrc") if isinstance(value_data, dict) else None,
            value_data.get("photos") if isinstance(value_data, dict) else None,
        )
        if rentcast_photos:
            _log.info(
                "[rentcast] extracted %d photos for %s",
                len(rentcast_photos),
                cp.address or cp.address_line1 or "unknown",
            )
            cp.photos = rentcast_photos
            cp.primary_photo = _resolve_photo(cp.primary_photo, rentcast_photos)
            cp.value_sources["photos"] = cp.value_sources.get("photos") or "rentcast"

        cp.value_sources.update({
            "market_value": "rentcast",
            "monthly_rent_estimate": "rentcast",
        })

        return cp

    @staticmethod
    def _resolve_mashvisor_property_id(result: Dict[str, Any], normalized: Dict[str, Any]) -> Any:
        """Extract a Mashvisor property id from every possible location."""
        _id_keys = ("id", "property_id", "pid", "mashvisor_id", "mls_id")

        # 1. normalized (if normalize_mashvisor_validation ever populates it)
        for k in _id_keys:
            pid = normalized.get(k)
            if pid:
                return pid

        # 2. property response  {"status":"success","content":{"id":...}}
        for section_key in ("property", "lookup"):
            section = result.get(section_key)
            if not isinstance(section, dict):
                continue
            for container in (section.get("content"), section):
                if not isinstance(container, dict):
                    continue
                for k in _id_keys:
                    pid = container.get(k)
                    if pid:
                        return pid

        return None

    def _enrich_with_mashvisor(self, cp: CanonicalProperty) -> CanonicalProperty:
        if not self._mashvisor:
            _log.warning("[mashvisor] skipping enrichment -- no client")
            return cp
        if not self.budget.use("mashvisor_detail", 1):
            _log.info("[mashvisor] skipping enrichment -- budget exhausted")
            return cp

        addr = cp.address or cp.address_line1 or ""
        _log.info("[mashvisor] enriching %s, %s %s %s", addr, cp.city, cp.state, cp.zip_code)

        try:
            result = self._mashvisor.validate_property_with_mashvisor(
                address=addr,
                city=cp.city or "",
                state=cp.state or "",
                zip_code=cp.zip_code or "",
                beds=self._as_int(cp.beds) if cp.beds is not None else None,
                baths=cp.baths,
                lat=cp.latitude,
                lng=cp.longitude,
                include_comps=False,
            )
            _log.info("[mashvisor] validate ok  keys=%s  errors=%s",
                      list(result.keys()) if result else None,
                      result.get("errors") if result else None)
            normalized = normalize_mashvisor_validation(result)
        except MashvisorError as exc:
            _log.warning("[mashvisor] validate MashvisorError: %s", exc)
            return cp
        except Exception as exc:
            _log.warning("[mashvisor] validate exception: %s", exc)
            return cp

        cp.airbnb_rent_estimate = self._first_truthy(
            self._as_float(normalized.get("airbnb_revenue")),
            cp.airbnb_rent_estimate,
        )
        cp.occupancy_rate = self._first_truthy(
            self._as_float(normalized.get("occupancy_rate")),
            cp.occupancy_rate,
        )
        cp.airbnb_cash_on_cash = self._first_truthy(
            self._as_float(normalized.get("cash_on_cash_return")),
            cp.airbnb_cash_on_cash,
        )
        cp.airbnb_nightly_rate = self._first_truthy(
            self._as_float(normalized.get("adr")),
            cp.airbnb_nightly_rate,
        )
        cp.airbnb_cash_flow = self._first_truthy(
            self._as_float(normalized.get("cash_flow")),
            cp.airbnb_cash_flow,
        )
        cp.comp_confidence = self._first_truthy(
            str(normalized.get("confidence")) if normalized.get("confidence") is not None else None,
            cp.comp_confidence,
        )

        mashvisor_photos = self._extract_mashvisor_photos(normalized, result)
        _log.info("[mashvisor] inline photos extracted: %d", len(mashvisor_photos))

        property_id = self._resolve_mashvisor_property_id(result, normalized)
        _log.info("[mashvisor] resolved property_id=%s", property_id)

        if property_id:
            cp.provider_ids["mashvisor"] = property_id
            try:
                image_result = self._mashvisor.get_property_images(property_id)
                img_status = image_result.get("status")
                img_count = len(image_result.get("photos") or [])
                _log.info("[mashvisor] get_property_images status=%s  count=%d", img_status, img_count)
                if img_status == "success" and img_count:
                    mashvisor_photos = self._normalize_photo_candidates(
                        mashvisor_photos,
                        image_result.get("photos"),
                        image_result.get("primary_photo"),
                    )
            except Exception as exc:
                _log.warning("[mashvisor] get_property_images failed: %s", exc)
        else:
            _log.warning("[mashvisor] no property_id -- cannot fetch images")

        _log.info("[mashvisor] final photo count: mashvisor=%d  existing=%d", len(mashvisor_photos), len(cp.photos))
        if mashvisor_photos:
            cp.photos = self._normalize_photo_candidates(cp.photos, mashvisor_photos)
            if cp.photos:
                cp.primary_photo = _resolve_photo(cp.primary_photo, cp.photos)

        cp.value_sources.update({
            "airbnb_revenue": "mashvisor",
            "occupancy_rate": "mashvisor",
            "photos": "mashvisor" if cp.photos else cp.value_sources.get("photos"),
        })

        return cp

    def _enrich_with_realtor(self, cp: CanonicalProperty) -> CanonicalProperty:
        """Enrich with Realtor.com data (primarily for photos + list price).

        Uses the RapidAPI `/v2/property` endpoint via
        :func:`LoanMVP.services.realtor_provider.fetch_realtor_data`. Falls
        back to `/propertyPhotos` by property id when the detail call does
        not return photos.
        """
        addr = cp.address or cp.address_line1 or ""
        if not addr:
            return cp

        if not self.budget.use("realtor_detail", 1):
            _log.info("[realtor] skipping enrichment -- budget exhausted")
            return cp

        _log.info("[realtor] enriching %s, %s %s %s", addr, cp.city, cp.state, cp.zip_code)

        try:
            data = fetch_realtor_data(
                address=addr,
                city=cp.city or "",
                state=cp.state or "",
                zip_code=cp.zip_code or "",
            )
        except Exception as exc:
            _log.warning("[realtor] fetch_realtor_data failed: %s", exc)
            return cp

        if not isinstance(data, dict):
            return cp

        prop = data.get("property") or {}
        if not isinstance(prop, dict):
            prop = {}

        property_id = prop.get("property_id")
        if property_id:
            cp.provider_ids["realtor"] = property_id

        realtor_photos = self._normalize_photo_candidates(
            prop.get("primary_photo"),
            prop.get("photos"),
        )

        if not realtor_photos and property_id:
            try:
                gallery = fetch_realtor_photos(property_id)
            except Exception as exc:
                _log.warning("[realtor] fetch_realtor_photos failed: %s", exc)
                gallery = []
            if gallery:
                realtor_photos = self._normalize_photo_candidates(gallery)

        if not realtor_photos:
            realtor_photos = self._search_realtor_photos_fallback(cp)

        if realtor_photos:
            _log.info(
                "[realtor] extracted %d photos for %s",
                len(realtor_photos),
                addr,
            )
            # Merge realtor photos in front so they take priority when the
            # gallery is otherwise empty, while still retaining any photos
            # that ATTOM/RentCast/Mashvisor already surfaced.
            cp.photos = self._normalize_photo_candidates(realtor_photos, cp.photos)
            cp.primary_photo = _resolve_photo(cp.primary_photo, cp.photos)
            cp.value_sources["photos"] = cp.value_sources.get("photos") or "realtor"

        cp.listing_price = self._first_truthy(
            cp.listing_price,
            self._as_float(prop.get("price")),
        )
        cp.purchase_price = self._first_truthy(cp.purchase_price, cp.listing_price)
        cp.status = self._first_truthy(cp.status, prop.get("status"))
        cp.days_on_market = self._first_truthy(
            cp.days_on_market,
            self._as_int(prop.get("days_on_market")),
        )
        if isinstance(prop.get("description"), str) and prop.get("description"):
            cp.description = cp.description or prop.get("description")

        return cp

    def _search_realtor_photos_fallback(self, cp: CanonicalProperty) -> List[str]:
        """Search Realtor.com for-sale listings to find photos for *cp*.

        Only accepts results whose address closely matches the candidate
        property so we never attach a random listing's photos to the wrong
        property.
        """
        addr = cp.address or cp.address_line1 or ""
        location_parts = [p for p in (addr, cp.city, cp.state, cp.zip_code) if p]
        location = ", ".join(location_parts)
        if len(location) < 8:
            return []

        try:
            results = search_realtor_for_sale(location=location, limit=5, days_on=365)
        except Exception as exc:
            _log.warning("[realtor] search fallback failed: %s", exc)
            return []

        if not results:
            return []

        norm_target = _normalize_address_text(addr)
        if not norm_target:
            return []

        for listing in results:
            listing_addr = listing.get("address") or listing.get("address_line1") or ""
            norm_listing = _normalize_address_text(listing_addr)
            if not norm_listing:
                continue

            # Compare full normalized addresses with equality to avoid
            # false positives (e.g. "5 elm st" != "15 elm st",
            # "123 2nd st" != "123 22nd st").
            if norm_target == norm_listing:
                photos = self._normalize_photo_candidates(
                    listing.get("primary_photo"),
                    listing.get("photos"),
                )
                if photos:
                    _log.info(
                        "[realtor] search fallback matched %s -> %s (%d photos)",
                        addr, listing_addr, len(photos),
                    )
                    return photos

        _log.info("[realtor] search fallback found no address match for %s", addr)
        return []

    def _recover_gallery_depth(self, cp: CanonicalProperty, target_count: int = 4) -> CanonicalProperty:
        """Try to expand thin one-photo galleries without losing the primary photo."""
        existing = self._normalize_photo_candidates(cp.photos, cp.primary_photo)
        if len(existing) >= target_count:
            cp.photos = existing
            cp.primary_photo = _resolve_photo(cp.primary_photo, existing)
            return cp

        addr = cp.address or cp.address_line1 or ""
        log_label = addr or "unknown"

        def merge(source_label: str, *sources: Any) -> bool:
            nonlocal existing
            merged = self._normalize_photo_candidates(existing, *sources)
            if len(merged) > len(existing):
                existing = merged
                cp.photos = merged
                cp.primary_photo = _resolve_photo(cp.primary_photo, merged)
                cp.value_sources["photos"] = source_label
                _log.info(
                    "[photo_recovery] expanded gallery for %s to %d photos via %s",
                    log_label,
                    len(merged),
                    source_label,
                )
                return True
            return False

        raw = cp.raw or {}
        merge(
            "raw_gallery_expansion",
            raw.get("imgSrc"),
            raw.get("primaryPhoto"),
            raw.get("primaryPhotoUrl"),
            raw.get("photos"),
            raw.get("images"),
            raw.get("image"),
            raw.get("media"),
            raw.get("gallery"),
            raw.get("responsivePhotos"),
            raw.get("mixedSources"),
            raw.get("imageSources"),
            raw.get("data"),
            raw,
        )
        if len(existing) >= target_count:
            return cp

        if self._mashvisor:
            mashvisor_id = cp.provider_ids.get("mashvisor")
            if mashvisor_id:
                try:
                    img_result = self._mashvisor.get_property_images(mashvisor_id)
                    if isinstance(img_result, dict) and img_result.get("photos"):
                        merge("mashvisor_gallery_expansion", img_result.get("photos"), img_result.get("primary_photo"))
                except Exception as exc:
                    _log.warning("[photo_recovery] mashvisor gallery expansion failed: %s", exc)
            if len(existing) >= target_count:
                return cp

        realtor_id = cp.provider_ids.get("realtor")
        if realtor_id:
            try:
                merge("realtor_gallery_expansion", fetch_realtor_photos(realtor_id))
            except Exception as exc:
                _log.warning("[photo_recovery] realtor gallery expansion failed: %s", exc)
        if len(existing) >= target_count:
            return cp

        realtor_search_photos = self._search_realtor_photos_fallback(cp)
        if realtor_search_photos:
            merge("realtor_search_gallery_expansion", realtor_search_photos)
        if len(existing) >= target_count:
            return cp

        if addr:
            try:
                sale = find_rentcast_sale_listing(
                    address=addr,
                    city=cp.city or "",
                    state=cp.state or "",
                    zip_code=cp.zip_code or "",
                    limit=10,
                )
                if sale:
                    normalized_sale = normalize_rentcast_sale_listing(sale)
                    merge(
                        "rentcast_gallery_expansion",
                        normalized_sale.get("primary_photo"),
                        normalized_sale.get("photos"),
                        sale.get("imgSrc"),
                        sale.get("photos"),
                        sale.get("images"),
                        sale,
                    )
            except Exception as exc:
                _log.warning("[photo_recovery] rentcast gallery expansion failed: %s", exc)

        if existing:
            cp.photos = existing
            cp.primary_photo = _resolve_photo(cp.primary_photo, existing)

        return cp

    def _recover_photos(self, cp: CanonicalProperty) -> CanonicalProperty:
        """Last-resort photo recovery after all enrichment providers failed.

        Tries every available source aggressively:
        1. Re-scan raw data blobs for missed image URLs
        2. Mashvisor get_property_images (by id or address lookup)
        3. Realtor.com photos endpoint
        4. RentCast sale listing imgSrc re-check
        """
        addr = cp.address or cp.address_line1 or ""
        log_label = addr or "unknown"
        _log.info("[photo_recovery] attempting recovery for %s", log_label)

        raw = cp.raw or {}
        recovered = self._normalize_photo_candidates(
            raw.get("imgSrc"),
            raw.get("primaryPhoto"),
            raw.get("photos"),
            raw.get("images"),
            raw.get("image"),
            raw.get("media"),
            raw.get("photo"),
            raw.get("coverPhoto"),
            raw.get("thumbnail"),
        )
        if recovered:
            _log.info("[photo_recovery] found %d photos in raw data for %s", len(recovered), log_label)
            cp.photos = recovered
            cp.primary_photo = _resolve_photo(None, recovered)
            cp.value_sources["photos"] = "raw_recovery"
            return cp

        # Mashvisor: retry with property_id or address-based lookup
        if self._mashvisor:
            mashvisor_id = cp.provider_ids.get("mashvisor")
            if mashvisor_id:
                try:
                    img_result = self._mashvisor.get_property_images(mashvisor_id)
                    if img_result.get("status") == "success" and img_result.get("photos"):
                        recovered = self._normalize_photo_candidates(
                            img_result.get("photos"),
                            img_result.get("primary_photo"),
                        )
                        if recovered:
                            _log.info("[photo_recovery] mashvisor images returned %d for %s", len(recovered), log_label)
                            cp.photos = recovered
                            cp.primary_photo = _resolve_photo(None, recovered)
                            cp.value_sources["photos"] = "mashvisor_recovery"
                            return cp
                except Exception as exc:
                    _log.warning("[photo_recovery] mashvisor get_property_images failed: %s", exc)


            if not mashvisor_id and addr:  # skip if addr is empty
                pid = None
                try:
                    prop_data = self._mashvisor.get_property_by_address(
                        address=addr,
                        city=cp.city or "",
                        state=cp.state or "",
                        zip_code=cp.zip_code or "",
                    )
                    content = (prop_data.get("content") or {}) if isinstance(prop_data, dict) else {}
                    if isinstance(content, dict):
                        pid = content.get("id") or content.get("property_id")
                except Exception as exc:
                    _log.warning("[photo_recovery] mashvisor address lookup failed: %s", exc)

                # 409 "Property already exist" returns no pid — try airbnb lookup
                if not pid:
                    try:
                        lookup_data = self._mashvisor.get_airbnb_lookup(
                            address=addr,
                            city=cp.city or "",
                            state=cp.state or "",
                            zip_code=cp.zip_code or "",
                        )
                        lookup_content = (lookup_data.get("content") or {}) if isinstance(lookup_data, dict) else {}
                        if isinstance(lookup_content, dict):
                            pid = (
                                lookup_content.get("id")
                                or lookup_content.get("property_id")
                                or lookup_content.get("pid")
                            )
                            if not pid and isinstance(lookup_content.get("property_info"), dict):
                                pid = lookup_content["property_info"].get("id")
                    except Exception as exc:
                        _log.warning("[photo_recovery] mashvisor airbnb lookup fallback failed: %s", exc)

                if pid:
                    try:
                        cp.provider_ids["mashvisor"] = pid
                        img_result = self._mashvisor.get_property_images(pid)
                        if img_result.get("status") == "success" and img_result.get("photos"):
                            recovered = self._normalize_photo_candidates(
                                img_result.get("photos"),
                                img_result.get("primary_photo"),
                            )
                            if recovered:
                                _log.info("[photo_recovery] mashvisor address lookup returned %d photos for %s", len(recovered), log_label)
                                cp.photos = recovered
                                cp.primary_photo = _resolve_photo(None, recovered)
                                cp.value_sources["photos"] = "mashvisor_recovery"
                                return cp
                    except Exception as exc:
                        _log.warning("[photo_recovery] mashvisor get_property_images failed for pid=%s: %s", pid, exc)


        # Realtor.com photos endpoint (by property ID)
        realtor_id = cp.provider_ids.get("realtor")
        if realtor_id:
            try:
                gallery = fetch_realtor_photos(realtor_id)
            except Exception:
                gallery = []
            if gallery:
                recovered = self._normalize_photo_candidates(gallery)
                if recovered:
                    _log.info("[photo_recovery] realtor photos endpoint returned %d for %s", len(recovered), log_label)
                    cp.photos = recovered
                    cp.primary_photo = _resolve_photo(None, recovered)
                    cp.value_sources["photos"] = "realtor_recovery"
                    return cp

        # Realtor.com search fallback (address-based, no ID required).
        # This may have been skipped during enrichment if the budget was
        # exhausted, so we always try it here as a recovery step.
        realtor_search_photos = self._search_realtor_photos_fallback(cp)
        if realtor_search_photos:
            cp.photos = realtor_search_photos
            cp.primary_photo = _resolve_photo(None, realtor_search_photos)
            cp.value_sources["photos"] = "realtor_search_recovery"
            _log.info("[photo_recovery] realtor search fallback returned %d for %s", len(realtor_search_photos), log_label)
            return cp

        # RentCast: re-check sale listing for imgSrc (skip if no usable address)
        rentcast_id = cp.provider_ids.get("rentcast")
        if addr:
            try:
                sale = find_rentcast_sale_listing(
                    address=addr,
                    city=cp.city or "",
                    state=cp.state or "",
                    zip_code=cp.zip_code or "",
                    limit=5,
                )
                if sale:
                    normalized_sale = normalize_rentcast_sale_listing(sale)
                    recovered = self._normalize_photo_candidates(
                        normalized_sale.get("primary_photo"),
                        normalized_sale.get("photos"),
                        (sale or {}).get("imgSrc"),
                    )
                    if recovered:
                        _log.info("[photo_recovery] rentcast sale re-check returned %d for %s", len(recovered), log_label)
                        cp.photos = recovered
                        cp.primary_photo = _resolve_photo(None, recovered)
                        cp.value_sources["photos"] = "rentcast_recovery"
                        return cp
            except Exception as exc:
                _log.warning("[photo_recovery] rentcast re-check failed: %s", exc)

        # Absolute last resort: generate a Google Street View URL from
        # coordinates so the property card has a real photo instead of a
        # placeholder.  The proxy layer will append the API key before
        # requesting the image from Google.
        lat = cp.latitude
        lon = cp.longitude
        if lat is not None and lon is not None:
            try:
                lat_f, lon_f = float(lat), float(lon)
                if lat_f != 0.0 or lon_f != 0.0:
                    sv_url = (
                        "https://maps.googleapis.com/maps/api/streetview"
                        f"?size=600x400&location={lat_f},{lon_f}"
                    )
                    cp.primary_photo = sv_url
                    cp.value_sources["photos"] = "streetview"
                    _log.info("[photo_recovery] set streetview fallback for %s (%.4f, %.4f)", log_label, lat_f, lon_f)
                    return cp
            except (TypeError, ValueError):
                pass

        _log.info("[photo_recovery] no photos recovered for %s — no coordinates for streetview", log_label)
        return cp

    def rank_candidates(self, results: List[CanonicalProperty]) -> List[CanonicalProperty]:
        ranked: List[CanonicalProperty] = []

        for idx, cp in enumerate(results):
            cp = self._recommend_exit_strategy(cp)

            if idx < 4 and self.budget.use("deal_architect", 1):
                cp = self._apply_ravlo_opinion(cp)
            else:
                cp = self._annotate_default(cp)

            cp = self._apply_marketplace_signals(cp)
            ranked.append(cp)

        ranked.sort(
            key=lambda x: (
                x.deal_score is not None,
                x.buy_box_fit_score or 0,
                x.buyer_demand_score or 0,
                x.deal_score or 0,
            ),
            reverse=True,
        )
        return ranked

    def _apply_ravlo_opinion(self, cp: CanonicalProperty) -> CanonicalProperty:
        score, why, risks = self._score_candidate(cp)
        cp.deal_score = score

        if score >= 72:
            cp.opportunity_tier = "strong"
            cp.deal_finder_signal = "advance_to_lender_package"
        elif score >= 48:
            cp.opportunity_tier = "moderate"
            cp.deal_finder_signal = "validate_zoning_and_pricing"
        else:
            cp.opportunity_tier = "risk"
            cp.deal_finder_signal = "retrade_or_pass"

        best_exit = cp.best_exit_strategy or self.strategy

        if best_exit == "rental":
            cp.strategy_tag = cp.strategy_tag or "Hold Candidate"
            cp.estimated_best_use = cp.estimated_best_use or "Long-term rental hold"
        elif best_exit == "airbnb":
            cp.strategy_tag = cp.strategy_tag or "STR Candidate"
            cp.estimated_best_use = cp.estimated_best_use or "Short-term rental operation"
        elif best_exit == "land":
            cp.strategy_tag = cp.strategy_tag or "Land Optionality"
            cp.estimated_best_use = cp.estimated_best_use or "Land bank or build-oriented strategy"
        else:
            cp.strategy_tag = cp.strategy_tag or "Flip Candidate"
            cp.estimated_best_use = cp.estimated_best_use or "Fix and flip reposition"

        cp.recommended_strategy = cp.recommended_strategy or best_exit
        cp.next_step = cp.next_step or (
            "Move this into Project Studio and underwrite the plan."
            if cp.opportunity_tier == "strong"
            else "Validate comps, scope, and pricing before planning."
        )

        cp.why_it_made_list = why if why else cp.why_it_made_list or ["Worth deeper review in Project Studio."]
        cp.risk_notes = risks if risks else cp.risk_notes or ["Confirm data before committing to execution."]
        cp.primary_strengths = cp.primary_strengths or cp.why_it_made_list[:2]
        cp.primary_risks = cp.primary_risks or cp.risk_notes[:2]

        return cp

    def _annotate_default(self, cp: CanonicalProperty) -> CanonicalProperty:
        result_payload = cp.to_result_dict()
        if result_payload.get("deal_score") is None:
            pre_rank = (cp.raw.get("deal_finder") or {}).get("pre_rank_score")
            result_payload["deal_score"] = int(round(self._clamp(pre_rank or 42, 35, 49)))

        result = _annotate_deal_finder_opportunity(result_payload, self.strategy)
        cp.deal_score = result.get("deal_score")
        cp.opportunity_tier = result.get("opportunity_tier")
        cp.deal_finder_signal = result.get("deal_finder_signal")
        cp.strategy_tag = result.get("strategy_tag")
        cp.recommended_strategy = result.get("recommended_strategy")
        cp.estimated_best_use = result.get("estimated_best_use")
        cp.next_step = result.get("next_step")
        cp.primary_strengths = result.get("primary_strengths") or cp.primary_strengths
        cp.primary_risks = result.get("primary_risks") or cp.primary_risks
        cp.risk_notes = result.get("risk_notes") or cp.risk_notes
        cp.why_it_made_list = result.get("why_it_made_list") or cp.why_it_made_list
        return cp

    def run_search(
        self,
        *,
        address: str = "",
        city: str = "",
        state: str = "",
        zip_code: str = "",
        limit: int = 12,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        candidates = self.search_candidates(
            address=address,
            city=city,
            state=state,
            zip_code=zip_code,
            limit=limit,
        )
        candidates = self._pre_rank_candidates(candidates)
        enriched = self.enrich_top_candidates(candidates, top_n=4)
        ranked = self.rank_candidates(enriched)

        return_limit = min(max(int(limit or 4), 4), 8)
        results = [cp.to_result_dict() for cp in ranked[:return_limit]]

        # Log photo availability summary for debugging.
        with_photos = sum(1 for r in results if r.get("listing_photos") or r.get("primary_photo") or r.get("image_url"))
        _log.info(
            "[run_search] returning %d results, %d with photos (address=%s zip=%s)",
            len(results), with_photos, address, zip_code,
        )
        for r in results:
            _log.debug(
                "  -> %s  photos=%d  primary=%s",
                r.get("address", "?"),
                len(r.get("listing_photos") or []),
                bool(r.get("primary_photo") or r.get("image_url")),
            )

        meta = {
            "count": len(results),
            "total_matches": len(ranked),
            "strategy": self.strategy,
            "asset_type": self.asset_type,
            "asset_type_label": _asset_type_label(self.asset_type),
            "zip": zip_code,
            "address": address,
            "engine_ready": any(r.get("deal_score") is not None for r in results),
            "budget_remaining": {
                "rentcast_search": self.budget.rentcast_search,
                "attom_detail": self.budget.attom_detail,
                "rentcast_detail": self.budget.rentcast_detail,
                "mashvisor_detail": self.budget.mashvisor_detail,
                "realtor_detail": self.budget.realtor_detail,
                "deal_architect": self.budget.deal_architect,
            },
        }
        return results, meta
