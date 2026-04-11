from __future__ import annotations

from typing import Any, Dict

from flask import current_app

from LoanMVP.services.mashvisor_client import MashvisorClient
from LoanMVP.services.mashvisor_service import (
    get_property_analytics,
    extract_core_fields,
)

from LoanMVP.services.investor.investor_helpers import (
    _safe_float,
    _safe_int,
    _first_non_empty,
)

from LoanMVP.services.investor.investor_media_helpers import (
    _normalize_photo_list,
)


# -------------------------
# FULL MASHVISOR ANALYSIS
# -------------------------

def _run_full_mashvisor_analysis(snapshot: dict) -> dict | None:
    """
    Full Mashvisor integration:
    - property lookup
    - STR lookup
    - comps
    - analytics
    - photo extraction
    """

    if not snapshot:
        return None

    address = (snapshot.get("address") or "").strip()
    city = (snapshot.get("city") or "").strip()
    state = (snapshot.get("state") or "").strip()
    zip_code = (snapshot.get("zip_code") or "").strip()

    if not address or not city or not state or not zip_code:
        return None

    property_type = (snapshot.get("property_type") or "single_family").strip()

    try:
        client = MashvisorClient()

        property_result = client.get_property_by_address(
            address=address,
            city=city,
            state=state,
            zip_code=zip_code,
        )

        lookup_result = client.get_airbnb_lookup(
            address=address,
            city=city,
            state=state,
            zip_code=zip_code,
            beds=_safe_int(snapshot.get("beds")),
            baths=_safe_float(snapshot.get("baths")),
            lat=_safe_float(snapshot.get("latitude")),
            lng=_safe_float(snapshot.get("longitude")),
        )

        comps_result = client.get_airbnb_comps(
            state=state,
            zip_code=zip_code,
        )

        analytics_result = get_property_analytics(
            address=address,
            city=city,
            state=state,
            zip_code=zip_code,
            property_type=property_type,
        )

        analytics = extract_core_fields(analytics_result)

        # normalize payloads
        property_content = (
            property_result.get("content", property_result)
            if isinstance(property_result, dict) else {}
        )

        lookup_content = (
            lookup_result.get("content", lookup_result)
            if isinstance(lookup_result, dict) else {}
        )

        comps_content = (
            comps_result.get("content", comps_result)
            if isinstance(comps_result, dict) else {}
        )

        # -------------------------
        # PHOTOS
        # -------------------------

        photos = _normalize_photo_list(
            _first_non_empty(
                property_content.get("photos") if isinstance(property_content, dict) else None,
                property_content.get("images") if isinstance(property_content, dict) else None,
                property_content.get("media") if isinstance(property_content, dict) else None,
                property_result.get("photos") if isinstance(property_result, dict) else None,
                property_result.get("images") if isinstance(property_result, dict) else None,
            )
        )

        # -------------------------
        # FINAL NORMALIZED OBJECT
        # -------------------------

        return {
            "address": _first_non_empty(
                property_content.get("address") if isinstance(property_content, dict) else None,
                address,
            ),

            "listing_price": _first_non_empty(
                analytics.get("listing_price"),
                property_content.get("price") if isinstance(property_content, dict) else None,
                snapshot.get("purchase_price"),
            ),

            "price_per_sqft": analytics.get("price_per_sqft"),
            "walk_score": analytics.get("walk_score"),
            "days_on_market": analytics.get("days_on_market"),

            # -------------------------
            # LONG-TERM RENTAL
            # -------------------------

            "traditional_rent": analytics.get("traditional_rent"),
            "traditional_cash_flow": analytics.get("traditional_cash_flow"),
            "traditional_cap_rate": analytics.get("traditional_cap_rate"),
            "traditional_coc": analytics.get("traditional_coc"),

            # -------------------------
            # AIRBNB / STR
            # -------------------------

            "airbnb_revenue": _first_non_empty(
                lookup_content.get("rental_income") if isinstance(lookup_content, dict) else None,
                lookup_content.get("airbnb_rental_income") if isinstance(lookup_content, dict) else None,
                lookup_content.get("monthly_revenue") if isinstance(lookup_content, dict) else None,
                analytics.get("airbnb_rent"),
            ),

            "airbnb_cash_flow": _first_non_empty(
                analytics.get("airbnb_cash_flow"),
                lookup_content.get("cash_flow") if isinstance(lookup_content, dict) else None,
            ),

            "airbnb_cap_rate": analytics.get("airbnb_cap_rate"),
            "airbnb_coc": analytics.get("airbnb_coc"),

            "occupancy_rate": _first_non_empty(
                lookup_content.get("occupancy_rate") if isinstance(lookup_content, dict) else None,
                lookup_content.get("airbnb_occupancy_rate") if isinstance(lookup_content, dict) else None,
                analytics.get("occupancy_rate"),
            ),

            "adr": _first_non_empty(
                lookup_content.get("daily_rate") if isinstance(lookup_content, dict) else None,
                lookup_content.get("adr") if isinstance(lookup_content, dict) else None,
                lookup_content.get("average_daily_rate") if isinstance(lookup_content, dict) else None,
            ),

            # -------------------------
            # CONFIDENCE / DATA QUALITY
            # -------------------------

            "confidence": _first_non_empty(
                lookup_content.get("data_quality") if isinstance(lookup_content, dict) else None,
                lookup_content.get("confidence") if isinstance(lookup_content, dict) else None,
                lookup_content.get("sample_size") if isinstance(lookup_content, dict) else None,
                "Moderate",
            ),

            # -------------------------
            # COMPS
            # -------------------------

            "airbnb_comps": _first_non_empty(
                comps_content.get("list") if isinstance(comps_content, dict) else None,
                comps_content.get("comparables") if isinstance(comps_content, dict) else None,
                [],
            ),

            # -------------------------
            # MEDIA
            # -------------------------

            "photos": photos,
            "primary_photo": photos[0] if photos else None,

            # -------------------------
            # RAW DEBUG PAYLOAD
            # -------------------------

            "raw": {
                "property": property_result,
                "lookup": lookup_result,
                "comps": comps_result,
                "analytics": analytics_result,
            },
        }

    except Exception as exc:
        current_app.logger.warning(
            "full mashvisor analysis failed for %s: %s",
            snapshot.get("address"),
            exc,
        )
        return {"error": str(exc)}


# -------------------------
# LIGHTWEIGHT VALIDATION
# -------------------------

def _project_studio_validate_with_mashvisor(
    scope_budget: dict | None,
    mashvisor_data: dict | None,
) -> str | None:
    """
    Compare Ravlo internal outcome vs Mashvisor signal
    """

    if not scope_budget or not mashvisor_data or mashvisor_data.get("error"):
        return None

    internal_reference = _safe_float(scope_budget.get("outcome"))
    mashvisor_revenue = _safe_float(mashvisor_data.get("airbnb_revenue"))

    if (
        internal_reference is None
        or mashvisor_revenue is None
        or internal_reference == 0
    ):
        return "Market validation is available, but there is not enough aligned data yet for a direct comparison."

    pct = ((mashvisor_revenue - internal_reference) / abs(internal_reference)) * 100

    if abs(pct) <= 10:
        return "Market data is generally aligned with Ravlo's current planning assumptions."

    if pct < 0:
        return "Market data is coming in below Ravlo's internal planning signal, so pressure-test the revenue assumptions."

    return "Market data is stronger than Ravlo's current planning signal, which may support more upside."