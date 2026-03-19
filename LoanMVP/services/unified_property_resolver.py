"""
Adapter layer that converts unified resolver output
into the structure expected by the Deal Workspace UI.
"""

from LoanMVP.services.unified_resolver import resolve_property_unified


def resolve_property_intelligence(property_id, comps):
    """
    Converts saved comps + unified resolver output into the
    structure required by the Deal Workspace intelligence grid.
    """

    unified = comps.get("resolved") or {}

    prop = unified.get("property") or {}
    valuation = unified.get("valuation") or {}
    rent_estimate = unified.get("rent_estimate") or {}
    normalized_comps = unified.get("comps") or {}
    market_snapshot = unified.get("market_snapshot") or {}

    return {
        "property": {
            "id": property_id,
            "address": prop.get("address"),
            "city": prop.get("city"),
            "state": prop.get("state"),
            "zip": prop.get("zip"),
            "beds": prop.get("beds"),
            "baths": prop.get("baths"),
            "sqft": prop.get("sqft"),
            "year_built": prop.get("year_built"),
            "property_type": prop.get("property_type"),
            "price": prop.get("price"),
            "photos": prop.get("photos") or [],
            "primary_photo": prop.get("primary_photo"),

            "valuation": valuation,
            "rent_estimate": rent_estimate,
            "market_snapshot": market_snapshot,

            "comps": {
                "sales": normalized_comps.get("sales") or [],
                "rentals": normalized_comps.get("rentals") or [],
                "meta": normalized_comps.get("meta") or {},
            },
        },

        "ai_summary": unified.get("ai_summary"),
        "primary_source": unified.get("primary_source") or unified.get("source"),
    }
