import os
from typing import Optional, Dict, Any
from LoanMVP.services.attom_service import get_property_detail, AttomServiceError

def fetch_attom_data(address: str, city: str, state: str, zip_code: str = "") -> Optional[Dict[str, Any]]:
    """
    Thin wrapper around ATTOM detail lookup.
    Returns normalized ATTOM detail or None.
    """
    try:
        detail = get_property_detail(
            address=address,
            city=city,
            state=state,
            postalcode=zip_code,
        )
        return detail
    except AttomServiceError as e:
        print("ATTOM Provider Error:", e)
        return None
    except Exception as e:
        print("ATTOM Provider Exception:", e)
        return None
