# LoanMVP/services/deal_workspace_calcs.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional


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


def _get_prop_sqft(comps: Dict[str, Any]) -> int:
    return safe_int((comps.get("property") or {}).get("sqft"), 0)


def _get_purchase_price(form, comps: Dict[str, Any]) -> float:
    # priority: form override, then saved price
    p_form = safe_float(form.get("purchase_price")) if form else 0.0
    if p_form > 0:
        return p_form
    p_saved = safe_float((comps.get("property") or {}).get("price"))
    return p_saved if p_saved > 0 else 0.0


def _get_arv(comps: Dict[str, Any], form=None) -> float:
    # priority: form override, then arv_estimate, then median of resale comps
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

    # fallback: median from rental comps list (if you used Rentometer)
    rentals = comps.get("rental_comps") or []
    rents = [safe_float(r.get("rent")) for r in rentals if safe_float(r.get("rent")) > 0]
    if rents:
        rents.sort()
        return rents[len(rents) // 2]
    return 0.0


def calculate_flip_budget(form, comps: Dict[str, Any]) -> Dict[str, Any]:
    purchase_price = _get_purchase_price(form, comps)
    arv = _get_arv(comps, form=form)

    # rehab inputs
    rehab_total = safe_float(form.get("rehab_total")) if form else safe_float(comps.get("rehab_total"))
    if rehab_total <= 0:
        rehab_total = safe_float((comps.get("rehab_summary") or {}).get("total"))

    # holding + selling
    holding_months = safe_int(form.get("holding_months"), 6) if form else 6
    monthly_holding = safe_float(form.get("monthly_holding_cost"), 0.0) if form else 0.0
    holding_cost = monthly_holding * holding_months

    selling_cost_rate = safe_float(form.get("selling_cost_rate"), 0.08) if form else 0.08  # 8% default
    selling_costs = arv * selling_cost_rate

    # financing
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
        "ok": True,
    }


def calculate_rental_budget(form, comps: Dict[str, Any]) -> Dict[str, Any]:
    purchase_price = _get_purchase_price(form, comps)
    rehab_total = safe_float(form.get("rehab_total")) if form else safe_float(comps.get("rehab_total"))
    if rehab_total <= 0:
        rehab_total = safe_float((comps.get("rehab_summary") or {}).get("total"))

    monthly_rent = _get_market_rent(comps, form=form)

    # expenses defaults
    taxes = safe_float(form.get("monthly_taxes"), 0.0) if form else 0.0
    insurance = safe_float(form.get("monthly_insurance"), 0.0) if form else 0.0
    hoa = safe_float(form.get("monthly_hoa"), 0.0) if form else 0.0
    maintenance = safe_float(form.get("monthly_maintenance"), monthly_rent * 0.05) if form else monthly_rent * 0.05
    vacancy = safe_float(form.get("vacancy_rate"), 0.05) if form else 0.05
    management = safe_float(form.get("management_rate"), 0.08) if form else 0.08

    effective_rent = monthly_rent * (1 - vacancy)
    mgmt_cost = effective_rent * management
    total_expenses = taxes + insurance + hoa + maintenance + mgmt_cost

    # mortgage assumptions (optional override)
    down_payment_rate = safe_float(form.get("down_payment_rate"), 0.25) if form else 0.25
    down_payment = purchase_price * down_payment_rate
    loan_amount = max(purchase_price - down_payment, 0.0)
    rate = safe_float(form.get("interest_rate"), 0.075) if form else 0.075
    term_years = safe_int(form.get("term_years"), 30) if form else 30

    # rough amortized payment (safe approximation)
    r = rate / 12.0
    n = term_years * 12
    if loan_amount > 0 and r > 0:
        payment = loan_amount * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
    elif loan_amount > 0:
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
        "effective_rent": effective_rent,
        "monthly_expenses": total_expenses,
        "mortgage_payment": payment,
        "net_cashflow": net_cashflow,
        "annual_noi": annual_noi,
        "cap_rate": cap_rate,
        "dscr": dscr,
        "loan_amount": loan_amount,
        "down_payment": down_payment,
        "ok": True,
    }


def calculate_airbnb_budget(form, comps: Dict[str, Any]) -> Dict[str, Any]:
    """
    Beta version:
    - nightly_rate and occupancy can be user inputs
    - if not provided, we estimate from long-term rent as a proxy
    """
    purchase_price = _get_purchase_price(form, comps)
    rehab_total = safe_float(form.get("rehab_total")) if form else safe_float(comps.get("rehab_total"))
    if rehab_total <= 0:
        rehab_total = safe_float((comps.get("rehab_summary") or {}).get("total"))

    nightly_rate = safe_float(form.get("nightly_rate"), 0.0) if form else 0.0
    occupancy = safe_float(form.get("occupancy_rate"), 0.55) if form else 0.55

    if nightly_rate <= 0:
        # proxy from long-term rent: assume STR monthly gross ~ 1.6x LTR gross in good markets (tunable)
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
        "ok": True,
    }


def recommend_strategy(comparison: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Simple recommendation logic:
    - prefer highest profit for flip
    - prefer highest net cashflow for rental/airbnb
    - add a basic risk score
    """
    flip = comparison.get("flip") or {}
    rental = comparison.get("rental") or {}
    airbnb = comparison.get("airbnb") or {}

    score = {}

    # Flip score: profit
    score["flip"] = safe_float(flip.get("profit"))

    # Rental score: net cashflow * 12 + bonus for DSCR >= 1.15
    dscr = safe_float(rental.get("dscr"))
    score["rental"] = safe_float(rental.get("net_cashflow")) * 12 + (5000 if dscr >= 1.15 else 0)

    # Airbnb score: net monthly * 12 but penalize low occupancy assumptions
    occ = safe_float(airbnb.get("occupancy_rate"), 0.55)
    score["airbnb"] = safe_float(airbnb.get("net_monthly")) * 12 - (3000 if occ < 0.45 else 0)

    best = max(score, key=score.get) if score else "rental"

    return {
        "best": best,
        "scores": score,
        "notes": {
            "flip": "Higher profit wins. Watch holding + sell costs.",
            "rental": "Higher annual cashflow with DSCR bonus.",
            "airbnb": "High cashflow but occupancy sensitivity.",
        }
    }