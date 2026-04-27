"""
Ravlo Subject Normalizer
-------------------------
Merges ATTOM, RentCast, and Mashvisor raw data into one internal schema
so downstream analysis never has to guess which field name to use.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _safe_float(val: Any) -> Optional[float]:
    if val is None or val == "" or val == "None":
        return None
    try:
        if isinstance(val, (int, float)):
            return float(val)
        return float(str(val).replace("$", "").replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _safe_int(val: Any) -> Optional[int]:
    f = _safe_float(val)
    return int(round(f)) if f is not None else None


def _first(*values: Any) -> Any:
    for v in values:
        if v is not None and v != "" and v != "None":
            return v
    return None


def normalize_subject(
    attom_data: Dict[str, Any],
    rentcast_data: Dict[str, Any],
    mashvisor_data: Optional[Dict[str, Any]] = None,
    listing_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Produce a single unified subject dict from all available providers.

    Each provider dict may be empty if that source was unavailable.
    """
    attom = attom_data or {}
    rc = rentcast_data or {}
    mash = mashvisor_data or {}
    listing = listing_data or {}

    address = _first(
        attom.get("address"),
        rc.get("formattedAddress"),
        rc.get("address"),
        listing.get("address"),
        mash.get("address"),
    )

    property_type = _first(
        attom.get("property_type"),
        rc.get("propertyType"),
        rc.get("property_type"),
        mash.get("property_type"),
        listing.get("propertyType"),
    )

    beds = _safe_int(_first(
        attom.get("beds"), attom.get("bedrooms"),
        rc.get("bedrooms"), rc.get("beds"),
        listing.get("beds"), listing.get("bedrooms"),
        mash.get("bedrooms"),
    ))

    baths = _safe_float(_first(
        attom.get("baths"), attom.get("bathrooms"),
        rc.get("bathrooms"), rc.get("baths"),
        listing.get("baths"), listing.get("bathrooms"),
        mash.get("bathrooms"),
    ))

    living_sqft = _safe_float(_first(
        attom.get("sqft"), attom.get("livingSize"),
        rc.get("squareFootage"), rc.get("sqft"),
        listing.get("square_feet"), listing.get("sqft"),
        mash.get("sqft"),
    ))

    lot_sqft = _safe_float(_first(
        attom.get("lot_sqft"), attom.get("lotSize"),
        rc.get("lotSize"), rc.get("lotSizeSqFt"),
        listing.get("lot_size_sqft"),
        mash.get("lot_sqft"),
    ))

    year_built = _safe_int(_first(
        attom.get("year_built"), attom.get("yearBuilt"),
        rc.get("yearBuilt"),
        listing.get("year_built"),
        mash.get("year_built"),
    ))

    last_sale_price = _safe_float(_first(
        attom.get("last_sale_price"),
        rc.get("lastSalePrice"),
    ))

    last_sale_date = _first(
        attom.get("last_sale_date"),
        rc.get("lastSaleDate"),
    )

    current_listing_price = _safe_float(_first(
        listing.get("price"), listing.get("listPrice"),
        rc.get("listing_price"),
    ))

    estimated_value_by_source: Dict[str, Optional[float]] = {}

    attom_market = _safe_float(attom.get("market_value"))
    attom_assessed = _safe_float(attom.get("assessed_value"))
    if attom_market:
        estimated_value_by_source["attom_market"] = attom_market
    if attom_assessed:
        estimated_value_by_source["attom_assessed"] = attom_assessed

    rc_avm = _safe_float(_first(
        rc.get("price"), rc.get("value"), rc.get("avm"),
        rc.get("estimatedValue"), rc.get("avm_value"),
    ))
    if rc_avm:
        estimated_value_by_source["rentcast"] = rc_avm

    mash_val = _safe_float(_first(
        mash.get("estimated_value"), mash.get("value"),
    ))
    if mash_val:
        estimated_value_by_source["mashvisor"] = mash_val

    rent_estimate_by_source: Dict[str, Optional[float]] = {}

    rc_rent = _safe_float(_first(
        rc.get("rent"), rc.get("estimatedRent"),
        rc.get("rentEstimate"), rc.get("traditional_rent"),
    ))
    if rc_rent:
        rent_estimate_by_source["rentcast"] = rc_rent

    mash_rent = _safe_float(_first(
        mash.get("traditional_rent"), mash.get("rent"),
    ))
    if mash_rent:
        rent_estimate_by_source["mashvisor"] = mash_rent

    is_vacant_lot = _detect_vacant_lot(property_type, living_sqft, lot_sqft)

    return {
        "address": address,
        "property_type": property_type,
        "is_vacant_lot": is_vacant_lot,
        "beds": beds,
        "baths": baths,
        "living_sqft": living_sqft,
        "lot_sqft": lot_sqft,
        "year_built": year_built,
        "last_sale_price": last_sale_price,
        "last_sale_date": last_sale_date,
        "current_listing_price": current_listing_price,
        "estimated_value_by_source": estimated_value_by_source,
        "rent_estimate_by_source": rent_estimate_by_source,
        "latitude": _safe_float(_first(
            attom.get("latitude"), rc.get("latitude"),
            listing.get("latitude"), mash.get("latitude"),
        )),
        "longitude": _safe_float(_first(
            attom.get("longitude"), rc.get("longitude"),
            listing.get("longitude"), mash.get("longitude"),
        )),
        "data_sources": {
            "attom": bool(attom),
            "rentcast": bool(rc),
            "mashvisor": bool(mash),
            "listing": bool(listing),
        },
    }


def _detect_vacant_lot(
    property_type: Optional[str],
    living_sqft: Optional[float],
    lot_sqft: Optional[float],
) -> bool:
    if property_type:
        pt_lower = str(property_type).lower()
        land_keywords = ["land", "lot", "vacant", "acre", "parcel", "unimproved"]
        if any(kw in pt_lower for kw in land_keywords):
            return True
    if lot_sqft and lot_sqft > 0 and (not living_sqft or living_sqft <= 0):
        return True
    return False
