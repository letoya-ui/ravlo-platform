"""
Adapter layer that converts the RentCast unified resolver output
into the structure expected by the Deal Workspace UI.
"""

from LoanMVP.services.unified_resolver import resolve_property_unified


def resolve_property_intelligence(property_id, comps):
    """
    Converts the saved comps + unified resolver output into the
    structure required by the Deal Workspace intelligence grid.
    """

    # comps["resolved"] already contains the unified resolver output
    unified = comps.get("resolved") or {}
    prop = unified.get("property") or {}

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

            "valuation": unified.get("property", {}).get("valuation"),
            "rent_estimate": unified.get("property", {}).get("rent_estimate"),
            "photos": unified.get("property", {}).get("photos") or [],

            "comps": {
                "sales": (prop.get("comps") or {}).get("sales") or [],
                "rentals": (prop.get("comps") or {}).get("rentals") or [],
            },
        },

        "ai_summary": unified.get("ai_summary"),
        "primary_source": unified.get("primary_source"),
    }
