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
    address = (address or "").strip()
    if not address:
        return {"status": "error", "error": "address_required"}

    try:
        # -------------------------
        # 1. ATTOM BASE (ALWAYS)
        # -------------------------
        payload = _attom_get("property/address", {"address1": address})
        properties = _extract_attom_properties(payload)

        if not properties:
            return {
                "status": "error",
                "source": "attom",
                "error": "No property found",
            }

        subject_raw = properties[0]
        prop = _normalize_attom_subject(subject_raw, address)

        # -------------------------
        # 2. RENTCAST (RENT + PRICE)
        # -------------------------
        rentcast_data = {}
        try:
            from LoanMVP.services.dealfinder_service import get_rentcast_data

            rentcast_data = get_rentcast_data(
                address=prop.get("address"),
                city=prop.get("city"),
                state=prop.get("state"),
                zip_code=prop.get("zip_code"),
            ) or {}

        except Exception as e:
            current_app.logger.warning(f"RentCast failed: {e}")

        # -------------------------
        # 3. MASHVISOR (STR + PHOTOS)
        # -------------------------
        mashvisor_data = {}
        try:
            from LoanMVP.services.mashvisor_client import MashvisorClient

            client = MashvisorClient()

            mashvisor_data = client.get_property_by_address(
                address=prop.get("address"),
                city=prop.get("city"),
                state=prop.get("state"),
                zip_code=prop.get("zip_code"),
            ) or {}

        except Exception as e:
            current_app.logger.warning(f"Mashvisor failed: {e}")

        # -------------------------
        # 4. MERGE PHOTOS
        # -------------------------
        def _extract_photos(data):
            if not isinstance(data, dict):
                return []

            return (
                data.get("photos")
                or data.get("images")
                or data.get("media")
                or []
            )

        photos = _normalize_photos(
            _extract_photos(mashvisor_data)
            + _extract_photos(rentcast_data)
        )

        primary_photo = photos[0] if photos else None

        # -------------------------
        # 5. MERGE PRICING
        # -------------------------
        listing_price = _safe_float(
            rentcast_data.get("price")
            or rentcast_data.get("listing_price")
            or mashvisor_data.get("price")
            or prop.get("price")
        )

        market_value = _safe_float(
            rentcast_data.get("market_value")
            or mashvisor_data.get("market_value")
            or prop.get("assessed_value")
        )

        # -------------------------
        # 6. RENT + STR
        # -------------------------
        rent_estimate = {
            "rent": _safe_float(
                rentcast_data.get("rent_estimate")
                or mashvisor_data.get("traditional_rent")
            ),
            "airbnb_rent": _safe_float(
                mashvisor_data.get("airbnb_rent")
                or mashvisor_data.get("airbnb_revenue")
            ),
        }

        # -------------------------
        # 7. FINAL PROPERTY OBJECT
        # -------------------------
        prop.update({
            "price": listing_price,
            "market_value": market_value,
            "traditional_rent": rent_estimate.get("rent"),
            "airbnb_rent": rent_estimate.get("airbnb_rent"),
            "photos": photos,
            "primary_photo": primary_photo,
        })

        valuation = {
            "estimate": market_value,
            "assessed_value": prop.get("assessed_value"),
            "last_sale_price": prop.get("price"),
        }

        market_snapshot = _calculate_market_snapshot([], [], {})

        return {
            "status": "ok",
            "source": "stacked",
            "property": prop,
            "valuation": valuation,
            "rent_estimate": rent_estimate,
            "comps": {},
            "market_snapshot": market_snapshot,
            "ai_summary": "Stacked data from ATTOM, RentCast, and Mashvisor.",
            "raw": {
                "attom": subject_raw,
                "rentcast": rentcast_data,
                "mashvisor": mashvisor_data,
            },
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
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

def _build_property_tool_result(raw_match, profile_bundle):
    """
    Convert normalized + scored dealfinder output into the shape
    expected by property_tool.html.

    This version is more defensive about:
    - listing price
    - display value
    - primary photo / gallery
    - provider fallbacks
    """
    profile_bundle = profile_bundle or {}
    profile = profile_bundle.get("profile") or {}
    scoring = profile_bundle.get("scoring") or {}
    raw_sources = profile.get("raw_sources") or {}

    realtor_source = raw_sources.get("realtor") or {}
    rentcast_source = raw_sources.get("rentcast") or {}
    mashvisor_source = raw_sources.get("mashvisor") or {}
    attom_source = raw_sources.get("attom") or {}

    def _first_truthy(*vals):
        for v in vals:
            if v not in (None, "", [], {}):
                return v
        return None

    def _normalize_photo_candidates(*sources):
        out = []
        seen = set()

        def _push(url):
            if not url:
                return
            url = str(url).strip()
            if not url or url in seen:
                return
            seen.add(url)
            out.append(url)

        def _walk(value):
            if not value:
                return
            if isinstance(value, str):
                _push(value)
            elif isinstance(value, list):
                for item in value:
                    _walk(item)
            elif isinstance(value, dict):
                for key in ("url", "src", "href", "photo", "image", "thumbnail"):
                    if value.get(key):
                        _push(value.get(key))
                for key in ("photos", "images", "media", "gallery"):
                    if value.get(key):
                        _walk(value.get(key))

        for src in sources:
            _walk(src)

        return out

    def _as_float(value):
        try:
            if value in (None, "", "None"):
                return None
            if isinstance(value, (int, float)):
                return float(value)
            return float(str(value).replace("$", "").replace(",", "").strip())
        except Exception:
            return None

    def _as_int(value):
        try:
            n = _as_float(value)
            return int(round(n)) if n is not None else None
        except Exception:
            return None

    # -------------------------
    # PHOTOS
    # -------------------------
    photos = _normalize_photo_candidates(
        profile.get("photos"),
        realtor_source.get("photos"),
        realtor_source.get("images"),
        realtor_source.get("media"),
        rentcast_source.get("photos"),
        rentcast_source.get("images"),
        mashvisor_source.get("photos"),
        mashvisor_source.get("images"),
        attom_source.get("photos"),
        raw_match.get("photos"),
        raw_match.get("images"),
        raw_match.get("media"),
        raw_match.get("primary_photo"),
        raw_match.get("photo"),
        raw_match.get("thumbnail"),
        raw_match.get("image_url"),
    )

    primary_photo = _first_truthy(
        profile.get("primary_photo"),
        realtor_source.get("primary_photo"),
        realtor_source.get("photo"),
        realtor_source.get("thumbnail"),
        rentcast_source.get("primary_photo"),
        mashvisor_source.get("primary_photo"),
        raw_match.get("primary_photo"),
        raw_match.get("photo"),
        raw_match.get("thumbnail"),
        raw_match.get("image_url"),
        photos[0] if photos else None,
    )

    # -------------------------
    # PRICE / VALUE
    # -------------------------
    listing_price = _as_float(_first_truthy(
        profile.get("listing_price"),
        realtor_source.get("price"),
        realtor_source.get("list_price"),
        realtor_source.get("listPrice"),
        rentcast_source.get("price"),
        rentcast_source.get("listing_price"),
        mashvisor_source.get("listing_price"),
        profile.get("price") if (
            profile.get("status")
            or profile.get("days_on_market")
            or profile.get("description")
        ) else None,
        raw_match.get("price"),
        raw_match.get("list_price"),
        raw_match.get("listPrice"),
        raw_match.get("listedPrice"),
    ))

    market_value = _as_float(_first_truthy(
        profile.get("market_value"),
        mashvisor_source.get("market_value"),
        rentcast_source.get("market_value"),
        attom_source.get("market_value"),
        raw_match.get("market_value"),
    ))

    assessed_value = _as_float(_first_truthy(
        profile.get("assessed_value"),
        attom_source.get("assessed_value"),
        raw_match.get("assessed_value"),
    ))

    last_sale_price = _as_float(_first_truthy(
        profile.get("last_sale_price"),
        attom_source.get("last_sale_price"),
        raw_match.get("last_sale_price"),
    ))

    display_value = _first_truthy(
        listing_price,
        market_value,
        assessed_value,
        last_sale_price,
    )

    if listing_price is not None:
        display_value_label = "List Price"
        display_value_secondary = _first_truthy(market_value, assessed_value, last_sale_price)
        display_value_secondary_label = (
            "Estimated Market Value" if market_value is not None else
            "Assessed Value" if assessed_value is not None else
            "Last Sale Price" if last_sale_price is not None else
            None
        )
    elif market_value is not None:
        display_value_label = "Market Value"
        display_value_secondary = _first_truthy(assessed_value, last_sale_price)
        display_value_secondary_label = (
            "Assessed Value" if assessed_value is not None else
            "Last Sale Price" if last_sale_price is not None else
            None
        )
    elif assessed_value is not None:
        display_value_label = "Assessed Value"
        display_value_secondary = last_sale_price
        display_value_secondary_label = (
            "Last Sale Price" if last_sale_price is not None else None
        )
    else:
        display_value_label = "Last Recorded Sale"
        display_value_secondary = profile.get("last_sale_date")
        display_value_secondary_label = (
            "Last Sale Date" if profile.get("last_sale_date") else None
        )

    # -------------------------
    # RENT SIGNALS
    # -------------------------
    traditional_rent = _as_float(_first_truthy(
        profile.get("traditional_rent"),
        mashvisor_source.get("traditional_rent"),
        rentcast_source.get("rent_estimate"),
        rentcast_source.get("market_rent"),
    ))

    airbnb_rent = _as_float(_first_truthy(
        profile.get("airbnb_rent"),
        mashvisor_source.get("airbnb_rent"),
        mashvisor_source.get("airbnb_revenue"),
    ))

    traditional_cap_rate = _as_float(_first_truthy(
        profile.get("traditional_cap_rate"),
        mashvisor_source.get("traditional_cap_rate"),
    ))
    traditional_coc = _as_float(_first_truthy(
        profile.get("traditional_coc"),
        mashvisor_source.get("traditional_coc"),
    ))
    airbnb_cap_rate = _as_float(_first_truthy(
        profile.get("airbnb_cap_rate"),
        mashvisor_source.get("airbnb_cap_rate"),
    ))
    airbnb_coc = _as_float(_first_truthy(
        profile.get("airbnb_coc"),
        mashvisor_source.get("airbnb_coc"),
    ))
    occupancy_rate = _as_float(_first_truthy(
        profile.get("occupancy_rate"),
        mashvisor_source.get("occupancy_rate"),
    ))

    overall_score = scoring.get("overall_score")
    recommended_strategy = scoring.get("recommended_strategy")
    score_reasons = scoring.get("score_reasons") or []

    return {
        "address": _first_truthy(
            profile.get("address_line1"),
            profile.get("address"),
            raw_match.get("address"),
            raw_match.get("address_line1"),
        ),
        "address_line1": _first_truthy(
            profile.get("address_line1"),
            raw_match.get("address_line1"),
            raw_match.get("address"),
        ),
        "city": _first_truthy(profile.get("city"), raw_match.get("city")),
        "state": _first_truthy(profile.get("state"), raw_match.get("state")),
        "zip_code": _first_truthy(profile.get("zip_code"), raw_match.get("zip_code")),
        "attom_id": _first_truthy(profile.get("attom_id"), raw_match.get("attom_id")),

        "property_type": _first_truthy(
            profile.get("property_type"),
            raw_match.get("property_type"),
        ),
        "property_sub_type": profile.get("property_sub_type"),

        "beds": _as_int(_first_truthy(profile.get("beds"), raw_match.get("beds"), raw_match.get("bedrooms"))),
        "baths": _as_float(_first_truthy(profile.get("baths"), raw_match.get("baths"), raw_match.get("bathrooms"))),
        "square_feet": _as_int(_first_truthy(
            profile.get("sqft"),
            raw_match.get("square_feet"),
            raw_match.get("sqft"),
        )),
        "sqft": _as_int(_first_truthy(
            profile.get("sqft"),
            raw_match.get("square_feet"),
            raw_match.get("sqft"),
        )),
        "lot_size_sqft": _as_int(_first_truthy(
            profile.get("lot_sqft"),
            raw_match.get("lot_size_sqft"),
            raw_match.get("lotSizeSqft"),
        )),
        "year_built": _as_int(_first_truthy(
            profile.get("year_built"),
            raw_match.get("year_built"),
            raw_match.get("yearBuilt"),
        )),

        "display_value": display_value,
        "display_value_label": display_value_label,
        "display_value_secondary": display_value_secondary,
        "display_value_secondary_label": display_value_secondary_label,

        "price": listing_price,
        "listing_price": listing_price,
        "market_value": market_value,
        "assessed_value": assessed_value,
        "last_sale_price": last_sale_price,
        "data_status": "enriched",
        "last_sale_date": profile.get("last_sale_date"),
        "tax_amount": _as_float(profile.get("tax_amount")),
        "status": _first_truthy(profile.get("status"), raw_match.get("status")),
        "days_on_market": _as_int(_first_truthy(
            profile.get("days_on_market"),
            raw_match.get("days_on_market"),
            raw_match.get("daysOnMarket"),
        )),
        "description": _first_truthy(profile.get("description"), raw_match.get("description")),

        "traditional_rent": traditional_rent,
        "airbnb_rent": airbnb_rent,
        "traditional_cap_rate": traditional_cap_rate,
        "traditional_coc": traditional_coc,
        "airbnb_cap_rate": airbnb_cap_rate,
        "airbnb_coc": airbnb_coc,
        "occupancy_rate": occupancy_rate,

        "distressed": bool(profile.get("distressed")),
        "foreclosure_status": profile.get("foreclosure_status"),
        "owner_occupied": profile.get("owner_occupied"),

        "ravlo_score": overall_score,
        "recommended_strategy": recommended_strategy or "Hold / Review",
        "score_reasons": score_reasons,

        "primary_photo": primary_photo,
        "photo": primary_photo,
        "thumbnail": primary_photo,
        "photos": photos,

        "latitude": _as_float(_first_truthy(profile.get("latitude"), raw_match.get("latitude"))),
        "longitude": _as_float(_first_truthy(profile.get("longitude"), raw_match.get("longitude"))),

        "source_status": profile_bundle.get("source_status") or {},
        "provider_errors": profile_bundle.get("errors") or [],
        "raw_sources": raw_sources,
    }