"""
Ravlo ARV Engine
----------------
Main orchestrator for multi-source ARV analysis.

Single entry point: analyze_arv() merges all providers, scores comps,
calculates ARV bands, generates explanation, and optionally runs web search.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from LoanMVP.services.ravlo_subject_normalizer import normalize_subject
from LoanMVP.services.ravlo_comp_scorer import score_all_comps
from LoanMVP.services.ravlo_arv_calculator import calculate_arv
from LoanMVP.services.ravlo_arv_explainer import generate_explanation
from LoanMVP.services.ravlo_web_search import should_trigger_web_search, search_comps_web

logger = logging.getLogger(__name__)


def analyze_arv(
    address: str,
    city: str,
    state: str,
    zip_code: str = "",
    property_type: str = "single_family",
    form_overrides: Optional[Dict[str, Any]] = None,
    skip_web_search: bool = False,
    skip_explanation: bool = False,
) -> Dict[str, Any]:
    """
    Full ARV analysis pipeline.

    Returns a comprehensive report with subject facts, ARV bands,
    comp evidence, explanation, and warnings.
    """
    errors: List[str] = []

    # ── Step 1: Gather raw data from providers ──
    attom_data, rentcast_data, mashvisor_data, listing_data, raw_comps, provider_errors = (
        _fetch_all_provider_data(address, city, state, zip_code, property_type)
    )
    errors.extend(provider_errors)

    # ── Step 2: Normalize subject ──
    subject = normalize_subject(attom_data, rentcast_data, mashvisor_data, listing_data)

    # Apply form overrides (user-provided values take priority)
    if form_overrides:
        subject = _apply_overrides(subject, form_overrides)

    # ── Step 3: Build provider estimates dict ──
    provider_estimates = _build_provider_estimates(attom_data, rentcast_data, mashvisor_data)

    # ── Step 4: Score comps ──
    included_comps, rejected_comps = score_all_comps(subject, raw_comps)

    # ── Step 5: Web search fallback ──
    web_search_result = {"searched": False, "results": [], "market_context": "", "error": None}
    if not skip_web_search:
        # Run a preliminary ARV to decide if web search is needed
        preliminary_arv = calculate_arv(subject, included_comps, rejected_comps, provider_estimates)
        if should_trigger_web_search(subject, preliminary_arv, included_comps, provider_estimates):
            web_search_result = search_comps_web(subject, preliminary_arv, included_comps)
            if web_search_result.get("results"):
                # Score web search comps and merge
                web_included, web_rejected = score_all_comps(subject, web_search_result["results"])
                for wc in web_included:
                    wc["source"] = wc.get("source") or "web_search"
                for wc in web_rejected:
                    wc["source"] = wc.get("source") or "web_search"
                included_comps = _merge_comps(included_comps, web_included)
                rejected_comps = _merge_comps(rejected_comps, web_rejected)

    # ── Step 6: Calculate ARV bands ──
    arv_result = calculate_arv(subject, included_comps, rejected_comps, provider_estimates)

    # ── Step 7: Generate explanation ──
    explanation = ""
    if not skip_explanation:
        explanation = generate_explanation(
            subject, arv_result, included_comps, rejected_comps, provider_estimates
        )

    # ── Step 8: Serialize comp evidence ──
    comp_evidence = _serialize_comps(included_comps, rejected_comps)

    return {
        "subject": subject,
        "arv": {
            "conservative": arv_result["conservative"],
            "base": arv_result["base"],
            "aggressive": arv_result["aggressive"],
            "confidence": arv_result["confidence"],
            "confidence_score": arv_result["confidence_score"],
            "land_value": arv_result.get("land_value"),
            "method": arv_result["method"],
        },
        "provider_estimates": provider_estimates,
        "comps": {
            "included": comp_evidence["included"],
            "rejected": comp_evidence["rejected"],
            "total_found": len(included_comps) + len(rejected_comps),
            "total_included": len(included_comps),
            "total_rejected": len(rejected_comps),
        },
        "explanation": explanation,
        "warnings": arv_result.get("warnings", []),
        "web_search_used": web_search_result.get("searched", False),
        "web_search_context": web_search_result.get("market_context", ""),
        "errors": errors,
    }


def _fetch_all_provider_data(
    address: str,
    city: str,
    state: str,
    zip_code: str,
    property_type: str,
) -> tuple:
    """
    Fetch from ATTOM, RentCast, and Mashvisor.
    Returns (attom_data, rentcast_data, mashvisor_data, listing_data, raw_comps, errors).
    """
    errors: List[str] = []
    attom_data: Dict[str, Any] = {}
    rentcast_data: Dict[str, Any] = {}
    mashvisor_data: Dict[str, Any] = {}
    listing_data: Dict[str, Any] = {}
    raw_comps: List[Dict[str, Any]] = []

    # ── ATTOM ──
    try:
        from LoanMVP.services.attom_service import (
            get_property_detail,
            extract_core_fields,
            normalize_attom_property,
        )
        attom_raw = get_property_detail(
            address=address, city=city, state=state, postalcode=zip_code,
        )
        core = extract_core_fields(attom_raw)
        attom_data = normalize_attom_property(core)
    except Exception as e:
        errors.append(f"ATTOM: {e}")
        logger.warning("ATTOM fetch failed: %s", e)

    # ── RentCast: value estimate ──
    try:
        from LoanMVP.services.rentcast_service import get_rentcast_value_estimate
        value_raw = get_rentcast_value_estimate(
            address=address, city=city, state=state,
            zip_code=zip_code, property_type=property_type,
        )
        rentcast_data.update({
            "avm_value": value_raw.get("price") or value_raw.get("value") or value_raw.get("estimatedValue"),
            "value_raw": value_raw,
        })
    except Exception as e:
        errors.append(f"RentCast value: {e}")

    # ── RentCast: rent estimate ──
    try:
        from LoanMVP.services.rentcast_service import get_rentcast_rent_estimate
        rent_raw = get_rentcast_rent_estimate(
            address=address, city=city, state=state,
            zip_code=zip_code, property_type=property_type,
        )
        rentcast_data.update({
            "rent": rent_raw.get("rent") or rent_raw.get("estimatedRent"),
            "traditional_rent": rent_raw.get("rent") or rent_raw.get("estimatedRent"),
            "rent_low": rent_raw.get("rentRangeLow"),
            "rent_high": rent_raw.get("rentRangeHigh"),
            "rent_raw": rent_raw,
        })
    except Exception as e:
        errors.append(f"RentCast rent: {e}")

    # ── RentCast: sale comps (sold) ──
    try:
        from LoanMVP.services.rentcast_service import get_rentcast_sale_listings
        sold_listings = get_rentcast_sale_listings(
            city=city, state=state, zip_code=zip_code,
            status="Sold", limit=20,
        )
        for item in sold_listings:
            item["status"] = item.get("status") or "Sold"
        raw_comps.extend(sold_listings)
    except Exception as e:
        errors.append(f"RentCast sold comps: {e}")

    # ── RentCast: active listings ──
    try:
        from LoanMVP.services.rentcast_service import (
            get_rentcast_sale_listings,
            find_rentcast_sale_listing,
        )
        active_listings = get_rentcast_sale_listings(
            city=city, state=state, zip_code=zip_code,
            status="Active", limit=15,
        )
        for item in active_listings:
            item["status"] = item.get("status") or "Active"
        raw_comps.extend(active_listings)

        # Also try to find the subject's own listing
        subject_listing = find_rentcast_sale_listing(
            address=address, city=city, state=state, zip_code=zip_code,
        )
        if subject_listing:
            listing_data = subject_listing
    except Exception as e:
        errors.append(f"RentCast active listings: {e}")

    # ── RentCast: comps from unified resolver ──
    try:
        from LoanMVP.services.unified_resolver import resolve_property_unified
        resolved = resolve_property_unified(address)
        if resolved.get("status") == "ok":
            prop = resolved.get("property") or {}
            comps_data = prop.get("comps") or {}
            if isinstance(comps_data, dict):
                for c in (comps_data.get("sales") or []):
                    c["status"] = c.get("status") or "Sold"
                    c["source"] = "rentcast_resolver"
                    raw_comps.append(c)
            # Also grab the valuation
            valuation = prop.get("valuation") or {}
            rc_val = valuation.get("value") or valuation.get("price")
            if rc_val:
                rentcast_data["value"] = rc_val
    except Exception as e:
        errors.append(f"Unified resolver: {e}")

    # ── Mashvisor (if configured) ──
    mashvisor_key = os.getenv("MASHVISOR_API_KEY", "").strip()
    if mashvisor_key:
        try:
            from LoanMVP.services.market_service import get_market_snapshot
            mashvisor_data = get_market_snapshot(address, zip_code) or {}
        except Exception as e:
            errors.append(f"Mashvisor: {e}")

    # Deduplicate comps by address
    raw_comps = _deduplicate_comps(raw_comps)

    return attom_data, rentcast_data, mashvisor_data, listing_data, raw_comps, errors


def _build_provider_estimates(
    attom_data: Dict[str, Any],
    rentcast_data: Dict[str, Any],
    mashvisor_data: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    estimates: Dict[str, Dict[str, Any]] = {}

    if attom_data:
        estimates["attom"] = {
            "market_value": attom_data.get("market_value"),
            "assessed_value": attom_data.get("assessed_value"),
            "last_sale_price": attom_data.get("last_sale_price"),
        }

    if rentcast_data:
        estimates["rentcast"] = {
            "avm": rentcast_data.get("avm_value") or rentcast_data.get("value"),
            "rent": rentcast_data.get("rent") or rentcast_data.get("traditional_rent"),
            "rent_low": rentcast_data.get("rent_low"),
            "rent_high": rentcast_data.get("rent_high"),
        }

    if mashvisor_data:
        estimates["mashvisor"] = {
            "value": mashvisor_data.get("estimated_value") or mashvisor_data.get("value"),
            "traditional_rent": mashvisor_data.get("traditional_rent"),
            "airbnb_rent": mashvisor_data.get("airbnb_rent"),
            "occupancy_rate": mashvisor_data.get("occupancy_rate"),
        }

    return estimates


def _apply_overrides(subject: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Apply user form overrides to the normalized subject."""
    field_map = {
        "beds": "beds",
        "baths": "baths",
        "sqft": "living_sqft",
        "living_sqft": "living_sqft",
        "lot_sqft": "lot_sqft",
        "year_built": "year_built",
        "property_type": "property_type",
    }
    for form_key, subj_key in field_map.items():
        val = overrides.get(form_key)
        if val is not None and val != "" and val != "None":
            subject[subj_key] = val
    return subject


def _deduplicate_comps(comps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate comps by normalized address."""
    seen: set = set()
    unique: List[Dict[str, Any]] = []
    for c in comps:
        addr = str(
            c.get("formattedAddress") or c.get("address") or ""
        ).lower().strip().replace(",", "").replace(".", "")
        if not addr or addr in seen:
            continue
        seen.add(addr)
        unique.append(c)
    return unique


def _merge_comps(
    existing: List[Dict[str, Any]],
    new: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Merge new comps into existing list, avoiding duplicates."""
    existing_addrs = {
        str(c.get("formattedAddress") or c.get("address") or "").lower().strip().replace(",", "").replace(".", "")
        for c in existing
    }
    merged = list(existing)
    for c in new:
        addr = str(c.get("formattedAddress") or c.get("address") or "").lower().strip().replace(",", "").replace(".", "")
        if addr and addr not in existing_addrs:
            merged.append(c)
            existing_addrs.add(addr)
    return sorted(merged, key=lambda x: x.get("comp_score", 0), reverse=True)


def _serialize_comps(
    included: List[Dict[str, Any]],
    rejected: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Serialize comps to the storage/display schema."""
    fields = [
        "address", "formattedAddress", "status", "status_normalized",
        "price", "sold_date", "lastSaleDate", "sale_date", "list_date",
        "sqft", "squareFootage", "square_feet",
        "beds", "bedrooms", "baths", "bathrooms",
        "year_built", "yearBuilt",
        "lot_sqft", "lotSize", "lotSizeSqFt",
        "distance", "distance_miles",
        "price_per_sqft", "source", "source_url",
        "comp_score", "score_breakdown",
        "included", "rejection_reason", "inclusion_reasons",
        "months_ago", "property_type", "propertyType",
    ]

    def _pick(comp: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for f in fields:
            if f in comp:
                out[f] = comp[f]
        # Normalize address
        out["address"] = comp.get("address") or comp.get("formattedAddress") or ""
        out["status"] = comp.get("status_normalized") or comp.get("status") or "unknown"
        out["sqft"] = comp.get("sqft") or comp.get("squareFootage") or comp.get("square_feet")
        out["beds"] = comp.get("beds") or comp.get("bedrooms")
        out["baths"] = comp.get("baths") or comp.get("bathrooms")
        out["year_built"] = comp.get("year_built") or comp.get("yearBuilt")
        out["lot_sqft"] = comp.get("lot_sqft") or comp.get("lotSize") or comp.get("lotSizeSqFt")
        out["distance"] = comp.get("distance") or comp.get("distance_miles")
        return out

    return {
        "included": [_pick(c) for c in included],
        "rejected": [_pick(c) for c in rejected],
    }
