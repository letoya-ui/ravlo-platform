# LoanMVP/services/partner_marketplace_service.py

import os
import requests

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


def search_google_places(location_text, category, limit=8):
    if not GOOGLE_API_KEY or not location_text or not category:
        return []

    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    query = f"{category} near {location_text}"

    try:
        res = requests.get(
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


def search_internal_partners(Partner, category=None, city=None, state=None, zip_code=None):
    query = Partner.query.filter_by(is_active=True)

    if category:
        query = query.filter(Partner.category.ilike(f"%{category}%"))

    if zip_code:
        query = query.filter(Partner.zip_code.ilike(f"%{zip_code}%"))
    elif city:
        query = query.filter(Partner.city.ilike(f"%{city}%"))
        if state:
            query = query.filter(Partner.state.ilike(f"%{state}%"))
    elif state:
        query = query.filter(Partner.state.ilike(f"%{state}%"))

    partners = query.all()

    serialized = []
    for p in partners:
        serialized.append({
            "id": p.id,
            "name": p.business_name or p.name,
            "business_name": p.business_name,
            "category": p.category,
            "address": p.address,
            "city": p.city,
            "state": p.state,
            "zip_code": p.zip_code,
            "phone": p.phone,
            "email": p.email,
            "website": p.website,
            "bio": p.bio,
            "rating": p.rating,
            "review_count": p.review_count,
            "is_verified": p.is_verified,
            "is_preferred": p.is_preferred,
            "source": "ravlo",
            "score": score_partner(
                rating=p.rating,
                review_count=p.review_count,
                preferred=p.is_preferred,
                verified=p.is_verified,
            ),
            "is_internal": True,
        })

    serialized.sort(
        key=lambda x: (
            0 if x.get("is_preferred") else 1,
            -(x.get("score") or 0)
        )
    )

    return serialized
