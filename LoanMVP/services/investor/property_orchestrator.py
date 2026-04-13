from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from LoanMVP.services.realtor_provider import search_realtor_for_sale
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

# Keep using your existing route/helper logic so the UI stays aligned.
from LoanMVP.routes.investor.property_tool_helpers import (
    _normalize_asset_type,
    _asset_type_label,
    _property_matches_asset_type,
    _annotate_deal_finder_opportunity,
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
        out = []
        seen = set()

        def _push(url):
            if not url:
                return
            url = str(url).strip()
            if not url or url in seen:
                return
            seen.add(url)
            out.append(url)

        def _walk(value):
            if not value:
                return
            if isinstance(value, str):
                _push(value)
            elif isinstance(value, list):
                for item in value:
                    _walk(item)
            elif isinstance(value, dict):
                for key in ("url", "src", "href", "photo", "image", "thumbnail"):
                    if value.get(key):
                        _push(value.get(key))
                for key in ("photos", "images", "media", "gallery"):
                    if value.get(key):
                        _walk(value.get(key))

        for src in sources:
            _walk(src)

        return out

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
        return [self._from_realtor_listing(item) for item in filtered]

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

    def enrich_top_candidates(self, results: List[CanonicalProperty], top_n: int = 4) -> List[CanonicalProperty]:
        enriched: List[CanonicalProperty] = []

        for idx, cp in enumerate(results):
            if idx >= top_n:
                enriched.append(cp)
                continue

            cp = self._enrich_with_attom(cp)
            cp = self._enrich_with_rentcast(cp)

            # Only top 2 get Mashvisor depth
            if idx < 2:
                cp = self._enrich_with_mashvisor(cp)

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

        if not cp.primary_photo and sale_listing.get("primary_photo"):
            cp.primary_photo = sale_listing.get("primary_photo")
            cp.photos = [cp.primary_photo]

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

        cp.airbnb_rent_estimate = self._first_truthy(self._as_float(normalized.get("airbnb_revenue")), cp.airbnb_rent_estimate)
        cp.occupancy_rate = self._first_truthy(self._as_float(normalized.get("occupancy_rate")), cp.occupancy_rate)
        cp.airbnb_cash_on_cash = self._first_truthy(self._as_float(normalized.get("cash_on_cash_return")), cp.airbnb_cash_on_cash)
        cp.comp_confidence = self._first_truthy(
            str(normalized.get("confidence")) if normalized.get("confidence") is not None else None,
            cp.comp_confidence,
        )

        cp.value_sources.update({
            "airbnb_revenue": "mashvisor",
            "occupancy_rate": "mashvisor",
        })

        return cp

    def rank_candidates(self, results: List[CanonicalProperty]) -> List[CanonicalProperty]:
        ranked: List[CanonicalProperty] = []

        for idx, cp in enumerate(results):
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

        if self.strategy == "rental":
            cp.strategy_tag = cp.strategy_tag or "Hold Candidate"
            cp.estimated_best_use = cp.estimated_best_use or "Long-term rental hold"
        elif self.strategy == "airbnb":
            cp.strategy_tag = cp.strategy_tag or "STR Candidate"
            cp.estimated_best_use = cp.estimated_best_use or "Short-term rental operation"
        else:
            cp.strategy_tag = cp.strategy_tag or "Flip Candidate"
            cp.estimated_best_use = cp.estimated_best_use or "Fix and flip reposition"

        cp.recommended_strategy = cp.recommended_strategy or self.strategy
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