"""
Comps Service
-------------
Handles comparable property data for:
- Saved properties
- Rental comps (Rentometer)
- Resale comps (via unified resolver: RentCast)
- Placeholder Airbnb comps
"""

import requests
import json
from datetime import datetime, timedelta

from LoanMVP.extensions import db
from LoanMVP.models.property import SavedProperty
from LoanMVP.models.loan_models import BorrowerProfile
from LoanMVP.services.market_service import get_market_snapshot

# ✅ NEW: unified resolver (RentCast-backed)
from LoanMVP.services.unified_resolver import resolve_property_unified


# ---------------------------------------------------------
# RENTOMETER RENTAL COMPS
# ---------------------------------------------------------
def get_rental_comps(address, zipcode, api_key):
    """
    Fetch rental comps from Rentometer API.
    """
    try:
        url = "https://api.rentometer.com/v2/summary"
        params = {
            "api_key": api_key,
            "address": address,
            "zip": zipcode,
            "bedrooms": 2,
        }

        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        rentals = []
        for comp in data.get("comps", []):
            rentals.append({
                "address": comp.get("address"),
                "rent": comp.get("rent"),
                "beds": comp.get("bedrooms"),
                "baths": comp.get("bathrooms"),
                "sqft": comp.get("sqft"),
            })

        return rentals

    except Exception as e:
        print("Rentometer error:", e)
        return []


# ---------------------------------------------------------
# PLACEHOLDER AIRBNB COMPS
# ---------------------------------------------------------
def get_airbnb_comps(address, zipcode):
    """
    Placeholder for Airbnb API integration.
    """
    return {
        "airbnb_comps": [],
        "airbnb_rate_estimate": None,
        "airbnb_occupancy_estimate": None,
    }


# ---------------------------------------------------------
# RESALE + RENT + AVM (via Unified Resolver)
# ---------------------------------------------------------
def get_resale_comps_unified(address):
    """
    Uses resolve_property_unified() (RentCast-backed) to produce:
      - resale_comps (sales comps)
      - arv_estimate (value estimate)
      - market_rent_estimate (rent estimate)
    """
    resolved = resolve_property_unified(address)
    if resolved.get("status") != "ok":
        return {
            "resale_comps": [],
            "arv_estimate": None,
            "market_rent_estimate": None,
            "unified_property": None,
        }

    prop = resolved.get("property") or {}

    # ✅ Rentcast_resolver sets prop["comps"] = {"sales":[...], "rentals":[...], "meta": {...}}
    raw_comps = prop.get("comps") or {}
    sales_list = []
    rentals_list = []

    if isinstance(raw_comps, dict):
        sales_list = raw_comps.get("sales") or []
        rentals_list = raw_comps.get("rentals") or []
    elif isinstance(raw_comps, list):
        # If for some reason you ever store a flat list
        sales_list = raw_comps

    # Normalize each comp to your expected resale comp format
    resale_comps = []
    for c in (sales_list or [])[:10]:
        resale_comps.append({
            "address": c.get("formattedAddress") or c.get("address"),
            "price": c.get("price") or c.get("value"),
            "beds": c.get("bedrooms") or c.get("beds"),
            "baths": c.get("bathrooms") or c.get("baths"),
            "sqft": c.get("squareFootage") or c.get("squareFeet") or c.get("sqft"),
            "distance": c.get("distance"),
            "sold_date": c.get("soldDate") or c.get("lastSaleDate") or c.get("removedDate"),
        })

    # ARV estimate = best “value” estimate available
    valuation = prop.get("valuation") or {}
    arv_estimate = valuation.get("value") or valuation.get("price") or valuation.get("estimate")

    # Market rent estimate
    rent_est = prop.get("rent_estimate") or {}
    market_rent_estimate = (
        rent_est.get("rent")
        or rent_est.get("price")
        or rent_est.get("estimate")
        or rent_est.get("monthlyRent")
    )

    return {
        "resale_comps": resale_comps,
        "arv_estimate": arv_estimate,
        "market_rent_estimate": market_rent_estimate,
        "unified_property": prop,
    }


# ---------------------------------------------------------
# UNIFIED COMPS RESOLVER
# ---------------------------------------------------------
def get_comps_for_property(address, zipcode, rentometer_api_key=None):
    """
    Unified comps resolver for a property.
    """
    unified = get_resale_comps_unified(address)
    airbnb = get_airbnb_comps(address, zipcode)

    rental_comps = []
    if rentometer_api_key:
        rental_comps = get_rental_comps(address, zipcode, rentometer_api_key)

    return {
        "resale_comps": unified.get("resale_comps", []),
        "arv_estimate": unified.get("arv_estimate"),
        "market_rent_estimate": unified.get("market_rent_estimate"),
        "rental_comps": rental_comps,
        "airbnb_comps": airbnb.get("airbnb_comps", []),
        "airbnb_rate_estimate": airbnb.get("airbnb_rate_estimate"),
        "airbnb_occupancy_estimate": airbnb.get("airbnb_occupancy_estimate"),
        "unified_property": unified.get("unified_property"),
    }


# ---------------------------------------------------------
# SAVED PROPERTY COMPS WRAPPER
# ---------------------------------------------------------
def get_saved_property_comps(user_id, property_id=None, saved_property_id=None, rentometer_api_key=None):
    # allow either param name
    if property_id is None and saved_property_id is not None:
        property_id = saved_property_id

    borrower = BorrowerProfile.query.filter_by(user_id=user_id).first()
    if not borrower or not property_id:
        return {}

    try:
        prop_id = int(property_id)
    except (ValueError, TypeError):
        return {}

    prop = SavedProperty.query.filter_by(
        id=prop_id,
        borrower_profile_id=borrower.id
    ).first()

    if not prop:
        return {}

    zipcode = prop.zipcode or ""

    # ✅ Use saved snapshot first (if fresh)
    resolved = None
    if getattr(prop, "resolved_json", None):
        try:
            resolved = json.loads(prop.resolved_json)
        except Exception:
            resolved = None

    # optional: refresh snapshot if older than X days
    refresh_needed = False
    if getattr(prop, "resolved_at", None):
        refresh_needed = (datetime.utcnow() - prop.resolved_at) > timedelta(days=7)

    if not resolved or refresh_needed:
        resolved = resolve_property_unified(prop.address)

        # update snapshot (if columns exist)
        try:
            prop.resolved_json = json.dumps(resolved)
            prop.resolved_at = datetime.utcnow()
            db.session.commit()
        except Exception:
            pass

    comps = get_comps_for_property(
        address=prop.address,
        zipcode=zipcode,
        rentometer_api_key=rentometer_api_key,
    )

    resolved_prop = (resolved.get("property", {}) or {}) if resolved else {}

    comps["property"] = {
        "id": prop.id,
        "address": prop.address,
        "price": prop.price or resolved_prop.get("price"),
        "sqft": prop.sqft or resolved_prop.get("sqft"),
        "zip": zipcode,
    }

    # ✅ FIX: pass zipcode as a keyword argument
    comps["market_snapshot"] = get_market_snapshot(zipcode=zipcode) if zipcode else {}
    comps["resolved"] = resolved

    return comps


# ---------------------------------------------------------
# COMPS FOR EXPORTS (PDF, CSV, ETC.)
# ---------------------------------------------------------
def build_comps(address, zipcode, rentometer_api_key):
    """
    Used for PDF exports.
    """
    unified = get_resale_comps_unified(address)

    return {
        "sales": unified.get("resale_comps", []),
        "rentals": get_rental_comps(address, zipcode, rentometer_api_key) if rentometer_api_key else [],
        "market": get_market_snapshot(zipcode=zipcode) if zipcode else {},
        "arv_estimate": unified.get("arv_estimate"),
        "market_rent_estimate": unified.get("market_rent_estimate"),
    }
