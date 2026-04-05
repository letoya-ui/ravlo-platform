from typing import Dict, Any


def clamp(n: float, low: float, high: float) -> float:
    return max(low, min(high, n))


def compute_deal_score(profile: Dict[str, Any]) -> Dict[str, Any]:
    price = float(profile.get("price") or 0)
    traditional_cap_rate = float(profile.get("traditional_cap_rate") or 0)
    airbnb_cap_rate = float(profile.get("airbnb_cap_rate") or 0)
    traditional_coc = float(profile.get("traditional_coc") or 0)
    airbnb_coc = float(profile.get("airbnb_coc") or 0)
    occupancy = float(profile.get("occupancy_rate") or 0)
    distressed = bool(profile.get("distressed"))
    year_built = int(profile.get("year_built") or 0) if profile.get("year_built") else 0
    rent_to_price = float(profile.get("rent_to_price_ratio") or 0)

    rental_score = (
        clamp(traditional_cap_rate * 4.5, 0, 30) +
        clamp(traditional_coc * 2.5, 0, 25) +
        clamp(rent_to_price * 120, 0, 20)
    )

    airbnb_score = (
        clamp(airbnb_cap_rate * 4.5, 0, 30) +
        clamp(airbnb_coc * 2.5, 0, 25) +
        clamp(occupancy * 0.25, 0, 20)
    )

    distress_bonus = 10 if distressed else 0
    age_penalty = 0
    if year_built and year_built < 1960:
        age_penalty = 6
    elif year_built and year_built < 1980:
        age_penalty = 3

    rental_total = clamp(rental_score + distress_bonus - age_penalty, 0, 100)
    airbnb_total = clamp(airbnb_score - age_penalty, 0, 100)

    if distressed and rental_total >= 65:
        recommended = "BRRRR"
    elif rental_total >= airbnb_total and rental_total >= 60:
        recommended = "Rental"
    elif airbnb_total > rental_total and airbnb_total >= 60:
        recommended = "Airbnb"
    elif distressed:
        recommended = "Flip"
    else:
        recommended = "Hold / Review"

    overall = round(max(rental_total, airbnb_total), 1)

    return {
        "overall_score": overall,
        "rental_score": round(rental_total, 1),
        "airbnb_score": round(airbnb_total, 1),
        "recommended_strategy": recommended,
        "score_reasons": [
            f"Traditional cap rate: {profile.get('traditional_cap_rate') or 0}",
            f"Traditional CoC: {profile.get('traditional_coc') or 0}",
            f"Airbnb cap rate: {profile.get('airbnb_cap_rate') or 0}",
            f"Airbnb occupancy: {profile.get('occupancy_rate') or 0}",
            f"Distressed: {'Yes' if distressed else 'No'}",
        ],
    }
