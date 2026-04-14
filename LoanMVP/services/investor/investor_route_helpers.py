from __future__ import annotations

import copy
import hashlib
from datetime import datetime

from flask_login import current_user

from LoanMVP.extensions import db
from LoanMVP.models.borrowers import Deal
from LoanMVP.models.investor_models import InvestorProfile
from LoanMVP.models.renovation_models import RenovationMockup
from LoanMVP.services.investor.investor_helpers import safe_float, safe_int
from LoanMVP.services.investor.investor_media_helpers import _normalize_photo_urls, _resolve_photo


def search_external_partners_google(search_google_places, *, category="", city="", state="", limit=8):
    location_text = ", ".join([part for part in [city, state] if part]).strip(", ")
    return search_google_places(location_text=location_text, category=category, limit=limit)


def _set_if_attr(obj, attr_name, value) -> bool:
    if hasattr(obj, attr_name):
        setattr(obj, attr_name, value)
        return True
    return False


def _get_owned_deal_or_404(deal_id: int):
    return Deal.query.filter_by(id=deal_id, user_id=current_user.id).first_or_404()


def _safe_first_related(obj, relationship_name: str):
    related = getattr(obj, relationship_name, None)
    if related is None:
        return None
    if hasattr(related, "first") and callable(related.first):
        return related.first()
    if isinstance(related, (list, tuple)):
        return related[0] if related else None
    return related


def _render_state_blob(deal, deal_results):
    results = deal_results(deal)
    return results.get("_render_state", {}) or {}


def _route_state_helpers():
    from LoanMVP.routes.investor_routes import _deal_results, _set_deal_results
    return _deal_results, _set_deal_results


def _deal_render_lock_active(deal) -> bool:
    deal_results, _ = _route_state_helpers()
    return bool(_render_state_blob(deal, deal_results).get("processing"))


def _set_deal_render_processing(deal):
    deal_results, set_deal_results = _route_state_helpers()
    results = deal_results(deal)
    state = results.get("_render_state", {}) or {}
    state.update({"processing": True, "started_at": datetime.utcnow().isoformat()})
    results["_render_state"] = state
    set_deal_results(deal, results)


def _clear_deal_render_processing(deal):
    deal_results, set_deal_results = _route_state_helpers()
    results = deal_results(deal)
    state = results.get("_render_state", {}) or {}
    state.update({"processing": False, "cleared_at": datetime.utcnow().isoformat()})
    results["_render_state"] = state
    set_deal_results(deal, results)


def _normalize_style_preset(value: str) -> str:
    preset = (value or "").strip().lower()
    allowed = {"luxury", "modern", "coastal", "industrial", "minimal", "hgtv"}
    return preset if preset in allowed else "luxury"


def _stable_render_seed(*parts) -> int:
    source = "|".join(str(part or "").strip() for part in parts)
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _save_before_url_to_deal(deal, before_url: str):
    deal_results, set_deal_results = _route_state_helpers()
    results = deal_results(deal)
    rehab_project = results.get("rehab_project", {}) or {}
    rehab_project["before"] = {"image_url": before_url}
    results["rehab_project"] = rehab_project
    set_deal_results(deal, results)
    if hasattr(deal, "final_before_url"):
        deal.final_before_url = before_url
    db.session.commit()


def _save_mockups_for_deal(*, deal, before_url, after_urls, style_prompt="", style_preset="", mode="", saved_property_id=None):
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    saved = 0
    for after_url in after_urls or []:
        db.session.add(RenovationMockup(
            user_id=current_user.id,
            investor_profile_id=getattr(ip, "id", None),
            property_id=getattr(deal, "property_id", None),
            saved_property_id=saved_property_id or getattr(deal, "saved_property_id", None),
            deal_id=deal.id,
            before_url=before_url,
            after_url=after_url,
            style_prompt=style_prompt or mode,
            style_preset=style_preset or mode,
        ))
        saved += 1
    if saved:
        db.session.flush()
    return saved


def _get_rehab_mockups_for_deal(deal):
    return (
        RenovationMockup.query
        .filter_by(deal_id=deal.id, user_id=current_user.id)
        .order_by(RenovationMockup.created_at.desc(), RenovationMockup.id.desc())
        .all()
    )


def _set_featured_rehab(*, deal, after_url, before_url="", style_preset="", style_prompt=""):
    deal_results, set_deal_results = _route_state_helpers()
    featured = {
        "after_url": after_url,
        "before_url": before_url,
        "style_preset": _normalize_style_preset(style_preset),
        "style_prompt": style_prompt,
        "updated_at": datetime.utcnow().isoformat(),
    }
    results = deal_results(deal)
    rehab_project = results.get("rehab_project", {}) or {}
    rehab_project["featured"] = featured
    results["rehab_project"] = rehab_project
    set_deal_results(deal, results)
    db.session.commit()
    return featured


def _featured_rehab_data(deal):
    deal_results, _ = _route_state_helpers()
    results = deal_results(deal)
    rehab_project = results.get("rehab_project", {}) or {}
    return rehab_project.get("featured", {}) or {}


def _get_rehab_export_payload(deal):
    deal_results, _ = _route_state_helpers()
    results = deal_results(deal)
    rehab_scope = results.get("rehab_scope") or getattr(deal, "rehab_scope_json", None) or {}
    rehab_project = results.get("rehab_project", {}) or {}
    featured = rehab_project.get("featured", {}) or {}
    latest = rehab_project.get("latest", {}) or {}
    return {
        "scope": rehab_scope,
        "total": rehab_scope.get("cost_high") or rehab_scope.get("estimated_rehab_cost") or getattr(deal, "rehab_cost", None),
        "estimated_rehab_cost": rehab_scope.get("cost_high") or getattr(deal, "rehab_cost", None),
        "cost_per_sqft": rehab_scope.get("cost_per_sqft"),
        "items": rehab_scope.get("line_items") or rehab_scope.get("items") or {},
        "before_url": featured.get("before_url") or (rehab_project.get("before", {}) or {}).get("image_url"),
        "after_url": featured.get("after_url") or latest.get("image_url"),
    }


def _build_budget_seed_from_results(results: dict) -> dict:
    rehab_scope = results.get("rehab_scope", {}) or {}
    build_analysis = results.get("build_analysis", {}) or {}
    rehab_project = results.get("rehab_project", {}) or {}
    latest = rehab_project.get("latest", {}) or {}
    return {
        "rehab_cost": rehab_scope.get("cost_high") or rehab_scope.get("estimated_rehab_cost"),
        "arv": rehab_scope.get("arv") or build_analysis.get("projected_value"),
        "line_items": rehab_scope.get("line_items") or build_analysis.get("line_items") or [],
        "before_url": (rehab_project.get("before", {}) or {}).get("image_url"),
        "after_url": latest.get("image_url"),
    }


def _build_loan_sizing_from_budget(deal, budget):
    purchase_price = safe_float(getattr(deal, "purchase_price", None)) or 0
    rehab_cost = safe_float(getattr(deal, "rehab_cost", None)) or 0
    arv = safe_float(getattr(deal, "arv", None)) or 0
    total_budget = safe_float(getattr(budget, "total_budget", None)) or safe_float(getattr(budget, "total_cost", None)) or rehab_cost
    total_project_cost = purchase_price + total_budget
    return {
        "purchase_price": purchase_price,
        "rehab_budget": total_budget,
        "project_cost": total_project_cost,
        "arv": arv,
        "max_ltc_85": round(total_project_cost * 0.85, 2) if total_project_cost else 0,
        "max_ltv_75": round(arv * 0.75, 2) if arv else 0,
    }


def _build_mashvisor_insight(scope_budget: dict | None, mashvisor_data: dict | None) -> dict:
    from LoanMVP.routes.investor_routes import _fmt_money
    scope_budget = scope_budget or {}
    mashvisor_data = mashvisor_data or {}
    rent = safe_float(mashvisor_data.get("traditional_rent"))
    airbnb = safe_float(mashvisor_data.get("airbnb_revenue"))
    budget_high = safe_float(scope_budget.get("budget_high"))
    return {
        "traditional_rent": rent,
        "airbnb_revenue": airbnb,
        "budget_high": budget_high,
        "summary": (
            f"Traditional rent signal is {fmt_money(rent)} and short-term revenue signal is {fmt_money(airbnb)} "
            f"against a projected scope ceiling of {fmt_money(budget_high)}."
        ),
    }


def _build_attom_fallback(raw: dict) -> dict:
    photos = _normalize_photo_urls(raw.get("photos"), raw.get("media"), raw.get("gallery"))
    return {
        "address": (raw.get("address_line1") or raw.get("address") or raw.get("address_one_line") or "").strip(),
        "city": (raw.get("city") or "").strip(),
        "state": (raw.get("state") or "").strip(),
        "zip_code": (raw.get("zip_code") or raw.get("postal_code") or "").strip(),
        "property_type": raw.get("property_type"),
        "beds": safe_int(raw.get("beds") or raw.get("bedrooms")),
        "baths": safe_float(raw.get("baths") or raw.get("bathrooms")),
        "square_feet": safe_int(raw.get("square_feet") or raw.get("sqft")),
        "lot_size_sqft": safe_int(raw.get("lot_size_sqft") or raw.get("lot_sqft")),
        "year_built": safe_int(raw.get("year_built")),
        "price": safe_float(raw.get("price") or raw.get("listing_price")),
        "listing_price": safe_float(raw.get("price") or raw.get("listing_price")),
        "last_sale_price": safe_float(raw.get("last_sale_price")),
        "assessed_value": safe_float(raw.get("assessed_value")),
        "market_value": safe_float(raw.get("market_value") or raw.get("estimated_value")),
        "traditional_rent": safe_float(raw.get("traditional_rent") or raw.get("rent")),
        "days_on_market": safe_int(raw.get("days_on_market")),
        "latitude": raw.get("latitude"),
        "longitude": raw.get("longitude"),
        "primary_photo": _resolve_photo(raw.get("primary_photo"), photos),
        "photos": photos,
    }


def _annotate_deal_finder_opportunity(result: dict, strategy: str) -> dict:
    annotated = copy.deepcopy(result or {})
    score = safe_float(annotated.get("deal_score") or annotated.get("ravlo_score"))
    annotated["strategy"] = strategy
    annotated["strategy_label"] = (strategy or "hold").replace("_", " ").title()
    annotated["score_badge"] = "High Priority" if score and score >= 80 else "Review" if score and score >= 60 else "Early Look"
    return annotated

def _property_matches_asset_type(prop: dict, asset_type: str | None) -> bool:
    normalized_filter = _normalize_asset_type(asset_type)
    if normalized_filter == "any":
        return True

    prop_type = _normalize_asset_type(
        prop.get("property_type")
        or prop.get("prop_type")
        or prop.get("type")
        or prop.get("property_sub_type")
        or ""
    )

    if prop_type == normalized_filter:
        return True

    if normalized_filter == "multifamily" and prop_type in {"apartment", "duplex", "triplex", "quadplex"}:
        return True

    if normalized_filter == "hospitality" and prop_type in {"hotel", "motel"}:
        return True

    return False

def _normalize_asset_type(value: str | None) -> str:
    """
    Normalize UI / provider asset-type values into a stable internal key.
    """
    raw = (value or "").strip().lower()

    if not raw:
        return "any"

    aliases = {
        "any": "any",
        "all": "any",
        "all asset types": "any",

        "single family": "single_family",
        "single_family": "single_family",
        "single-family": "single_family",
        "sfr": "single_family",

        "multifamily": "multifamily",
        "multi family": "multifamily",
        "multi-family": "multifamily",

        "office": "office",
        "retail": "retail",
        "restaurant": "restaurant",

        "mixed use": "mixed_use",
        "mixed_use": "mixed_use",
        "mixed-use": "mixed_use",

        "industrial": "industrial",
        "warehouse": "warehouse",
        "hospitality": "hospitality",
        "hotel": "hospitality",
        "medical": "medical",

        "land": "land",
        "lot": "land",
    }

    return aliases.get(raw, raw.replace(" ", "_").replace("-", "_"))


def _asset_type_label(asset_type: str | None) -> str:
    """
    Human-friendly label for UI responses.
    """
    normalized = _normalize_asset_type(asset_type)

    labels = {
        "any": "All Asset Types",
        "single_family": "Single Family",
        "multifamily": "Multifamily",
        "office": "Office",
        "retail": "Retail",
        "restaurant": "Restaurant",
        "mixed_use": "Mixed Use",
        "industrial": "Industrial",
        "warehouse": "Warehouse",
        "hospitality": "Hospitality",
        "medical": "Medical",
        "land": "Land",
    }

    return labels.get(normalized, normalized.replace("_", " ").title())