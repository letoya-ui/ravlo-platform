# LoanMVP/services/partner_marketplace_service.py

import os
import requests

from LoanMVP.utils.safe_http import safe_call

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()


def normalize_text(value):
    return (value or "").strip().lower()


def score_partner(rating=None, review_count=0, preferred=False, verified=False):
    rating = float(rating or 0)
    review_count = int(review_count or 0)

    score = (rating * 20) + (min(review_count, 100) * 0.35)

    if preferred:
        score += 20
    if verified:
        score += 15

    return round(score, 2)


def get_place_details(place_id):
    """Fetch phone + website for a Google Place using the Place Details API."""
    if not GOOGLE_API_KEY or not place_id:
        return {}
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    try:
        res = safe_call(
            requests.get,
            url,
            params={
                "place_id": place_id,
                "fields": "formatted_phone_number,website,international_phone_number",
                "key": GOOGLE_API_KEY,
            },
            timeout=10,
        )
        res.raise_for_status()
        data = res.json()
        result = data.get("result", {}) or {}
        return {
            "phone": result.get("formatted_phone_number") or result.get("international_phone_number"),
            "website": result.get("website"),
        }
    except Exception:
        return {}


def search_google_places(location_text, category, limit=8):
    if not GOOGLE_API_KEY or not location_text or not category:
        return []

    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    query = f"{category} near {location_text}"

    try:
        res = safe_call(
            requests.get,
            url,
            params={"query": query, "key": GOOGLE_API_KEY},
            timeout=20,
        )
        res.raise_for_status()
        data = res.json()
    except Exception:
        return []

    results = []
    for place in data.get("results", [])[:limit]:
        geometry = place.get("geometry", {}).get("location", {}) or {}

        results.append({
            "name": place.get("name"),
            "business_name": place.get("name"),
            "category": category,
            "address": place.get("formatted_address"),
            "rating": place.get("rating"),
            "review_count": place.get("user_ratings_total", 0),
            "external_id": place.get("place_id"),
            "latitude": geometry.get("lat"),
            "longitude": geometry.get("lng"),
            "source": "google",
            "score": score_partner(
                rating=place.get("rating"),
                review_count=place.get("user_ratings_total", 0),
            ),
            "is_internal": False,
        })

    return sorted(results, key=lambda x: x.get("score", 0), reverse=True)


def search_internal_partners(Partner, category=None, city=None, state=None,
                             zip_code=None, name_q=None):
    """Search Ravlo-network partners with location + category filtering.

    Filters by the correct column names on the Partner model (active/approved,
    not is_active/is_approved which don't exist).  Location matching uses
    zip_code → city+state → state fallback, and also searches the free-text
    service_area field so partners who cover a metro show up correctly.
    """
    from sqlalchemy import or_

    query = Partner.query.filter(
        Partner.active.is_(True),
        Partner.approved.is_(True),
    )

    if category:
        query = query.filter(
            or_(
                Partner.category.ilike(f"%{category}%"),
                Partner.type.ilike(f"%{category}%"),
            )
        )

    if name_q:
        query = query.filter(
            or_(
                Partner.name.ilike(f"%{name_q}%"),
                Partner.company.ilike(f"%{name_q}%"),
            )
        )

    # Location: zip is most precise; fall back to city/state; also search
    # the free-text service_area field for matches like "Atlanta Metro"
    if zip_code:
        query = query.filter(
            or_(
                Partner.zip_code.ilike(f"%{zip_code}%"),
                Partner.service_area.ilike(f"%{zip_code}%"),
            )
        )
    elif city and state:
        query = query.filter(
            or_(
                (Partner.city.ilike(f"%{city}%") & Partner.state.ilike(f"%{state}%")),
                Partner.service_area.ilike(f"%{city}%"),
                Partner.service_area.ilike(f"%{state}%"),
            )
        )
    elif city:
        query = query.filter(
            or_(
                Partner.city.ilike(f"%{city}%"),
                Partner.service_area.ilike(f"%{city}%"),
            )
        )
    elif state:
        query = query.filter(
            or_(
                Partner.state.ilike(f"%{state}%"),
                Partner.service_area.ilike(f"%{state}%"),
            )
        )

    partners = query.order_by(
        Partner.featured.desc(),
        Partner.rating.desc().nullslast(),
    ).limit(30).all()

    serialized = []
    for p in partners:
        # Gracefully handle partners that may be missing newer columns
        rating      = getattr(p, "rating", None)
        review_count = getattr(p, "review_count", 0) or 0
        is_preferred = getattr(p, "is_preferred", False) or False
        is_verified  = getattr(p, "is_verified", False) or False

        serialized.append({
            "id":            p.id,
            "name":          getattr(p, "business_name", None) or p.name,
            "business_name": getattr(p, "business_name", None),
            "category":      p.category,
            "type":          p.type,
            "address":       p.address,
            "city":          p.city,
            "state":         p.state,
            "zip_code":      p.zip_code,
            "service_area":  p.service_area,
            "phone":         p.phone,
            "email":         p.email,
            "website":       p.website,
            "bio":           p.bio,
            "rating":        rating,
            "review_count":  review_count,
            "is_verified":   is_verified,
            "is_preferred":  is_preferred,
            "source":        "ravlo",
            "score":         score_partner(
                rating=rating,
                review_count=review_count,
                preferred=is_preferred,
                verified=is_verified,
            ),
            "is_internal":   True,
        })

    serialized.sort(key=lambda x: (
        0 if x.get("is_preferred") else 1,
        -(x.get("score") or 0),
    ))

    return serialized
