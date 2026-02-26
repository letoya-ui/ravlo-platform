def to_property_card_dto(unified: dict) -> dict:
    prop = unified.get("property", {}) or unified
    
    return {
        "source": unified.get("primary_source") or prop.get("source"),
        "address": prop.get("address"),
        "price": prop.get("price"),
        "zestimate": prop.get("zestimate"),
        "beds": prop.get("beds"),
        "baths": prop.get("baths"),
        "sqft": prop.get("sqft"),
        "lat": prop.get("lat"),
        "lng": prop.get("lng"),
        "thumbnail": (prop.get("photos") or [None])[0],
        "has_comps": bool(prop.get("comps")),
        "has_history": bool(prop.get("price_history") or prop.get("tax_history")),
        "ai_summary": unified.get("ai_summary"),
    }
