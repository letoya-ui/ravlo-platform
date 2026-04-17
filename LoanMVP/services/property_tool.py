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


def _build_display_value(
    *,
    listing_price: Optional[float] = None,
    market_value: Optional[float],
    assessed_value: Optional[float],
    last_sale_price: Optional[float],
    last_sale_date: Optional[str],
) -> Dict[str, Optional[Any]]:
    if listing_price is not None:
        return {
            "display_value": listing_price,
            "display_value_label": "List Price",
            "display_value_source": "listing_price",
            "display_value_secondary": market_value or assessed_value or last_sale_price,
            "display_value_secondary_label": (
                "Estimated Market Value" if market_value is not None
                else "Assessed Value" if assessed_value is not None
                else "Last Recorded Sale" if last_sale_price is not None
                else None
            ),
        }

    if market_value is not None:
        return {
            "display_value": market_value,
            "display_value_label": "Estimated Market Value",
            "display_value_source": "market_value",
            "display_value_secondary": last_sale_price,
            "display_value_secondary_label": "Last Recorded Sale",
        }

    if assessed_value is not None:
        return {
            "display_value": assessed_value,
            "display_value_label": "Assessed Value",
            "display_value_source": "assessed_value",
            "display_value_secondary": last_sale_price,
            "display_value_secondary_label": "Last Recorded Sale",
        }

    if last_sale_price is not None:
        secondary_label = "Recorded Sale Date" if last_sale_date else None
        return {
            "display_value": last_sale_price,
            "display_value_label": "Last Recorded Sale",
            "display_value_source": "last_sale_price",
            "display_value_secondary": last_sale_date,
            "display_value_secondary_label": secondary_label,
        }

    return {
        "display_value": None,
        "display_value_label": "Value Signal Unavailable",
        "display_value_source": None,
        "display_value_secondary": None,
        "display_value_secondary_label": None,
    }


def _needs_detail_enrichment(prop: Dict[str, Any]) -> bool:
    return not any(
        _to_float(prop.get(field)) is not None
        for field in ("display_value", "price", "market_value", "assessed_value", "last_sale_price")
    )


def _merge_property_data(base: Dict[str, Any], detail: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in (detail or {}).items():
        if key == "raw":
            continue
        if merged.get(key) in (None, "", [], {}) and value not in (None, "", [], {}):
            merged[key] = value

    if detail:
        merged["raw"] = detail.get("raw") or base.get("raw")

    return merged


def _enrich_property_with_detail(prop: Dict[str, Any]) -> Dict[str, Any]:
    if not _needs_detail_enrichment(prop):
        return prop

    address1 = (prop.get("address_line1") or prop.get("address") or "").strip()
    city = (prop.get("city") or "").strip()
    state = (prop.get("state") or "").strip()
    zip_code = (prop.get("zip_code") or "").strip()
    attom_id = (prop.get("attom_id") or "").strip() if isinstance(prop.get("attom_id"), str) else prop.get("attom_id")

    if not attom_id and (not address1 or not city or not state):
        return prop

    detail = {}
    try:
        if attom_id:
            payload = _request_attom("property/detail", params={"attomid": attom_id})
        else:
            address2 = ", ".join(part for part in [city, state] if part).strip()
            if zip_code:
                address2 = f"{address2} {zip_code}".strip()
            payload = _request_attom(
                "property/detail",
                params={
                    "address1": address1,
                    "address2": address2,
                },
            )
        raw_detail = _extract_first_property(payload)
        if raw_detail:
            detail = _normalize_attom_property(raw_detail)
    except Exception:
        detail = {}

    rentcast_detail = {}
    try:
        from LoanMVP.services.rentcast_service import get_rentcast_rent_estimate

        rentcast_raw = get_rentcast_rent_estimate(
            address=address1,
            city=city,
            state=state,
            zip_code=zip_code,
            property_type=(prop.get("property_type") or detail.get("property_type") or "single_family"),
        )
        rentcast_detail = {
            "estimated_rent": _to_float(
                rentcast_raw.get("rent")
                or rentcast_raw.get("estimatedRent")
                or rentcast_raw.get("rentEstimate")
                or rentcast_raw.get("price")
            )
        }
    except Exception:
        rentcast_detail = {}

    display_value = _build_display_value(
        listing_price=_to_float(prop.get("price")),
        market_value=_to_float(detail.get("market_value")),
        assessed_value=_to_float(detail.get("assessed_value")),
        last_sale_price=_to_float(detail.get("last_sale_price")),
        last_sale_date=detail.get("last_sale_date"),
    )

    enriched = _merge_property_data(prop, detail)
    enriched = _merge_property_data(enriched, rentcast_detail)
    enriched.update(display_value)
    return enriched


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
    market_value = _to_float(
        _safe_get(raw, "assessment", "market", "mktttlvalue")
        or _safe_get(raw, "assessment", "market", "mktTtlValue")
    )
    tax_amount = _to_float(
        _safe_get(raw, "assessment", "tax", "taxamt")
        or _safe_get(raw, "assessment", "tax", "taxAmt")
    )
    mortgage_amount = _to_float(
        _safe_get(raw, "mortgage", "amount")
        or _safe_get(raw, "mortgage", "mtgamt")
    )
    owner_occupied = _safe_get(raw, "summary", "ownerOccupied")
    distressed = bool(
        _safe_get(raw, "foreclosure", "status")
        or _safe_get(raw, "preforeclosure")
    )
    primary_photo = (
        _safe_get(raw, "photo")
        or _safe_get(raw, "primary_photo")
        or _safe_get(raw, "primaryPhoto")
        or _safe_get(raw, "media", "primaryPhoto")
        or _safe_get(raw, "photos", 0, "url")
        or _safe_get(raw, "photos", 0)
    )

    attom_id = _safe_get(raw, "identifier", "attomId") or _safe_get(raw, "identifier", "Id")

    ravlo_score = None
    score_reasons: List[str] = []

    if distressed:
        ravlo_score = 68
        score_reasons.append("Distress signal detected")
    else:
        ravlo_score = 50

    if market_value and last_sale_price and last_sale_price < (market_value * 0.85):
        ravlo_score += 10
        score_reasons.append("Sale appears below current market value")

    if owner_occupied is False:
        ravlo_score += 6
        score_reasons.append("Non-owner occupied")

    if year_built and year_built < 1980:
        ravlo_score -= 4
        score_reasons.append("Older property may need heavier updates")

    ravlo_score = max(1, min(100, int(round(ravlo_score))))

    recommended_strategy = "Needs Review"
    if distressed and owner_occupied is False:
        recommended_strategy = "Flip / BRRRR"
    elif distressed:
        recommended_strategy = "Flip"
    elif market_value:
        recommended_strategy = "Rental Review"

    display_value = _build_display_value(
        listing_price=None,
        market_value=market_value,
        assessed_value=assessed_value,
        last_sale_price=last_sale_price,
        last_sale_date=last_sale_date,
    )

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
        "market_value": market_value,
        "tax_amount": tax_amount,
        "mortgage_amount": mortgage_amount,
        "owner_occupied": owner_occupied,
        "distressed": distressed,
        "ravlo_score": ravlo_score,
        "recommended_strategy": recommended_strategy,
        "score_reasons": score_reasons,
        "primary_photo": primary_photo,
        **display_value,
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


def _extract_first_property(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    props = (
        payload.get("property")
        or payload.get("properties")
        or _safe_get(payload, "response", "property")
        or []
    )

    if isinstance(props, dict):
        return props
    if isinstance(props, list) and props:
        first = props[0]
        return first if isinstance(first, dict) else None
    return None


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
    normalized = [_normalize_attom_property(p) for p in properties]
    return [_enrich_property_with_detail(p) for p in normalized]


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
    normalized = [_normalize_attom_property(p) for p in properties]
    return [_enrich_property_with_detail(p) for p in normalized]


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
        "source": "attom",
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
        "market_value": prop.get("market_value"),
        "assessed_value": prop.get("assessed_value"),
        "beds": prop.get("beds"),
        "baths": prop.get("baths"),
        "sqft": prop.get("square_feet"),
        "lot_size_sqft": prop.get("lot_size_sqft"),
        "year_built": prop.get("year_built"),
        "property_type": prop.get("property_type"),
        "primary_photo": prop.get("primary_photo"),
        "photos": prop.get("photos") or [],
        "ravlo_score": prop.get("ravlo_score"),
        "recommended_strategy": prop.get("recommended_strategy"),
        "latitude": prop.get("latitude"),
        "longitude": prop.get("longitude"),
        "attom_id": prop.get("attom_id"),
    }
