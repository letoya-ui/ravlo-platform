import os
import requests
from typing import Any, Dict, Optional

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
    address1 = (address or "").strip()
    address2_parts = [p.strip() for p in [city, state] if p and str(p).strip()]
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


def _to_float(val: Any, default: float = 0.0) -> float:
    try:
        if val in (None, "", "None"):
            return float(default)
        return float(val)
    except Exception:
        return float(default)


def _to_int(val: Any, default: int = 0) -> int:
    try:
        if val in (None, "", "None"):
            return int(default)
        return int(float(val))
    except Exception:
        return int(default)


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
        "distressed": bool(
            safe_get(raw, "foreclosure", "status")
            or safe_get(raw, "preforeclosure")
        ),

        "raw": raw,
    }


def normalize_attom_property(core: Dict[str, Any]) -> Dict[str, Any]:
    market_value = _to_float(core.get("market_value"))
    assessed_value = _to_float(core.get("assessed_value"))
    last_sale_price = _to_float(core.get("last_sale_price"))
    tax_amount = _to_float(core.get("tax_amount"))
    mortgage_amount = _to_float(core.get("mortgage_amount"))

    sqft = _to_int(core.get("sqft"))
    lot_sqft = _to_int(core.get("lot_sqft"))
    bedrooms = _to_float(core.get("bedrooms"))
    bathrooms = _to_float(core.get("bathrooms"))

    return {
        "attom_id": core.get("attom_id"),
        "apn": core.get("apn"),
        "fips": core.get("fips"),

        "address": core.get("address_one_line") or core.get("address_line1"),
        "address_one_line": core.get("address_one_line"),
        "address_line1": core.get("address_line1"),
        "city": core.get("city"),
        "state": core.get("state"),
        "zip_code": core.get("zip_code"),

        "latitude": core.get("latitude"),
        "longitude": core.get("longitude"),

        "property_type": core.get("property_type"),
        "property_sub_type": core.get("property_sub_type"),
        "year_built": _to_int(core.get("year_built")) if core.get("year_built") not in (None, "", "None") else None,

        "beds": bedrooms,
        "baths": bathrooms,
        "sqft": sqft,
        "lot_sqft": lot_sqft,
        "rooms_total": _to_int(core.get("rooms_total")) if core.get("rooms_total") not in (None, "", "None") else None,

        "owner_name": core.get("owner_name"),
        "owner_occupied": core.get("owner_occupied"),

        "market_value": market_value,
        "assessed_value": assessed_value,
        "last_sale_price": last_sale_price,
        "last_sale_date": core.get("last_sale_date"),
        "tax_amount": tax_amount,
        "mortgage_amount": mortgage_amount,

        "foreclosure_status": core.get("foreclosure_status"),
        "distressed": bool(core.get("distressed")),

        "raw": core.get("raw") or {},
    }


def compute_attom_only_score(profile: Dict[str, Any]) -> Dict[str, Any]:
    score = 50
    reasons = []

    distressed = bool(profile.get("distressed"))
    owner_occupied = profile.get("owner_occupied")
    year_built = profile.get("year_built") or 0
    market_value = _to_float(profile.get("market_value"))
    assessed_value = _to_float(profile.get("assessed_value"))
    tax_amount = _to_float(profile.get("tax_amount"))
    last_sale_price = _to_float(profile.get("last_sale_price"))

    if distressed:
        score += 18
        reasons.append("Distress or foreclosure signal detected")

    if owner_occupied is False:
        score += 8
        reasons.append("Non-owner occupied")

    if market_value > 0 and assessed_value > 0 and assessed_value < market_value:
        score += 6
        reasons.append("Assessed value below market value")

    if market_value > 0 and last_sale_price > 0 and last_sale_price < (market_value * 0.85):
        score += 8
        reasons.append("Prior sale appears below current market value")

    if tax_amount > 0 and market_value > 0:
        tax_ratio = tax_amount / market_value
        if tax_ratio < 0.015:
            score += 4
            reasons.append("Relatively favorable tax load")
        elif tax_ratio > 0.03:
            score -= 5
            reasons.append("Higher property tax burden")

    if year_built:
        if year_built < 1950:
            score -= 8
            reasons.append("Older property may require heavier rehab")
        elif year_built < 1980:
            score -= 3
            reasons.append("Aging property; inspect systems closely")
        else:
            score += 3
            reasons.append("Newer property age profile")

    recommended_strategy = "Needs Review"
    if distressed and owner_occupied is False:
        recommended_strategy = "Flip / BRRRR"
    elif distressed:
        recommended_strategy = "Flip"
    elif market_value > 0:
        recommended_strategy = "Rental Review"

    score = max(1, min(100, round(score)))

    return {
        "ravlo_score": score,
        "recommended_strategy": recommended_strategy,
        "score_reasons": reasons,
    }


def build_attom_dealfinder_profile(
    address: str,
    city: str,
    state: str,
    zip_code: str = "",
) -> Dict[str, Any]:
    raw = get_property_detail(
        address=address,
        city=city,
        state=state,
        postalcode=zip_code,
    )

    core = extract_core_fields(raw)
    profile = normalize_attom_property(core)
    score = compute_attom_only_score(profile)
    profile.update(score)

    return profile
