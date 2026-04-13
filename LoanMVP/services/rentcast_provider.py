import os
import requests
from typing import Optional, Dict, Any

RENTCAST_API_KEY = os.getenv("RENTCAST_API_KEY")

def fetch_rentcast_data(address: str, city: str, state: str, zip_code: str = "") -> Optional[Dict[str, Any]]:
    """
    Fetch RentCast long-term rent estimate.
    Returns raw RentCast JSON or None.
    """
    try:
        url = "https://api.rentcast.io/v1/avm/rent/long-term"

        params = {
            "address": f"{address}, {city}, {state} {zip_code}".strip()
        }

        headers = {
            "X-Api-Key": RENTCAST_API_KEY
        }

        res = requests.get(url, headers=headers, params=params, timeout=10)

        if not res.ok:
            print("RentCast Provider Error:", res.text[:300])
            return None

        return res.json()

    except Exception as e:
        print("RentCast Provider Exception:", e)
        return None
