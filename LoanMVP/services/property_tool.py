import os
import requests
from typing import Any, Dict, List, Optional


ATTOM_API_KEY = os.getenv("ATTOM_API_KEY", "").strip()
ATTOM_BASE_URL = os.getenv("ATTOM_BASE_URL", "https://api.gateway.attomdata.com/propertyapi/v1.0.0").strip()

DEFAULT_TIMEOUT = int(os.getenv("PROPERTY_API_TIMEOUT", "30"))


class PropertyAPIError(Exception):
    pass


def _attom_headers() -> Dict[str, str]:
    if not ATTOM_API_KEY:
        raise PropertyAPIError("ATTOM_API_KEY is not set.")
    return {
        "apikey": ATTOM_API_KEY,
        "Accept": "application/json",
    }


def _safe_get(data: Any, *keys, default=None):
    """
    Safe nested lookup:
    _safe_get(obj, "a", "b", 0, "c")
    """
    cur = data
    for key in keys:
        try:
            if isinstance(cur, dict):
                cur = cur.get(key)
            elif isinstance(cur, list) and isinstance(key, int):
                cur = cur[key]
            else:
                return default
        except Exception:
            return default
        if cur is None:
            return default
    return cur


def _to_float(value: Any) -> Optional[float]:
    try:
        if value in (None, "", "null"):
            return None
        return float(value)
    except Exception:
        return None


def _to_int(value: Any) -> Optional[int]:
    try:
        if value in (None, "", "null"):
            return None
        return int(float(value))
    except Exception:
        return None


def _request_attom(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{ATTOM_BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    try:
        res = requests.get(
            url,
            headers=_attom_headers(),
            params=params or {},
            timeout=DEFAULT_TIMEOUT,
        )
    except requests.RequestException as e:
        raise PropertyAPIError(f"ATTOM request failed: {e}")

    if not res.ok:
        snippet = (res.text or "")[:500]
        raise PropertyAPIError(
            f"ATTOM error {res.status_code} for {url}. Response: {snippet}"
        )

    try:
        return res.json()
    except Exception:
        snippet = (res.text or "")[:500]
        raise PropertyAPIError(f"ATTOM returned invalid JSON. Response: {snippet}")


def _normalize_attom_property(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizes one ATTOM property result into a clean Ravlo-friendly shape.
    ATTOM responses can vary by endpoint, so we safely probe multiple paths.
    """

    address_one_line = _safe_get(raw, "address", "oneLine")
    line1 = _safe_get(raw, "address", "line1")
    city = _safe_get(raw, "address", "locality")
    state = _safe_get(raw, "address", "countrySubd")
    zip_code = _safe_get(raw, "address", "postal1")

    latitude = _to_float(_safe_get(raw, "location", "latitude"))
    longitude = _to_float(_safe_get(raw, "location", "longitude"))

    beds = _to_int(_safe_get(raw, "building", "rooms", "beds"))
    baths_total = _to_float(_safe_get(raw, "building", "rooms", "bathstotal"))
    sqft = _to_int(_safe_get(raw, "building", "size", "universalsize"))
    lot_sqft = _to_int(_safe_get(raw, "lot", "lotsize1"))
    year_built = _to_int(_safe_get(raw, "summary", "yearbuilt"))

    property_type = (
        _safe_get(raw, "summary", "proptype")
        or _safe_get(raw, "summary", "propertyType")
        or _safe_get(raw, "building", "summary", "proptype")
    )

    # Sale / assessed / estimated values
    last_sale_price = _to_float(
        _safe_get(raw, "sale", "amount", "saleamt")
        or _safe_get(raw, "sale", "saleamt")
        or _safe_get(raw, "summary", "saleamt")
    )

    last_sale_date = (
        _safe_get(raw, "sale", "amount", "saledate")
        or _safe_get(raw, "sale", "saletransdate")
        or _safe_get(raw, "summary", "saletransdate")
    )

    assessed_value = _to_float(
        _safe_get(raw, "assessment", "assessed", "assdttlvalue")
        or _safe_get(raw, "assessment", "market", "mktttlvalue")
        or _safe_get(raw, "assessment", "assdttlvalue")
    )

    attom_id = _safe_get(raw, "identifier", "attomId") or _safe_get(raw, "identifier", "Id")

    return {
        "attom_id": attom_id,
        "address": address_one_line or line1,
        "address_line1": line1,
        "city": city,
        "state": state,
        "zip_code": zip_code,
        "latitude": latitude,
        "longitude": longitude,
        "beds": beds,
        "baths": baths_total,
        "square_feet": sqft,
        "lot_size_sqft": lot_sqft,
        "year_built": year_built,
        "property_type": property_type,
        "last_sale_price": last_sale_price,
        "last_sale_date": last_sale_date,
        "assessed_value": assessed_value,
        "raw": raw,
    }


def _extract_property_list(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    ATTOM commonly returns payload['property'] as the main list.
    """
    props = payload.get("property") or []
    if isinstance(props, list):
        return props
    return []


def search_properties_by_zip(postalcode: str, page: int = 1, page_size: int = 25) -> List[Dict[str, Any]]:
    payload = _request_attom(
        "property/address",
        params={
            "postalcode": postalcode,
            "page": page,
            "pagesize": page_size,
        },
    )
    properties = _extract_property_list(payload)
    return [_normalize_attom_property(p) for p in properties]


def search_property_by_address(
    address1: str,
    postalcode: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Flexible ATTOM address search.
    """
    params: Dict[str, Any] = {"address1": address1}

    if postalcode:
        params["postalcode"] = postalcode
    if city:
        params["locality"] = city
    if state:
        params["region"] = state

    payload = _request_attom("property/address", params=params)
    properties = _extract_property_list(payload)
    return [_normalize_attom_property(p) for p in properties]


def get_best_property_match(
    address1: str,
    postalcode: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    results = search_property_by_address(
        address1=address1,
        postalcode=postalcode,
        city=city,
        state=state,
    )
    return results[0] if results else None


def get_property_detail_by_attom_id(attom_id: str) -> Optional[Dict[str, Any]]:
    """
    You can expand this later if you want deeper detail endpoints.
    For now, this uses ATTOM detail profile endpoint pattern.
    """
    payload = _request_attom(
        "property/detail",
        params={"attomid": attom_id},
    )
    properties = _extract_property_list(payload)
    if not properties:
        return None
    return _normalize_attom_property(properties[0])


def get_property_search_result(
    address: Optional[str] = None,
    postalcode: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
) -> Dict[str, Any]:
    """
    Ravlo-friendly wrapper for routes/services.
    """

    if address:
        results = search_property_by_address(
            address1=address,
            postalcode=postalcode,
            city=city,
            state=state,
        )
    elif postalcode:
        results = search_properties_by_zip(
            postalcode=postalcode,
            page=page,
            page_size=page_size,
        )
    else:
        raise PropertyAPIError("You must provide either address or postalcode.")

    return {
        "ok": True,
        "count": len(results),
        "properties": results,
    }


def build_property_card_data(prop: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simple UI-ready transform for investor cards or Deal Finder.
    """
    return {
        "title": prop.get("address") or "Property",
        "subtitle": ", ".join(
            [x for x in [prop.get("city"), prop.get("state"), prop.get("zip_code")] if x]
        ),
        "price": prop.get("last_sale_price"),
        "beds": prop.get("beds"),
        "baths": prop.get("baths"),
        "sqft": prop.get("square_feet"),
        "lot_size_sqft": prop.get("lot_size_sqft"),
        "year_built": prop.get("year_built"),
        "property_type": prop.get("property_type"),
        "latitude": prop.get("latitude"),
        "longitude": prop.get("longitude"),
        "attom_id": prop.get("attom_id"),
    }
