from __future__ import annotations
from typing import Dict, Any


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
        ""
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
    score["rental"] = safe_float(rental.get("net_cashflow")) * 12 + (5000 if dscr >= 1.15 else 0) + (safe_float(rental.get("cap_rate")) * 1000)
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


def build_exit_strategy_cards(comparison: Dict[str, Dict[str, Any]]) -> list[Dict[str, Any]]:
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
            "ARV support improves the flip thesis."
        ],
        "rental": [
            "Long-term rent support appears stable.",
            "Cash flow and cap rate make the hold path more durable.",
            "This opportunity looks more suited to recurring income than quick resale."
        ],
        "airbnb": [
            "Short-term revenue potential appears stronger than long-term rent.",
            "The revenue profile may justify deeper hospitality underwriting.",
            "Occupancy and nightly assumptions create a higher-upside path."
        ],
        "land": [
            "This asset reads more like land optionality than a standard residential hold.",
            "Site value and lot profile matter more than current in-place operations.",
            "A build or parcel strategy appears stronger than traditional rental underwriting."
        ],
    }

    watch_map = {
        "flip": [
            "Verify rehab scope and resale timeline.",
            "Stress-test exit value using conservative comps."
        ],
        "rental": [
            "Confirm taxes, insurance, and maintenance assumptions.",
            "Validate current rent support with fresh comps."
        ],
        "airbnb": [
            "Validate local STR rules and seasonality.",
            "Pressure-test occupancy and nightly rate assumptions."
        ],
        "land": [
            "Verify zoning and entitlement path.",
            "Confirm utility access, frontage, and resale demand."
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
