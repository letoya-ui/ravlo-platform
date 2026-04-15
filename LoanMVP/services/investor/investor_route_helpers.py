from __future__ import annotations

import json
import math
import random
from typing import Dict, Any, List, Optional


# -------------------------------------------------------------------
# BASIC SAFETY / NORMALIZATION
# -------------------------------------------------------------------

def safe_float(x, default=0.0):
    try:
        if x is None:
            return default
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).replace("$", "").replace(",", "").strip()
        return float(s) if s else default
    except Exception:
        return default


def safe_int(x, default=0):
    try:
        return int(round(safe_float(x, default)))
    except Exception:
        return default


def safe_str(x, default=""):
    try:
        if x is None:
            return default
        s = str(x).strip()
        return s if s else default
    except Exception:
        return default


def to_float(value, default=0.0):
    try:
        if value in (None, "", "None"):
            return float(default)
        if isinstance(value, str):
            value = value.replace("$", "").replace(",", "").strip()
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_first_related(items, default=None):
    try:
        return items[0] if items else default
    except Exception:
        return default


def _set_if_attr(obj, attr_name, value):
    if hasattr(obj, attr_name):
        setattr(obj, attr_name, value)


# -------------------------------------------------------------------
# ASSET TYPE + DEAL FINDER HELPERS
# -------------------------------------------------------------------

def _normalize_asset_type(asset_type: str | None) -> str:
    value = safe_str(asset_type, "any").lower()

    mapping = {
        "any": "any",
        "all": "any",
        "single_family": "single_family",
        "single family": "single_family",
        "sfr": "single_family",
        "multi_family": "multi_family",
        "multi family": "multi_family",
        "multifamily": "multi_family",
        "duplex": "multi_family",
        "triplex": "multi_family",
        "quadplex": "multi_family",
        "condo": "condo",
        "townhome": "townhome",
        "townhouse": "townhome",
        "land": "land",
        "lot": "land",
        "vacant_land": "land",
        "vacant land": "land",
        "manufactured": "manufactured",
        "mobile_home": "manufactured",
        "mobile home": "manufactured",
        "commercial": "commercial",
    }

    return mapping.get(value, value or "any")


def _asset_type_label(asset_type: str | None) -> str:
    value = _normalize_asset_type(asset_type)

    labels = {
        "any": "All Property Types",
        "single_family": "Single Family",
        "multi_family": "Multi Family",
        "condo": "Condo",
        "townhome": "Townhome",
        "land": "Land",
        "manufactured": "Manufactured",
        "commercial": "Commercial",
    }

    return labels.get(value, value.replace("_", " ").title())


def _property_matches_asset_type(item: Dict[str, Any], asset_type: str | None) -> bool:
    normalized_type = _normalize_asset_type(asset_type)
    if normalized_type == "any":
        return True

    prop_type = safe_str(
        item.get("property_type")
        or item.get("homeType")
        or item.get("property_sub_type")
        or item.get("prop_type")
        or "",
        "",
    ).lower()

    if normalized_type == "single_family":
        return any(x in prop_type for x in ["single", "sfr", "single family", "single-family"])
    if normalized_type == "multi_family":
        return any(x in prop_type for x in ["multi", "duplex", "triplex", "quad", "apartment"])
    if normalized_type == "condo":
        return "condo" in prop_type
    if normalized_type == "townhome":
        return "town" in prop_type
    if normalized_type == "land":
        return any(x in prop_type for x in ["land", "lot", "vacant", "acre", "parcel"])
    if normalized_type == "manufactured":
        return any(x in prop_type for x in ["manufactured", "mobile"])
    if normalized_type == "commercial":
        return "commercial" in prop_type

    return True


def _annotate_deal_finder_opportunity(result: Dict[str, Any], strategy: str = "flip") -> Dict[str, Any]:
    result = dict(result or {})
    best_exit = result.get("best_exit_strategy") or strategy or "flip"

    score = safe_float(result.get("deal_score"), 50)
    result["deal_score"] = score

    if score >= 72:
        result["opportunity_tier"] = result.get("opportunity_tier") or "strong"
        result["deal_finder_signal"] = result.get("deal_finder_signal") or "advance_to_lender_package"
    elif score >= 48:
        result["opportunity_tier"] = result.get("opportunity_tier") or "moderate"
        result["deal_finder_signal"] = result.get("deal_finder_signal") or "validate_zoning_and_pricing"
    else:
        result["opportunity_tier"] = result.get("opportunity_tier") or "risk"
        result["deal_finder_signal"] = result.get("deal_finder_signal") or "retrade_or_pass"

    if best_exit == "rental":
        result["strategy_tag"] = result.get("strategy_tag") or "Hold Candidate"
        result["recommended_strategy"] = result.get("recommended_strategy") or "rental"
        result["estimated_best_use"] = result.get("estimated_best_use") or "Long-term rental hold"
    elif best_exit == "airbnb":
        result["strategy_tag"] = result.get("strategy_tag") or "STR Candidate"
        result["recommended_strategy"] = result.get("recommended_strategy") or "airbnb"
        result["estimated_best_use"] = result.get("estimated_best_use") or "Short-term rental operation"
    elif best_exit == "land":
        result["strategy_tag"] = result.get("strategy_tag") or "Land Optionality"
        result["recommended_strategy"] = result.get("recommended_strategy") or "land"
        result["estimated_best_use"] = result.get("estimated_best_use") or "Land bank or build strategy"
    else:
        result["strategy_tag"] = result.get("strategy_tag") or "Flip Candidate"
        result["recommended_strategy"] = result.get("recommended_strategy") or "flip"
        result["estimated_best_use"] = result.get("estimated_best_use") or "Fix and flip reposition"

    result["next_step"] = result.get("next_step") or (
        "Move this into Project Studio and underwrite the plan."
        if score >= 72
        else "Validate comps, scope, and pricing before planning."
    )

    result["primary_strengths"] = result.get("primary_strengths") or result.get("why_it_made_list") or []
    result["primary_risks"] = result.get("primary_risks") or result.get("risk_notes") or []

    return result


# -------------------------------------------------------------------
# COMPS + WORKSPACE NORMALIZATION
# -------------------------------------------------------------------

def normalize_workspace_comps(raw_comps):
    normalized = []

    for comp in raw_comps or []:
        if not isinstance(comp, dict):
            continue

        normalized.append({
            "address": comp.get("address") or comp.get("formatted_address"),
            "price": to_float(comp.get("price") or comp.get("sale_price") or comp.get("list_price")),
            "sqft": to_float(comp.get("sqft") or comp.get("square_feet")),
            "beds": to_float(comp.get("beds") or comp.get("bedrooms")),
            "baths": to_float(comp.get("baths") or comp.get("bathrooms")),
            "distance_miles": to_float(comp.get("distance_miles") or comp.get("distance")),
            "months_ago": to_float(comp.get("months_ago") or comp.get("sold_months_ago")),
            "source": comp.get("source"),
        })

    return normalized


# -------------------------------------------------------------------
# STRATEGY / BUDGET CALCS
# -------------------------------------------------------------------

def _get_prop_sqft(comps: Dict[str, Any]) -> int:
    return safe_int((comps.get("property") or {}).get("sqft"), 0)


def _get_prop_lot_sqft(comps: Dict[str, Any]) -> float:
    prop = comps.get("property") or {}
    return safe_float(
        prop.get("lot_sqft")
        or prop.get("lot_size_sqft")
        or prop.get("lotSize")
        or 0
    )


def _get_property_type(comps: Dict[str, Any], form=None) -> str:
    if form:
        form_type = safe_str(form.get("property_type"))
        if form_type:
            return form_type.lower()

    prop = comps.get("property") or {}
    return safe_str(
        prop.get("property_type")
        or prop.get("homeType")
        or prop.get("property_sub_type")
        or "",
        "",
    ).lower()


def _get_purchase_price(form, comps: Dict[str, Any]) -> float:
    p_form = safe_float(form.get("purchase_price")) if form else 0.0
    if p_form > 0:
        return p_form
    p_saved = safe_float((comps.get("property") or {}).get("price"))
    return p_saved if p_saved > 0 else 0.0


def _get_arv(comps: Dict[str, Any], form=None) -> float:
    arv_form = safe_float(form.get("arv")) if form else 0.0
    if arv_form > 0:
        return arv_form

    arv = safe_float(comps.get("arv_estimate"))
    if arv > 0:
        return arv

    resale = comps.get("resale_comps") or []
    prices = [safe_float(c.get("price")) for c in resale if safe_float(c.get("price")) > 0]
    if prices:
        prices.sort()
        return prices[len(prices) // 2]
    return 0.0


def _get_market_rent(comps: Dict[str, Any], form=None) -> float:
    rent_form = safe_float(form.get("monthly_rent")) if form else 0.0
    if rent_form > 0:
        return rent_form

    rent = safe_float(comps.get("market_rent_estimate"))
    if rent > 0:
        return rent

    rentals = comps.get("rental_comps") or []
    rents = [safe_float(r.get("rent")) for r in rentals if safe_float(r.get("rent")) > 0]
    if rents:
        rents.sort()
        return rents[len(rents) // 2]
    return 0.0


def classify_property_type(form, comps: Dict[str, Any]) -> str:
    prop_type = _get_property_type(comps, form=form)
    sqft = _get_prop_sqft(comps)
    lot_sqft = _get_prop_lot_sqft(comps)

    looks_like_land = any(
        key in prop_type
        for key in ["land", "lot", "vacant", "acre", "parcel"]
    )

    has_structure = sqft > 0

    if looks_like_land or (lot_sqft > 0 and not has_structure):
        return "land"

    rehab_total = safe_float(form.get("rehab_total")) if form else safe_float(comps.get("rehab_total"))
    purchase_price = _get_purchase_price(form, comps)
    rehab_ratio = (rehab_total / purchase_price) if purchase_price > 0 else 0

    if rehab_ratio >= 0.15:
        return "fixer_upper"

    rent = _get_market_rent(comps, form=form)
    if rent > 0:
        return "rental_candidate"

    return "general_opportunity"


def calculate_flip_budget(form, comps: Dict[str, Any]) -> Dict[str, Any]:
    purchase_price = _get_purchase_price(form, comps)
    arv = _get_arv(comps, form=form)

    rehab_total = safe_float(form.get("rehab_total")) if form else safe_float(comps.get("rehab_total"))
    if rehab_total <= 0:
        rehab_total = safe_float((comps.get("rehab_summary") or {}).get("total"))

    holding_months = safe_int(form.get("holding_months"), 6) if form else 6
    monthly_holding = safe_float(form.get("monthly_holding_cost"), 0.0) if form else 0.0
    holding_cost = monthly_holding * holding_months

    selling_cost_rate = safe_float(form.get("selling_cost_rate"), 0.08) if form else 0.08
    selling_costs = arv * selling_cost_rate

    down_payment_rate = safe_float(form.get("down_payment_rate"), 0.2) if form else 0.2
    down_payment = purchase_price * down_payment_rate
    loan_amount = max(purchase_price - down_payment, 0.0)

    interest_rate = safe_float(form.get("interest_rate"), 0.10) if form else 0.10
    points_rate = safe_float(form.get("points_rate"), 0.02) if form else 0.02
    points_cost = loan_amount * points_rate

    interest_cost = loan_amount * (interest_rate / 12.0) * holding_months
    total_in = purchase_price + rehab_total + holding_cost + selling_costs + points_cost + interest_cost
    profit = arv - total_in
    roi = (profit / (down_payment + rehab_total + points_cost)) if (down_payment + rehab_total + points_cost) > 0 else 0.0
    margin_pct = (profit / arv) if arv > 0 else 0.0

    return {
        "strategy": "flip",
        "purchase_price": purchase_price,
        "arv": arv,
        "rehab_total": rehab_total,
        "holding_months": holding_months,
        "holding_cost": holding_cost,
        "selling_cost_rate": selling_cost_rate,
        "selling_costs": selling_costs,
        "loan_amount": loan_amount,
        "down_payment": down_payment,
        "interest_rate": interest_rate,
        "interest_cost": interest_cost,
        "points_rate": points_rate,
        "points_cost": points_cost,
        "total_investment": total_in,
        "profit": profit,
        "roi": roi,
        "margin_pct": margin_pct,
        "deal_score_base": roi,
        "recommended_strategy": "Flip",
        "ok": True,
    }


def calculate_rental_budget(form, comps: Dict[str, Any]) -> Dict[str, Any]:
    purchase_price = _get_purchase_price(form, comps)
    rehab_total = safe_float(form.get("rehab_total")) if form else safe_float(comps.get("rehab_total"))
    if rehab_total <= 0:
        rehab_total = safe_float((comps.get("rehab_summary") or {}).get("total"))

    monthly_rent = _get_market_rent(comps, form=form)

    taxes = safe_float(form.get("monthly_taxes"), 0.0) if form else 0.0
    insurance = safe_float(form.get("monthly_insurance"), 0.0) if form else 0.0
    hoa = safe_float(form.get("monthly_hoa"), 0.0) if form else 0.0
    maintenance = safe_float(form.get("monthly_maintenance"), monthly_rent * 0.05) if form else monthly_rent * 0.05
    vacancy = safe_float(form.get("vacancy_rate"), 0.05) if form else 0.05
    management = safe_float(form.get("management_rate"), 0.08) if form else 0.08

    effective_rent = monthly_rent * (1 - vacancy)
    mgmt_cost = effective_rent * management
    total_expenses = taxes + insurance + hoa + maintenance + mgmt_cost

    down_payment_rate = safe_float(form.get("down_payment_rate"), 0.25) if form else 0.25
    down_payment = purchase_price * down_payment_rate
    loan_amount = max(purchase_price - down_payment, 0.0)
    rate = safe_float(form.get("interest_rate"), 0.075) if form else 0.075
    term_years = safe_int(form.get("term_years"), 30) if form else 30

    r = rate / 12.0
    n = term_years * 12
    if loan_amount > 0 and r > 0:
        payment = loan_amount * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
    elif loan_amount > 0 and n > 0:
        payment = loan_amount / n
    else:
        payment = 0.0

    net_cashflow = effective_rent - total_expenses - payment
    annual_noi = (effective_rent - total_expenses) * 12
    cap_rate = (annual_noi / purchase_price) if purchase_price > 0 else 0.0
    dscr = ((effective_rent - total_expenses) / payment) if payment > 0 else 0.0

    return {
        "strategy": "rental",
        "purchase_price": purchase_price,
        "rehab_total": rehab_total,
        "monthly_rent": monthly_rent,
        "rent_est": monthly_rent,
        "effective_rent": effective_rent,
        "monthly_expenses": total_expenses,
        "mortgage_payment": payment,
        "net_cashflow": net_cashflow,
        "net_cashflow_mo": net_cashflow,
        "annual_noi": annual_noi,
        "cap_rate": cap_rate,
        "dscr": dscr,
        "loan_amount": loan_amount,
        "down_payment": down_payment,
        "recommended_strategy": "Rental",
        "ok": True,
    }


def calculate_airbnb_budget(form, comps: Dict[str, Any]) -> Dict[str, Any]:
    purchase_price = _get_purchase_price(form, comps)
    rehab_total = safe_float(form.get("rehab_total")) if form else safe_float(comps.get("rehab_total"))
    if rehab_total <= 0:
        rehab_total = safe_float((comps.get("rehab_summary") or {}).get("total"))

    nightly_rate = safe_float(form.get("nightly_rate"), 0.0) if form else 0.0
    occupancy = safe_float(form.get("occupancy_rate"), 0.55) if form else 0.55

    if occupancy > 1:
        occupancy = occupancy / 100.0

    if nightly_rate <= 0:
        ltr = _get_market_rent(comps, form=form)
        nightly_rate = max((ltr * 1.6) / 30.0, 80.0)

    nights_booked = 30.0 * occupancy
    gross = nightly_rate * nights_booked

    platform_fee = safe_float(form.get("platform_fee_rate"), 0.03) if form else 0.03
    cleaning_per_stay = safe_float(form.get("cleaning_fee_cost"), 120.0) if form else 120.0
    avg_stay_nights = safe_float(form.get("avg_stay_nights"), 3.0) if form else 3.0
    stays = max(nights_booked / max(avg_stay_nights, 1.0), 1.0)

    utilities = safe_float(form.get("monthly_utilities"), 350.0) if form else 350.0
    supplies = safe_float(form.get("monthly_supplies"), 120.0) if form else 120.0
    maintenance = safe_float(form.get("monthly_maintenance"), gross * 0.05) if form else gross * 0.05
    management = safe_float(form.get("management_rate"), 0.15) if form else 0.15

    fees = gross * platform_fee
    cleaning = cleaning_per_stay * stays
    mgmt_cost = gross * management
    total_expenses = fees + cleaning + utilities + supplies + maintenance + mgmt_cost
    net = gross - total_expenses

    return {
        "strategy": "airbnb",
        "purchase_price": purchase_price,
        "rehab_total": rehab_total,
        "nightly_rate": nightly_rate,
        "occupancy_rate": occupancy,
        "gross_monthly": gross,
        "monthly_expenses": total_expenses,
        "net_monthly": net,
        "recommended_strategy": "Airbnb",
        "ok": True,
    }


def calculate_land_budget(form, comps: Dict[str, Any]) -> Dict[str, Any]:
    purchase_price = _get_purchase_price(form, comps)
    lot_sqft = _get_prop_lot_sqft(comps)
    entitlement_cost = safe_float(form.get("entitlement_cost"), 0.0) if form else 0.0
    carry_cost = safe_float(form.get("land_carry_cost"), 0.0) if form else 0.0
    projected_exit = safe_float(form.get("land_exit_value"), 0.0) if form else 0.0

    total_basis = purchase_price + entitlement_cost + carry_cost
    projected_upside = projected_exit - total_basis if projected_exit > 0 else 0.0
    score = 65 if lot_sqft > 0 else 25

    return {
        "strategy": "land",
        "purchase_price": purchase_price,
        "lot_sqft": lot_sqft,
        "entitlement_cost": entitlement_cost,
        "carry_cost": carry_cost,
        "land_value": purchase_price,
        "projected_exit_value": projected_exit,
        "projected_upside": projected_upside,
        "total_investment": total_basis,
        "score": score,
        "recommended_strategy": "Land / Build",
        "ok": True,
    }


def recommend_strategy(comparison: Dict[str, Dict[str, Any]], property_classification: str = "") -> Dict[str, Any]:
    flip = comparison.get("flip") or {}
    rental = comparison.get("rental") or {}
    airbnb = comparison.get("airbnb") or {}
    land = comparison.get("land") or {}

    score = {}
    score["flip"] = safe_float(flip.get("profit")) + (safe_float(flip.get("roi")) * 1000)

    dscr = safe_float(rental.get("dscr"))
    score["rental"] = (
        safe_float(rental.get("net_cashflow")) * 12
        + (5000 if dscr >= 1.15 else 0)
        + (safe_float(rental.get("cap_rate")) * 1000)
    )

    occ = safe_float(airbnb.get("occupancy_rate"), 0.55)
    score["airbnb"] = safe_float(airbnb.get("net_monthly")) * 12 - (3000 if occ < 0.45 else 0)

    score["land"] = safe_float(land.get("projected_upside")) + (safe_float(land.get("score")) * 100)

    if property_classification == "land":
        score["land"] += 5000
        score["flip"] -= 5000
        score["rental"] -= 5000
        score["airbnb"] -= 5000

    best = max(score, key=score.get) if score else "rental"

    return {
        "best": best,
        "scores": score,
        "notes": {
            "flip": "Higher spread and resale margin wins. Watch holding and disposition costs.",
            "rental": "Higher annual cash flow with DSCR support wins.",
            "airbnb": "High cash flow wins, but occupancy makes this more volatile.",
            "land": "Optionality, lot size, and projected parcel upside drive the score.",
        }
    }


def build_exit_strategy_cards(comparison: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    flip = comparison.get("flip") or {}
    rental = comparison.get("rental") or {}
    airbnb = comparison.get("airbnb") or {}
    land = comparison.get("land") or {}

    return [
        {
            "key": "flip",
            "label": "Flip",
            "headline_label": "Projected Profit",
            "headline_value": safe_float(flip.get("profit")),
            "score": safe_float(flip.get("roi")) * 100,
            "summary": "Resale-driven value-add path.",
            "metrics": flip,
        },
        {
            "key": "rental",
            "label": "Rental",
            "headline_label": "Monthly Cash Flow",
            "headline_value": safe_float(rental.get("net_cashflow")),
            "score": safe_float(rental.get("cap_rate")) * 100,
            "summary": "Long-term hold and income path.",
            "metrics": rental,
        },
        {
            "key": "airbnb",
            "label": "Airbnb",
            "headline_label": "Net Monthly",
            "headline_value": safe_float(airbnb.get("net_monthly")),
            "score": safe_float(airbnb.get("occupancy_rate")) * 100,
            "summary": "Short-term rental revenue path.",
            "metrics": airbnb,
        },
        {
            "key": "land",
            "label": "Land / Build",
            "headline_label": "Projected Upside",
            "headline_value": safe_float(land.get("projected_upside")),
            "score": safe_float(land.get("score")),
            "summary": "Land optionality or build-out path.",
            "metrics": land,
        },
    ]


def build_ai_recommendation(best: str, property_classification: str, comparison: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    why_map = {
        "flip": [
            "Projected resale spread appears stronger than hold alternatives.",
            "The deal looks more like a value-add execution than a stabilized hold.",
            "ARV support improves the flip thesis.",
        ],
        "rental": [
            "Long-term rent support appears stable.",
            "Cash flow and cap rate make the hold path more durable.",
            "This opportunity looks more suited to recurring income than quick resale.",
        ],
        "airbnb": [
            "Short-term revenue potential appears stronger than long-term rent.",
            "The revenue profile may justify deeper hospitality underwriting.",
            "Occupancy and nightly assumptions create a higher-upside path.",
        ],
        "land": [
            "This asset reads more like land optionality than a standard residential hold.",
            "Site value and lot profile matter more than current in-place operations.",
            "A build or parcel strategy appears stronger than traditional rental underwriting.",
        ],
    }

    watch_map = {
        "flip": [
            "Verify rehab scope and resale timeline.",
            "Stress-test exit value using conservative comps.",
        ],
        "rental": [
            "Confirm taxes, insurance, and maintenance assumptions.",
            "Validate current rent support with fresh comps.",
        ],
        "airbnb": [
            "Validate local STR rules and seasonality.",
            "Pressure-test occupancy and nightly rate assumptions.",
        ],
        "land": [
            "Verify zoning and entitlement path.",
            "Confirm utility access, frontage, and resale demand.",
        ],
    }

    return {
        "confidence": "high" if best in ("rental", "flip") else "moderate",
        "property_classification": property_classification,
        "why": why_map.get(best, []),
        "watch_items": watch_map.get(best, []),
    }


def generate_ai_deal_summary(metrics):
    roi = metrics.get("roi") or 0
    profit = metrics.get("profit") or 0
    rent = metrics.get("rent_est") or metrics.get("monthly_rent") or 0
    cashflow = metrics.get("net_cashflow_mo") or metrics.get("net_cashflow") or 0
    airbnb_net = metrics.get("net_monthly") or 0
    strategy = metrics.get("strategy") or "deal"

    if strategy == "flip":
        recommendation = "Flip" if roi > 0.20 else "Review Carefully"
    elif strategy == "rental":
        recommendation = "Rental" if cashflow > 250 else "Review Carefully"
    elif strategy == "airbnb":
        recommendation = "Airbnb" if airbnb_net > 500 else "Review Carefully"
    elif strategy == "land":
        recommendation = "Land / Build" if profit > 0 else "Review Carefully"
    else:
        recommendation = "Review Carefully"

    return f"""
This property shows potential under the {strategy.title()} strategy.

Estimated ROI: {round(roi * 100)}%
Projected flip profit: ${profit:,.0f}
Estimated monthly rent: ${rent:,.0f}
Estimated monthly cash flow: ${cashflow:,.0f}
Estimated Airbnb net monthly: ${airbnb_net:,.0f}

Recommended strategy: {recommendation}.
""".strip()


# -------------------------------------------------------------------
# WORKSPACE-SPECIFIC ANALYSIS
# -------------------------------------------------------------------

def build_workspace_exit_comparison(
    selected_prop,
    deal,
    workspace_analysis,
    comps,
    rehab_analysis,
):
    purchase_price = to_float(
        (deal.purchase_price if deal else None)
        or workspace_analysis.get("purchase_price")
        or getattr(selected_prop, "price", 0)
    )

    rehab_cost = to_float(
        (deal.rehab_cost if deal else None)
        or rehab_analysis.get("total")
        or workspace_analysis.get("rehab_cost")
    )

    arv = to_float(
        (deal.arv if deal else None)
        or workspace_analysis.get("arv")
        or comps.get("arv_estimate")
    )

    estimated_rent = to_float(
        (deal.estimated_rent if deal else None)
        or workspace_analysis.get("estimated_rent")
        or workspace_analysis.get("monthly_rent")
    )

    total_basis = purchase_price + rehab_cost
    sell_cost_pct = 0.08
    sell_cost = arv * sell_cost_pct if arv else 0
    flip_profit = (arv - total_basis - sell_cost) if arv else 0
    flip_roi = (flip_profit / total_basis) if total_basis > 0 else 0

    taxes_monthly = to_float(workspace_analysis.get("monthly_taxes"))
    insurance_monthly = to_float(workspace_analysis.get("monthly_insurance"))
    maintenance_monthly = to_float(workspace_analysis.get("monthly_maintenance"))
    vacancy_monthly = estimated_rent * 0.05 if estimated_rent else 0

    rental_expenses = taxes_monthly + insurance_monthly + maintenance_monthly + vacancy_monthly
    rental_cashflow = estimated_rent - rental_expenses
    annual_noi = rental_cashflow * 12
    rental_cap_rate = (annual_noi / total_basis) if total_basis > 0 else 0
    dscr = ((estimated_rent * 12) / max((total_basis * 0.09), 1)) if total_basis > 0 else 0

    airbnb_nightly = to_float(workspace_analysis.get("airbnb_nightly_rate"))
    airbnb_occupancy = to_float(workspace_analysis.get("airbnb_occupancy_rate"))
    if airbnb_occupancy > 1:
        airbnb_occupancy = airbnb_occupancy / 100.0

    airbnb_gross = airbnb_nightly * 30 * airbnb_occupancy if airbnb_nightly and airbnb_occupancy else 0
    airbnb_net = airbnb_gross * 0.62 if airbnb_gross else 0

    lot_size = to_float(
        workspace_analysis.get("lot_size_sqft")
        or getattr(selected_prop, "lot_size_sqft", 0)
    )
    land_value = to_float(workspace_analysis.get("land_value"))
    land_upside = to_float(workspace_analysis.get("land_projected_upside"))

    return {
        "flip": {
            "profit": flip_profit,
            "total_investment": total_basis,
            "arv": arv,
            "roi": flip_roi,
        },
        "rental": {
            "monthly_rent": estimated_rent,
            "net_cashflow": rental_cashflow,
            "annual_noi": annual_noi,
            "cap_rate": rental_cap_rate,
            "dscr": dscr,
        },
        "airbnb": {
            "nightly_rate": airbnb_nightly,
            "occupancy_rate": airbnb_occupancy,
            "gross_monthly": airbnb_gross,
            "net_monthly": airbnb_net,
        },
        "land": {
            "land_value": land_value or lot_size,
            "projected_upside": land_upside,
            "score": 65 if lot_size and not getattr(selected_prop, "sqft", None) else 20,
        },
    }


def build_exit_strategy_analysis(
    selected_prop,
    deal,
    workspace_analysis,
    comps,
    comparison,
):
    property_type = (
        workspace_analysis.get("property_type")
        or getattr(selected_prop, "property_type", "")
        or ""
    ).lower()

    sqft = to_float(
        workspace_analysis.get("square_feet")
        or getattr(selected_prop, "sqft", 0)
        or getattr(selected_prop, "square_feet", 0)
    )
    beds = to_float(workspace_analysis.get("beds") or getattr(selected_prop, "beds", 0))
    baths = to_float(workspace_analysis.get("baths") or getattr(selected_prop, "baths", 0))
    lot_size = to_float(workspace_analysis.get("lot_size_sqft") or getattr(selected_prop, "lot_size_sqft", 0))

    has_structure = bool(sqft or beds or baths)
    looks_like_land = any(x in property_type for x in ["land", "lot", "vacant", "acre"]) or (lot_size and not has_structure)

    flip = comparison.get("flip", {})
    rental = comparison.get("rental", {})
    airbnb = comparison.get("airbnb", {})
    land = comparison.get("land", {})

    flip_profit = to_float(flip.get("profit"))
    flip_roi = to_float(flip.get("roi")) * 100
    rental_cap = to_float(rental.get("cap_rate")) * 100
    rental_cashflow = to_float(rental.get("net_cashflow"))
    airbnb_net = to_float(airbnb.get("net_monthly"))
    airbnb_occ = to_float(airbnb.get("occupancy_rate")) * 100
    land_score = to_float(land.get("score"))

    if looks_like_land:
        property_classification = "land"
    elif flip_profit > 0 and flip_roi >= 12:
        property_classification = "fixer_upper"
    elif airbnb_net > rental_cashflow and airbnb_occ >= 45:
        property_classification = "str_candidate"
    elif rental_cashflow > 0 or rental_cap >= 5:
        property_classification = "rental_candidate"
    else:
        property_classification = "general_opportunity"

    purchase_price_for_airbnb = max(
        to_float((deal.purchase_price if deal else None) or workspace_analysis.get("purchase_price") or getattr(selected_prop, "price", 1)),
        1,
    )

    strategy_scores = {
        "flip": max(flip_roi, 0) + (10 if flip_profit > 0 else 0),
        "rental": max(rental_cap, 0) + (8 if rental_cashflow > 0 else 0),
        "airbnb": max((airbnb_net * 12) / purchase_price_for_airbnb * 100, 0),
        "land": land_score if property_classification == "land" else max(land_score - 25, 0),
    }

    best_exit = max(strategy_scores, key=strategy_scores.get)

    reasons = {
        "flip": "Flip shows the best spread between basis and exit value.",
        "rental": "Rental shows the strongest risk-adjusted hold profile with recurring income support.",
        "airbnb": "Short-term rental shows the highest revenue upside based on current hospitality assumptions.",
        "land": "This opportunity looks better as land optionality or a build-oriented play than a standard residential hold.",
    }

    why = {
        "flip": [
            "Projected flip margin is competitive.",
            "ARV appears to support a resale thesis.",
            "This looks more like a value-add than a stabilized hold.",
        ],
        "rental": [
            "Rent support is present.",
            "The hold profile looks more stable than the resale spread.",
            "This asset appears to fit a long-term residential strategy.",
        ],
        "airbnb": [
            "Short-term revenue appears stronger than long-term rent.",
            "Hospitality-style upside may justify deeper underwriting.",
            "The property may support a higher-revenue furnished strategy.",
        ],
        "land": [
            "The asset reads more like land or optionality than a conventional income property.",
            "Structure data is limited relative to site size or parcel value.",
            "A build or hold thesis may be stronger than a standard buy-and-hold.",
        ],
    }

    watch_items = {
        "flip": [
            "Verify final rehab scope and sale costs.",
            "Stress-test ARV against conservative comps.",
        ],
        "rental": [
            "Confirm taxes, insurance, and maintenance assumptions.",
            "Verify long-term rent support with current comps.",
        ],
        "airbnb": [
            "Validate STR regulation and seasonality.",
            "Confirm occupancy and nightly rate assumptions.",
        ],
        "land": [
            "Verify zoning and entitlement path.",
            "Validate utility access, frontage, and resale demand.",
        ],
    }

    cards = [
        {
            "key": "flip",
            "label": "Flip",
            "headline_label": "Projected Profit",
            "headline_value": flip_profit,
            "score": strategy_scores["flip"],
            "summary": reasons["flip"],
            "metrics": flip,
        },
        {
            "key": "rental",
            "label": "Rental",
            "headline_label": "Monthly Cash Flow",
            "headline_value": rental_cashflow,
            "score": strategy_scores["rental"],
            "summary": reasons["rental"],
            "metrics": rental,
        },
        {
            "key": "airbnb",
            "label": "Airbnb",
            "headline_label": "Net Monthly",
            "headline_value": airbnb_net,
            "score": strategy_scores["airbnb"],
            "summary": reasons["airbnb"],
            "metrics": airbnb,
        },
        {
            "key": "land",
            "label": "Land / Build",
            "headline_label": "Optionality Score",
            "headline_value": land_score,
            "score": strategy_scores["land"],
            "summary": reasons["land"],
            "metrics": land,
        },
    ]

    return {
        "property_classification": property_classification,
        "exit_strategy_cards": cards,
        "best_exit_strategy": best_exit,
        "best_exit_reason": reasons[best_exit],
        "ai_recommendation": {
            "confidence": "high" if strategy_scores[best_exit] >= 12 else "moderate",
            "why": why[best_exit],
            "watch_items": watch_items[best_exit],
        },
    }


# -------------------------------------------------------------------
# BUDGET / LOAN SIZING
# -------------------------------------------------------------------

def _build_budget_seed_from_results(results_json: Dict[str, Any]) -> Dict[str, Any]:
    results = results_json or {}
    workspace = results.get("workspace_analysis", {}) or {}
    comp_analysis = results.get("comp_analysis", {}) or {}
    rehab_analysis = results.get("rehab_analysis", {}) or {}
    strategy_analysis = results.get("strategy_analysis", {}) or {}
    exit_analysis = results.get("exit_strategy_analysis", {}) or {}

    purchase_price = to_float(
        workspace.get("purchase_price")
        or results.get("purchase_price")
        or comp_analysis.get("purchase_price")
    )
    rehab_cost = to_float(
        rehab_analysis.get("total")
        or workspace.get("rehab_cost")
        or results.get("rehab_cost")
    )
    arv = to_float(
        workspace.get("arv")
        or comp_analysis.get("arv_estimate")
        or results.get("arv")
    )
    estimated_rent = to_float(
        workspace.get("estimated_rent")
        or workspace.get("monthly_rent")
        or results.get("estimated_rent")
    )

    total_project_cost = purchase_price + rehab_cost
    contingency = rehab_cost * 0.1 if rehab_cost > 0 else 0.0

    return {
        "purchase_price": purchase_price,
        "rehab_cost": rehab_cost,
        "contingency": contingency,
        "total_project_cost": total_project_cost + contingency,
        "arv": arv,
        "estimated_rent": estimated_rent,
        "recommended_strategy": (
            exit_analysis.get("best_exit_strategy")
            or strategy_analysis.get("recommended_strategy")
            or workspace.get("selected_strategy")
            or "flip"
        ),
        "property_classification": exit_analysis.get("property_classification"),
        "budget_line_items": rehab_analysis.get("line_items", {}),
    }


def _build_loan_sizing_from_budget(seed: Dict[str, Any]) -> Dict[str, Any]:
    seed = seed or {}

    purchase_price = to_float(seed.get("purchase_price"))
    rehab_cost = to_float(seed.get("rehab_cost"))
    contingency = to_float(seed.get("contingency"))
    total_cost = to_float(seed.get("total_project_cost")) or (purchase_price + rehab_cost + contingency)
    arv = to_float(seed.get("arv"))

    ltc_limit = total_cost * 0.85
    arv_limit = arv * 0.70 if arv > 0 else 0.0
    recommended_loan = min(x for x in [ltc_limit, arv_limit] if x > 0) if any(x > 0 for x in [ltc_limit, arv_limit]) else ltc_limit

    return {
        "purchase_price": purchase_price,
        "rehab_cost": rehab_cost,
        "contingency": contingency,
        "total_cost": total_cost,
        "arv": arv,
        "max_loan_ltc": ltc_limit,
        "max_loan_arv": arv_limit,
        "recommended_loan_amount": recommended_loan,
        "estimated_cash_required": max(total_cost - recommended_loan, 0),
    }


# -------------------------------------------------------------------
# MASHVISOR / ATTOM / PARTNER FALLBACK SHIMS
# -------------------------------------------------------------------

def _build_mashvisor_insight(data: Dict[str, Any] | None) -> Dict[str, Any]:
    data = data or {}
    return {
        "traditional_roi": to_float(data.get("traditional_roi")),
        "traditional_cap_rate": to_float(data.get("traditional_cap_rate")),
        "airbnb_roi": to_float(data.get("airbnb_roi")),
        "airbnb_cap_rate": to_float(data.get("airbnb_cap_rate")),
        "traditional_rent": to_float(data.get("traditional_rent")),
        "airbnb_rent": to_float(data.get("airbnb_rent")),
        "occupancy_rate": to_float(data.get("occupancy_rate")),
        "confidence": data.get("confidence"),
        "source": "mashvisor" if data else None,
    }


def _build_attom_fallback(data: Dict[str, Any] | None = None) -> Dict[str, Any]:
    data = data or {}
    return {
        "market_value": to_float(data.get("market_value")),
        "assessed_value": to_float(data.get("assessed_value")),
        "last_sale_price": to_float(data.get("last_sale_price")),
        "last_sale_date": data.get("last_sale_date"),
        "beds": to_float(data.get("beds")),
        "baths": to_float(data.get("baths")),
        "sqft": to_float(data.get("sqft")),
        "lot_sqft": to_float(data.get("lot_sqft")),
        "year_built": safe_int(data.get("year_built")),
        "property_type": data.get("property_type"),
        "source": "attom",
    }


def search_external_partners_google(*args, **kwargs):
    return []


# -------------------------------------------------------------------
# DEAL / REHAB / RENDER PLACEHOLDERS
# -------------------------------------------------------------------

def _deal_render_lock_active(deal) -> bool:
    return bool(getattr(deal, "render_processing", False))


def _set_deal_render_processing(deal, value: bool = True):
    _set_if_attr(deal, "render_processing", bool(value))


def _clear_deal_render_processing(deal):
    _set_if_attr(deal, "render_processing", False)


def _stable_render_seed(*parts) -> int:
    """Create a deterministic seed from any number of hashable parts.

    Accepts positional arguments of any type (deal_id, variant strings,
    image URLs, etc.) and hashes them into a stable integer seed.
    Falls back to a random seed when all parts are empty/None.
    """
    import hashlib
    combined = "|".join(safe_str(p) for p in parts if p is not None)
    if not combined.strip("|"):
        return random.randint(1000, 999999)
    digest = int(hashlib.md5(combined.encode()).hexdigest(), 16)
    return digest % 999999 + 1


def _normalize_style_preset(style: str | None) -> str:
    value = safe_str(style, "modern")
    return value.lower().replace(" ", "_")


def _featured_rehab_data(deal) -> Dict[str, Any]:
    results = getattr(deal, "results_json", {}) or {}
    featured = results.get("featured_rehab", {}) or {}
    return {
        "before_url": featured.get("before_url"),
        "after_url": featured.get("after_url"),
        "style_preset": featured.get("style_preset"),
    }


def _save_before_url_to_deal(deal, before_url: str | None):
    results = getattr(deal, "results_json", {}) or {}
    featured = results.get("featured_rehab", {}) or {}
    featured["before_url"] = before_url
    results["featured_rehab"] = featured
    _set_if_attr(deal, "results_json", results)


def _save_mockups_for_deal(deal, mockups: List[Dict[str, Any]] | None):
    results = getattr(deal, "results_json", {}) or {}
    results["mockups"] = mockups or []
    _set_if_attr(deal, "results_json", results)


def _set_featured_rehab(deal, after_url: str | None, before_url: str | None = None, style_preset: str | None = None, style_prompt: str | None = None):
    results = getattr(deal, "results_json", {}) or {}
    featured = {
        "after_url": after_url,
        "before_url": before_url,
        "style_preset": style_preset,
    }
    if style_prompt:
        featured["style_prompt"] = style_prompt
    results["featured_rehab"] = featured
    _set_if_attr(deal, "results_json", results)
    return featured


def _get_rehab_mockups_for_deal(deal) -> List[Dict[str, Any]]:
    results = getattr(deal, "results_json", {}) or {}
    return results.get("mockups", []) or []


def _get_rehab_export_payload(deal) -> Dict[str, Any]:
    return {
        "deal_id": getattr(deal, "id", None),
        "title": getattr(deal, "title", None),
        "address": getattr(deal, "address", None),
        "featured_rehab": _featured_rehab_data(deal),
        "mockups": _get_rehab_mockups_for_deal(deal),
    }


def _get_owned_deal_or_404(queryset_or_deal_id, deal_id: int | None = None, user_id: int | None = None):
    """
    Backward-compatible helper.

    Supports:
    - _get_owned_deal_or_404(deal_id)
    - _get_owned_deal_or_404(queryset, deal_id, user_id)
    """
    if deal_id is None:
        from flask_login import current_user
        from LoanMVP.models.borrowers import Deal

        return Deal.query.filter_by(
            id=queryset_or_deal_id,
            user_id=current_user.id,
        ).first_or_404()

    return queryset_or_deal_id.filter_by(id=deal_id, user_id=user_id).first_or_404()
