# LoanMVP/services/property_tool.py
import os
import re
import requests

RENTCAST_BASE = "https://api.rentcast.io/v1"
RENTCAST_KEY = (os.environ.get("RENTCAST_API_KEY") or "").strip()  # strip matters

def _headers():
    if not RENTCAST_KEY:
        raise RuntimeError("RENTCAST_API_KEY is missing.")
    return {"X-Api-Key": RENTCAST_KEY}

def _as_float(x):
    try:
        return float(x)
    except Exception:
        return None

def _keyword_fixer_score(text: str) -> int:
    """
    Simple fixer-upper signal from listing remarks.
    (You can improve later with your AI or a classifier.)
    """
    if not text:
        return 0
    t = text.lower()
    hits = [
        "as-is", "needs work", "investor special", "handyman", "tlc",
        "fixer", "rehab", "cash only", "foundation", "fire", "mold",
        "water damage", "roof", "vacant", "estate sale",
    ]
    return sum(1 for w in hits if w in t)

def _estimate_rehab_from_score(score: int, sqft: float | None) -> float:
    """
    Lightweight rehab estimate. Replace with your rehab engine later.
    """
    if not sqft:
        sqft = 1400
    # baseline per-sqft bands
    if score <= 1:
        per = 15
    elif score <= 3:
        per = 30
    elif score <= 6:
        per = 45
    else:
        per = 65
    return float(per) * float(sqft)

def _flip_metrics(purchase_price: float, arv: float, rehab: float):
    """
    Basic flip math. You can swap to your existing calculate_flip_budget later.
    """
    if not purchase_price or not arv:
        return {}
    # holding + selling rough assumptions
    selling_cost_rate = 0.08
    holding = 0.02 * purchase_price  # rough placeholder
    selling = selling_cost_rate * arv

    profit = arv - purchase_price - rehab - holding - selling
    roi = profit / max((purchase_price + rehab), 1)
    return {
        "profit": round(profit, 0),
        "roi": round(roi, 4),
        "rehab_est": round(rehab, 0),
        "arv": round(arv, 0),
    }

def _rental_metrics(purchase_price: float, rent: float):
    """
    Basic rental math; replace with your DSCR/expense model later.
    """
    if not purchase_price or not rent:
        return {}
    # placeholder expenses
    taxes_insurance_hoa = 0.18 * rent
    maintenance = 0.10 * rent
    vacancy = 0.06 * rent
    mgmt = 0.08 * rent
    net = rent - (taxes_insurance_hoa + maintenance + vacancy + mgmt)

    # DSCR rough: NOI / (P&I approx)
    annual_noi = net * 12
    annual_debt_service = 0.08 * purchase_price  # placeholder; swap to amortization later
    dscr = annual_noi / max(annual_debt_service, 1)

    return {
        "net_cashflow_mo": round(net, 0),
        "dscr": round(dscr, 2),
        "rent_est": round(rent, 0),
    }

def _rentcast_sale_listings(zip_code: str, limit: int = 20, price_min=None, price_max=None, beds_min=None, baths_min=None):
    params = {"zipCode": zip_code, "limit": limit}
    if price_min is not None: params["priceMin"] = price_min
    if price_max is not None: params["priceMax"] = price_max
    if beds_min is not None: params["bedsMin"] = beds_min
    if baths_min is not None: params["bathsMin"] = baths_min

    r = requests.get(f"{RENTCAST_BASE}/listings/sale", headers=_headers(), params=params, timeout=30)
    r.raise_for_status()
    return r.json() if isinstance(r.json(), list) else (r.json().get("listings") or [])

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
        beds = l.get("bedrooms")
        baths = l.get("bathrooms")
        sqft = _as_float(l.get("squareFootage"))
        remarks = l.get("description") or l.get("remarks") or ""

        fixer_score = _keyword_fixer_score(remarks)
        rehab = _estimate_rehab_from_score(fixer_score, sqft)

        # Estimates
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

        metrics = {}
        if strategy in ("flip", "all"):
            metrics.update(_flip_metrics(price or 0, arv or 0, rehab))
        if strategy in ("rental", "all"):
            metrics.update(_rental_metrics(price or 0, rent or 0))

        # Filters
        if min_roi is not None and metrics.get("roi") is not None:
            if float(metrics["roi"]) < float(min_roi):
                continue
        if min_cashflow is not None and metrics.get("net_cashflow_mo") is not None:
            if float(metrics["net_cashflow_mo"]) < float(min_cashflow):
                continue

        out.append({
            "address": addr,
            "city": city,
            "state": state,
            "zip": z,
            "price": price,
            "beds": beds,
            "baths": baths,
            "sqft": sqft,
            "photo": (l.get("imageUrl") or l.get("primaryPhoto") or None),
            "fixer_score": fixer_score,
            "metrics": metrics,
        })

    # Sort best first
    if strategy == "flip":
        out.sort(key=lambda x: (x["metrics"].get("roi") or -999), reverse=True)
    elif strategy == "rental":
        out.sort(key=lambda x: (x["metrics"].get("net_cashflow_mo") or -999), reverse=True)

    return out
