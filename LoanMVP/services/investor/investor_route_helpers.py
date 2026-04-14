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

def normalize_workspace_comps(raw_comps):
    normalized = []

    for comp in raw_comps or []:
        if not isinstance(comp, dict):
            continue

        normalized.append({
            "address": comp.get("address") or comp.get("formatted_address"),
            "price": to_float(comp.get("price") or comp.get("sale_price") or comp.get("list_price")),
            "sqft": to_float(comp.get("sqft") or comp.get("square_feet")),
            "beds": to_float(comp.get("beds") or comp.get("bedrooms")),
            "baths": to_float(comp.get("baths") or comp.get("bathrooms")),
            "distance_miles": to_float(comp.get("distance_miles") or comp.get("distance")),
            "months_ago": to_float(comp.get("months_ago") or comp.get("sold_months_ago")),
            "source": comp.get("source"),
        })

    return normalized

    def build_exit_strategy_analysis(selected_prop, deal, workspace_analysis, comps, comparison):
    property_type = (
        workspace_analysis.get("property_type")
        or getattr(selected_prop, "property_type", "")
        or ""
    ).lower()

    sqft = to_float(
        workspace_analysis.get("square_feet")
        or getattr(selected_prop, "sqft", 0)
        or getattr(selected_prop, "square_feet", 0)
    )
    beds = to_float(workspace_analysis.get("beds") or getattr(selected_prop, "beds", 0))
    baths = to_float(workspace_analysis.get("baths") or getattr(selected_prop, "baths", 0))
    lot_size = to_float(workspace_analysis.get("lot_size_sqft") or getattr(selected_prop, "lot_size_sqft", 0))

    has_structure = bool(sqft or beds or baths)
    looks_like_land = any(x in property_type for x in ["land", "lot", "vacant", "acre"]) or (lot_size and not has_structure)

    flip = comparison.get("flip", {})
    rental = comparison.get("rental", {})
    airbnb = comparison.get("airbnb", {})
    land = comparison.get("land", {})

    flip_profit = to_float(flip.get("profit"))
    flip_roi = to_float(flip.get("roi")) * 100
    rental_cap = to_float(rental.get("cap_rate")) * 100
    rental_cashflow = to_float(rental.get("net_cashflow"))
    airbnb_net = to_float(airbnb.get("net_monthly"))
    airbnb_occ = to_float(airbnb.get("occupancy_rate")) * 100
    land_score = to_float(land.get("score"))

    if looks_like_land:
        property_classification = "land"
    elif flip_profit > 0 and flip_roi >= 12:
        property_classification = "fixer_upper"
    elif airbnb_net > rental_cashflow and airbnb_occ >= 45:
        property_classification = "str_candidate"
    elif rental_cashflow > 0 or rental_cap >= 5:
        property_classification = "rental_candidate"
    else:
        property_classification = "general_opportunity"

    strategy_scores = {
        "flip": max(flip_roi, 0) + (10 if flip_profit > 0 else 0),
        "rental": max(rental_cap, 0) + (8 if rental_cashflow > 0 else 0),
        "airbnb": max((airbnb_net * 12) / max(to_float((deal.purchase_price if deal else None) or workspace_analysis.get("purchase_price") or getattr(selected_prop, "price", 1)), 1) * 100, 0),
        "land": land_score if property_classification == "land" else max(land_score - 25, 0),
    }

    best_exit = max(strategy_scores, key=strategy_scores.get)

    reasons = {
        "flip": "Flip shows the best spread between basis and exit value.",
        "rental": "Rental shows the strongest risk-adjusted hold profile with recurring income support.",
        "airbnb": "Short-term rental shows the highest revenue upside based on current hospitality assumptions.",
        "land": "This opportunity looks better as land optionality or a build-oriented play than a standard residential hold.",
    }

    why = {
        "flip": [
            "Projected flip margin is competitive.",
            "ARV appears to support a resale thesis.",
            "This looks more like a value-add than a stabilized hold."
        ],
        "rental": [
            "Rent support is present.",
            "The hold profile looks more stable than the resale spread.",
            "This asset appears to fit a long-term residential strategy."
        ],
        "airbnb": [
            "Short-term revenue appears stronger than long-term rent.",
            "Hospitality-style upside may justify deeper underwriting.",
            "The property may support a higher-revenue furnished strategy."
        ],
        "land": [
            "The asset reads more like land or optionality than a conventional income property.",
            "Structure data is limited relative to site size or parcel value.",
            "A build or hold thesis may be stronger than a standard buy-and-hold."
        ],
    }

    watch_items = {
        "flip": [
            "Verify final rehab scope and sale costs.",
            "Stress-test ARV against conservative comps.",
        ],
        "rental": [
            "Confirm taxes, insurance, and maintenance assumptions.",
            "Verify long-term rent support with current comps.",
        ],
        "airbnb": [
            "Validate STR regulation and seasonality.",
            "Confirm occupancy and nightly rate assumptions.",
        ],
        "land": [
            "Verify zoning and entitlement path.",
            "Validate utility access, frontage, and resale demand.",
        ],
    }

    cards = [
        {
            "key": "flip",
            "label": "Flip",
            "headline_label": "Projected Profit",
            "headline_value": flip_profit,
            "score": strategy_scores["flip"],
            "summary": reasons["flip"],
            "metrics": flip,
        },
        {
            "key": "rental",
            "label": "Rental",
            "headline_label": "Monthly Cash Flow",
            "headline_value": rental_cashflow,
            "score": strategy_scores["rental"],
            "summary": reasons["rental"],
            "metrics": rental,
        },
        {
            "key": "airbnb",
            "label": "Airbnb",
            "headline_label": "Net Monthly",
            "headline_value": airbnb_net,
            "score": strategy_scores["airbnb"],
            "summary": reasons["airbnb"],
            "metrics": airbnb,
        },
        {
            "key": "land",
            "label": "Land / Build",
            "headline_label": "Optionality Score",
            "headline_value": land_score,
            "score": strategy_scores["land"],
            "summary": reasons["land"],
            "metrics": land,
        },
    ]

    return {
        "property_classification": property_classification,
        "exit_strategy_cards": cards,
        "best_exit_strategy": best_exit,
        "best_exit_reason": reasons[best_exit],
        "ai_recommendation": {
            "confidence": "high" if strategy_scores[best_exit] >= 12 else "moderate",
            "why": why[best_exit],
            "watch_items": watch_items[best_exit],
        },
    }

    def build_exit_strategy_analysis(selected_prop, deal, workspace_analysis, comps, comparison):
    property_type = (
        workspace_analysis.get("property_type")
        or getattr(selected_prop, "property_type", "")
        or ""
    ).lower()

    sqft = to_float(
        workspace_analysis.get("square_feet")
        or getattr(selected_prop, "sqft", 0)
        or getattr(selected_prop, "square_feet", 0)
    )
    beds = to_float(workspace_analysis.get("beds") or getattr(selected_prop, "beds", 0))
    baths = to_float(workspace_analysis.get("baths") or getattr(selected_prop, "baths", 0))
    lot_size = to_float(workspace_analysis.get("lot_size_sqft") or getattr(selected_prop, "lot_size_sqft", 0))

    has_structure = bool(sqft or beds or baths)
    looks_like_land = any(x in property_type for x in ["land", "lot", "vacant", "acre"]) or (lot_size and not has_structure)

    flip = comparison.get("flip", {})
    rental = comparison.get("rental", {})
    airbnb = comparison.get("airbnb", {})
    land = comparison.get("land", {})

    flip_profit = to_float(flip.get("profit"))
    flip_roi = to_float(flip.get("roi")) * 100
    rental_cap = to_float(rental.get("cap_rate")) * 100
    rental_cashflow = to_float(rental.get("net_cashflow"))
    airbnb_net = to_float(airbnb.get("net_monthly"))
    airbnb_occ = to_float(airbnb.get("occupancy_rate")) * 100
    land_score = to_float(land.get("score"))

    if looks_like_land:
        property_classification = "land"
    elif flip_profit > 0 and flip_roi >= 12:
        property_classification = "fixer_upper"
    elif airbnb_net > rental_cashflow and airbnb_occ >= 45:
        property_classification = "str_candidate"
    elif rental_cashflow > 0 or rental_cap >= 5:
        property_classification = "rental_candidate"
    else:
        property_classification = "general_opportunity"

    strategy_scores = {
        "flip": max(flip_roi, 0) + (10 if flip_profit > 0 else 0),
        "rental": max(rental_cap, 0) + (8 if rental_cashflow > 0 else 0),
        "airbnb": max((airbnb_net * 12) / max(to_float((deal.purchase_price if deal else None) or workspace_analysis.get("purchase_price") or getattr(selected_prop, "price", 1)), 1) * 100, 0),
        "land": land_score if property_classification == "land" else max(land_score - 25, 0),
    }

    best_exit = max(strategy_scores, key=strategy_scores.get)

    reasons = {
        "flip": "Flip shows the best spread between basis and exit value.",
        "rental": "Rental shows the strongest risk-adjusted hold profile with recurring income support.",
        "airbnb": "Short-term rental shows the highest revenue upside based on current hospitality assumptions.",
        "land": "This opportunity looks better as land optionality or a build-oriented play than a standard residential hold.",
    }

    why = {
        "flip": [
            "Projected flip margin is competitive.",
            "ARV appears to support a resale thesis.",
            "This looks more like a value-add than a stabilized hold."
        ],
        "rental": [
            "Rent support is present.",
            "The hold profile looks more stable than the resale spread.",
            "This asset appears to fit a long-term residential strategy."
        ],
        "airbnb": [
            "Short-term revenue appears stronger than long-term rent.",
            "Hospitality-style upside may justify deeper underwriting.",
            "The property may support a higher-revenue furnished strategy."
        ],
        "land": [
            "The asset reads more like land or optionality than a conventional income property.",
            "Structure data is limited relative to site size or parcel value.",
            "A build or hold thesis may be stronger than a standard buy-and-hold."
        ],
    }

    watch_items = {
        "flip": [
            "Verify final rehab scope and sale costs.",
            "Stress-test ARV against conservative comps.",
        ],
        "rental": [
            "Confirm taxes, insurance, and maintenance assumptions.",
            "Verify long-term rent support with current comps.",
        ],
        "airbnb": [
            "Validate STR regulation and seasonality.",
            "Confirm occupancy and nightly rate assumptions.",
        ],
        "land": [
            "Verify zoning and entitlement path.",
            "Validate utility access, frontage, and resale demand.",
        ],
    }

    cards = [
        {
            "key": "flip",
            "label": "Flip",
            "headline_label": "Projected Profit",
            "headline_value": flip_profit,
            "score": strategy_scores["flip"],
            "summary": reasons["flip"],
            "metrics": flip,
        },
        {
            "key": "rental",
            "label": "Rental",
            "headline_label": "Monthly Cash Flow",
            "headline_value": rental_cashflow,
            "score": strategy_scores["rental"],
            "summary": reasons["rental"],
            "metrics": rental,
        },
        {
            "key": "airbnb",
            "label": "Airbnb",
            "headline_label": "Net Monthly",
            "headline_value": airbnb_net,
            "score": strategy_scores["airbnb"],
            "summary": reasons["airbnb"],
            "metrics": airbnb,
        },
        {
            "key": "land",
            "label": "Land / Build",
            "headline_label": "Optionality Score",
            "headline_value": land_score,
            "score": strategy_scores["land"],
            "summary": reasons["land"],
            "metrics": land,
        },
    ]

    return {
        "property_classification": property_classification,
        "exit_strategy_cards": cards,
        "best_exit_strategy": best_exit,
        "best_exit_reason": reasons[best_exit],
        "ai_recommendation": {
            "confidence": "high" if strategy_scores[best_exit] >= 12 else "moderate",
            "why": why[best_exit],
            "watch_items": watch_items[best_exit],
        },
    }
