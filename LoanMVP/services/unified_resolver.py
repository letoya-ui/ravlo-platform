import time
import re
import hashlib

from LoanMVP.services.ai_summary import generate_property_summary
from LoanMVP.services.attom_service import (
    build_attom_dealfinder_profile,
    AttomServiceError,
)

from LoanMVP.services.realtor_provider import fetch_realtor_data
from LoanMVP.services.rentcast_provider import fetch_rentcast_data
from LoanMVP.services.attom_provider import fetch_attom_data

_CACHE = {}
_TTL = 60 * 60 * 6  # 6 hours


def resolve_property_unified(address: str, *, beds=None, baths=None, sqft=None, property_type=None) -> dict:
    """
    Unified property resolver with ATTOM as base and Realtor.com enrichment.
    Returns:
    - property (ATTOM + Realtor merged)
    - valuation
    - rent_estimate (placeholder)
    - comps (placeholder)
    - market_snapshot
    - ai_summary
    - raw payloads
    """

    from LoanMVP.services.realtor_provider import fetch_realtor_data

    address = (address or "").strip()
    if not address:
        return {"status": "error", "error": "address_required"}

    try:
        # -----------------------------------------
        # 1) ATTOM lookup
        # -----------------------------------------
        payload = _attom_get("property/address", {"address1": address})
        properties = _extract_attom_properties(payload)

        if not properties:
            return {
                "status": "error",
                "source": "attom",
                "stage": "property_lookup",
                "error": "No property found for this address.",
            }

        subject_raw = properties[0]
        prop = _normalize_attom_subject(subject_raw, address)

        # -----------------------------------------
        # 2) Realtor.com enrichment
        # -----------------------------------------
        try:
            realtor_raw = fetch_realtor_data(
                prop.get("address_line1") or prop.get("address"),
                prop.get("city"),
                prop.get("state")
            )
        except Exception:
            realtor_raw = None

        if realtor_raw and realtor_raw.get("property"):
            listing = realtor_raw["property"]

            prop["price"] = listing.get("price") or prop.get("price")
            prop["photos"] = listing.get("photos") or prop.get("photos")
            prop["primary_photo"] = listing.get("primary_photo") or prop.get("primary_photo")
            prop["status"] = listing.get("status")
            prop["days_on_market"] = listing.get("days_on_market")
            prop["description"] = listing.get("description")

        # -----------------------------------------
        # 3) Valuation (ATTOM-based)
        # -----------------------------------------
        valuation = {
            "estimate": prop.get("price"),
            "low": None,
            "high": None,
            "confidence": None,
            "assessed_value": prop.get("assessed_value"),
            "last_sale_price": prop.get("price"),
        }

        # -----------------------------------------
        # 4) Rent estimate placeholder
        # -----------------------------------------
        rent_estimate = {
            "rent": None,
            "low": None,
            "high": None,
            "confidence": None,
        }

        # -----------------------------------------
        # 5) Comps placeholder
        # -----------------------------------------
        comps = {
            "sales": [],
            "rentals": [],
            "meta": {
                "comp_count": 0,
                "max_radius": None,
                "days_old": None,
            },
        }

        # -----------------------------------------
        # 6) Market snapshot
        # -----------------------------------------
        market_snapshot = _calculate_market_snapshot([], [], comps["meta"])

        # -----------------------------------------
        # 7) AI summary
        # -----------------------------------------
        summary_bits = []
        if prop.get("property_type"):
            summary_bits.append(f"Type: {prop['property_type']}")
        if prop.get("year_built"):
            summary_bits.append(f"Built: {prop['year_built']}")
        if prop.get("square_feet"):
            summary_bits.append(f"Size: {prop['square_feet']:,} sqft")
        if prop.get("price"):
            summary_bits.append(f"Last recorded sale: ${prop['price']:,.0f}")
        if prop.get("assessed_value"):
            summary_bits.append(f"Assessed value: ${prop['assessed_value']:,.0f}")

        ai_summary = " | ".join(summary_bits) if summary_bits else "Public record property data loaded."

        # -----------------------------------------
        # 8) Final return
        # -----------------------------------------
        return {
            "status": "ok",
            "source": "realtor" if realtor_raw else "attom",
            "property": prop,
            "valuation": valuation,
            "rent_estimate": rent_estimate,
            "comps": comps,
            "market_snapshot": market_snapshot,
            "ai_summary": ai_summary,
            "raw": {
                "property_lookup": subject_raw,
                "realtor": realtor_raw,
            },
        }

    except Exception as e:
        return {
            "status": "error",
            "source": "attom",
            "stage": "property_lookup",
            "error": str(e),
        }


def resolve_property(address, city, state):
    # 1. Realtor.com (photos + price)
    realtor = fetch_realtor_data(address, city, state)
    if realtor:
        return realtor

    # 2. RentCast (valuation, rent, comps)
    rentcast = fetch_rentcast_data(address, city, state)
    if rentcast:
        return rentcast

    # 3. ATTOM (public record fallback)
    attom = fetch_attom_data(address, city, state)
    if attom:
        return attom

    return {"source": "none", "error": "No data found"}

