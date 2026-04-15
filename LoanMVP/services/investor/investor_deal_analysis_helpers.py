from __future__ import annotations

from typing import Any, Dict


def _safe_engine_num(value):
    if value in (None, "", "—"):
        return None
    try:
        return float(str(value).replace("$", "").replace(",", "").strip())
    except Exception:
        return None


def _safe_float(value):
    try:
        if value in (None, "", "None"):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        return float(str(value).replace("$", "").replace(",", "").strip())
    except Exception:
        return None


def _safe_int(value):
    try:
        number = _safe_float(value)
        return int(round(number)) if number is not None else None
    except Exception:
        return None


def _build_flip_analysis(snapshot: dict, scope_budget: dict | None = None) -> dict:
    purchase_price = _safe_float(snapshot.get("purchase_price")) or 0
    arv = _safe_float(snapshot.get("arv")) or 0
    rehab_cost = (
        _safe_float((scope_budget or {}).get("total_cost"))
        or _safe_float(snapshot.get("rehab_cost"))
        or 0
    )

    holding_cost = round((purchase_price + rehab_cost) * 0.01 * 6, 2)
    selling_cost = round(arv * 0.08, 2)
    all_in_cost = purchase_price + rehab_cost + holding_cost + selling_cost
    profit = arv - all_in_cost
    margin_pct = (profit / arv * 100) if arv else 0

    return {
        "label": "Fix & Flip",
        "purchase_price": purchase_price,
        "rehab_cost": rehab_cost,
        "holding_cost": holding_cost,
        "selling_cost": selling_cost,
        "all_in_cost": all_in_cost,
        "exit_value": arv,
        "profit": profit,
        "margin_pct": margin_pct,
        "timeline_months": 6,
    }


def _build_rental_analysis(snapshot: dict, mashvisor: dict | None) -> dict:
    rent = (
        _safe_float((mashvisor or {}).get("traditional_rent"))
        or _safe_float(snapshot.get("estimated_rent"))
        or 0
    )
    cash_flow = _safe_float((mashvisor or {}).get("traditional_cash_flow"))
    cap_rate = _safe_float((mashvisor or {}).get("traditional_cap_rate"))
    coc = _safe_float((mashvisor or {}).get("traditional_coc"))

    return {
        "label": "Long-Term Rental",
        "monthly_rent": rent,
        "annual_rent": rent * 12 if rent else 0,
        "cash_flow": cash_flow,
        "cap_rate": cap_rate,
        "cash_on_cash_return": coc,
        "confidence": (mashvisor or {}).get("confidence"),
    }


def _build_airbnb_analysis(snapshot: dict, mashvisor: dict | None) -> dict:
    revenue = _safe_float((mashvisor or {}).get("airbnb_revenue")) or 0
    occupancy = _safe_float((mashvisor or {}).get("occupancy_rate"))
    adr = _safe_float((mashvisor or {}).get("adr"))
    cash_flow = _safe_float((mashvisor or {}).get("airbnb_cash_flow"))
    cap_rate = _safe_float((mashvisor or {}).get("airbnb_cap_rate"))
    coc = _safe_float((mashvisor or {}).get("airbnb_coc"))

    return {
        "label": "Airbnb / STR",
        "monthly_revenue": revenue,
        "annual_revenue": revenue * 12 if revenue else 0,
        "occupancy_rate": occupancy,
        "adr": adr,
        "cash_flow": cash_flow,
        "cap_rate": cap_rate,
        "cash_on_cash_return": coc,
        "confidence": (mashvisor or {}).get("confidence"),
    }


def _build_brrrr_analysis(snapshot: dict, rental: dict, flip: dict) -> dict:
    arv = _safe_float(snapshot.get("arv")) or 0
    all_in_cost = _safe_float(flip.get("all_in_cost")) or 0
    monthly_rent = _safe_float(rental.get("monthly_rent")) or 0
    cash_flow = _safe_float(rental.get("cash_flow"))

    refi_ltv = 0.75
    refi_value = arv
    cash_out = refi_value * refi_ltv if refi_value else 0
    capital_left_in_deal = max(all_in_cost - cash_out, 0)

    return {
        "label": "BRRRR",
        "refi_value": refi_value,
        "cash_out": cash_out,
        "capital_left_in_deal": capital_left_in_deal,
        "stabilized_rent": monthly_rent,
        "post_refi_cash_flow": cash_flow,
    }


def _recommend_exit_strategy(
    flip: dict,
    rental: dict,
    airbnb: dict,
    brrrr: dict,
) -> dict:
    flip_margin = _safe_float(flip.get("margin_pct")) or 0
    rental_cf = _safe_float(rental.get("cash_flow")) or 0
    airbnb_cf = _safe_float(airbnb.get("cash_flow")) or 0

    if airbnb_cf > rental_cf and airbnb_cf > 0:
        baseline = rental_cf * 1.25 if rental_cf else airbnb_cf
        return {
            "best_strategy": "Airbnb / STR",
            "confidence": "High" if airbnb_cf >= baseline else "Moderate",
            "reason": "Highest projected monthly income and strongest short-term revenue profile.",
        }

    if flip_margin >= 15:
        return {
            "best_strategy": "Fix & Flip",
            "confidence": "High",
            "reason": "Strong projected resale margin with enough room for execution risk.",
        }

    if rental_cf > 0:
        return {
            "best_strategy": "Long-Term Rental",
            "confidence": "Moderate",
            "reason": "Stable rental cash flow with a simpler operating model than short-term rental.",
        }

    return {
        "best_strategy": "BRRRR",
        "confidence": "Moderate",
        "reason": "Best fit when the goal is recycling capital and holding long-term exposure.",
    }


def _build_deal_architect_payload(result: dict, strategy: str = "flip") -> dict:
    address = (result.get("address") or result.get("address_line1") or "").strip()
    city = (result.get("city") or "").strip()
    state = (result.get("state") or "").strip()
    zip_code = (result.get("zip_code") or "").strip()

    beds = _safe_engine_num(result.get("beds"))
    baths = _safe_engine_num(result.get("baths"))
    sqft = _safe_engine_num(result.get("square_feet") or result.get("sqft"))
    lot_sqft = _safe_engine_num(result.get("lot_size_sqft"))
    assessed_value = _safe_engine_num(result.get("assessed_value"))
    tax_amount = _safe_engine_num(result.get("tax_amount"))
    market_value = _safe_engine_num(result.get("market_value") or result.get("display_value"))
    sale_price = _safe_engine_num(result.get("last_sale_price") or result.get("price"))
    monthly_rent = _safe_engine_num(result.get("traditional_rent"))
    property_type = (result.get("property_type") or "single family").strip()

    strategy_label = {
        "flip": "fix and flip candidate",
        "rental": "rental hold candidate",
        "all": "investment property candidate",
    }.get((strategy or "flip").lower(), "investment property candidate")

    description_parts = [
        f"{address}, {city}, {state} {zip_code}".strip(", ").strip(),
        f"{int(beds)} bed" if beds is not None else None,
        f"{baths} bath" if baths is not None else None,
        f"{int(sqft):,} sqft" if sqft else None,
        strategy_label,
    ]

    return {
        "project_name": address or "Deal Finder Property",
        "description": " • ".join([p for p in description_parts if p]),
        "property_type": property_type,
        "lot_size": f"{int(lot_sqft):,} sq ft lot" if lot_sqft else "",
        "zoning": result.get("zoning") or "",
        "asking_price": sale_price,
        "square_feet_target": sqft,
        "city": city,
        "state": state,
        "zip_code": zip_code,
        "arv": market_value,
        "monthly_rent": monthly_rent,
        "local_facts": {
            "bedrooms": beds,
            "bathrooms": baths,
            "year_built": _safe_engine_num(result.get("year_built")),
            "lot_sqft": lot_sqft,
            "assessed_value": assessed_value,
            "annual_tax_amount": tax_amount,
            "latitude": result.get("latitude"),
            "longitude": result.get("longitude"),
            "source": "deal_finder",
        },
    }


def _attach_deal_architect_signals(result: dict, engine_data: dict) -> dict:
    enriched = dict(result)
    meta = engine_data.get("meta") or {}

    enriched.update({
        "deal_score": engine_data.get("deal_score"),
        "opportunity_tier": engine_data.get("opportunity_tier"),
        "deal_finder_signal": meta.get("deal_finder_signal"),
        "primary_strengths": meta.get("primary_strengths") or [],
        "primary_risks": meta.get("primary_risks") or [],
        "dscr_estimate": meta.get("dscr_estimate"),
        "rent_yield": meta.get("rent_yield"),
        "monthly_rent_estimate": meta.get("monthly_rent_estimate"),
        "next_step": engine_data.get("next_step"),
        "engine_value": engine_data.get("estimated_value"),
        "valuation_source_label": meta.get("valuation_source_label"),
        "comp_confidence": meta.get("comp_confidence"),
        "engine_summary": engine_data.get("summary"),
        "engine_meta": meta,
    })
    return enriched


def _build_full_deal_analysis(
    snapshot: dict,
    *,
    scope_budget: dict | None = None,
    mashvisor: dict | None = None,
) -> dict:
    """
    Convenience wrapper to produce the full strategy comparison object.
    Useful for project studio previews and dedicated deal analysis pages.
    """
    flip = _build_flip_analysis(snapshot, scope_budget=scope_budget)
    rental = _build_rental_analysis(snapshot, mashvisor)
    airbnb = _build_airbnb_analysis(snapshot, mashvisor)
    brrrr = _build_brrrr_analysis(snapshot, rental, flip)
    recommendation = _recommend_exit_strategy(
        flip=flip,
        rental=rental,
        airbnb=airbnb,
        brrrr=brrrr,
    )

    return {
        "flip": flip,
        "rental": rental,
        "airbnb": airbnb,
        "brrrr": brrrr,
        "recommendation": recommendation,
        "mashvisor": mashvisor or {},
    }