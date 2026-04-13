import os
from typing import Any, Dict

from LoanMVP.services.rentcast_service import (
    get_rentcast_rent_estimate,
    get_rentcast_value_estimate,
    find_rentcast_sale_listing,
    normalize_rentcast_sale_listing,
    RentCastServiceError,
)


class RentCastAdapter:
    def enabled(self) -> bool:
        return bool(os.getenv("RENTCAST_API_KEY", "").strip())

    def enrich_property(
        self,
        *,
        address: str,
        city: str,
        state: str,
        zip_code: str = "",
        property_type: str = "single_family",
    ) -> Dict[str, Any]:
        if not self.enabled():
            return {}

        out: Dict[str, Any] = {
            "rent_estimate": None,
            "value_estimate": None,
            "sale_listing": None,
            "errors": [],
        }

        try:
            out["rent_estimate"] = get_rentcast_rent_estimate(
                address=address,
                city=city,
                state=state,
                zip_code=zip_code,
                property_type=property_type,
            )
        except RentCastServiceError as exc:
            out["errors"].append({"rent_estimate": str(exc)})

        try:
            out["value_estimate"] = get_rentcast_value_estimate(
                address=address,
                city=city,
                state=state,
                zip_code=zip_code,
                property_type=property_type,
            )
        except RentCastServiceError as exc:
            out["errors"].append({"value_estimate": str(exc)})

        try:
            listing = find_rentcast_sale_listing(
                address=address,
                city=city,
                state=state,
                zip_code=zip_code,
                limit=25,
            )
            if listing:
                out["sale_listing"] = normalize_rentcast_sale_listing(listing)
        except RentCastServiceError as exc:
            out["errors"].append({"sale_listing": str(exc)})

        return out

    @staticmethod
    def normalize(result: Dict[str, Any]) -> Dict[str, Any]:
        rent = result.get("rent_estimate") or {}
        value = result.get("value_estimate") or {}
        listing = result.get("sale_listing") or {}

        rent_estimate = (
            rent.get("rent")
            or rent.get("price")
            or rent.get("estimate")
            or rent.get("monthlyRent")
        )

        value_estimate = (
            value.get("price")
            or value.get("value")
            or value.get("estimate")
            or value.get("avm")
        )

        return {
            "market_value": value_estimate,
            "monthly_rent_estimate": rent_estimate,
            "listing_price": listing.get("price"),
            "beds": listing.get("beds"),
            "baths": listing.get("baths"),
            "square_feet": listing.get("square_feet"),
            "lot_size_sqft": listing.get("lot_size_sqft"),
            "year_built": listing.get("year_built"),
            "property_type": listing.get("property_type"),
            "status": listing.get("status"),
            "days_on_market": listing.get("days_on_market"),
            "primary_photo": listing.get("primary_photo"),
            "value_sources": {
                "market_value": "rentcast",
                "monthly_rent_estimate": "rentcast",
                "listing_fallback": "rentcast" if listing else None,
            },
            "raw_rentcast": result,
        }