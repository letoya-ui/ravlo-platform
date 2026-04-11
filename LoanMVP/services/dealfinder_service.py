from typing import Dict, Any

from LoanMVP.services.attom_service import (
    get_property_detail,
    extract_core_fields as extract_attom_fields,
    AttomServiceError,
)
from LoanMVP.services.rentcast_service import (
    get_rentcast_rent_estimate,
    RentCastServiceError,
)
from LoanMVP.services.dealfinder_normalizer import normalize_property
from LoanMVP.services.dealfinder_scoring import compute_deal_score
import requests
from LoanMVP.services.realtor_provider import fetch_realtor_data

RENTCAST_API_KEY = "d0bdb63befcc468897409c4293fd5049"


def extract_attom_fields(raw):
    try:
        prop = raw.get("property", {}) or raw

        market = (
            prop.get("market_value")
            or prop.get("marketValue")
            or prop.get("avm", {}).get("amount")
            or prop.get("assessment", {}).get("market", {}).get("mktttlvalue")
        )

        assessed = (
            prop.get("assessed_value")
            or prop.get("assessment", {}).get("assessed", {}).get("assdttlvalue")
        )

        sale = (
            prop.get("last_sale_price")
            or prop.get("sale", {}).get("amount")
        )

        return {
            "market_value": market,
            "assessed_value": assessed,
            "last_sale_price": sale,
            "bedrooms": prop.get("beds") or prop.get("bedrooms"),
            "bathrooms": prop.get("baths") or prop.get("bathrooms"),
            "sqft": prop.get("sqft") or prop.get("livingSize"),
            "year_built": prop.get("yearBuilt"),
        }

    except Exception:
        return {}

def _extract_rentcast_fields(rentcast_raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Maps RentCast response into the secondary analytics shape expected by
    normalize_property().

    Keep this adapter thin so the rest of Ravlo can stay unchanged.
    """
    if not rentcast_raw:
        return {}

    rent = (
        rentcast_raw.get("rent")
        or rentcast_raw.get("estimatedRent")
        or rentcast_raw.get("rentEstimate")
        or rentcast_raw.get("price")
    )

    rent_low = (
        rentcast_raw.get("rentRangeLow")
        or rentcast_raw.get("lowerRent")
        or rentcast_raw.get("minRent")
    )

    rent_high = (
        rentcast_raw.get("rentRangeHigh")
        or rentcast_raw.get("upperRent")
        or rentcast_raw.get("maxRent")
    )

    confidence = (
        rentcast_raw.get("confidence")
        or rentcast_raw.get("confidenceScore")
    )

    property_type = (
        rentcast_raw.get("propertyType")
        or rentcast_raw.get("property_type")
    )

    return {
        # normalized fields expected by existing normalizer
        "traditional_rent": rent,
        "traditional_cash_flow": 0,
        "traditional_cap_rate": 0,
        "traditional_coc": 0,

        # placeholders until STR / deeper analytics are connected
        "airbnb_rent": 0,
        "airbnb_cash_flow": 0,
        "airbnb_cap_rate": 0,
        "airbnb_coc": 0,
        "occupancy_rate": 0,

        # useful extras for UI/debugging
        "rent_low": rent_low,
        "rent_high": rent_high,
        "confidence": confidence,
        "property_type": property_type,
        "raw": rentcast_raw,
    }


def build_dealfinder_profile(
    address: str,
    city: str,
    state: str,
    zip_code: str = "",
    property_type: str = "single_family",
) -> Dict[str, Any]:
    errors = []
    attom_core: Dict[str, Any] = {}
    rentcast_core: Dict[str, Any] = {}
    realtor_core: Dict[str, Any] = {}

    try:
        attom_raw = get_property_detail(
            address=address,
            city=city,
            state=state,
            postalcode=zip_code,
        )
        attom_core = extract_attom_fields(attom_raw)
    except AttomServiceError as e:
        errors.append(f"ATTOM: {e}")

    try:
        rentcast_raw = get_rentcast_rent_estimate(
            address=address,
            city=city,
            state=state,
            zip_code=zip_code,
            property_type=property_type,
        )
        rentcast_core = _extract_rentcast_fields(rentcast_raw)
    except RentCastServiceError as e:
        errors.append(f"RentCast rent: {e}")
    except Exception as e:
        errors.append(f"RentCast rent: {e}")

    try:
        value_raw = get_rentcast_value_estimate(
            address=address,
            city=city,
            state=state,
            zip_code=zip_code,
            property_type=property_type,
        )
        rentcast_core["listing_price"] = (
            value_raw.get("price")
            or value_raw.get("value")
            or value_raw.get("avm")
            or value_raw.get("estimatedValue")
        )
        rentcast_core["avm_value"] = (
            value_raw.get("price")
            or value_raw.get("value")
            or value_raw.get("avm")
            or value_raw.get("estimatedValue")
        )
        rentcast_core["value_raw"] = value_raw
    except RentCastServiceError as e:
        errors.append(f"RentCast value: {e}")
    except Exception as e:
        errors.append(f"RentCast value: {e}")

    try:
        sale_listing = find_rentcast_sale_listing(
            address=address,
            city=city,
            state=state,
            zip_code=zip_code,
        )
        if sale_listing:
            realtor_core.update({
                "price": (
                    sale_listing.get("price")
                    or sale_listing.get("listPrice")
                    or sale_listing.get("listingPrice")
                ),
                "photos": sale_listing.get("photos"),
                "primary_photo": (
                    sale_listing.get("primaryPhoto")
                    or sale_listing.get("primary_photo")
                    or sale_listing.get("photo")
                ),
                "status": sale_listing.get("status"),
                "days_on_market": (
                    sale_listing.get("daysOnMarket")
                    or sale_listing.get("days_on_market")
                ),
                "description": sale_listing.get("description"),
            })
    except RentCastServiceError as e:
        errors.append(f"RentCast sale listing: {e}")
    except Exception as e:
        errors.append(f"RentCast sale listing: {e}")

    try:
        realtor_raw = fetch_realtor_data(address, city, state)
        if realtor_raw and realtor_raw.get("property"):
            prop = realtor_raw["property"]
            realtor_core.update({
                "price": prop.get("price") or realtor_core.get("price"),
                "photos": prop.get("photos") or realtor_core.get("photos"),
                "primary_photo": prop.get("primary_photo") or realtor_core.get("primary_photo"),
                "status": prop.get("status") or realtor_core.get("status"),
                "days_on_market": prop.get("days_on_market") or realtor_core.get("days_on_market"),
                "description": prop.get("description") or realtor_core.get("description"),
            })
    except Exception as e:
        errors.append(f"Realtor: {e}")

    if not attom_core:
        return {
            "ok": False,
            "errors": errors or ["No ATTOM property detail returned."],
            "profile": {},
            "scoring": {},
            "source_status": {
                "attom": False,
                "rentcast": bool(rentcast_core),
                "realtor": bool(realtor_core),
            },
        }

    profile = normalize_property(attom_core, rentcast_core, realtor_core)
    scoring = compute_deal_score(profile)

    if rentcast_core:
        profile["rent_low"] = rentcast_core.get("rent_low")
        profile["rent_high"] = rentcast_core.get("rent_high")
        profile["rent_confidence"] = rentcast_core.get("confidence")
        profile["avm_value"] = rentcast_core.get("avm_value")

    return {
        "ok": True,
        "errors": errors,
        "profile": profile,
        "scoring": scoring,
        "source_status": {
            "attom": bool(attom_core),
            "rentcast": bool(rentcast_core),
            "realtor": bool(realtor_core),
        },
    }

def get_rentcast_data(address, city, state, zip_code):
    try:
        url = "https://api.rentcast.io/v1/avm/rent/long-term"

        params = {
            "address": f"{address}, {city}, {state} {zip_code}"
        }

        headers = {
            "X-Api-Key": RENTCAST_API_KEY
        }

        res = requests.get(url, headers=headers, params=params, timeout=10)

        if res.status_code != 200:
            return None

        return res.json()

    except Exception:
        return None
