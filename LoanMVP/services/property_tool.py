# LoanMVP/services/property_tool.py
import os
import requests

from LoanMVP.services.deal_workspace_calcs import (
    calculate_flip_budget,
    calculate_rental_budget,
    calculate_airbnb_budget,
    recommend_strategy,
    generate_ai_deal_summary,
    safe_float,
)


RENTCAST_BASE = "https://api.rentcast.io/v1"
RENTCAST_KEY = (os.environ.get("RENTCAST_API_KEY") or "").strip()


def _headers():
    if not RENTCAST_KEY:
        raise RuntimeError("RENTCAST_API_KEY is missing.")
    return {"X-Api-Key": RENTCAST_KEY}


def _as_float(x):
    try:
        return float(x)
    except Exception:
        return None
def _safe_int(x):
    try:
        return int(float(x))
    except Exception:
        return None

def _keyword_fixer_score(text: str) -> int:
    if not text:
        return 0
    t = text.lower()
    hits = [
        "as-is", "needs work", "investor special", "handyman", "tlc",
        "fixer", "rehab", "cash only", "foundation", "fire", "mold",
        "water damage", "roof", "vacant", "estate sale",
    ]
    return sum(1 for w in hits if w in t)

def _listing_photo(listing: dict):
    if not isinstance(listing, dict):
        return None

    candidates = [
        listing.get("imageUrl"),
        listing.get("primaryPhoto"),
        listing.get("photo"),
        listing.get("photos"),
        listing.get("imageUrls"),
        listing.get("photoUrls"),
        listing.get("images"),
    ]

    for val in candidates:
        if isinstance(val, str) and val.strip():
            return val.strip()
        if isinstance(val, list) and val:
            first = val[0]
            if isinstance(first, str) and first.strip():
                return first.strip()
            if isinstance(first, dict):
                url = first.get("url") or first.get("href") or first.get("src")
                if isinstance(url, str) and url.strip():
                    return url.strip()

    return None
    
def _estimate_rehab_from_score(score: int, sqft: float | None) -> float:
    if not sqft:
        sqft = 1400
    if score <= 1:
        per = 15
    elif score <= 3:
        per = 30
    elif score <= 6:
        per = 45
    else:
        per = 65
    return float(per) * float(sqft)


def calculate_deal_score(metrics: dict) -> dict:
    roi = metrics.get("roi") or 0
    profit = metrics.get("profit") or 0
    cashflow = metrics.get("net_cashflow_mo") or metrics.get("net_cashflow") or 0
    airbnb_net = metrics.get("net_monthly") or 0

    score = 0

    if roi >= 0.30:
        score += 40
    elif roi >= 0.20:
        score += 30
    elif roi >= 0.15:
        score += 20

    if profit >= 75000:
        score += 30
    elif profit >= 40000:
        score += 20
    elif profit >= 20000:
        score += 10

    if cashflow >= 500:
        score += 30
    elif cashflow >= 300:
        score += 20
    elif cashflow >= 150:
        score += 10

    if airbnb_net >= 800:
        score += 20
    elif airbnb_net >= 400:
        score += 10

    label = "Pass"
    if score >= 80:
        label = "Strong Deal"
    elif score >= 60:
        label = "Good Deal"
    elif score >= 40:
        label = "Marginal"

    return {
        "score": score,
        "label": label,
    }


def determine_strategy(metrics: dict, comparison: dict | None = None) -> str:
    roi = metrics.get("roi") or 0
    cashflow = metrics.get("net_cashflow_mo") or metrics.get("net_cashflow") or 0
    airbnb_net = metrics.get("net_monthly") or 0

    if comparison:
        best = (comparison.get("best") or "").lower()
        if best == "flip":
            return "Flip"
        if best == "rental":
            return "Rental"
        if best == "airbnb":
            return "Airbnb"

    if roi >= 0.20:
        return "Flip"
    if cashflow >= 250:
        return "Rental"
    if airbnb_net >= 500:
        return "Airbnb"
    return "Review"


def _rentcast_sale_listings(zip_code: str, limit: int = 20, price_min=None, price_max=None, beds_min=None, baths_min=None):
    params = {"zipCode": zip_code, "limit": limit}
    if price_min is not None:
        params["priceMin"] = price_min
    if price_max is not None:
        params["priceMax"] = price_max
    if beds_min is not None:
        params["bedsMin"] = beds_min
    if baths_min is not None:
        params["bathsMin"] = baths_min

    r = requests.get(f"{RENTCAST_BASE}/listings/sale", headers=_headers(), params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else (data.get("listings") or [])


def _rentcast_value_estimate(address: str, city: str, state: str, zip_code: str):
    params = {"address": address, "city": city, "state": state, "zip": zip_code}
    r = requests.get(f"{RENTCAST_BASE}/avm/value", headers=_headers(), params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def _rentcast_rent_estimate(address: str, city: str, state: str, zip_code: str):
    params = {"address": address, "city": city, "state": state, "zip": zip_code}
    r = requests.get(f"{RENTCAST_BASE}/avm/rent/long-term", headers=_headers(), params=params, timeout=30)
    r.raise_for_status()
    return r.json()



            
def search_deals_for_zip(
    zip_code: str,
    strategy: str = "flip",
    price_min=None,
    price_max=None,
    beds_min=None,
    baths_min=None,
    min_roi=None,
    min_cashflow=None,
    limit: int = 20,
):
    listings = _rentcast_sale_listings(
        zip_code=zip_code,
        limit=limit,
        price_min=price_min,
        price_max=price_max,
        beds_min=beds_min,
        baths_min=baths_min,
    )

    out = []

    for l in listings:
        addr = (l.get("addressLine1") or l.get("address") or "").strip()
        city = (l.get("city") or "").strip()
        state = (l.get("state") or "").strip()
        z = (l.get("zipCode") or zip_code or "").strip()

        price = _as_float(l.get("price"))
        beds = _safe_int(l.get("bedrooms") or l.get("beds"))
        baths = _safe_float(l.get("bathrooms") or l.get("baths"))
        sqft = _as_float(l.get("squareFootage") or l.get("sqft"))
        year_built = _safe_int(l.get("yearBuilt") or l.get("year_built"))
        remarks = l.get("description") or l.get("remarks") or ""

        fixer_score = _keyword_fixer_score(remarks)
        rehab = _estimate_rehab_from_score(fixer_score, sqft)

        arv = None
        rent = None

        try:
            v = _rentcast_value_estimate(addr, city, state, z)
            arv = _as_float(v.get("price") or v.get("value") or v.get("estimate"))
        except Exception:
            pass

        try:
            r = _rentcast_rent_estimate(addr, city, state, z)
            rent = _as_float(r.get("rent") or r.get("value") or r.get("estimate"))
        except Exception:
            pass

        comps = {
            "property": {
                "price": price,
                "sqft": sqft,
                "address": addr,
                "city": city,
                "state": state,
                "zip": z,
                "beds": beds,
                "baths": baths,
                "year_built": year_built,
                "property_type": l.get("propertyType") or l.get("propertySubType"),
            },
            "arv_estimate": arv,
            "market_rent_estimate": rent,
            "rehab_total": rehab,
            "rehab_summary": {
                "total": rehab,
                "scope": "light" if fixer_score <= 1 else "medium" if fixer_score <= 4 else "heavy",
            },
        }

        form = {
            "purchase_price": price,
            "arv": arv,
            "monthly_rent": rent,
            "rehab_total": rehab,
            "holding_months": 6,
            "monthly_holding_cost": 0,
            "selling_cost_rate": 0.08,
            "down_payment_rate": 0.20,
            "interest_rate": 0.10,
        }

        flip_metrics = calculate_flip_budget(form, comps)
        rental_metrics = calculate_rental_budget(form, comps)
        airbnb_metrics = calculate_airbnb_budget(form, comps)

        comparison = {
            "flip": flip_metrics,
            "rental": rental_metrics,
            "airbnb": airbnb_metrics,
        }

        recommendation = recommend_strategy(comparison)

        if strategy == "flip":
            metrics = flip_metrics
        elif strategy == "rental":
            metrics = rental_metrics
        elif strategy == "airbnb":
            metrics = airbnb_metrics
        else:
            metrics = {
                **flip_metrics,
                **rental_metrics,
                **airbnb_metrics,
            }

        score_data = calculate_deal_score(metrics)
        recommended_strategy = determine_strategy(metrics, recommendation)
        ai_summary = generate_ai_deal_summary(metrics)

        if min_roi is not None and metrics.get("roi") is not None:
            if float(metrics["roi"]) < float(min_roi):
                continue

        cashflow_value = metrics.get("net_cashflow_mo")
        if cashflow_value is None:
            cashflow_value = metrics.get("net_cashflow")

        if min_cashflow is not None and cashflow_value is not None:
            if float(cashflow_value) < float(min_cashflow):
                continue

        out.append({
            "address": addr,
            "city": city,
            "state": state,
            "zip": z,
            "price": price,
            "beds": beds,
            "baths": baths,
            "sqft": _safe_int(sqft),
            "year_built": year_built,
            "photo": _listing_photo(l),
            "property_id": l.get("id") or l.get("propertyId") or None,
            "property_type": l.get("propertyType") or l.get("propertySubType") or None,
            "fixer_score": fixer_score,
            "metrics": metrics,
            "comparison": comparison,
            "recommendation": recommendation,
            "recommended_strategy": recommended_strategy,
            "deal_score": {
                "score": score_data["score"],
                "label": score_data["label"],
            },
            "ai_summary": ai_summary,
        })

    out.sort(
        key=lambda x: (
            (x.get("deal_score") or {}).get("score", 0),
            x.get("metrics", {}).get("roi", 0) or 0,
            x.get("metrics", {}).get("profit", 0) or 0,
            x.get("metrics", {}).get("net_cashflow_mo", 0)
            or x.get("metrics", {}).get("net_cashflow", 0)
            or 0,
        ),
        reverse=True,
    )

    return out           
