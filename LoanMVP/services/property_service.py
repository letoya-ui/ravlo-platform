from flask import current_app
import requests


class PropertyToolError(Exception):
    pass


def _safe_float(x):
    try:
        if x in (None, "", "None", "null"):
            return None
        return float(x)
    except Exception:
        return None


def _safe_int(x):
    try:
        if x in (None, "", "None", "null"):
            return None
        return int(float(x))
    except Exception:
        return None


def _safe_get(data, *keys, default=None):
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


def _normalize_photos(photos) -> list:
    normalized = []

    if isinstance(photos, list):
        for p in photos:
            if isinstance(p, str) and p.strip():
                normalized.append(p.strip())
            elif isinstance(p, dict):
                url = p.get("url") or p.get("href") or p.get("src")
                if isinstance(url, str) and url.strip():
                    normalized.append(url.strip())

    elif isinstance(photos, str) and photos.strip():
        normalized.append(photos.strip())

    seen = set()
    clean = []
    for url in normalized:
        if url not in seen:
            clean.append(url)
            seen.add(url)

    return clean


def _attom_api_key():
    key = (current_app.config.get("ATTOM_API_KEY") or "").strip()
    if not key:
        raise PropertyToolError("ATTOM_API_KEY is not configured.")
    return key


def _attom_base_url():
    return (
        current_app.config.get("ATTOM_BASE_URL")
        or "https://api.gateway.attomdata.com/propertyapi/v1.0.0"
    ).rstrip("/")


def _attom_timeout():
    try:
        return int(current_app.config.get("PROPERTY_API_TIMEOUT", 30))
    except Exception:
        return 30


def _attom_headers():
    return {
        "apikey": _attom_api_key(),
        "Accept": "application/json",
    }


def _attom_get(path: str, params: dict | None = None) -> dict:
    url = f"{_attom_base_url()}/{path.lstrip('/')}"
    try:
        res = requests.get(
            url,
            headers=_attom_headers(),
            params=params or {},
            timeout=_attom_timeout(),
        )
    except requests.RequestException as e:
        raise PropertyToolError(f"ATTOM request failed: {e}")

    if not res.ok:
        snippet = (res.text or "")[:400]
        raise PropertyToolError(
            f"ATTOM error {res.status_code}: {snippet}"
        )

    try:
        return res.json()
    except Exception:
        snippet = (res.text or "")[:400]
        raise PropertyToolError(f"ATTOM returned invalid JSON: {snippet}")


def _extract_attom_properties(payload: dict) -> list:
    props = payload.get("property") or payload.get("properties") or []
    return props if isinstance(props, list) else []


def _normalize_attom_subject(subject: dict, fallback_address: str) -> dict:
    subject = subject or {}

    address_one_line = _safe_get(subject, "address", "oneLine")
    address_line1 = _safe_get(subject, "address", "line1")
    city = _safe_get(subject, "address", "locality")
    state = _safe_get(subject, "address", "countrySubd")
    zip_code = _safe_get(subject, "address", "postal1")

    beds = _safe_int(_safe_get(subject, "building", "rooms", "beds"))
    baths = _safe_float(_safe_get(subject, "building", "rooms", "bathstotal"))
    sqft = _safe_int(_safe_get(subject, "building", "size", "universalsize"))
    lot_size_sqft = _safe_int(_safe_get(subject, "lot", "lotsize1"))
    year_built = _safe_int(_safe_get(subject, "summary", "yearbuilt"))

    property_type = (
        _safe_get(subject, "summary", "proptype")
        or _safe_get(subject, "summary", "propertyType")
    )

    latitude = _safe_float(_safe_get(subject, "location", "latitude"))
    longitude = _safe_float(_safe_get(subject, "location", "longitude"))

    attom_id = (
        _safe_get(subject, "identifier", "attomId")
        or _safe_get(subject, "identifier", "Id")
    )

    last_sale_price = _safe_float(
        _safe_get(subject, "sale", "amount", "saleamt")
        or _safe_get(subject, "sale", "saleamt")
        or _safe_get(subject, "summary", "saleamt")
    )

    assessed_value = _safe_float(
        _safe_get(subject, "assessment", "assessed", "assdttlvalue")
        or _safe_get(subject, "assessment", "market", "mktttlvalue")
        or _safe_get(subject, "assessment", "assdttlvalue")
    )

    return {
        "property_id": attom_id,
        "attom_id": attom_id,
        "address": address_one_line or address_line1 or fallback_address,
        "address_line1": address_line1,
        "city": city,
        "state": state,
        "zip": zip_code,
        "zip_code": zip_code,
        "beds": beds,
        "baths": baths,
        "sqft": sqft,
        "square_feet": sqft,
        "lot_size_sqft": lot_size_sqft,
        "year_built": year_built,
        "property_type": property_type,
        "latitude": latitude,
        "longitude": longitude,
        "photos": [],
        "primary_photo": None,
        "price": last_sale_price,
        "assessed_value": assessed_value,
        "listing": None,
    }


def _normalize_sale_comp(comp: dict) -> dict:
    comp = comp or {}
    return {
        "address": comp.get("address"),
        "price": _safe_float(comp.get("price")),
        "beds": _safe_int(comp.get("beds")),
        "baths": _safe_float(comp.get("baths")),
        "sqft": _safe_int(comp.get("sqft")),
        "distance": _safe_float(comp.get("distance")),
        "days_old": _safe_int(comp.get("days_old")),
        "year_built": _safe_int(comp.get("year_built")),
        "property_type": comp.get("property_type"),
        "photos": _normalize_photos(comp.get("photos")),
    }


def _normalize_rental_comp(comp: dict) -> dict:
    comp = comp or {}
    return {
        "address": comp.get("address"),
        "rent": _safe_float(comp.get("rent")),
        "beds": _safe_int(comp.get("beds")),
        "baths": _safe_float(comp.get("baths")),
        "sqft": _safe_int(comp.get("sqft")),
        "distance": _safe_float(comp.get("distance")),
        "days_old": _safe_int(comp.get("days_old")),
        "year_built": _safe_int(comp.get("year_built")),
        "property_type": comp.get("property_type"),
        "photos": _normalize_photos(comp.get("photos")),
    }


def _calculate_market_snapshot(sales_comps: list, rental_comps: list, meta: dict | None = None) -> dict:
    sales = sales_comps or []
    rentals = rental_comps or []
    meta = meta or {}

    sale_prices = [c["price"] for c in sales if c.get("price") is not None]
    rental_values = [c["rent"] for c in rentals if c.get("rent") is not None]

    sale_ppsf = []
    for c in sales:
        price = c.get("price")
        sqft = c.get("sqft")
        if price is not None and sqft:
            try:
                sale_ppsf.append(round(price / sqft, 2))
            except Exception:
                pass

    avg_sale_comp_price = round(sum(sale_prices) / len(sale_prices), 2) if sale_prices else None
    avg_rental_comp_rent = round(sum(rental_values) / len(rental_values), 2) if rental_values else None
    avg_sale_ppsf = round(sum(sale_ppsf) / len(sale_ppsf), 2) if sale_ppsf else None

    return {
        "avg_sale_comp_price": avg_sale_comp_price,
        "avg_rental_comp_rent": avg_rental_comp_rent,
        "avg_sale_ppsf": avg_sale_ppsf,
        "sale_comp_count": len(sales),
        "rental_comp_count": len(rentals),
        "days_old": meta.get("days_old"),
        "max_radius": meta.get("max_radius"),
    }


def resolve_property_unified(address: str, *, beds=None, baths=None, sqft=None, property_type=None) -> dict:
    """
    ATTOM-first property resolver.
    Current version returns:
    - property
    - valuation
    - rent_estimate (placeholder)
    - comps (placeholder)
    - market_snapshot
    - raw payloads
    """
    address = (address or "").strip()
    if not address:
        return {"status": "error", "error": "address_required"}

    try:
        payload = _attom_get("property/address", {"address1": address})
        properties = _extract_attom_properties(payload)

        if not properties:
            return {
                "status": "error",
                "source": "attom",
                "stage": "property_lookup",
                "error": "No property found for this address.",
            }

        subject_raw = properties[0]
        prop = _normalize_attom_subject(subject_raw, address)

        valuation = {
            "estimate": prop.get("price"),
            "low": None,
            "high": None,
            "confidence": None,
            "assessed_value": prop.get("assessed_value"),
            "last_sale_price": prop.get("price"),
        }

        rent_estimate = {
            "rent": None,
            "low": None,
            "high": None,
            "confidence": None,
        }

        comps = {
            "sales": [],
            "rentals": [],
            "meta": {
                "comp_count": 0,
                "max_radius": None,
                "days_old": None,
            },
        }

        market_snapshot = _calculate_market_snapshot([], [], comps["meta"])

        summary_bits = []
        if prop.get("property_type"):
            summary_bits.append(f"Type: {prop['property_type']}")
        if prop.get("year_built"):
            summary_bits.append(f"Built: {prop['year_built']}")
        if prop.get("square_feet"):
            summary_bits.append(f"Size: {prop['square_feet']:,} sqft")
        if prop.get("price"):
            summary_bits.append(f"Last recorded sale: ${prop['price']:,.0f}")
        if prop.get("assessed_value"):
            summary_bits.append(f"Assessed value: ${prop['assessed_value']:,.0f}")

        ai_summary = " | ".join(summary_bits) if summary_bits else "Public record property data loaded."

        return {
            "status": "ok",
            "source": "attom",
            "property": prop,
            "valuation": valuation,
            "rent_estimate": rent_estimate,
            "comps": comps,
            "market_snapshot": market_snapshot,
            "ai_summary": ai_summary,
            "raw": {
                "property_lookup": subject_raw,
            },
        }

    except Exception as e:
        return {
            "status": "error",
            "source": "attom",
            "stage": "property_lookup",
            "error": str(e),
        }


def build_property_card_data(prop: dict) -> dict:
    prop = prop or {}
    return {
        "title": prop.get("address") or "Property",
        "subtitle": ", ".join(
            [x for x in [prop.get("city"), prop.get("state"), prop.get("zip_code") or prop.get("zip")] if x]
        ),
        "price": prop.get("price"),
        "beds": prop.get("beds"),
        "baths": prop.get("baths"),
        "sqft": prop.get("square_feet") or prop.get("sqft"),
        "lot_size_sqft": prop.get("lot_size_sqft"),
        "year_built": prop.get("year_built"),
        "property_type": prop.get("property_type"),
        "latitude": prop.get("latitude"),
        "longitude": prop.get("longitude"),
        "assessed_value": prop.get("assessed_value"),
        "attom_id": prop.get("attom_id") or prop.get("property_id"),
    }


def calculate_deal_score(metrics: dict) -> dict:
    metrics = metrics or {}

    roi = metrics.get("roi") or 0
    profit = metrics.get("profit") or 0
    cashflow = metrics.get("net_cashflow_mo") or 0

    score = 0

    if roi >= 0.30:
        score += 40
    elif roi >= 0.20:
        score += 30
    elif roi >= 0.15:
        score += 20

    if profit >= 75000:
        score += 30
    elif profit >= 40000:
        score += 20
    elif profit >= 20000:
        score += 10

    if cashflow >= 500:
        score += 30
    elif cashflow >= 300:
        score += 20
    elif cashflow >= 150:
        score += 10

    label = "Pass"
    if score >= 80:
        label = "Strong Deal"
    elif score >= 60:
        label = "Good Deal"
    elif score >= 40:
        label = "Marginal"

    return {
        "score": score,
        "label": label
    }


def generate_ai_deal_summary(metrics):
    metrics = metrics or {}

    roi = metrics.get("roi") or 0
    profit = metrics.get("profit") or 0
    rent = metrics.get("rent_est") or 0
    cashflow = metrics.get("net_cashflow_mo") or 0

    if roi > 0.25:
        recommendation = "Flip"
    elif cashflow > 300:
        recommendation = "Rental"
    else:
        recommendation = "Review Carefully"

    return f"""
This property shows potential with an estimated ROI of {round(roi * 100)}%.

Projected flip profit may reach approximately ${profit:,.0f}.
Rental income may average around ${rent:,.0f} per month.

Estimated monthly cash flow could be near ${cashflow:,.0f}.

Recommended strategy: {recommendation}.
""".strip()

def build_property_card(address: str, *, beds=None, baths=None, sqft=None, property_type=None) -> dict:
    bundle = resolve_property_unified(
        address=address,
        beds=beds,
        baths=baths,
        sqft=sqft,
        property_type=property_type,
    )

    if bundle.get("status") != "ok":
        return bundle

    prop = bundle.get("property") or {}

    return {
        "status": "ok",
        "source": bundle.get("source"),
        "property": prop,
        "valuation": bundle.get("valuation") or {},
        "rent_estimate": bundle.get("rent_estimate") or {},
        "comps": bundle.get("comps") or {},
        "market_snapshot": bundle.get("market_snapshot") or {},
        "card": build_property_card_data(prop),
    }
