import os
import requests
from typing import Any, Dict, Optional, List

ATTOM_API_KEY = os.getenv("ATTOM_API_KEY", "")
ATTOM_BASE_URL = os.getenv("ATTOM_BASE_URL", "https://api.gateway.attomdata.com").rstrip("/")
TIMEOUT = int(os.getenv("DEALFINDER_TIMEOUT", "20"))

_session = requests.Session()


class AttomServiceError(Exception):
    pass


def _headers() -> Dict[str, str]:
    if not ATTOM_API_KEY:
        raise AttomServiceError("ATTOM_API_KEY is not configured.")
    return {
        "accept": "application/json",
        "apikey": ATTOM_API_KEY,
    }


def _get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{ATTOM_BASE_URL}{path}"
    try:
        res = _session.get(url, headers=_headers(), params=params or {}, timeout=TIMEOUT)
        res.raise_for_status()
        return res.json()
    except requests.HTTPError as e:
        body = ""
        try:
            body = res.text[:400]
        except Exception:
            pass
        raise AttomServiceError(f"ATTOM HTTP error: {e}. body={body}")
    except Exception as e:
        raise AttomServiceError(f"ATTOM request failed: {e}")


def search_property_by_address(address1: str, address2: str) -> Dict[str, Any]:
    """
    Example:
      address1 = "4529 Winona Court"
      address2 = "Denver, CO"
    """
    return _get(
        "/propertyapi/v1.0.0/property/detail",
        params={
            "address1": address1,
            "address2": address2,
        },
    )


def search_property_expanded(
    address: str = "",
    city: str = "",
    state: str = "",
    postalcode: str = "",
) -> Dict[str, Any]:
    """
    Safer wrapper if you have split fields and want to build address2 dynamically.
    """
    address1 = address.strip()
    address2_parts = [p.strip() for p in [city, state] if p and p.strip()]
    address2 = ", ".join(address2_parts)
    if postalcode:
        address2 = f"{address2} {postalcode}".strip()

    if not address1 or not address2:
        raise AttomServiceError("ATTOM search requires address and city/state.")
    return search_property_by_address(address1=address1, address2=address2)


def get_property_detail(address: str, city: str, state: str, postalcode: str = "") -> Dict[str, Any]:
    data = search_property_expanded(
        address=address,
        city=city,
        state=state,
        postalcode=postalcode,
    )

    props = (
        data.get("property")
        or data.get("properties")
        or data.get("response", {}).get("property")
        or []
    )

    if isinstance(props, dict):
        return props
    if isinstance(props, list) and props:
        return props[0]

    raise AttomServiceError("ATTOM returned no matching property.")


def safe_get(dct: Any, *keys: str, default=None):
    cur = dct
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def extract_core_fields(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    ATTOM payloads vary by endpoint/plan.
    This mapper is intentionally defensive.
    """
    return {
        "attom_id": raw.get("identifier", {}).get("attomId") or raw.get("attomid"),
        "apn": safe_get(raw, "identifier", "apn"),
        "fips": safe_get(raw, "area", "census", "fips"),
        "address_one_line": safe_get(raw, "address", "oneLine"),
        "address_line1": safe_get(raw, "address", "line1"),
        "city": safe_get(raw, "address", "locality"),
        "state": safe_get(raw, "address", "countrySubd"),
        "zip_code": safe_get(raw, "address", "postal1"),
        "latitude": safe_get(raw, "location", "latitude"),
        "longitude": safe_get(raw, "location", "longitude"),
        "property_type": safe_get(raw, "summary", "propType"),
        "property_sub_type": safe_get(raw, "summary", "propSubType"),
        "year_built": safe_get(raw, "summary", "yearBuilt"),
        "bedrooms": safe_get(raw, "building", "rooms", "beds"),
        "bathrooms": safe_get(raw, "building", "rooms", "bathstotal"),
        "rooms_total": safe_get(raw, "building", "rooms", "roomsTotal"),
        "sqft": safe_get(raw, "building", "size", "universalsize"),
        "lot_sqft": safe_get(raw, "lot", "lotSize1"),
        "owner_name": safe_get(raw, "owner", "owner1", "fullName"),
        "owner_occupied": safe_get(raw, "summary", "ownerOccupied"),
        "last_sale_date": safe_get(raw, "sale", "saleTransDate"),
        "last_sale_price": safe_get(raw, "sale", "amount", "saleAmt"),
        "market_value": safe_get(raw, "assessment", "market", "mktttlvalue"),
        "assessed_value": safe_get(raw, "assessment", "assessed", "assdttlvalue"),
        "tax_amount": safe_get(raw, "assessment", "tax", "taxamt"),
        "mortgage_amount": safe_get(raw, "mortgage", "amount"),
        "foreclosure_status": safe_get(raw, "foreclosure", "status"),
        "distressed": bool(safe_get(raw, "foreclosure", "status") or safe_get(raw, "preforeclosure")),
        "raw": raw,
    }
