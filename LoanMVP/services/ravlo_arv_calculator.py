"""
Ravlo ARV Calculator
--------------------
Produces conservative / base / aggressive ARV bands and confidence score.
Special logic for vacant lots: land value + finished-home ARV.
"""

from __future__ import annotations

import statistics
from typing import Any, Dict, List, Optional, Tuple


def _safe_float(val: Any) -> Optional[float]:
    if val is None or val == "" or val == "None":
        return None
    try:
        if isinstance(val, (int, float)):
            return float(val)
        return float(str(val).replace("$", "").replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def calculate_arv(
    subject: Dict[str, Any],
    included_comps: List[Dict[str, Any]],
    rejected_comps: List[Dict[str, Any]],
    provider_estimates: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Main ARV calculation.

    Returns:
    {
        "conservative": float,
        "base": float,
        "aggressive": float,
        "confidence": "low" | "medium" | "high",
        "confidence_score": int (0-100),
        "land_value": float | None,
        "method": str,
        "warnings": [str],
    }
    """
    is_lot = subject.get("is_vacant_lot", False)

    if is_lot:
        return _calculate_lot_arv(subject, included_comps, rejected_comps, provider_estimates)
    return _calculate_standard_arv(subject, included_comps, rejected_comps, provider_estimates)


def _calculate_standard_arv(
    subject: Dict[str, Any],
    included: List[Dict[str, Any]],
    rejected: List[Dict[str, Any]],
    providers: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    warnings: List[str] = []

    sold_comps = [c for c in included if c.get("status_normalized") == "sold"]
    active_comps = [c for c in included if c.get("status_normalized") == "active"]
    pending_comps = [c for c in included if c.get("status_normalized") == "pending"]

    subj_sqft = _safe_float(subject.get("living_sqft")) or 0

    # Gather price/sqft from sold comps weighted by score
    sold_ppsf = _weighted_ppsf(sold_comps, subj_sqft)
    active_ppsf = _weighted_ppsf(active_comps, subj_sqft)

    # Also gather raw prices weighted by score for comps without sqft
    sold_prices = _weighted_prices(sold_comps)
    active_prices = _weighted_prices(active_comps)

    base_arv = None
    method = "weighted_comp_analysis"

    if sold_ppsf and subj_sqft > 0:
        base_arv = sold_ppsf * subj_sqft
    elif sold_prices:
        base_arv = sold_prices
        method = "weighted_comp_prices"
    else:
        # Fall back to provider AVMs
        provider_values = _collect_provider_avms(providers)
        if provider_values:
            base_arv = statistics.median(provider_values)
            method = "provider_avm_median"
            warnings.append("No strong sold comps — using provider AVM median as base")
        else:
            return {
                "conservative": 0,
                "base": 0,
                "aggressive": 0,
                "confidence": "low",
                "confidence_score": 10,
                "land_value": None,
                "method": "insufficient_data",
                "warnings": ["Insufficient data to produce ARV estimate"],
            }

    # Conservative: 25th percentile ppsf, or base * 0.92
    # Aggressive: include active listings as upper bound, or base * 1.08
    conservative, aggressive = _compute_bands(
        base_arv, sold_comps, active_comps, subj_sqft
    )

    if active_comps and not sold_comps:
        warnings.append("Active listing only — not treated as proof of value")
    if len(sold_comps) < 3:
        warnings.append(f"Only {len(sold_comps)} sold comp(s) found")

    confidence, confidence_score = _compute_confidence(
        sold_comps, active_comps, pending_comps, providers, base_arv
    )

    return {
        "conservative": round(conservative),
        "base": round(base_arv),
        "aggressive": round(aggressive),
        "confidence": confidence,
        "confidence_score": confidence_score,
        "land_value": None,
        "method": method,
        "warnings": warnings,
    }


def _calculate_lot_arv(
    subject: Dict[str, Any],
    included: List[Dict[str, Any]],
    rejected: List[Dict[str, Any]],
    providers: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Vacant lot: produce land value + finished-home ARV.
    Finished-home ARV comes from nearby completed SFH comps.
    """
    warnings: List[str] = ["Vacant lot — finished ARV estimated separately"]

    # Land value from assessed value or provider estimates
    land_value = _estimate_land_value(subject, providers)

    # For finished-home ARV, filter comps to completed homes only
    home_comps = [
        c for c in included
        if not _is_lot_comp(c)
    ]

    lot_comps = [c for c in included if _is_lot_comp(c)]

    sold_homes = [c for c in home_comps if c.get("status_normalized") == "sold"]
    active_homes = [c for c in home_comps if c.get("status_normalized") == "active"]

    subj_sqft = _safe_float(subject.get("living_sqft")) or 0
    # For lots we may not have living sqft; estimate from nearby home comps
    if subj_sqft <= 0 and sold_homes:
        comp_sqfts = [
            _safe_float(c.get("sqft") or c.get("squareFootage") or c.get("square_feet"))
            for c in sold_homes
        ]
        comp_sqfts = [s for s in comp_sqfts if s and s > 0]
        if comp_sqfts:
            subj_sqft = statistics.median(comp_sqfts)
            warnings.append(f"Estimated finished sqft from comps: {subj_sqft:,.0f}")

    sold_ppsf = _weighted_ppsf(sold_homes, subj_sqft)
    sold_prices = _weighted_prices(sold_homes)

    base_arv = None
    method = "lot_finished_home_comps"

    if sold_ppsf and subj_sqft > 0:
        base_arv = sold_ppsf * subj_sqft
    elif sold_prices:
        base_arv = sold_prices
        method = "lot_weighted_comp_prices"
    else:
        # For vacant lots, provider AVMs represent lot value not finished-home
        # value, so skip them as a base. Use land_value multiplier instead.
        if land_value and land_value > 0:
            base_arv = land_value * 3
            method = "lot_land_multiplier"
            warnings.append("No finished-home comps — ARV estimated as 3× land value")
        else:
            provider_values = _collect_provider_avms(providers)
            if provider_values:
                base_arv = statistics.median(provider_values) * 3
                method = "lot_provider_avm_multiplier"
                warnings.append("No finished-home comps — ARV estimated as 3× provider lot AVM")
            else:
                base_arv = 0
                method = "lot_insufficient_data"
                warnings.append("Insufficient data for finished-home ARV estimate")

    if base_arv and base_arv > 0:
        conservative, aggressive = _compute_bands(
            base_arv, sold_homes, active_homes, subj_sqft
        )
    else:
        conservative = 0
        aggressive = 0

    confidence, confidence_score = _compute_confidence(
        sold_homes, active_homes, [], providers, base_arv
    )
    # Lots inherently have lower confidence
    confidence_score = max(confidence_score - 15, 10)
    if confidence_score < 40:
        confidence = "low"
    elif confidence_score < 65:
        confidence = "medium"

    return {
        "conservative": round(conservative) if conservative else 0,
        "base": round(base_arv) if base_arv else 0,
        "aggressive": round(aggressive) if aggressive else 0,
        "confidence": confidence,
        "confidence_score": confidence_score,
        "land_value": round(land_value) if land_value else None,
        "method": method,
        "warnings": warnings,
    }


def _weighted_ppsf(
    comps: List[Dict[str, Any]],
    target_sqft: float,
) -> Optional[float]:
    """Weighted average price-per-sqft using comp scores as weights."""
    total_weight = 0.0
    weighted_sum = 0.0
    for c in comps:
        ppsf = _safe_float(c.get("price_per_sqft"))
        score = _safe_float(c.get("comp_score")) or 0
        if ppsf and ppsf > 0 and score > 0:
            weighted_sum += ppsf * score
            total_weight += score
    if total_weight > 0:
        return weighted_sum / total_weight
    return None


def _weighted_prices(comps: List[Dict[str, Any]]) -> Optional[float]:
    """Weighted average of raw prices using comp scores."""
    total_weight = 0.0
    weighted_sum = 0.0
    for c in comps:
        price = _safe_float(c.get("price") or c.get("value"))
        score = _safe_float(c.get("comp_score")) or 0
        if price and price > 0 and score > 0:
            weighted_sum += price * score
            total_weight += score
    if total_weight > 0:
        return weighted_sum / total_weight
    return None


def _compute_bands(
    base_arv: float,
    sold_comps: List[Dict[str, Any]],
    active_comps: List[Dict[str, Any]],
    subj_sqft: float,
) -> Tuple[float, float]:
    """
    Conservative: 25th percentile of sold comp ppsf × sqft, floor at base * 0.88
    Aggressive: active listings provide ceiling, cap at base * 1.12
    """
    sold_ppsfs = []
    for c in sold_comps:
        ppsf = _safe_float(c.get("price_per_sqft"))
        if ppsf and ppsf > 0:
            sold_ppsfs.append(ppsf)

    active_ppsfs = []
    for c in active_comps:
        ppsf = _safe_float(c.get("price_per_sqft"))
        if ppsf and ppsf > 0:
            active_ppsfs.append(ppsf)

    if sold_ppsfs and subj_sqft > 0:
        sorted_ppsf = sorted(sold_ppsfs)
        p25_idx = max(0, len(sorted_ppsf) // 4)
        conservative = sorted_ppsf[p25_idx] * subj_sqft
    else:
        conservative = base_arv * 0.92

    conservative = max(conservative, base_arv * 0.88)
    conservative = min(conservative, base_arv)

    if active_ppsfs and subj_sqft > 0:
        max_active_ppsf = max(active_ppsfs)
        aggressive_from_active = max_active_ppsf * subj_sqft
        aggressive = min(aggressive_from_active, base_arv * 1.15)
        aggressive = max(aggressive, base_arv * 1.05)
    else:
        aggressive = base_arv * 1.08

    return conservative, aggressive


def _compute_confidence(
    sold_comps: List[Dict[str, Any]],
    active_comps: List[Dict[str, Any]],
    pending_comps: List[Dict[str, Any]],
    providers: Dict[str, Dict[str, Any]],
    base_arv: Optional[float],
) -> Tuple[str, int]:
    """
    Confidence score 0-100 based on data quality.
    """
    score = 30  # baseline

    # Strong sold comps
    n_sold = len(sold_comps)
    if n_sold >= 5:
        score += 25
    elif n_sold >= 3:
        score += 18
    elif n_sold >= 1:
        score += 8

    # Recent comps (any within 6 months)
    recent = [c for c in sold_comps if (c.get("months_ago") or 99) <= 6]
    if len(recent) >= 2:
        score += 10
    elif len(recent) >= 1:
        score += 5

    # High-scoring comps
    strong = [c for c in sold_comps if (c.get("comp_score") or 0) >= 70]
    if len(strong) >= 2:
        score += 10
    elif len(strong) >= 1:
        score += 5

    # Provider agreement
    provider_values = _collect_provider_avms(providers)
    if base_arv and base_arv > 0 and len(provider_values) >= 2:
        max_diff = max(abs(v - base_arv) / base_arv for v in provider_values)
        if max_diff < 0.10:
            score += 10
        elif max_diff < 0.20:
            score += 5
        else:
            score -= 5

    # Active/pending corroboration
    if active_comps:
        score += 3
    if pending_comps:
        score += 5

    score = max(10, min(100, score))

    if score >= 65:
        label = "high"
    elif score >= 40:
        label = "medium"
    else:
        label = "low"

    return label, score


def _collect_provider_avms(providers: Dict[str, Dict[str, Any]]) -> List[float]:
    values = []
    for key, data in providers.items():
        for field in ("avm", "market_value", "value", "estimatedValue", "price"):
            v = _safe_float(data.get(field) if isinstance(data, dict) else None)
            if v and v > 0:
                values.append(v)
                break
    return values


def _estimate_land_value(
    subject: Dict[str, Any],
    providers: Dict[str, Dict[str, Any]],
) -> Optional[float]:
    # First try assessed land value from ATTOM
    attom = providers.get("attom") or {}
    assessed = _safe_float(attom.get("assessed_value"))
    if assessed and assessed > 0:
        return assessed

    # Provider AVM for the lot itself
    provider_values = _collect_provider_avms(providers)
    if provider_values:
        return statistics.median(provider_values)

    # Last sale price as fallback
    last_sale = _safe_float(subject.get("last_sale_price"))
    if last_sale and last_sale > 0:
        return last_sale

    return None


def _is_lot_comp(comp: Dict[str, Any]) -> bool:
    pt = str(comp.get("property_type") or comp.get("propertyType") or "").lower()
    return any(kw in pt for kw in ["land", "lot", "vacant", "unimproved"])
