import os
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

RENTCAST_API_KEY = os.getenv("RENTCAST_API_KEY", "").strip()


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

def _build_flip_strategy_card(result: dict) -> dict:
    price = _safe_float(result.get("price") or result.get("listing_price")) or 0
    market_value = _safe_float(
        result.get("engine_value")
        or result.get("market_value")
        or result.get("display_value")
    ) or 0

    rehab_guess = _safe_float(result.get("estimated_rehab_cost"))
    if rehab_guess is None:
        sqft = _safe_float(result.get("square_feet") or result.get("sqft")) or 0
        strategy_tag = str(result.get("strategy_tag") or "").lower()

        if "heavy" in strategy_tag or "teardown" in strategy_tag:
            rehab_guess = max(85000, sqft * 55 if sqft else 85000)
        else:
            rehab_guess = max(35000, sqft * 28 if sqft else 35000)

    holding_cost = (price + rehab_guess) * 0.06
    selling_cost = market_value * 0.08 if market_value else 0
    all_in_cost = price + rehab_guess + holding_cost + selling_cost
    profit = market_value - all_in_cost if market_value else None
    margin_pct = (profit / market_value * 100) if market_value and profit is not None else None

    return {
        "key": "flip",
        "label": "Fix & Flip",
        "headline_value": profit,
        "headline_label": "Projected Profit",
        "metrics": {
            "purchase_price": price,
            "rehab_cost": rehab_guess,
            "all_in_cost": all_in_cost,
            "exit_value": market_value,
            "margin_pct": margin_pct,
        },
        "summary": (
            f"${profit:,.0f} projected spread"
            if profit is not None else
            "Not enough value data yet"
        ),
    }


def _build_rental_strategy_card(result: dict) -> dict:
    price = _safe_float(result.get("price") or result.get("listing_price")) or 0
    rent = _safe_float(
        result.get("traditional_rent")
        or result.get("monthly_rent_estimate")
    ) or 0

    taxes = (_safe_float(result.get("tax_amount")) or 0) / 12
    insurance = max(price * 0.004 / 12, 100) if price else 150
    maintenance = rent * 0.08 if rent else 0
    vacancy = rent * 0.05 if rent else 0
    management = rent * 0.08 if rent else 0

    expenses = taxes + insurance + maintenance + vacancy + management
    net_cashflow = rent - expenses if rent else None
    annual_noi = (net_cashflow * 12) if net_cashflow is not None else None
    cap_rate = (annual_noi / price * 100) if price and annual_noi is not None else None

    return {
        "key": "rental",
        "label": "Long-Term Rental",
        "headline_value": net_cashflow,
        "headline_label": "Monthly Cash Flow",
        "metrics": {
            "monthly_rent": rent,
            "monthly_expenses": expenses,
            "monthly_cash_flow": net_cashflow,
            "cap_rate": cap_rate,
        },
        "summary": (
            f"${net_cashflow:,.0f}/mo projected cash flow"
            if net_cashflow is not None else
            "Not enough rent data yet"
        ),
    }


def _build_airbnb_strategy_card(result: dict) -> dict:
    price = _safe_float(result.get("price") or result.get("listing_price")) or 0
    monthly_revenue = _safe_float(
        result.get("airbnb_rent")
        or result.get("airbnb_revenue")
    ) or 0

    if not monthly_revenue:
        traditional_rent = _safe_float(result.get("traditional_rent")) or 0
        monthly_revenue = traditional_rent * 1.55 if traditional_rent else 0

    occupancy_rate = _safe_float(result.get("occupancy_rate"))
    if occupancy_rate is None and monthly_revenue:
        occupancy_rate = 62.0

    cleaning = monthly_revenue * 0.10 if monthly_revenue else 0
    platform = monthly_revenue * 0.03 if monthly_revenue else 0
    utilities = max(250, monthly_revenue * 0.05) if monthly_revenue else 250
    taxes = (_safe_float(result.get("tax_amount")) or 0) / 12
    insurance = max(price * 0.005 / 12, 140) if price else 175
    reserve = monthly_revenue * 0.08 if monthly_revenue else 0

    expenses = cleaning + platform + utilities + taxes + insurance + reserve
    net_cashflow = monthly_revenue - expenses if monthly_revenue else None
    annual_noi = (net_cashflow * 12) if net_cashflow is not None else None
    cap_rate = (annual_noi / price * 100) if price and annual_noi is not None else None

    adr = None
    if monthly_revenue and occupancy_rate:
        try:
            adr = monthly_revenue / (30 * (occupancy_rate / 100))
        except Exception:
            adr = None

    return {
        "key": "airbnb",
        "label": "Airbnb / STR",
        "headline_value": net_cashflow,
        "headline_label": "Monthly Cash Flow",
        "metrics": {
            "monthly_revenue": monthly_revenue,
            "occupancy_rate": occupancy_rate,
            "adr": adr,
            "monthly_cash_flow": net_cashflow,
            "cap_rate": cap_rate,
        },
        "summary": (
            f"${monthly_revenue:,.0f}/mo STR revenue potential"
            if monthly_revenue else
            "No STR signal yet"
        ),
    }


def _pick_best_exit_strategy(cards: list[dict]) -> dict:
    best = None
    best_score = None

    for card in cards:
        key = card.get("key")
        metrics = card.get("metrics") or {}

        if key == "flip":
            score = _safe_float(metrics.get("margin_pct")) or -999
        else:
            score = _safe_float(metrics.get("monthly_cash_flow")) or -999

        if best is None or score > best_score:
            best = card
            best_score = score

    if not best:
        return {
            "label": "Review",
            "reason": "Not enough data to confidently rank exit paths yet.",
        }

    reason_map = {
        "flip": "Strongest projected resale spread.",
        "rental": "Best stable long-term income profile.",
        "airbnb": "Strongest short-term income potential.",
    }

    return {
        "label": best.get("label"),
        "reason": reason_map.get(best.get("key"), "Best current signal."),
    }


def _attach_exit_strategy_cards(result: dict) -> dict:
    flip_card = _build_flip_strategy_card(result)
    rental_card = _build_rental_strategy_card(result)
    airbnb_card = _build_airbnb_strategy_card(result)

    cards = [flip_card, rental_card, airbnb_card]
    best_exit = _pick_best_exit_strategy(cards)

    result["exit_strategy_cards"] = cards
    result["best_exit_strategy"] = best_exit.get("label")
    result["best_exit_reason"] = best_exit.get("reason")

    # Keep recommended_strategy aligned if it is weak / empty
    if not result.get("recommended_strategy") or result.get("recommended_strategy") == "Hold / Review":
        result["recommended_strategy"] = best_exit.get("label")

    return result
