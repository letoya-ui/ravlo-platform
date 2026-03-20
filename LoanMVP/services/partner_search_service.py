# services/partner_search_service.py

import requests
import os

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

def search_external_partners(location, service):
    query = f"{service} near {location}"

    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"

    params = {
        "query": query,
        "key": GOOGLE_API_KEY
    }

    res = requests.get(url, params=params)
    data = res.json()

    results = []

    for place in data.get("results", [])[:5]:
        results.append({
            "name": place.get("name"),
            "address": place.get("formatted_address"),
            "rating": place.get("rating"),
            "reviews": place.get("user_ratings_total"),
            "source": "google",
        })

    return results
