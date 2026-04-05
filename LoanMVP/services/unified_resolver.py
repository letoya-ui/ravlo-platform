import time
import re
import hashlib

from LoanMVP.services.ai_summary import generate_property_summary
from LoanMVP.services.attom_service import (
    build_attom_dealfinder_profile,
    AttomServiceError,
)

_CACHE = {}
_TTL = 60 * 60 * 6  # 6 hours


def resolve_property_unified(address: str = None, zipcode: str = None, **kwargs) -> dict:
    """
    Unified property resolver.

    Backward compatible:
      - accepts zipcode
      - accepts extra kwargs from older callers without crashing
      - returns the same general structure expected by current routes/templates
    """

    raw_query = (address or "").strip()
    zipcode = (zipcode or "").strip()

    if not raw_query:
        return {
            "status": "error",
            "provider": "attom",
            "error": "address_required",
            "stage": "input",
        }

    # ---- cache ----
    key = _ck(raw_query, zipcode=zipcode)
    cached = _cache_get(key)
    if cached:
        return cached

    parsed = _parse_address_query(raw_query, zipcode=zipcode)
    if not parsed:
        out = {
            "status": "error",
            "provider": "attom",
            "error": "Enter full address as: 123 Main St, Atlanta, GA 30308",
            "stage": "parse",
        }
        _cache_set(key, out)
        return out

    try:
        profile = build_attom_dealfinder_profile(
            address=parsed["address"],
            city=parsed["city"],
            state=parsed["state"],
            zip_code=parsed.get("zip_code") or "",
        )

        property_payload = {
            "property_id": profile.get("attom_id"),
            "id": profile.get("attom_id"),
            "propertyId": profile.get("attom_id"),
            "address": profile.get("address") or profile.get("address_line1") or raw_query,
            "address_line1": profile.get("address_line1"),
            "city": profile.get("city"),
            "state": profile.get("state"),
            "zip": profile.get("zip_code"),
            "zipCode": profile.get("zip_code"),
            "postalCode": profile.get("zip_code"),
            "sqft": profile.get("sqft"),
            "squareFootage": profile.get("sqft"),
            "beds": profile.get("beds"),
            "baths": profile.get("baths"),
            "property_type": profile.get("property_type"),
            "property_sub_type": profile.get("property_sub_type"),
            "year_built": profile.get("year_built"),
            "owner_name": profile.get("owner_name"),
            "owner_occupied": profile.get("owner_occupied"),
            "apn": profile.get("apn"),
            "latitude": profile.get("latitude"),
            "longitude": profile.get("longitude"),
            "price": profile.get("market_value") or profile.get("assessed_value") or 0,
            "photos": [],
            "primary_photo": None,
            "ravlo_score": profile.get("ravlo_score"),
            "recommended_strategy": profile.get("recommended_strategy"),
            "score_reasons": profile.get("score_reasons", []),
        }

        valuation = {
            "market_value": profile.get("market_value"),
            "assessed_value": profile.get("assessed_value"),
            "last_sale_price": profile.get("last_sale_price"),
            "last_sale_date": profile.get("last_sale_date"),
            "tax_amount": profile.get("tax_amount"),
        }

        rent_estimate = {}
        comps = {}
        market_snapshot = {
            "foreclosure_status": profile.get("foreclosure_status"),
            "distressed": profile.get("distressed"),
            "mortgage_amount": profile.get("mortgage_amount"),
            "owner_occupied": profile.get("owner_occupied"),
        }

        summary = generate_property_summary({
            "property": property_payload,
            "valuation": valuation,
            "rent_estimate": rent_estimate,
            "comps": comps,
            "market_snapshot": market_snapshot,
            "source": "attom",
        })

        out = {
            "status": "ok",
            "provider": "attom",
            "stage": "property_detail",
            "property": property_payload,
            "valuation": valuation,
            "rent_estimate": rent_estimate,
            "comps": comps,
            "market_snapshot": market_snapshot,
            "ai_summary": summary,
            "primary_source": "attom",
            "raw_profile": profile,
        }

        _cache_set(key, out)
        return out

    except AttomServiceError as e:
        out = {
            "status": "error",
            "provider": "attom",
            "error": str(e),
            "stage": "property_detail",
        }
        _cache_set(key, out)
