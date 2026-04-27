"""
Ravlo Comp Scorer
-----------------
Scores each comparable property 0-100 relative to a subject.
Higher score = stronger evidence for ARV estimation.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


INCLUSION_THRESHOLD = 50

# Weight caps per factor
_WEIGHTS = {
    "distance": 15,
    "property_type": 10,
    "sale_status": 10,
    "recency": 15,
    "bed_bath": 10,
    "sqft": 15,
    "year_built": 5,
    "lot_size": 5,
    "neighborhood": 5,
    "location_premium": 5,
    "price_per_sqft": 5,
}


def _safe_float(val: Any) -> Optional[float]:
    if val is None or val == "" or val == "None":
        return None
    try:
        if isinstance(val, (int, float)):
            return float(val)
        return float(str(val).replace("$", "").replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _safe_int(val: Any) -> Optional[int]:
    f = _safe_float(val)
    return int(round(f)) if f is not None else None


def _parse_date(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(str(val).strip()[:19], fmt)
        except (ValueError, TypeError):
            continue
    return None


def _months_ago(dt: Optional[datetime]) -> Optional[float]:
    if dt is None:
        return None
    delta = datetime.utcnow() - dt
    return max(delta.days / 30.44, 0)


def _pct_diff(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return abs(a - b) / b


def _extract_street(address: Optional[str]) -> Optional[str]:
    if not address:
        return None
    parts = str(address).lower().replace(",", "").split()
    if len(parts) >= 3:
        return " ".join(parts[1:3])
    return None


def score_comp(
    subject: Dict[str, Any],
    comp: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Score a single comp against the subject.
    Returns the comp dict enriched with `comp_score`, `score_breakdown`,
    `included`, and `rejection_reason`.
    """
    breakdown: Dict[str, float] = {}
    reasons: List[str] = []

    # ── Distance ──
    dist = _safe_float(comp.get("distance") or comp.get("distance_miles"))
    if dist is not None:
        if dist <= 0.25:
            breakdown["distance"] = 15
        elif dist <= 0.5:
            breakdown["distance"] = 12
        elif dist <= 1.0:
            breakdown["distance"] = 8
        elif dist <= 3.0:
            breakdown["distance"] = 4
        else:
            breakdown["distance"] = 0
            reasons.append(f"Too far ({dist:.1f} mi)")
    else:
        breakdown["distance"] = 5  # unknown distance, neutral

    # ── Property type match ──
    subj_type = str(subject.get("property_type") or "").lower()
    comp_type = str(comp.get("property_type") or comp.get("propertyType") or "").lower()
    if subj_type and comp_type:
        if subj_type == comp_type or _types_equivalent(subj_type, comp_type):
            breakdown["property_type"] = 10
        else:
            breakdown["property_type"] = 2
            reasons.append(f"Different property type ({comp_type})")
    else:
        breakdown["property_type"] = 6

    # ── Sale status ──
    status = str(comp.get("status") or "").lower()
    if status in ("sold", "closed", "recently sold"):
        breakdown["sale_status"] = 10
    elif status in ("pending", "under contract"):
        breakdown["sale_status"] = 7
    elif status in ("active", "for sale"):
        breakdown["sale_status"] = 3
        reasons.append("Active listing (not sold)")
    else:
        breakdown["sale_status"] = 5

    # ── Sale recency ──
    sale_date = _parse_date(
        comp.get("sold_date") or comp.get("lastSaleDate") or comp.get("soldDate")
        or comp.get("sale_date") or comp.get("removedDate") or comp.get("list_date")
    )
    months = _months_ago(sale_date)
    if months is not None:
        if months <= 6:
            breakdown["recency"] = 15
        elif months <= 12:
            breakdown["recency"] = 12
        elif months <= 18:
            breakdown["recency"] = 8
        elif months <= 24:
            breakdown["recency"] = 4
        else:
            breakdown["recency"] = 1
            reasons.append(f"Old sale ({months:.0f} months ago)")
    else:
        breakdown["recency"] = 5

    # ── Bed/bath similarity ──
    subj_beds = _safe_int(subject.get("beds"))
    subj_baths = _safe_float(subject.get("baths"))
    comp_beds = _safe_int(comp.get("beds") or comp.get("bedrooms"))
    comp_baths = _safe_float(comp.get("baths") or comp.get("bathrooms"))

    bed_diff = abs(subj_beds - comp_beds) if subj_beds and comp_beds else None
    bath_diff = abs(subj_baths - comp_baths) if subj_baths and comp_baths else None

    bb_score = 10
    if bed_diff is not None:
        if bed_diff == 0:
            pass
        elif bed_diff == 1:
            bb_score -= 2
        else:
            bb_score -= min(bed_diff * 3, 8)
            reasons.append(f"Bed count differs by {bed_diff}")
    if bath_diff is not None:
        if bath_diff > 1:
            bb_score -= min(int(bath_diff * 2), 5)
    breakdown["bed_bath"] = max(bb_score, 0)

    # ── Sqft similarity ──
    subj_sqft = _safe_float(subject.get("living_sqft"))
    comp_sqft = _safe_float(comp.get("sqft") or comp.get("squareFootage") or comp.get("square_feet"))
    pct = _pct_diff(subj_sqft, comp_sqft)
    if pct is not None:
        if pct <= 0.10:
            breakdown["sqft"] = 15
        elif pct <= 0.20:
            breakdown["sqft"] = 10
        elif pct <= 0.30:
            breakdown["sqft"] = 5
        else:
            breakdown["sqft"] = 1
            reasons.append(f"Sqft differs by {pct:.0%}")
    else:
        breakdown["sqft"] = 5

    # ── Year built ──
    subj_yr = _safe_int(subject.get("year_built"))
    comp_yr = _safe_int(comp.get("year_built") or comp.get("yearBuilt"))
    if subj_yr and comp_yr:
        yr_diff = abs(subj_yr - comp_yr)
        if yr_diff <= 5:
            breakdown["year_built"] = 5
        elif yr_diff <= 15:
            breakdown["year_built"] = 3
        else:
            breakdown["year_built"] = 1
    else:
        breakdown["year_built"] = 3

    # ── Lot size ──
    subj_lot = _safe_float(subject.get("lot_sqft"))
    comp_lot = _safe_float(comp.get("lot_sqft") or comp.get("lotSize") or comp.get("lotSizeSqFt"))
    lot_pct = _pct_diff(subj_lot, comp_lot)
    if lot_pct is not None:
        if lot_pct <= 0.20:
            breakdown["lot_size"] = 5
        elif lot_pct <= 0.50:
            breakdown["lot_size"] = 3
        else:
            breakdown["lot_size"] = 1
    else:
        breakdown["lot_size"] = 3

    # ── Neighborhood / same street ──
    subj_street = _extract_street(subject.get("address"))
    comp_street = _extract_street(
        comp.get("address") or comp.get("formattedAddress")
    )
    if subj_street and comp_street and subj_street == comp_street:
        breakdown["neighborhood"] = 5
    else:
        breakdown["neighborhood"] = 2

    # ── Location premium (waterfront/beach/view) ──
    comp_desc = str(comp.get("description") or "").lower()
    comp_addr = str(comp.get("address") or "").lower()
    premium_keywords = ["waterfront", "beachfront", "ocean", "bay", "lake", "canal", "water view"]
    has_premium = any(kw in comp_desc or kw in comp_addr for kw in premium_keywords)
    subj_desc = str(subject.get("address") or "").lower()
    subj_premium = any(kw in subj_desc for kw in premium_keywords)

    if has_premium and subj_premium:
        breakdown["location_premium"] = 5
    elif has_premium and not subj_premium:
        breakdown["location_premium"] = 1
        reasons.append("Comp has location premium subject lacks")
    elif not has_premium and subj_premium:
        breakdown["location_premium"] = 1
        reasons.append("Subject has location premium comp lacks")
    else:
        breakdown["location_premium"] = 3

    # ── Price per sqft reasonableness ──
    comp_price = _safe_float(comp.get("price") or comp.get("value"))
    if comp_price and comp_sqft and comp_sqft > 0:
        ppsf = comp_price / comp_sqft
        if 50 <= ppsf <= 2000:
            breakdown["price_per_sqft"] = 5
        else:
            breakdown["price_per_sqft"] = 1
            reasons.append(f"Unusual $/sqft (${ppsf:,.0f})")
    else:
        breakdown["price_per_sqft"] = 3

    total_score = sum(breakdown.values())
    total_score = max(0, min(100, round(total_score)))

    included = total_score >= INCLUSION_THRESHOLD
    rejection_reason = None
    if not included:
        rejection_reason = "; ".join(reasons) if reasons else "Low overall similarity"

    comp_price = _safe_float(comp.get("price") or comp.get("value"))
    price_per_sqft = None
    if comp_price and comp_sqft and comp_sqft > 0:
        price_per_sqft = round(comp_price / comp_sqft, 2)

    return {
        **comp,
        "comp_score": total_score,
        "score_breakdown": breakdown,
        "included": included,
        "rejection_reason": rejection_reason,
        "inclusion_reasons": reasons,
        "price_per_sqft": price_per_sqft,
        "months_ago": round(months, 1) if months is not None else None,
        "status_normalized": _normalize_status(status),
    }


def score_all_comps(
    subject: Dict[str, Any],
    comps: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Score all comps. Returns (included, rejected) sorted by score desc.
    """
    scored = [score_comp(subject, c) for c in comps]
    included = sorted(
        [c for c in scored if c["included"]],
        key=lambda x: x["comp_score"],
        reverse=True,
    )
    rejected = sorted(
        [c for c in scored if not c["included"]],
        key=lambda x: x["comp_score"],
        reverse=True,
    )
    return included, rejected


def _types_equivalent(a: str, b: str) -> bool:
    equivalences = [
        {"single family", "single_family", "sfr", "house", "detached", "single-family"},
        {"condo", "condominium", "apartment"},
        {"townhouse", "townhome", "attached"},
        {"multi family", "multi_family", "multifamily", "duplex", "triplex", "fourplex"},
        {"land", "lot", "vacant land", "vacant", "unimproved"},
    ]
    for group in equivalences:
        if a in group and b in group:
            return True
    return False


def _normalize_status(status: str) -> str:
    s = status.lower().strip()
    if s in ("sold", "closed", "recently sold"):
        return "sold"
    if s in ("pending", "under contract"):
        return "pending"
    if s in ("active", "for sale", "new"):
        return "active"
    return s or "unknown"
