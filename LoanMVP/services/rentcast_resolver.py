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
        "photos": subject.get("photos") or subject.get("imageUrls") or subject.get("images") or subject.get("photoUrls") or None,
        "price": None,     # ensure always present
        "listing": None,   # ensure always present
    }


def _normalize_from_comp(comp: dict, fallback_address: str) -> dict:
    comp = comp or {}
    return {
        "property_id": comp.get("id") or None,
        "address": comp.get("formattedAddress") or comp.get("address") or comp.get("addressLine1") or fallback_address,
        "city": comp.get("city"),
        "state": comp.get("state"),
        "zip": comp.get("zipCode") or comp.get("zip") or comp.get("postalCode"),
        "beds": _safe_int(comp.get("bedrooms")),
        "baths": _safe_float(comp.get("bathrooms")),
        "sqft": _safe_int(comp.get("squareFootage")),
        "year_built": _safe_int(comp.get("yearBuilt")),
        "property_type": comp.get("propertyType"),
        "photos": comp.get("photos") or comp.get("imageUrls") or comp.get("images") or comp.get("photoUrls") or None,
        "price": None,
        "listing": None,
    }


def resolve_rentcast_investor_bundle(address: str, *, beds=None, baths=None, sqft=None, property_type=None) -> dict:

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

    # --------------------------------------------------
    # 1️⃣ VALUE AVM
    # --------------------------------------------------
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

    # --------------------------------------------------
    # 2️⃣ RENT AVM
    # --------------------------------------------------
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

    sales_comps = value.get("comparables") or value.get("comps") or []
    rental_comps = rent.get("comparables") or rent.get("comps") or []

    # --------------------------------------------------
    # 3️⃣ SUBJECT RESOLUTION
    # --------------------------------------------------
    subject = subject_v or subject_r or {}

    property_record_raw = None
    if not subject:
        prop_resp = rentcast_get("/properties", {"address": address})
        if prop_resp.get("status") == "ok":
            property_record_raw = _pick_first_property_record(prop_resp.get("data"))
            if property_record_raw:
                subject = property_record_raw

    # Normalize ONCE
    if subject:
        prop = _normalize_subject(subject, address)
    else:
        first_comp = (
            (sales_comps[0] if sales_comps else None)
            or (rental_comps[0] if rental_comps else None)
        )
        prop = (
            _normalize_from_comp(first_comp, address)
            if first_comp
            else _normalize_subject({}, address)
        )

    # Ensure safe keys exist
    prop.setdefault("price", None)
    prop.setdefault("photos", None)
    prop.setdefault("listing", None)

    # --------------------------------------------------
    # 4️⃣ MLS LISTING LOOKUP (MERGED LAST)
    # --------------------------------------------------
    listing_resp = rentcast_get("/listings/sale", {"address": address})
    listing = (
        _pick_first_listing(listing_resp)
        if listing_resp.get("status") == "ok"
        else None
    )

    if listing:

        list_price = (
            listing.get("price")
            or listing.get("listPrice")
            or listing.get("listedPrice")
        )

        if list_price is not None:
            prop["price"] = _safe_float(list_price)

        prop["listing"] = {
            "id": listing.get("id"),
            "status": listing.get("status"),
            "listedDate": listing.get("listedDate"),
            "removedDate": listing.get("removedDate"),
            "daysOnMarket": listing.get("daysOnMarket"),
            "price": _safe_float(list_price) if list_price is not None else None,
            "mlsName": listing.get("mlsName"),
            "mlsNumber": listing.get("mlsNumber"),
        }

        # Try photos from listing search
        photos = (
            listing.get("photos")
            or listing.get("images")
            or listing.get("photoUrls")
            or listing.get("imageUrls")
        )

        if isinstance(photos, str) and not photos.strip():
            photos = None
        if isinstance(photos, list) and not photos:
            photos = None

        if photos:
            prop["photos"] = photos

        # Try listing detail endpoint for richer photos
        listing_id = listing.get("id")
        if listing_id:
            detail_resp = rentcast_get(f"/listings/sale/{listing_id}", {})
            if detail_resp.get("status") == "ok":
                detail = detail_resp.get("data") or {}

                more_photos = (
                    detail.get("photos")
                    or detail.get("images")
                    or detail.get("photoUrls")
                    or detail.get("imageUrls")
                )

                # Check common nested structures
                if not more_photos:
                    for key in ("media", "assets", "listing", "property", "details"):
                        nested = detail.get(key)
                        if isinstance(nested, dict):
                            more_photos = (
                                nested.get("photos")
                                or nested.get("images")
                                or nested.get("photoUrls")
                                or nested.get("imageUrls")
                            )
                            if more_photos:
                                break

                if isinstance(more_photos, str) and not more_photos.strip():
                    more_photos = None
                if isinstance(more_photos, list) and not more_photos:
                    more_photos = None

                if more_photos:
                    prop["photos"] = more_photos

    # --------------------------------------------------
    # 5️⃣ VALUE + RENT ESTIMATES
    # --------------------------------------------------
    valuation = {
        "estimate": _safe_float(value.get("value"))
        or _safe_float(value.get("estimate"))
        or _safe_float(value.get("price")),
        "low": _safe_float(value.get("valueRangeLow"))
        or _safe_float(value.get("rangeLow")),
        "high": _safe_float(value.get("valueRangeHigh"))
        or _safe_float(value.get("rangeHigh")),
        "confidence": value.get("confidence"),
    }

    rent_estimate = {
        "rent": _safe_float(rent.get("rent"))
        or _safe_float(rent.get("estimate"))
        or _safe_float(rent.get("monthlyRent")),
        "low": _safe_float(rent.get("rentRangeLow"))
        or _safe_float(rent.get("rangeLow")),
        "high": _safe_float(rent.get("rentRangeHigh"))
        or _safe_float(rent.get("rangeHigh")),
        "confidence": rent.get("confidence"),
    }

    comps = {
        "sales": sales_comps,
        "rentals": rental_comps,
        "meta": {
            "comp_count": comp_count,
            "max_radius": max_radius,
            "days_old": days_old,
        },
    }

    return {
        "status": "ok",
        "source": "rentcast",
        "property": prop,
        "valuation": valuation,
        "rent_estimate": rent_estimate,
        "comps": comps,
        "raw": {
            "value_avm": value,
            "rent_avm": rent,
            "property_record": property_record_raw,
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

    listing = prop.get("listing") or {}
    photos = prop.get("photos") or []

    # normalize photos into a clean list of strings
    normalized_photos = []
    if isinstance(photos, list):
        for p in photos:
            if isinstance(p, str) and p.strip():
                normalized_photos.append(p.strip())
            elif isinstance(p, dict):
                url = p.get("url") or p.get("href") or p.get("src")
                if url:
                    normalized_photos.append(url)
    elif isinstance(photos, str) and photos.strip():
        normalized_photos = [photos.strip()]

    # normalize sales comps
    sales_comps = []
    for comp in (comps.get("sales") or [])[:10]:
        sales_comps.append({
            "address": comp.get("formattedAddress") or comp.get("address") or comp.get("addressLine1"),
            "price": _safe_float(comp.get("price") or comp.get("salePrice") or comp.get("closePrice")),
            "beds": _safe_int(comp.get("bedrooms") or comp.get("beds")),
            "baths": _safe_float(comp.get("bathrooms") or comp.get("baths")),
            "sqft": _safe_int(comp.get("squareFootage") or comp.get("sqft")),
            "distance": _safe_float(comp.get("distance")),
            "days_old": _safe_int(comp.get("daysOld") or comp.get("days_old")),
        })

    # normalize rental comps
    rental_comps = []
    for comp in (comps.get("rentals") or [])[:10]:
        rental_comps.append({
            "address": comp.get("formattedAddress") or comp.get("address") or comp.get("addressLine1"),
            "rent": _safe_float(comp.get("rent") or comp.get("price") or comp.get("monthlyRent")),
            "beds": _safe_int(comp.get("bedrooms") or comp.get("beds")),
            "baths": _safe_float(comp.get("bathrooms") or comp.get("baths")),
            "sqft": _safe_int(comp.get("squareFootage") or comp.get("sqft")),
            "distance": _safe_float(comp.get("distance")),
            "days_old": _safe_int(comp.get("daysOld") or comp.get("days_old")),
        })

    # quick market snapshot from sales comps
    sale_prices = [c["price"] for c in sales_comps if c.get("price") is not None]
    avg_comp_price = round(sum(sale_prices) / len(sale_prices), 2) if sale_prices else None

    rent_values = [c["rent"] for c in rental_comps if c.get("rent") is not None]
    avg_comp_rent = round(sum(rent_values) / len(rent_values), 2) if rent_values else None

    card = {
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
            "primary_photo": normalized_photos[0] if normalized_photos else None,
            "listing": listing,
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
        "comps": {
            "sales": sales_comps,
            "rentals": rental_comps,
            "meta": comps.get("meta") or {},
        },
        "market_snapshot": {
            "avg_sale_comp_price": avg_comp_price,
            "avg_rental_comp_rent": avg_comp_rent,
            "sale_comp_count": len(sales_comps),
            "rental_comp_count": len(rental_comps),
            "days_old": (comps.get("meta") or {}).get("days_old"),
            "max_radius": (comps.get("meta") or {}).get("max_radius"),
        }
    }

    return card

def calculate_deal_score(metrics: dict) -> dict:
    """
    Returns score + label for deal quality.
    """

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
This property shows potential with an estimated ROI of {round(roi*100)}%.

Projected flip profit may reach approximately ${profit:,.0f}.
Rental income may average around ${rent:,.0f} per month.

Estimated monthly cash flow could be near ${cashflow:,.0f}.

Recommended strategy: {recommendation}.
"""