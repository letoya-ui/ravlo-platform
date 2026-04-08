import os
import requests
from typing import Dict, Any


class RentCastServiceError(Exception):
    pass


RENTCAST_BASE_URL = os.getenv("RENTCAST_BASE_URL", "https://api.rentcast.io/v1")
RENTCAST_API_KEY = os.getenv("RENTCAST_API_KEY", "").strip()


def get_rentcast_rent_estimate(
    address: str,
    city: str,
    state: str,
    zip_code: str = "",
    property_type: str = "single_family",
) -> Dict[str, Any]:
    if not RENTCAST_API_KEY:
        raise RentCastServiceError("Missing RENTCAST_API_KEY")

    full_address = f"{address}, {city}, {state} {zip_code}".strip()

    # Adjust endpoint if your prior key setup used a different RentCast path.
    url = f"{RENTCAST_BASE_URL}/avm/rent/long-term"

    headers = {
        "X-Api-Key": RENTCAST_API_KEY,
        "Accept": "application/json",
    }

    params = {
        "address": full_address,
        "propertyType": property_type,
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=12)
    except requests.RequestException as e:
        raise RentCastServiceError(f"Request failed: {e}") from e

    if resp.status_code == 404:
        raise RentCastServiceError("No RentCast rent estimate found")

    if resp.status_code >= 400:
        raise RentCastServiceError(f"HTTP {resp.status_code}: {resp.text[:300]}")

    try:
        return resp.json() or {}
    except Exception as e:
        raise RentCastServiceError(f"Invalid JSON response: {e}") from e