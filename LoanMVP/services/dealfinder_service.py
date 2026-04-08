from typing import Dict, Any

from LoanMVP.services.attom_service import (
    get_property_detail,
    extract_core_fields as extract_attom_fields,
    AttomServiceError,
)
from LoanMVP.services.mashvisor_service import (
    get_property_analytics,
    extract_core_fields as extract_mash_fields,
    MashvisorServiceError,
)
from LoanMVP.services.dealfinder_normalizer import normalize_property
from LoanMVP.services.dealfinder_scoring import compute_deal_score
import requests

RENTCAST_API_KEY = d0bdb63befcc468897409c4293fd5049

def build_dealfinder_profile(
    address: str,
    city: str,
    state: str,
    zip_code: str = "",
    property_type: str = "single_family",
) -> Dict[str, Any]:
    errors = []
    attom_core = {}
    mash_core = {}

    try:
        attom_raw = get_property_detail(address=address, city=city, state=state, postalcode=zip_code)
        attom_core = extract_attom_fields(attom_raw)
    except AttomServiceError as e:
        errors.append(str(e))

    try:
        mash_raw = get_property_analytics(
            address=address,
            city=city,
            state=state,
            zip_code=zip_code,
            property_type=property_type,
        )
        mash_core = extract_mash_fields(mash_raw)
    except MashvisorServiceError as e:
        errors.append(str(e))

    if not attom_core and not mash_core:
        return {
            "ok": False,
            "errors": errors or ["No provider returned results."],
            "profile": {},
            "scoring": {},
        }

    profile = normalize_property(attom_core, mash_core)
    scoring = compute_deal_score(profile)

    return {
        "ok": True,
        "errors": errors,
        "profile": profile,
        "scoring": scoring,
        "source_status": {
            "attom": bool(attom_core),
            "mashvisor": bool(mash_core),
        },
    }



def get_rentcast_data(address, city, state, zip_code):
    try:
        url = "https://api.rentcast.io/v1/avm/rent/long-term"

        params = {
            "address": f"{address}, {city}, {state} {zip_code}"
        }

        headers = {
            "X-Api-Key": RENTCAST_API_KEY
        }

        res = requests.get(url, headers=headers, params=params, timeout=10)

        if res.status_code != 200:
            return None

        return res.json()

    except Exception:
        return None
