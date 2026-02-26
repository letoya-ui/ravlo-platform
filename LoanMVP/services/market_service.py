from LoanMVP.services.unified_resolver import resolve_property_unified

def get_market_snapshot(address=None, zipcode=None):
    """
    Lightweight snapshot.
    NOTE: Unified resolver is address-based (RentCast AVM). Zip-only snapshot is a placeholder for now.
    """

    empty = {
        "name": zipcode,
        "median_price": None,
        "median_rent": None,
        "inventory": None,
        "dom": None,
        "trend": None,
        "price_labels": [],
        "price_values": [],
        "rent_labels": [],
        "rent_values": [],
        "inventory_labels": [],
        "inventory_values": []
    }

    # If we only have zipcode, return placeholder (no crash)
    if not address:
        return empty

    result = resolve_property_unified(address)

    if not result or result.get("status") != "ok":
        return empty

    prop = result.get("property", {}) or {}
    valuation = prop.get("valuation", {}) or {}
    rent_est = prop.get("rent_estimate", {}) or {}

    return {
        **empty,
        "name": prop.get("city") or zipcode,
        "median_price": valuation.get("estimate"),
        "median_rent": rent_est.get("rent"),
    }