def build_deal_thesis(item: dict) -> list:
    """
    Generates human-readable reasons WHY this is a deal.
    This is what creates the "wow".
    """
    reasons = []

    price = item.get("price") or 0
    arv = item.get("arv") or 0
    rehab = item.get("rehab") or 0

    metrics = item.get("metrics") or {}
    roi = metrics.get("roi") or 0
    profit = metrics.get("profit") or 0
    cashflow = (
        metrics.get("net_cashflow_mo")
        or metrics.get("net_cashflow")
        or 0
    )

    # VALUE GAP
    if price and arv:
        try:
            discount = (arv - price) / arv
            if discount > 0.15:
                reasons.append("Priced significantly below market value")
            elif discount > 0.08:
                reasons.append("Below estimated value range")
        except Exception:
            pass

    # FLIP SIGNAL
    if profit > 50000:
        reasons.append("Strong flip profit potential")
    elif profit > 25000:
        reasons.append("Solid flip margin")

    # ROI
    if roi > 0.25:
        reasons.append("High ROI opportunity")
    elif roi > 0.18:
        reasons.append("Above-average ROI")

    # RENT FALLBACK
    if cashflow and cashflow > 250:
        reasons.append("Rental fallback remains cash-flow positive")

    # REHAB SIGNAL
    if rehab:
        if rehab < 25000:
            reasons.append("Light rehab — faster turnaround")
        elif rehab < 60000:
            reasons.append("Moderate rehab with upside")
        else:
            reasons.append("Heavy value-add opportunity")

    if not reasons:
        reasons.append("Meets baseline investment criteria")

    return reasons


def compute_ravlo_score(item: dict) -> dict:
    """
    Stronger scoring engine combining flip, rental, and risk signals.
    """
    metrics = item.get("metrics") or {}

    roi = metrics.get("roi") or 0
    profit = metrics.get("profit") or 0
    cashflow = (
        metrics.get("net_cashflow_mo")
        or metrics.get("net_cashflow")
        or 0
    )

    price = item.get("price") or 0
    arv = item.get("arv") or 0
    rehab = item.get("rehab") or 0

    score = 50
    risk = 0

    # ROI
    if roi > 0.30:
        score += 25
    elif roi > 0.20:
        score += 18
    elif roi > 0.15:
        score += 10

    # PROFIT
    if profit > 75000:
        score += 20
    elif profit > 40000:
        score += 14
    elif profit > 20000:
        score += 8

    # CASHFLOW
    if cashflow > 500:
        score += 15
    elif cashflow > 250:
        score += 10

    # DISCOUNT
    if price and arv:
        try:
            discount = (arv - price) / arv
            if discount > 0.15:
                score += 10
            elif discount > 0.08:
                score += 5
        except Exception:
            pass

    # RISK
    if rehab > 70000:
        risk += 10
    if roi < 0.12:
        risk += 10
    if profit < 15000:
        risk += 8

    score = max(1, min(100, round(score - risk)))

    if score >= 80:
        label = "Strong Deal"
    elif score >= 65:
        label = "Good Deal"
    elif score >= 50:
        label = "Borderline"
    else:
        label = "High Risk"

    return {
        "score": score,
        "label": label,
        "risk": risk,
    }


def determine_primary_and_fallback(item: dict) -> dict:
    """
    Gives investor confidence and a fallback plan.
    """
    comparison = item.get("comparison") or {}

    flip = comparison.get("flip") or {}
    rental = comparison.get("rental") or {}
    airbnb = comparison.get("airbnb") or {}

    flip_profit = flip.get("profit") or 0
    rental_cash = (
        rental.get("net_cashflow_mo")
        or rental.get("net_cashflow")
        or 0
    )
    airbnb_cash = (
        airbnb.get("net_monthly")
        or airbnb.get("net_cashflow_mo")
        or 0
    )

    primary = "Review"
    fallback = None

    if flip_profit > 40000:
        primary = "Flip"
        if rental_cash > 200:
            fallback = "Rental"
    elif rental_cash > 250:
        primary = "Rental"
    elif airbnb_cash > 500:
        primary = "Airbnb"

    return {
        "primary": primary,
        "fallback": fallback,
    }
