from LoanMVP.services.rentcast_service import (
    RentCastServiceError,
    get_rentcast_market_stats,
    normalize_rentcast_market_stats,
)
from LoanMVP.services.unified_resolver import resolve_property_unified


def _classify_trend(days_on_market):
    if days_on_market is None:
        return None
    if days_on_market <= 30:
        return "Fast-moving"
    if days_on_market <= 60:
        return "Balanced"
    return "Slow-moving"


def get_market_snapshot(address=None, zipcode=None):
    """
    Lightweight snapshot.

    Address given: per-property AVM via the unified resolver (RentCast).
    Zip only: zip-level aggregates via RentCast's /markets endpoint --
    median price/rent, days on market, active listing counts. This is
    what powers "is <zip> a fast-moving rental/flip market" style
    questions without needing a specific address.
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

    if not address:
        if not zipcode:
            return empty

        try:
            raw = get_rentcast_market_stats(zipcode)
        except RentCastServiceError:
            return empty

        stats = normalize_rentcast_market_stats(raw, zipcode)
        dom = stats["median_days_on_market"]

        return {
            **empty,
            "name": stats["zip_code"] or zipcode,
            "median_price": stats["median_sale_price"],
            "median_rent": stats["median_rent"],
            "inventory": stats["active_sale_listings"],
            "dom": dom,
            "trend": _classify_trend(dom),
        }

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
