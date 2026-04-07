from typing import Any, Dict


def _num(val: Any, default=0.0) -> float:
    try:
        if val is None or val == "":
            return float(default)
        return float(val)
    except Exception:
        return float(default)


def normalize_property(attom_data: Dict[str, Any], mash_data: Dict[str, Any]) -> Dict[str, Any]:
    price = _num(attom_data.get("market_value") or mash_data.get("listing_price"))
    traditional_rent = _num(mash_data.get("traditional_rent"))
    airbnb_rent = _num(mash_data.get("airbnb_rent"))
    sqft = _num(attom_data.get("sqft"))
    tax_amount = _num(attom_data.get("tax_amount"))

    return {
        "address": attom_data.get("address_one_line") or "",
        "address_line1": attom_data.get("address_line1") or "",
        "city": attom_data.get("city") or "",
        "state": attom_data.get("state") or "",
        "zip_code": attom_data.get("zip_code") or "",

        "attom_id": attom_data.get("attom_id"),
        "apn": attom_data.get("apn"),

        "price": price,
        "market_value": _num(attom_data.get("market_value")),
        "assessed_value": _num(attom_data.get("assessed_value")),
        "last_sale_price": _num(attom_data.get("last_sale_price")),
        "last_sale_date": attom_data.get("last_sale_date"),

        "property_type": attom_data.get("property_type"),
        "property_sub_type": attom_data.get("property_sub_type"),
        "beds": _num(attom_data.get("bedrooms")),
        "baths": _num(attom_data.get("bathrooms")),
        "sqft": sqft,
        "lot_sqft": _num(attom_data.get("lot_sqft")),
        "year_built": attom_data.get("year_built"),

        "owner_name": attom_data.get("owner_name"),
        "owner_occupied": attom_data.get("owner_occupied"),
        "distressed": bool(attom_data.get("distressed")),
        "foreclosure_status": attom_data.get("foreclosure_status"),
        "tax_amount": tax_amount,

        "traditional_rent": traditional_rent,
        "traditional_cash_flow": _num(mash_data.get("traditional_cash_flow")),
        "traditional_cap_rate": _num(mash_data.get("traditional_cap_rate")),
        "traditional_coc": _num(mash_data.get("traditional_coc")),

        "airbnb_rent": airbnb_rent,
        "airbnb_cash_flow": _num(mash_data.get("airbnb_cash_flow")),
        "airbnb_cap_rate": _num(mash_data.get("airbnb_cap_rate")),
        "airbnb_coc": _num(mash_data.get("airbnb_coc")),
        "occupancy_rate": _num(mash_data.get("occupancy_rate")),

        "rent_to_price_ratio": (traditional_rent * 12 / price) if price > 0 else 0,
        "price_per_sqft": (price / sqft) if sqft > 0 else 0,

        "raw_sources": {
            "attom": attom_data.get("raw", {}),
            "mashvisor": mash_data.get("raw", {}),
        },
    }
