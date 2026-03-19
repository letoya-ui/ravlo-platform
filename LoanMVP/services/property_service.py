from flask import current_app
from LoanMVP.services.rentcast_client import rentcast_get


def _safe_float(x):
    try:
        return float(x)
    except Exception:
        return None


def _safe_int(x):
    try:
        return int(float(x))
    except Exception:
        return None


def _normalize_photos(photos) -> list:
    """
    Normalize photo payloads into a clean list of URL strings.
    Supports:
    - ["https://..."]
    - [{"url": "https://..."}]
    - [{"href": "https://..."}]
    - [{"src": "https://..."}]
    - "https://..."
    """
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

    # dedupe while preserving order
    seen = set()
    clean = []
    for url in normalized:
        if url not in seen:
            clean.append(url)
            seen.add(url)

    return clean


def _pick_first_listing(resp: dict):
    data = (resp or {}).get("data")
    if isinstance(data, list):
        return data[0] if data else None
    if isinstance(data, dict):
        listings = data.get("listings") or data.get("results") or data.get("data") or []
        return listings[0] if isinstance(listings, list) and listings else None
    return None


def _pick_first_property_record(data):
    if isinstance(data, list) and data:
        return data[0]
    if isinstance(data, dict):
        for key in ("results", "properties", "data"):
            v = data.get(key)
            if isinstance(v, list) and v:
                return v[0]
    return None


def _normalize_subject(subject: dict, fallback_address: str) -> dict:
    subject = subject or {}
    raw_photos = (
        subject.get("photos")
        or subject.get("imageUrls")
        or subject.get("images")
        or subject.get("photoUrls")
    )
    photos = _normalize_photos(raw_photos)

    return {
        "property_id": subject.get("id") or subject.get("propertyId") or subject.get("property_id"),
        "address": subject.get("formattedAddress") or subject.get("address") or subject.get("addressLine1") or fallback_address,
        "city": subject.get("city"),
        "state": subject.get("state"),
        "zip": subject.get("zipCode") or subject.get("zip") or subject.get("postalCode"),
        "beds": _safe_int(subject.get("bedrooms") or subject.get("beds")),
        "baths": _safe_float(subject.get("bathrooms") or subject.get("baths")),
        "sqft": _safe_int(subject.get("squareFootage") or subject.get("sqft")),
        "year_built": _safe_int(subject.get("yearBuilt") or subject.get("year_built")),
        "property_type": subject.get("propertyType") or subject.get("property_type"),
        "photos": photos,
        "primary_photo": photos[0] if photos else None,
        "price": None,
        "listing": None,
    }


def _normalize_from_comp(comp: dict, fallback_address: str) -> dict:
    comp = comp or {}
    raw_photos = (
        comp.get("photos")
        or comp.get("imageUrls")
        or comp.get("images")
        or comp.get("photoUrls")
    )
    photos = _normalize_photos(raw_photos)

    return {
        "property_id": comp.get("id") or comp.get("propertyId") or comp.get("property_id"),
        "address": comp.get("formattedAddress") or comp.get("address") or comp.get("addressLine1") or fallback_address,
        "city": comp.get("city"),
        "state": comp.get("state"),
        "zip": comp.get("zipCode") or comp.get("zip") or comp.get("postalCode"),
        "beds": _safe_int(comp.get("bedrooms") or comp.get("beds")),
        "baths": _safe_float(comp.get("bathrooms") or comp.get("baths")),
        "sqft": _safe_int(comp.get("squareFootage") or comp.get("sqft")),
        "year_built": _safe_int(comp.get("yearBuilt") or comp.get("year_built")),
        "property_type": comp.get("propertyType") or comp.get("property_type"),
        "photos": photos,
        "primary_photo": photos[0] if photos else None,
        "price": None,
        "listing": None,
    }


def _normalize_sale_comp(comp: dict) -> dict:
    comp = comp or {}
    return {
        "address": comp.get("formattedAddress") or comp.get("address") or comp.get("addressLine1"),
        "price": _safe_float(comp.get("price") or comp.get("salePrice") or comp.get("closePrice")),
        "beds": _safe_int(comp.get("bedrooms") or comp.get("beds")),
        "baths": _safe_float(comp.get("bathrooms") or comp.get("baths")),
        "sqft": _safe_int(comp.get("squareFootage") or comp.get("sqft")),
        "distance": _safe_float(comp.get("distance")),
        "days_old": _safe_int(comp.get("daysOld") or comp.get("days_old")),
        "year_built": _safe_int(comp.get("yearBuilt") or comp.get("year_built")),
        "property_type": comp.get("propertyType") or comp.get("property_type"),
        "photos": _normalize_photos(
            comp.get("photos") or comp.get("imageUrls") or comp.get("images") or comp.get("photoUrls")
        ),
    }


def _normalize_rental_comp(comp: dict) -> dict:
    comp = comp or {}
    return {
        "address": comp.get("formattedAddress") or comp.get("address") or comp.get("addressLine1"),
        "rent": _safe_float(comp.get("rent") or comp.get("price") or comp.get("monthlyRent")),
        "beds": _safe_int(comp.get("bedrooms") or comp.get("beds")),
        "baths": _safe_float(comp.get("bathrooms") or comp.get("baths")),
        "sqft": _safe_int(comp.get("squareFootage") or comp.get("sqft")),
        "distance": _safe_float(comp.get("distance")),
        "days_old": _safe_int(comp.get("daysOld") or comp.get("days_old")),
        "year_built": _safe_int(comp.get("yearBuilt") or comp.get("year_built")),
        "property_type": comp.get("propertyType") or comp.get("property_type"),
        "photos": _normalize_photos(
            comp.get("photos") or comp.get("imageUrls") or comp.get("images") or comp.get("photoUrls")
        ),
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


def resolve_rentcast_investor_bundle(address: str, *, beds=None, baths=None, sqft=None, property_type=None) -> dict:
    """
    Resolve one property into a Ravlo-normalized bundle:
    - property
    - valuation
    - rent_estimate
    - comps
    - market_snapshot
    - raw payloads
    """
    address = (address or "").strip()
    if not address:
        return {"status": "error", "error": "address_required"}

    comp_count = int(current_app.config.get("RENTCAST_COMP_COUNT", 15))
    max_radius = float(current_app.config.get("RENTCAST_MAX_RADIUS", 2))
    days_old = int(current_app.config.get("RENTCAST_DAYS_OLD", 180))
    lookup_attrs = bool(current_app.config.get("RENTCAST_LOOKUP_SUBJECT_ATTRS", True))

    base_params = {
        "address": address,
        "compCount": comp_count,
        "maxRadius": max_radius,
        "daysOld": days_old,
        "lookupSubjectAttributes": "true" if lookup_attrs else "false",
    }

    if beds is not None:
        base_params["bedrooms"] = beds
    if baths is not None:
        base_params["bathrooms"] = baths
    if sqft is not None:
        base_params["squareFootage"] = sqft
    if property_type:
        base_params["propertyType"] = property_type

    # 1) VALUE AVM
    value_resp = rentcast_get("/avm/value", base_params)
    if value_resp.get("status") != "ok":
        return {
            "status": "error",
            "provider": "rentcast",
            "stage": "value_avm",
            "error": value_resp.get("error"),
        }

    value = value_resp.get("data") or {}
    subject_v = value.get("subject") or {}

    # 2) RENT AVM
    rent_resp = rentcast_get("/avm/rent/long-term", base_params)
    if rent_resp.get("status") != "ok":
        return {
            "status": "error",
            "provider": "rentcast",
            "stage": "rent_avm",
            "error": rent_resp.get("error"),
        }

    rent = rent_resp.get("data") or {}
    subject_r = rent.get("subject") or {}

    raw_sales_comps = value.get("comparables") or value.get("comps") or []
    raw_rental_comps = rent.get("comparables") or rent.get("comps") or []

    # 3) SUBJECT RESOLUTION
    subject = subject_v or subject_r or {}
    property_record_raw = None

    if not subject:
        prop_resp = rentcast_get("/properties", {"address": address})
        if prop_resp.get("status") == "ok":
            property_record_raw = _pick_first_property_record(prop_resp.get("data"))
            if property_record_raw:
                subject = property_record_raw

    if subject:
        prop = _normalize_subject(subject, address)
    else:
        first_comp = (raw_sales_comps[0] if raw_sales_comps else None) or (raw_rental_comps[0] if raw_rental_comps else None)
        prop = _normalize_from_comp(first_comp, address) if first_comp else _normalize_subject({}, address)

    # 4) MLS LISTING LOOKUP
    listing_resp = rentcast_get("/listings/sale", {"address": address})
    listing = _pick_first_listing(listing_resp) if listing_resp.get("status") == "ok" else None

    if listing:
        list_price = listing.get("price") or listing.get("listPrice") or listing.get("listedPrice")
        list_price_num = _safe_float(list_price)

        if list_price_num is not None:
            prop["price"] = list_price_num

        prop["listing"] = {
            "id": listing.get("id"),
            "status": listing.get("status"),
            "listedDate": listing.get("listedDate"),
            "removedDate": listing.get("removedDate"),
            "daysOnMarket": listing.get("daysOnMarket"),
            "price": list_price_num,
            "mlsName": listing.get("mlsName"),
            "mlsNumber": listing.get("mlsNumber"),
        }

        listing_photos = _normalize_photos(
            listing.get("photos")
            or listing.get("images")
            or listing.get("photoUrls")
            or listing.get("imageUrls")
        )
        if listing_photos:
            prop["photos"] = listing_photos
            prop["primary_photo"] = listing_photos[0]

        listing_id = listing.get("id")
        if listing_id:
            detail_resp = rentcast_get(f"/listings/sale/{listing_id}", {})
            if detail_resp.get("status") == "ok":
                detail = detail_resp.get("data") or {}

                detail_photos = _normalize_photos(
                    detail.get("photos")
                    or detail.get("images")
                    or detail.get("photoUrls")
                    or detail.get("imageUrls")
                )

                if not detail_photos:
                    for key in ("media", "assets", "listing", "property", "details"):
                        nested = detail.get(key)
                        if isinstance(nested, dict):
                            detail_photos = _normalize_photos(
                                nested.get("photos")
                                or nested.get("images")
                                or nested.get("photoUrls")
                                or nested.get("imageUrls")
                            )
                            if detail_photos:
                                break

                if detail_photos:
                    prop["photos"] = detail_photos
                    prop["primary_photo"] = detail_photos[0]

    # 5) FINAL PHOTO SAFETY PASS
    prop["photos"] = _normalize_photos(prop.get("photos"))
    prop["primary_photo"] = prop["photos"][0] if prop["photos"] else None

    # 6) VALUE + RENT ESTIMATES
    valuation = {
        "estimate": _safe_float(value.get("value")) or _safe_float(value.get("estimate")) or _safe_float(value.get("price")),
        "low": _safe_float(value.get("valueRangeLow")) or _safe_float(value.get("rangeLow")),
        "high": _safe_float(value.get("valueRangeHigh")) or _safe_float(value.get("rangeHigh")),
        "confidence": value.get("confidence"),
    }

    rent_estimate = {
        "rent": _safe_float(rent.get("rent")) or _safe_float(rent.get("estimate")) or _safe_float(rent.get("monthlyRent")),
        "low": _safe_float(rent.get("rentRangeLow")) or _safe_float(rent.get("rangeLow")),
        "high": _safe_float(rent.get("rentRangeHigh")) or _safe_float(rent.get("rangeHigh")),
        "confidence": rent.get("confidence"),
    }

    # 7) NORMALIZED COMPS
    sales_comps = [_normalize_sale_comp(comp) for comp in raw_sales_comps[:10]]
    rental_comps = [_normalize_rental_comp(comp) for comp in raw_rental_comps[:10]]

    comps_meta = {
        "comp_count": comp_count,
        "max_radius": max_radius,
        "days_old": days_old,
    }

    comps = {
        "sales": sales_comps,
        "rentals": rental_comps,
        "meta": comps_meta,
    }

    market_snapshot = _calculate_market_snapshot(sales_comps, rental_comps, comps_meta)

    return {
        "status": "ok",
        "source": "rentcast",
        "property": prop,
        "valuation": valuation,
        "rent_estimate": rent_estimate,
        "comps": comps,
        "market_snapshot": market_snapshot,
        "raw": {
            "value_avm": value,
            "rent_avm": rent,
            "property_record": property_record_raw,
            "listing_search": listing,
        },
    }


def build_ravlo_property_card(address: str, *, beds=None, baths=None, sqft=None, property_type=None) -> dict:
    """
    Returns a Ravlo-normalized property card payload for Deal Finder / Deal Workspace.
    """
    bundle = resolve_rentcast_investor_bundle(
        address=address,
        beds=beds,
        baths=baths,
        sqft=sqft,
        property_type=property_type,
    )

    if bundle.get("status") != "ok":
        return bundle

    prop = bundle.get("property") or {}
    valuation = bundle.get("valuation") or {}
    rent_estimate = bundle.get("rent_estimate") or {}
    comps = bundle.get("comps") or {}
    market_snapshot = bundle.get("market_snapshot") or {}

    normalized_photos = prop.get("photos") or []
    primary_photo = prop.get("primary_photo") or (normalized_photos[0] if normalized_photos else None)

    return {
        "status": "ok",
        "source": "rentcast",
        "property": {
            "property_id": prop.get("property_id"),
            "address": prop.get("address"),
            "city": prop.get("city"),
            "state": prop.get("state"),
            "zip": prop.get("zip"),
            "beds": prop.get("beds"),
            "baths": prop.get("baths"),
            "sqft": prop.get("sqft"),
            "year_built": prop.get("year_built"),
            "property_type": prop.get("property_type"),
            "price": prop.get("price"),
            "photos": normalized_photos,
            "primary_photo": primary_photo,
            "listing": prop.get("listing") or {},
        },
        "valuation": {
            "estimate": valuation.get("estimate"),
            "low": valuation.get("low"),
            "high": valuation.get("high"),
            "confidence": valuation.get("confidence"),
        },
        "rent_estimate": {
            "rent": rent_estimate.get("rent"),
            "low": rent_estimate.get("low"),
            "high": rent_estimate.get("high"),
            "confidence": rent_estimate.get("confidence"),
        },
        "comps": comps,
        "market_snapshot": market_snapshot,
    }


def calculate_deal_score(metrics: dict) -> dict:
    """
    Returns score + label for deal quality.
    """
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
