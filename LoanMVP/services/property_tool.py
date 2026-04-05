# LoanMVP/services/property_tool.py
import os
import requests
from typing import Any, Dict, List, Optional

from LoanMVP.services.deal_workspace_calcs import (
    calculate_flip_budget,
    calculate_rental_budget,
    calculate_airbnb_budget,
    recommend_strategy,
    generate_ai_deal_summary,
    safe_float,
)
from LoanMVP.services.deal_finder_engine import (
    build_deal_thesis,
    compute_ravlo_score,
    determine_primary_and_fallback,
)

ATTOM_BASE_URL = os.getenv("ATTOM_BASE_URL", "https://api.gateway.attomdata.com").rstrip("/")
ATTOM_API_KEY = (os.getenv("ATTOM_API_KEY") or "").strip()
ATTOM_TIMEOUT = int(os.getenv("DEALFINDER_TIMEOUT", "20"))

_session = requests.Session()


class AttomSearchError(Exception):
    pass


def _headers() -> Dict[str, str]:
    if not ATTOM_API_KEY:
        raise AttomSearchError("ATTOM_API_KEY is missing.")
    return {
        "accept": "application/json",
        "apikey": ATTOM_API_KEY,
    }


def _get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{ATTOM_BASE_URL}{path}"
    try:
        res = _session.get(
            url,
            headers=_headers(),
            params=params or {},
            timeout=ATTOM_TIMEOUT,
        )
        res.raise_for_status()
        return res.json()
    except requests.HTTPError as e:
        body = ""
        try:
            body = (res.text or "")[:500]
        except Exception:
            pass
        raise AttomSearchError(f"ATTOM HTTP error: {e}. body={body}")
    except Exception as e:
        raise AttomSearchError(f"ATTOM request failed: {e}")


def _safe_get(dct: Any, *keys: str, default=None):
    cur = dct
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


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


def _listing_photo(listing: dict):
    """
    ATTOM usually won't give you listing photos the way listing APIs do.
    Keep a safe placeholder.
    """
    return "/static/images/placeholder_property.jpg"


def _normalize_attom_listing(raw: Dict[str, Any], zip_code_fallback: str = "") -> Dict[str, Any]:
    address = _safe_get(raw, "address", "oneLine") or _safe_get(raw, "address", "line1") or ""
    city = _safe_get(raw, "address", "locality") or ""
    state = _safe_get(raw, "address", "countrySubd") or ""
    zip_code = _safe_get(raw, "address", "postal1") or zip_code_fallback or ""

    price = _as_float(
        _safe_get(raw, "assessment", "market", "mktttlvalue")
        or _safe_get(raw, "assessment", "assessed", "assdttlvalue")
        or _safe_get(raw, "sale", "amount", "saleAmt")
        or raw.get("avm")
        or raw.get("estimatedValue")
        or raw.get("marketValue")
        or raw.get("price")
    )

    beds = _safe_int(
        _safe_get(raw, "building", "rooms", "beds")
        or raw.get("bedrooms")
        or raw.get("beds")
    )

    baths = safe_float(
        _safe_get(raw, "building", "rooms", "bathstotal")
        or raw.get("bathrooms")
        or raw.get("baths")
    )

    sqft = _as_float(
        _safe_get(raw, "building", "size", "universalsize")
        or raw.get("sqft")
        or raw.get("squareFootage")
    )

    year_built = _safe_int(
        _safe_get(raw, "summary", "yearBuilt")
        or raw.get("yearBuilt")
        or raw.get("year_built")
    )

    remarks = raw.get("remarks") or raw.get("description") or ""

    attom_id = _safe_get(raw, "identifier", "attomId") or raw.get("attomid") or raw.get("id")
    property_type = (
        _safe_get(raw, "summary", "propType")
        or _safe_get(raw, "summary", "propSubType")
        or raw.get("propertyType")
        or raw.get("propertySubType")
    )

    return {
        "address": address.strip(),
        "city": city.strip(),
        "state": state.strip(),
        "zip": str(zip_code).strip(),
        "price": price,
        "beds": beds,
        "baths": baths,
        "sqft": _safe_int(sqft),
        "year_built": year_built,
        "remarks": remarks,
        "property_id": str(attom_id).strip() if attom_id else None,
        "property_type": property_type,
        "raw": raw,
    }


def _extract_attom_list(data: dict) -> list[dict]:
    candidates = (
        data.get("property")
        or data.get("properties")
        or _safe_get(data, "response", "property")
        or _safe_get(data, "response", "properties")
        or []
    )

    if isinstance(candidates, dict):
        return [candidates]
    if isinstance(candidates, list):
        return candidates
    return []


def _attom_sale_listings_by_zip(
    zip_code: str,
    limit: int = 20,
    price_min=None,
    price_max=None,
    beds_min=None,
    baths_min=None,
) -> list[dict]:
    page = 1
    page_size = min(max(int(limit or 20), 1), 100)

    params = {
        "postalcode": zip_code,
        "page": page,
        "pagesize": page_size,
    }

    data = _get("/propertyapi/v1.0.0/property/address", params=params)
    rows = _extract_attom_list(data)
    print("ATTOM RAW FIRST ROW:", rows[0] if rows else "NO ROWS")
    
    normalized = []
    for row in rows:
        item = _normalize_attom_listing(row, zip_code_fallback=zip_code)

        # Apply local filters since ATTOM endpoint support can vary by package
        price = _as_float(item.get("price"))
        beds = _safe_int(item.get("beds"))
        baths = safe_float(item.get("baths"))

        if price_min is not None and price is not None and float(price) < float(price_min):
            continue
        if price_max is not None and price is not None and float(price) > float(price_max):
            continue
        if beds_min is not None and beds is not None and int(beds) < int(float(beds_min)):
            continue
        if baths_min is not None and baths is not None and float(baths) < float(baths_min):
            continue

        normalized.append(item)

    return normalized[:limit]


def _attom_value_estimate(raw_listing: Dict[str, Any]) -> Optional[float]:
    raw = raw_listing.get("raw") or {}

    value = (
        _safe_get(raw, "assessment", "market", "mktttlvalue")
        or _safe_get(raw, "assessment", "assessed", "assdttlvalue")
        or _safe_get(raw, "sale", "amount", "saleAmt")
        or raw.get("avm")
        or raw.get("estimatedValue")
        or raw.get("marketValue")
        or raw.get("price")
    )

    return _as_float(value)

def _attom_rent_estimate(raw_listing: Dict[str, Any]) -> Optional[float]:
    """
    ATTOM does have rental AVM products, but package access can vary.
    Until you wire that product in your account, keep this conservative.
    """
    raw = raw_listing.get("raw") or {}
    return _as_float(
        _safe_get(raw, "avm", "rentalavm", "amount")
        or _safe_get(raw, "rentalavm", "amount")
        or _safe_get(raw, "rentalAVM", "amount")
    )


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
    provider: str = "auto",
):
    provider = (provider or "auto").strip().lower()

    if provider == "auto":
        provider = "attom"

    if provider == "attom":
        return _search_deals_for_zip_attom(
            zip_code=zip_code,
            strategy=strategy,
            price_min=price_min,
            price_max=price_max,
            beds_min=beds_min,
            baths_min=baths_min,
            min_roi=min_roi,
            min_cashflow=min_cashflow,
            limit=limit,
        )

    if provider == "unified":
        return _search_deals_for_zip_unified(
            zip_code=zip_code,
            strategy=strategy,
            price_min=price_min,
            price_max=price_max,
            beds_min=beds_min,
            baths_min=baths_min,
            min_roi=min_roi,
            min_cashflow=min_cashflow,
            limit=limit,
        )

    raise RuntimeError(f"Unsupported deal finder provider: {provider}")


def _search_deals_for_zip_attom(
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
    listings = _attom_sale_listings_by_zip(
        zip_code=zip_code,
        limit=limit,
        price_min=price_min,
        price_max=price_max,
        beds_min=beds_min,
        baths_min=baths_min,
    )

    out = []

    for idx, l in enumerate(listings):
        addr = (l.get("address") or "").strip()
        city = (l.get("city") or "").strip()
        state = (l.get("state") or "").strip()
        z = (l.get("zip") or zip_code or "").strip()

        price = _as_float(l.get("price"))
        beds = _safe_int(l.get("beds"))
        baths = safe_float(l.get("baths"))
        sqft = _as_float(l.get("sqft"))
        year_built = _safe_int(l.get("year_built"))
        remarks = l.get("remarks") or ""

        fixer_score = _keyword_fixer_score(remarks)
        rehab = _estimate_rehab_from_score(fixer_score, sqft)

        arv = _attom_value_estimate(l)
        rent = _attom_rent_estimate(l)

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
                "property_type": l.get("property_type"),
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

        score_data = compute_ravlo_score({
            "metrics": metrics,
            "price": price,
            "arv": arv,
            "rehab": rehab,
        })

        strategy_data = determine_primary_and_fallback({
            "comparison": comparison,
        })

        deal_thesis = build_deal_thesis({
            "metrics": metrics,
            "price": price,
            "arv": arv,
            "rehab": rehab,
            "rent": rent,
        })

        recommended_strategy = strategy_data["primary"] or determine_strategy(metrics, recommendation)
        ai_summary = generate_ai_deal_summary(metrics)

        photo = _listing_photo(l)

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
            "arv": arv,
            "rent_est": rent,
            "beds": beds,
            "baths": baths,
            "sqft": _safe_int(sqft),
            "year_built": year_built,
            "photo": photo,
            "property_id": l.get("property_id"),
            "property_type": l.get("property_type"),
            "fixer_score": fixer_score,
            "rehab": rehab,
            "metrics": metrics,
            "comparison": comparison,
            "recommendation": recommendation,
            "recommended_strategy": recommended_strategy,
            "primary_strategy": strategy_data["primary"],
            "fallback_strategy": strategy_data["fallback"],
            "deal_score": score_data,
            "deal_thesis": deal_thesis,
            "ai_summary": ai_summary,
            "provider": "attom",
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


def _search_deals_for_zip_unified(
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
    """
    Future ATTOM + Mashvisor flow.
    For now, return ATTOM-backed ZIP deal search.
    """
    return _search_deals_for_zip_attom(
        zip_code=zip_code,
        strategy=strategy,
        price_min=price_min,
        price_max=price_max,
        beds_min=beds_min,
        baths_min=baths_min,
        min_roi=min_roi,
        min_cashflow=min_cashflow,
        limit=limit,
        )
