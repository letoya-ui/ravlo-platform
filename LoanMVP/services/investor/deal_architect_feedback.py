# LoanMVP/services/investor/deal_architect_feedback.py
"""
Reads contractor_feedback, realtor_market_data, and lo_quotes
from deal.results_json and produces calibration signals that
Deal Architect uses to sharpen its estimates.

Used by:
  - _build_deal_architect_payload()  (GPU engine payload builder)
  - v1_deal_architect_underwrite()   (Render fallback endpoint)
"""

from __future__ import annotations

from typing import Any, Dict, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _f(val: Any, default: float = 0.0) -> float:
    try:
        if val in (None, "", "None"):
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _pct(val: Any) -> Optional[float]:
    """Returns a percentage as a plain float (e.g. 12.5 for 12.5%)."""
    try:
        if val in (None, "", "None"):
            return None
        return float(val)
    except (TypeError, ValueError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Contractor feedback
# ─────────────────────────────────────────────────────────────────────────────

def read_contractor_signals(results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reads contractor_feedback[] from results_json.

    Each entry has:
        ai_estimate       – what Deal Architect originally estimated
        contractor_total  – what the real contractor said it would cost
        delta             – contractor_total - ai_estimate
        delta_pct         – delta as % of ai_estimate

    Returns:
        {
            "has_data": bool,
            "entries": int,
            "ai_estimate_avg": float,       # average AI rehab estimate across submissions
            "contractor_avg": float,        # average real contractor total
            "avg_delta": float,             # contractor - AI (positive = AI underestimated)
            "avg_delta_pct": float,         # % over/under
            "calibrated_rehab": float,      # best rehab estimate after calibration
            "confidence": str,              # "high" / "medium" / "low"
            "signal": str,                  # human-readable summary
        }
    """
    feedback = results.get("contractor_feedback") or []
    if not isinstance(feedback, list) or not feedback:
        return {"has_data": False}

    ai_estimates = []
    contractor_totals = []
    deltas = []

    for entry in feedback:
        if not isinstance(entry, dict):
            continue
        ai_est = _f(entry.get("ai_estimate"))
        co_tot = _f(entry.get("contractor_total"))
        delta  = _f(entry.get("delta"))

        if ai_est > 0 and co_tot > 0:
            ai_estimates.append(ai_est)
            contractor_totals.append(co_tot)
            deltas.append(delta)

    if not contractor_totals:
        return {"has_data": False}

    n = len(contractor_totals)
    ai_avg  = sum(ai_estimates) / n
    co_avg  = sum(contractor_totals) / n
    d_avg   = sum(deltas) / n
    d_pct   = (d_avg / ai_avg * 100) if ai_avg > 0 else 0.0

    # Calibrated rehab = contractor average (real-world beats model)
    calibrated = co_avg

    confidence = "high" if n >= 3 else ("medium" if n == 2 else "low")

    if d_avg > 0:
        signal = (
            f"Contractors came in ${d_avg:,.0f} ({d_pct:.1f}%) above AI estimate on average. "
            f"Rehab budget adjusted upward."
        )
    elif d_avg < 0:
        signal = (
            f"Contractors came in ${abs(d_avg):,.0f} ({abs(d_pct):.1f}%) below AI estimate. "
            f"Rehab budget adjusted downward."
        )
    else:
        signal = "Contractor quotes align with AI estimate."

    return {
        "has_data": True,
        "entries": n,
        "ai_estimate_avg": round(ai_avg, 2),
        "contractor_avg": round(co_avg, 2),
        "avg_delta": round(d_avg, 2),
        "avg_delta_pct": round(d_pct, 2),
        "calibrated_rehab": round(calibrated, 2),
        "confidence": confidence,
        "signal": signal,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Realtor market data
# ─────────────────────────────────────────────────────────────────────────────

def read_realtor_signals(results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reads realtor_market_data from results_json.

    Entry has:
        suggested_arv   – realtor's ARV estimate
        arv_delta       – suggested_arv - deal.arv  (positive = realtor thinks higher)
        arv_delta_pct
        comps_note
        market_note
        days_on_market
        list_price

    Returns:
        {
            "has_data": bool,
            "realtor_arv": float,
            "ai_arv": float,
            "arv_delta": float,
            "arv_delta_pct": float,
            "calibrated_arv": float,
            "confidence": str,
            "signal": str,
            "days_on_market": int | None,
            "list_price": float | None,
            "comps_note": str,
            "market_note": str,
        }
    """
    rmd = results.get("realtor_market_data")
    if not isinstance(rmd, dict) or not rmd:
        return {"has_data": False}

    realtor_arv = _f(rmd.get("suggested_arv"))
    arv_delta   = _f(rmd.get("arv_delta"))
    arv_pct     = _pct(rmd.get("arv_delta_pct"))
    dom         = rmd.get("days_on_market")
    list_price  = _f(rmd.get("list_price")) or None
    comps_note  = (rmd.get("comps_note") or "").strip()
    market_note = (rmd.get("market_note") or "").strip()

    if realtor_arv <= 0:
        return {"has_data": False}

    # Blended ARV: weight realtor 60% when delta is meaningful
    if abs(arv_delta) > realtor_arv * 0.03:
        # Meaningful disagreement — trust the realtor more
        calibrated_arv = realtor_arv
        confidence = "high"
    else:
        calibrated_arv = realtor_arv
        confidence = "medium"

    if arv_delta > 0:
        signal = (
            f"Realtor ARV (${realtor_arv:,.0f}) is ${arv_delta:,.0f} above AI estimate. "
            f"ARV adjusted upward."
        )
    elif arv_delta < 0:
        signal = (
            f"Realtor ARV (${realtor_arv:,.0f}) is ${abs(arv_delta):,.0f} below AI estimate. "
            f"ARV adjusted downward."
        )
    else:
        signal = f"Realtor confirms AI ARV estimate of ${realtor_arv:,.0f}."

    return {
        "has_data": True,
        "realtor_arv": round(realtor_arv, 2),
        "arv_delta": round(arv_delta, 2),
        "arv_delta_pct": round(arv_pct, 2) if arv_pct is not None else None,
        "calibrated_arv": round(calibrated_arv, 2),
        "confidence": confidence,
        "signal": signal,
        "days_on_market": int(dom) if dom is not None else None,
        "list_price": round(list_price, 2) if list_price else None,
        "comps_note": comps_note,
        "market_note": market_note,
    }


# ─────────────────────────────────────────────────────────────────────────────
# LO quote signals
# ─────────────────────────────────────────────────────────────────────────────

def read_lo_signals(results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reads lo_quotes[] from results_json.

    Each entry has:
        quoted         – amount the LO quoted
        rate           – rate offered
        points
        term_months
        monthly_payment
        decision       – "quote" | "approve" | "decline"
        delta          – quoted - requested
        delta_pct

    Returns:
        {
            "has_data": bool,
            "entries": int,
            "best_quote": dict | None,      # lowest rate among quotes
            "approved_capital": dict | None, # capital_approved block if present
            "avg_rate": float,
            "avg_points": float,
            "total_quoted": float,
            "has_approval": bool,
            "signal": str,
        }
    """
    quotes = results.get("lo_quotes") or []
    capital_approved = results.get("capital_approved")

    if not isinstance(quotes, list) or not quotes:
        if capital_approved:
            return {
                "has_data": True,
                "entries": 0,
                "best_quote": None,
                "approved_capital": capital_approved,
                "avg_rate": _f(capital_approved.get("rate")),
                "avg_points": _f(capital_approved.get("points")),
                "total_quoted": _f(capital_approved.get("amount")),
                "has_approval": True,
                "signal": (
                    f"Capital approved at ${_f(capital_approved.get('amount')):,.0f} "
                    f"@ {_f(capital_approved.get('rate'))}% by "
                    f"{capital_approved.get('company', 'lender')}."
                ),
            }
        return {"has_data": False}

    valid_quotes = [
        q for q in quotes
        if isinstance(q, dict)
        and _f(q.get("quoted")) > 0
        and _f(q.get("rate")) > 0
    ]

    if not valid_quotes:
        return {"has_data": False}

    n = len(valid_quotes)
    rates  = [_f(q.get("rate"))   for q in valid_quotes]
    points = [_f(q.get("points")) for q in valid_quotes]
    quoted = [_f(q.get("quoted")) for q in valid_quotes]

    avg_rate   = sum(rates)  / n
    avg_points = sum(points) / n
    total      = sum(quoted) / n  # average quoted amount

    # Best quote = lowest rate
    best = min(valid_quotes, key=lambda q: _f(q.get("rate")))

    has_approval = bool(capital_approved) or any(
        q.get("decision") == "approve" for q in valid_quotes
    )

    if has_approval:
        approved = capital_approved or next(
            (q for q in valid_quotes if q.get("decision") == "approve"), None
        )
        if approved:
            signal = (
                f"Capital approved: ${_f(approved.get('amount') or approved.get('quoted')):,.0f} "
                f"@ {_f(approved.get('rate'))}% "
                f"by {approved.get('company', 'lender')}."
            )
        else:
            signal = "Capital approval recorded."
    else:
        signal = (
            f"{n} LO quote(s) received. Best rate: {_f(best.get('rate'))}% "
            f"on ${_f(best.get('quoted')):,.0f}. Average across quotes: {avg_rate:.2f}%."
        )

    return {
        "has_data": True,
        "entries": n,
        "best_quote": best,
        "approved_capital": capital_approved,
        "avg_rate": round(avg_rate, 3),
        "avg_points": round(avg_points, 3),
        "total_quoted": round(total, 2),
        "has_approval": has_approval,
        "signal": signal,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Master reader — combines all three signals
# ─────────────────────────────────────────────────────────────────────────────

def read_all_feedback_signals(results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Entry point. Call this before building the Deal Architect payload.

    Returns:
        {
            "contractor": {...},
            "realtor": {...},
            "lo": {...},
            "calibrated": {
                "rehab_cost": float | None,   # best rehab estimate
                "arv": float | None,           # best ARV estimate
                "rate": float | None,          # best LO rate
                "capital_amount": float | None,
                "has_approval": bool,
            },
            "signals": [str, ...],             # human-readable list for UI / AI prompt
        }
    """
    contractor = read_contractor_signals(results)
    realtor    = read_realtor_signals(results)
    lo         = read_lo_signals(results)

    signals = []
    if contractor.get("has_data"):
        signals.append(contractor["signal"])
    if realtor.get("has_data"):
        signals.append(realtor["signal"])
    if lo.get("has_data"):
        signals.append(lo["signal"])

    calibrated = {
        "rehab_cost":      contractor.get("calibrated_rehab") if contractor.get("has_data") else None,
        "arv":             realtor.get("calibrated_arv")      if realtor.get("has_data")    else None,
        "rate":            lo.get("avg_rate")                 if lo.get("has_data")         else None,
        "capital_amount":  lo.get("total_quoted")             if lo.get("has_data")         else None,
        "has_approval":    bool(lo.get("has_approval")),
    }

    return {
        "contractor": contractor,
        "realtor":    realtor,
        "lo":         lo,
        "calibrated": calibrated,
        "signals":    signals,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Calibrated fallback underwriter
# ─────────────────────────────────────────────────────────────────────────────

def calibrated_underwrite(
    *,
    asking_price: float,
    arv: float = 0.0,
    monthly_rent: float = 0.0,
    rehab_cost: float = 0.0,
    feedback: Dict[str, Any],
    down_payment_pct: float = 20.0,
    interest_rate: float = 8.5,
    hold_years: float = 5.0,
    annual_tax_rate: float = 0.012,
    annual_insurance_rate: float = 0.005,
    comps: list = None,
) -> Dict[str, Any]:
    """
    Fallback underwriter used when the GPU engine is offline.
    Uses feedback signals to calibrate ARV and rehab cost before
    running the same underwriting math as v1_deal_architect_underwrite.
    """
    cal = feedback.get("calibrated", {})

    # Apply calibrated values if available
    arv       = cal.get("arv")       or arv       or asking_price * 1.15
    rehab     = cal.get("rehab_cost") or rehab_cost or asking_price * 0.10
    rate      = cal.get("rate")       or interest_rate
    cap_amt   = cal.get("capital_amount") or asking_price * 0.70

    # Deal math
    total_cost    = asking_price + rehab
    gross_profit  = arv - total_cost
    holding_cost  = total_cost * 0.06
    selling_cost  = arv * 0.07
    net_profit    = gross_profit - holding_cost - selling_cost

    annual_taxes    = asking_price * annual_tax_rate
    annual_ins      = asking_price * annual_insurance_rate
    annual_debt_svc = cap_amt * (rate / 100)
    noi             = (monthly_rent * 12) - annual_taxes - annual_ins
    dscr            = round(noi / annual_debt_svc, 2) if annual_debt_svc > 0 else None

    ltv  = round(cap_amt / arv, 3) if arv else None

    # Score
    flip_strength   = max(0, min(40, round(net_profit / max(total_cost, 1) * 100 * 0.4)))
    rental_strength = max(0, min(30, round((dscr or 0) / 1.25 * 30)))
    market_signal   = 60  # static until live market data wired
    deal_score      = max(1, min(100, flip_strength + rental_strength + market_signal // 3))

    # Opportunity tier
    if deal_score >= 78:
        tier    = "A"
        verdict = "Strong proceed"
        rec     = "Buy & Hold" if (dscr or 0) >= 1.15 else "Fix & Flip"
    elif deal_score >= 62:
        tier    = "B"
        verdict = "Proceed with conditions"
        rec     = "Fix & Flip"
    else:
        tier    = "C"
        verdict = "Caution"
        rec     = "Review Required"

    strengths = []
    risks     = []

    if net_profit > 50000:
        strengths.append(f"Net flip profit estimated at ${net_profit:,.0f}.")
    if (dscr or 0) >= 1.25:
        strengths.append("Debt coverage exceeds standard DSCR threshold.")
    if cal.get("arv"):
        strengths.append("ARV calibrated by realtor market data.")
    if cal.get("rehab_cost"):
        strengths.append("Rehab estimate calibrated by contractor submission.")
    if cal.get("has_approval"):
        strengths.append("Capital approval already received from LO.")

    if net_profit <= 0:
        risks.append("Flip scenario shows negative net profit at current pricing.")
    if (dscr or 0) < 1.10:
        risks.append("DSCR is thin — may not qualify for standard lending.")
    if ltv and ltv > 0.80:
        risks.append("LTV is above 80% — higher leverage risk.")
    if not cal.get("arv") and not arv:
        risks.append("No ARV data — estimate needs validation.")

    # Feedback signals as context
    signal_list = feedback.get("signals", [])

    return {
        "summary":          f"{rec} is currently favored based on calibrated deal signals.",
        "recommended_type": rec,
        "deal_score":       deal_score,
        "opportunity_tier": tier,
        "cost_low":         round(total_cost * 0.95, 2),
        "cost_high":        round(total_cost * 1.05, 2),
        "estimated_value":  round(arv, 2),
        "next_step":        "Validate underwriting docs and confirm rent/comp assumptions.",
        "calibrated_inputs": {
            "arv":             round(arv, 2),
            "rehab_cost":      round(rehab, 2),
            "net_profit":      round(net_profit, 2),
            "ltv":             ltv,
            "dscr":            dscr,
            "capital_amount":  round(cap_amt, 2),
            "rate":            rate,
        },
        "feedback_signals": signal_list,
        "meta": {
            "all_in_low":            round(total_cost * 0.95, 2),
            "all_in_high":           round(total_cost * 1.05, 2),
            "estimated_margin_low":  round(arv - total_cost * 1.05, 2),
            "estimated_margin_high": round(arv - total_cost * 0.95, 2),
            "monthly_rent_estimate": round(monthly_rent, 2),
            "noi_estimate":          round(noi, 2),
            "dscr_estimate":         dscr,
            "verdict_breakdown": {
                "verdict":   verdict,
                "subscores": {
                    "flip":    flip_strength,
                    "rental":  rental_strength,
                    "market":  market_signal // 3,
                },
                "strengths": strengths,
                "risks":     risks,
            },
            "feedback_used": {
                "contractor": feedback.get("contractor", {}).get("has_data", False),
                "realtor":    feedback.get("realtor",    {}).get("has_data", False),
                "lo":         feedback.get("lo",         {}).get("has_data", False),
            },
        },
    }