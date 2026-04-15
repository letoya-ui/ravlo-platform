from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from LoanMVP.services.realtor_provider import search_realtor_for_sale
from LoanMVP.services.realtor_provider import fetch_realtor_photos
from LoanMVP.services.attom_service import build_attom_dealfinder_profile, AttomServiceError
from LoanMVP.services.rentcast_service import (
    get_rentcast_rent_estimate,
    get_rentcast_value_estimate,
    find_rentcast_sale_listing,
    normalize_rentcast_sale_listing,
    RentCastServiceError,
)
from LoanMVP.services.mashvisor_client import MashvisorClient, MashvisorError
from LoanMVP.services.mashvisor_service import normalize_mashvisor_validation

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


@dataclass
class ProviderBudget:
    realtor_search: int = 1
    attom_detail: int = 4
    rentcast_detail: int = 4
    mashvisor_detail: int = 2
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

    primary_strengths: List[str] = field(default_factory=list)
    primary_risks: List[str] = field(default_factory=list)
    risk_notes: List[str] = field(default_factory=list)
    why_it_made_list: List[str] = field(default_factory=list)

    traditional_cap_rate: Optional[float] = None
    traditional_cash_on_cash: Optional[float] = None
    airbnb_rent_estimate: Optional[float] = None
    airbnb_cap_rate: Optional[float] = None
    airbnb_cash_on_cash: Optional[float] = None
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
            "primary_strengths": self.primary_strengths,
            "primary_risks": self.primary_risks,
            "risk_notes": self.risk_notes,
            "why_it_made_list": self.why_it_made_list,
            "traditional_cap_rate": self.traditional_cap_rate,
            "traditional_cash_on_cash": self.traditional_cash_on_cash,
            "airbnb_rent_estimate": self.airbnb_rent_estimate,
            "airbnb_cap_rate": self.airbnb_cap_rate,
            "airbnb_cash_on_cash": self.airbnb_cash_on_cash,
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
            return MashvisorClient()
        except Exception:
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

    def _extract_mashvisor_photos(
        self,
        normalized: Dict[str, Any],
        raw_result: Dict[str, Any] | None = None,
    ) -> List[str]:
        raw_result = raw_result or {}
        content = raw_result.get("content") if isinstance(raw_result, dict) else {}

        if not isinstance(content, dict):
            content = {}

        photos = self._normalize_photo_candidates(
            normalized.get("photos"),
            normalized.get("images"),
            normalized.get("image"),
            normalized.get("extra_images"),
            raw_result.get("photos"),
            raw_result.get("images"),
            raw_result.get("image"),
            raw_result.get("extra_images"),
            content.get("photos"),
            content.get("images"),
            content.get("image"),
            content.get("extra_images"),
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

        if cp.airbnb_rent_estimate and (cp.occupancy_rate or 0) >= 0.45:
            return "str_candidate"

        if cp.monthly_rent_estimate and (cp.market_value or cp.listing_price):
            return "rental_candidate"

        if fixer_signal or (cp.assessed_value and cp.market_value and cp.assessed_value < cp.market_value):
            return "fixer_upper"

        return "general_opportunity"

    def _build_exit_strategy_cards(self, cp: CanonicalProperty) -> List[Dict[str, Any]]:
        purchase_price = self._as_float(cp.purchase_price) or self._as_float(cp.listing_price) or 0.0
        rehab_cost = 0.0
        arv = self._as_float(cp.arv) or self._as_float(cp.market_value) or 0.0
        monthly_rent = self._as_float(cp.monthly_rent_estimate) or 0.0
        airbnb_monthly = self._as_float(cp.airbnb_rent_estimate) or 0.0
        occupancy = self._as_float(cp.occupancy_rate) or 0.0

        flip_total = purchase_price + rehab_cost
        flip_profit = (arv - (flip_total + (arv * 0.08))) if arv > 0 else 0.0
        flip_roi = (flip_profit / flip_total * 100.0) if flip_total > 0 else 0.0

        rental_expenses = monthly_rent * 0.35 if monthly_rent > 0 else 0.0
        rental_cashflow = monthly_rent - rental_expenses
        annual_noi = rental_cashflow * 12.0
        rental_cap = (annual_noi / purchase_price * 100.0) if purchase_price > 0 else 0.0
        rental_dscr = ((monthly_rent - rental_expenses) / max((purchase_price * 0.0075), 1.0)) if purchase_price > 0 else 0.0

        airbnb_net = airbnb_monthly * 0.62 if airbnb_monthly > 0 else 0.0
        airbnb_roi = ((airbnb_net * 12.0) / purchase_price * 100.0) if purchase_price > 0 else 0.0

        land_score = 70.0 if self._classify_property(cp) == "land" else 20.0
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

        scores = {card["key"]: self._as_float(card.get("score")) or 0.0 for card in cards}

        if property_classification == "land":
            scores["land"] += 20
            scores["flip"] -= 20
            scores["rental"] -= 20
            scores["airbnb"] -= 20
        elif property_classification == "fixer_upper":
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

    def search_candidates(
        self,
        *,
        address: str = "",
        city: str = "",
        state: str = "",
        zip_code: str = "",
        limit: int = 12,
    ) -> List[CanonicalProperty]:
        if not self.budget.use("realtor_search", 1):
            return []

        location_parts = [x.strip() for x in [address, city, state, zip_code] if x and str(x).strip()]
        location = ", ".join(location_parts)

        listings = search_realtor_for_sale(
            location=location,
            limit=min(limit, 12),
            offset=0,
            sort="relevance",
            days_on=1,
            expand_search_radius=0,
        )

        filtered = [x for x in listings if _property_matches_asset_type(x, self.asset_type)]
        if filtered:
            return [self._from_realtor_listing(item) for item in filtered]

        fallback_listing = {}
        if city and state:
            try:
                fallback_listing = find_rentcast_sale_listing(
                    address=address,
                    city=city,
                    state=state,
                    zip_code=zip_code,
                    limit=min(max(limit, 5), 25),
                ) or {}
            except Exception:
                fallback_listing = {}

        if fallback_listing:
            normalized = normalize_rentcast_sale_listing(fallback_listing)
            if _property_matches_asset_type(normalized, self.asset_type):
                return [self._from_rentcast_listing(normalized)]

        return []

    def _from_realtor_listing(self, item: Dict[str, Any]) -> CanonicalProperty:
        photos = self._normalize_photo_candidates(
            item.get("photos"),
            item.get("primary_photo"),
            item.get("raw", {}),
        )

        return CanonicalProperty(
            provider_ids={"realtor": item.get("property_id")},
            address=item.get("address") or item.get("address_line1"),
            address_line1=item.get("address_line1") or item.get("address"),
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
            primary_photo=item.get("primary_photo") or (photos[0] if photos else None),
            photos=photos,
            status=item.get("status"),
            days_on_market=self._as_int(item.get("days_on_market")),
            description=item.get("description"),
            strategy=self.strategy,
            recommended_strategy=self.strategy,
            value_sources={
                "listing_price": "realtor",
                "photos": "realtor",
            },
            raw=item.get("raw") or item,
        )

    def _from_rentcast_listing(self, item: Dict[str, Any]) -> CanonicalProperty:
        photos = self._normalize_photo_candidates(
            item.get("photos"),
            item.get("primary_photo"),
            item.get("raw", {}),
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

            cp = self._enrich_with_realtor_photos(cp)
            cp = self._enrich_with_attom(cp)
            cp = self._enrich_with_rentcast(cp)

            if idx < 2:
                cp = self._enrich_with_mashvisor(cp)

            enriched.append(cp)

        return enriched

    def _enrich_with_realtor_photos(self, cp: CanonicalProperty) -> CanonicalProperty:
        property_id = cp.provider_ids.get("realtor")
        if not property_id:
            return cp

        try:
            extra_photos = fetch_realtor_photos(property_id)
        except Exception:
            extra_photos = []

        if extra_photos:
            cp.photos = self._normalize_photo_candidates(cp.photos, extra_photos)
            cp.primary_photo = _resolve_photo(cp.primary_photo, cp.photos)

        return cp

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

        sale_listing_photos = self._normalize_photo_candidates(
            cp.photos,
            sale_listing.get("primary_photo"),
            sale_listing.get("photos"),
            sale_listing.get("raw", {}),
        )
        if sale_listing_photos:
            cp.photos = sale_listing_photos
            cp.primary_photo = _resolve_photo(cp.primary_photo, sale_listing_photos)

        cp.value_sources.update({
            "market_value": "rentcast",
            "monthly_rent_estimate": "rentcast",
        })

        return cp

    def _enrich_with_mashvisor(self, cp: CanonicalProperty) -> CanonicalProperty:
        if not self._mashvisor or not self.budget.use("mashvisor_detail", 1):
            return cp

        try:
            result = self._mashvisor.validate_property_with_mashvisor(
                address=cp.address or cp.address_line1 or "",
                city=cp.city or "",
                state=cp.state or "",
                zip_code=cp.zip_code or "",
                beds=self._as_int(cp.beds) if cp.beds is not None else None,
                baths=cp.baths,
                lat=cp.latitude,
                lng=cp.longitude,
                include_comps=False,
            )
            normalized = normalize_mashvisor_validation(result)
        except MashvisorError:
            return cp
        except Exception:
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
        cp.comp_confidence = self._first_truthy(
            str(normalized.get("confidence")) if normalized.get("confidence") is not None else None,
            cp.comp_confidence,
        )

        mashvisor_photos = self._extract_mashvisor_photos(normalized, result)

        property_id = (
            normalized.get("property_id")
            or normalized.get("id")
            or (
                ((result.get("property") or {}).get("content") or {}).get("id")
                if isinstance(result, dict) and isinstance(result.get("property"), dict)
                else None
            )
            or (
                ((result.get("lookup") or {}).get("content") or {}).get("id")
                if isinstance(result, dict) and isinstance(result.get("lookup"), dict)
                else None
            )
        )

        if property_id and hasattr(self._mashvisor, "get_property_images"):
            try:
                image_result = self._mashvisor.get_property_images(property_id)
                if image_result.get("status") == "success":
                    mashvisor_photos = self._normalize_photo_candidates(
                        mashvisor_photos,
                        image_result.get("photos"),
                        image_result.get("primary_photo"),
                    )
            except Exception:
                pass

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

    def rank_candidates(self, results: List[CanonicalProperty]) -> List[CanonicalProperty]:
        ranked: List[CanonicalProperty] = []

        for idx, cp in enumerate(results):
            cp = self._recommend_exit_strategy(cp)

            if idx < 4 and self.budget.use("deal_architect", 1):
                cp = self._apply_ravlo_opinion(cp)
            else:
                cp = self._annotate_default(cp)

            ranked.append(cp)

        ranked.sort(key=lambda x: (x.deal_score is not None, x.deal_score or 0), reverse=True)
        return ranked

    def _apply_ravlo_opinion(self, cp: CanonicalProperty) -> CanonicalProperty:
        score = 50
        why: List[str] = []
        risks: List[str] = []

        if cp.listing_price and cp.market_value and cp.market_value > cp.listing_price:
            score += 12
            why.append("Pricing appears below current value signal.")

        if cp.monthly_rent_estimate:
            score += 10
            why.append("Rent estimate supports investor review.")

        if cp.assessed_value and cp.market_value and cp.assessed_value < cp.market_value:
            score += 4
            why.append("Public record values leave room for upside review.")

        if cp.primary_photo:
            score += 3

        if cp.square_feet:
            score += 3

        if not cp.market_value and not cp.assessed_value:
            score -= 10
            risks.append("Value signal still needs validation.")

        if self.strategy == "rental" and not cp.monthly_rent_estimate:
            score -= 10
            risks.append("Rental strategy needs stronger rent support.")

        if self.strategy == "airbnb" and not cp.airbnb_rent_estimate:
            score -= 12
            risks.append("Short-term rental strategy needs stronger hospitality signal.")

        if cp.year_built and cp.year_built < 1950:
            score -= 5
            risks.append("Older property may require heavier rehab review.")

        score = max(1, min(99, round(score)))
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

        cp.why_it_made_list = why[:3] if why else cp.why_it_made_list or ["Worth deeper review in Project Studio."]
        cp.risk_notes = risks[:2] if risks else cp.risk_notes or ["Confirm data before committing to execution."]
        cp.primary_strengths = cp.primary_strengths or cp.why_it_made_list[:2]
        cp.primary_risks = cp.primary_risks or cp.risk_notes[:2]

        return cp

    def _annotate_default(self, cp: CanonicalProperty) -> CanonicalProperty:
        result = _annotate_deal_finder_opportunity(cp.to_result_dict(), self.strategy)
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
        enriched = self.enrich_top_candidates(candidates, top_n=4)
        ranked = self.rank_candidates(enriched)

        results = [cp.to_result_dict() for cp in ranked[:4]]

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
                "realtor_search": self.budget.realtor_search,
                "attom_detail": self.budget.attom_detail,
                "rentcast_detail": self.budget.rentcast_detail,
                "mashvisor_detail": self.budget.mashvisor_detail,
                "deal_architect": self.budget.deal_architect,
            },
        }
        return results, meta
