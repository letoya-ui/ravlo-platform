from __future__ import annotations

import copy
import json
from datetime import datetime

from flask import current_app
from flask_login import current_user

from LoanMVP.extensions import db
from LoanMVP.models.borrowers import Deal
from LoanMVP.models.investor_models import InvestorProfile
from LoanMVP.models.property import SavedProperty
from LoanMVP.services.unified_resolver import resolve_property_unified
from LoanMVP.services.investor.investor_helpers import (
    _safe_float,
    _safe_int,
)
from LoanMVP.services.investor.investor_saved_property_helpers import (
    _profile_id_filter,
)
from LoanMVP.services.investor.investor_deal_analysis_helpers import (
    _build_deal_architect_payload,
    _attach_deal_architect_signals,
)


def _deal_results(deal):
    return copy.deepcopy(deal.results_json or {})


def _set_deal_results(deal, results):
    from sqlalchemy.orm.attributes import flag_modified

    deal.results_json = copy.deepcopy(results or {})
    flag_modified(deal, "results_json")


def _project_studio_market_label(engine_data: dict, valuation: dict) -> str:
    market_value = _safe_float((valuation or {}).get("market_value"))
    engine_value = _safe_float((engine_data or {}).get("estimated_value"))

    if engine_value and market_value:
        return f"${engine_value:,.0f} engine value vs ${market_value:,.0f} market value."
    if engine_value:
        return f"${engine_value:,.0f} engine value signal."
    if market_value:
        return f"${market_value:,.0f} market value signal."
    return "Live market value is still forming."


def _project_studio_flags(snapshot: dict) -> list[dict]:
    lot_size = _safe_float(snapshot.get("lot_size_sqft")) or 0
    sqft = _safe_float(snapshot.get("square_feet") or snapshot.get("sqft")) or 0
    year_built = _safe_int(snapshot.get("year_built")) or 0
    property_type = str(snapshot.get("property_type") or "").lower()
    dom = _safe_int(snapshot.get("days_on_market")) or 0
    price = _safe_float(snapshot.get("price") or snapshot.get("listing_price"))
    market_value = _safe_float(snapshot.get("market_value") or snapshot.get("engine_value"))

    flags = []

    if lot_size >= 10000:
        flags.append({
            "label": "Oversized Lot",
            "tone": "good",
            "detail": f"{lot_size:,.0f} sq ft creates extra optionality.",
        })

    if lot_size >= 14000 or any(term in property_type for term in ["land", "lot", "vacant"]):
        flags.append({
            "label": "Development Potential",
            "tone": "good",
            "detail": "Lot size and property profile suggest a bigger site play.",
        })

    if year_built and year_built <= 1965 and sqft and sqft <= 1500:
        flags.append({
            "label": "Teardown Potential",
            "tone": "watch",
            "detail": "Older, smaller structure may be less valuable than the site.",
        })

    if dom >= 45:
        flags.append({
            "label": "Negotiation Window",
            "tone": "watch",
            "detail": f"{dom} days on market may create pricing flexibility.",
        })

    if price and market_value and market_value > price:
        flags.append({
            "label": "Spread Detected",
            "tone": "good",
            "detail": f"${market_value - price:,.0f} gap between current price and value signals.",
        })

    return flags[:4]


def _project_studio_strategy_cards(snapshot: dict, engine_data: dict | None) -> list[dict]:
    engine_data = engine_data or {}
    meta = engine_data.get("meta") or {}

    price = _safe_float(
        snapshot.get("price")
        or snapshot.get("listing_price")
        or snapshot.get("last_sale_price")
    ) or 0
    market_value = _safe_float(
        snapshot.get("market_value")
        or engine_data.get("estimated_value")
        or snapshot.get("assessed_value")
    ) or 0
    rent = _safe_float(snapshot.get("traditional_rent") or meta.get("monthly_rent_estimate")) or 0
    sqft = _safe_float(snapshot.get("square_feet") or snapshot.get("sqft")) or 0
    lot_size = _safe_float(snapshot.get("lot_size_sqft")) or 0
    dom = _safe_int(snapshot.get("days_on_market")) or 0
    comp_conf = str(meta.get("comp_confidence") or snapshot.get("comp_confidence") or "Moderate")
    primary_strengths = [
        str(x).strip()
        for x in (meta.get("primary_strengths") or snapshot.get("primary_strengths") or [])
        if str(x).strip()
    ]
    primary_risks = [
        str(x).strip()
        for x in (meta.get("primary_risks") or snapshot.get("primary_risks") or [])
        if str(x).strip()
    ]
    market_label = _project_studio_market_label(engine_data, snapshot)

    rehab_budget_low = max(25000, round(sqft * 28)) if sqft else 45000
    rehab_budget_high = max(rehab_budget_low + 25000, round(sqft * 62)) if sqft else 95000
    rehab_arv = max(market_value, price * 1.18) if price else market_value
    rehab_profit = rehab_arv - price - ((rehab_budget_low + rehab_budget_high) / 2) if price and rehab_arv else None
    rehab_confidence = "High" if market_value and dom <= 45 else "Moderate"

    build_budget_low = max(140000, round((sqft or 900) * 155))
    build_budget_high = max(build_budget_low + 60000, round((sqft or 1100) * 215))
    build_arv = max(
        rehab_arv * 1.08 if rehab_arv else 0,
        market_value * 1.12 if market_value else 0,
    )
    build_outcome = build_arv - price - ((build_budget_low + build_budget_high) / 2) if price and build_arv else None
    build_confidence = "Moderate" if lot_size >= 7000 else "Watch"

    project_units = 4 if lot_size >= 18000 else 3 if lot_size >= 14000 else 2
    project_budget_low = max(260000, project_units * 180000)
    project_budget_high = max(project_budget_low + 140000, project_units * 255000)
    project_arv = max(
        build_arv * 1.35 if build_arv else 0,
        (market_value or rehab_arv or price) * 1.45 if (market_value or rehab_arv or price) else 0,
    )
    project_outcome = project_arv - price - ((project_budget_low + project_budget_high) / 2) if price and project_arv else None
    project_confidence = "Moderate" if lot_size >= 12000 else "Low"

    cards = [
        {
            "key": "rehab",
            "title": "Rehab",
            "badge": None,
            "arv": rehab_arv,
            "budget_low": rehab_budget_low,
            "budget_high": rehab_budget_high,
            "outcome": rehab_profit,
            "outcome_label": "Projected Spread",
            "timeline": "4-8 months",
            "confidence": rehab_confidence,
            "why": primary_strengths[0] if primary_strengths else "Use the existing structure and value gap for a focused improvement plan.",
            "tone": "good" if rehab_profit and rehab_profit > 0 else "watch",
        },
        {
            "key": "build_studio",
            "title": "Build Studio",
            "badge": None,
            "arv": build_arv,
            "budget_low": build_budget_low,
            "budget_high": build_budget_high,
            "outcome": build_outcome,
            "outcome_label": "Projected Outcome",
            "timeline": "8-14 months",
            "confidence": build_confidence,
            "why": "Test a bigger redesign, addition, or structure-first build path before committing to scope.",
            "tone": "good" if lot_size >= 8000 else "watch",
        },
    ]

    if lot_size >= 12000 or any(term in str(snapshot.get("property_type") or "").lower() for term in ["land", "lot", "vacant"]):
        cards.append({
            "key": "project_build",
            "title": "Project Build",
            "badge": None,
            "arv": project_arv,
            "budget_low": project_budget_low,
            "budget_high": project_budget_high,
            "outcome": project_outcome,
            "outcome_label": "Projected Outcome",
            "timeline": "12-20 months",
            "confidence": project_confidence,
            "why": f"Lot size supports a higher-and-better-use path, potentially around {project_units} units.",
            "tone": "good" if lot_size >= 14000 else "watch",
        })

    cards = [c for c in cards if c.get("arv") or c.get("budget_low")]
    cards.sort(
        key=lambda c: (
            _safe_float(c.get("outcome")) is not None,
            _safe_float(c.get("outcome")) or 0,
        ),
        reverse=True,
    )

    if cards:
        cards[0]["badge"] = "Recommended Strategy"

    highest_profit = max(cards, key=lambda c: _safe_float(c.get("outcome")) or float("-inf")) if cards else None
    if highest_profit and highest_profit.get("badge") != "Recommended Strategy":
        highest_profit["badge"] = "Highest Profit"

    lowest_risk = max(
        cards,
        key=lambda c: {"High": 3, "Moderate": 2, "Watch": 1, "Low": 0}.get(c.get("confidence"), 0),
    ) if cards else None
    if lowest_risk and not lowest_risk.get("badge"):
        lowest_risk["badge"] = "Lowest Risk"

    for card in cards:
        card["market_note"] = market_label
        card["comp_confidence"] = comp_conf
        if primary_risks:
            card["risk_note"] = primary_risks[0]
        elif dom >= 60:
            card["risk_note"] = "Long market time suggests demand or pricing friction."
        else:
            card["risk_note"] = "Validate zoning, scope, and exit assumptions before execution."

    recommended_type = str(engine_data.get("recommended_type") or "").strip().lower()
    for card in cards:
        if recommended_type and recommended_type in card["title"].lower():
            card["badge"] = "Recommended Strategy"

    return cards


def _call_deal_architect(payload: dict) -> dict:
    import requests

    engine_url = (current_app.config.get("RENOVATION_ENGINE_URL") or "").rstrip("/")
    if not engine_url:
        raise RuntimeError(
            "RENOVATION_ENGINE_URL is missing. Add it to your Flask app config or environment."
        )

    headers = {"Content-Type": "application/json"}
    api_key = (current_app.config.get("RENOVATION_ENGINE_API_KEY") or "").strip()
    if api_key:
        headers["X-API-Key"] = api_key

    resp = requests.post(
        f"{engine_url}/v1/deal_architect",
        json=payload,
        headers=headers,
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def _project_studio_lookup(address: str, city: str = "", state: str = "", zip_code: str = "") -> dict:
    address = (address or "").strip()
    city = (city or "").strip()
    state = (state or "").strip()
    zip_code = (zip_code or "").strip()
    lookup_parts = [address, city, state, zip_code]
    lookup_address = ", ".join([part for part in lookup_parts if part]).strip(", ")

    resolved = resolve_property_unified(address=lookup_address or address)
    if resolved.get("status") != "ok":
        raise ValueError(resolved.get("error") or "Property lookup failed.")

    property_data = resolved.get("property") or {}
    valuation = resolved.get("valuation") or {}
    rent_estimate = resolved.get("rent_estimate") or {}

    photos = property_data.get("photos") or []
    primary_photo = property_data.get("primary_photo") or (photos[0] if photos else None)

    snapshot = {
        "address": property_data.get("address") or address,
        "city": property_data.get("city") or city,
        "state": property_data.get("state") or state,
        "zip_code": property_data.get("zip_code") or zip_code,
        "property_id": property_data.get("property_id") or property_data.get("attom_id"),
        "property_type": property_data.get("property_type"),
        "beds": property_data.get("beds"),
        "baths": property_data.get("baths"),
        "square_feet": property_data.get("square_feet") or property_data.get("sqft"),
        "sqft": property_data.get("square_feet") or property_data.get("sqft"),
        "lot_size_sqft": property_data.get("lot_size_sqft") or property_data.get("lot_sqft"),
        "year_built": property_data.get("year_built"),
        "price": property_data.get("price") or valuation.get("market_value") or valuation.get("estimated_value"),
        "listing_price": property_data.get("price"),
        "market_value": valuation.get("market_value") or valuation.get("estimated_value"),
        "assessed_value": valuation.get("assessed_value"),
        "last_sale_price": valuation.get("last_sale_price"),
        "tax_amount": valuation.get("tax_amount"),
        "traditional_rent": rent_estimate.get("traditional_rent") or rent_estimate.get("estimated_rent"),
        "days_on_market": property_data.get("days_on_market"),
        "status": property_data.get("status"),
        "description": property_data.get("description"),
        "latitude": property_data.get("latitude"),
        "longitude": property_data.get("longitude"),
        "primary_photo": primary_photo,
        "photos": photos,
    }

    engine_data = None
    engine_error = None
    try:
        engine_data = _call_deal_architect(_build_deal_architect_payload(snapshot, strategy="all"))
        snapshot = _attach_deal_architect_signals(snapshot, engine_data)
    except Exception as exc:
        current_app.logger.warning(
            "project_studio engine enrichment failed for %s: %s",
            snapshot.get("address"),
            exc,
        )
        engine_error = str(exc)

    return {
        "snapshot": snapshot,
        "flags": _project_studio_flags(snapshot),
        "strategy_cards": _project_studio_strategy_cards(snapshot, engine_data),
        "ai_summary": resolved.get("ai_summary") or (engine_data or {}).get("summary"),
        "market_snapshot": resolved.get("market_snapshot") or {},
        "comps": resolved.get("comps") or {},
        "engine_error": engine_error,
    }


def _project_studio_scope_options(selected_strategy: str) -> list[dict]:
    key = (selected_strategy or "").strip().lower()

    if key == "rehab":
        return [
            {"value": "light", "label": "Light / Cosmetic", "detail": "Paint, flooring, fixtures, kitchen and bath refresh."},
            {"value": "medium", "label": "Medium", "detail": "Bigger interior upgrades with selective systems work."},
            {"value": "heavy", "label": "Heavy / Full Gut", "detail": "Major layout, systems, and structural-level renovation."},
        ]

    if key == "build_studio":
        return [
            {"value": "keep_structure", "label": "Keep Existing Structure", "detail": "Reuse the shell and plan around additions or redesign."},
            {"value": "demo_first", "label": "Demo Existing Structure First", "detail": "Clear the site before moving into a build path."},
            {"value": "ai_recommend", "label": "Let AI Recommend", "detail": "Have Ravlo choose between keep-vs-demo based on the site."},
        ]

    if key == "project_build":
        return [
            {"value": "2_units", "label": "2 Units", "detail": "Smaller multi-unit or dual-build concept."},
            {"value": "3_units", "label": "3 Units", "detail": "Mid-density concept for stronger site leverage."},
            {"value": "4_units", "label": "4+ Units", "detail": "Highest-intensity early planning path."},
        ]

    return []


def _project_studio_scope_budget(selected_card: dict | None, selected_strategy: str, selected_scope: str) -> dict | None:
    if not selected_card:
        return None

    low = _safe_float(selected_card.get("budget_low")) or 0
    high = _safe_float(selected_card.get("budget_high")) or 0
    outcome = _safe_float(selected_card.get("outcome"))
    timeline = str(selected_card.get("timeline") or "")

    multipliers = {
        "rehab": {
            "light": (0.85, 0.90, "4-6 months"),
            "medium": (1.0, 1.0, "5-8 months"),
            "heavy": (1.2, 1.3, "7-10 months"),
        },
        "build_studio": {
            "keep_structure": (0.90, 0.92, "8-12 months"),
            "demo_first": (1.08, 1.15, "10-15 months"),
            "ai_recommend": (1.0, 1.04, timeline or "8-14 months"),
        },
        "project_build": {
            "2_units": (0.92, 0.95, "12-16 months"),
            "3_units": (1.0, 1.0, "14-18 months"),
            "4_units": (1.12, 1.18, "16-22 months"),
        },
    }

    strategy_mults = multipliers.get((selected_strategy or "").lower(), {})
    low_mult, high_mult, timeline_out = strategy_mults.get(selected_scope, (1.0, 1.0, timeline or "Planning"))

    scoped_low = round(low * low_mult)
    scoped_high = round(high * high_mult)
    midpoint = (scoped_low + scoped_high) / 2 if scoped_low and scoped_high else None
    refined_outcome = round((outcome or 0) - ((midpoint - ((low + high) / 2)) if midpoint else 0)) if outcome is not None else None

    return {
        "budget_low": scoped_low,
        "budget_high": scoped_high,
        "timeline": timeline_out,
        "outcome": refined_outcome,
        "outcome_label": selected_card.get("outcome_label") or "Projected Outcome",
        "confidence": selected_card.get("confidence") or "Moderate",
    }


def _project_studio_upsert_deal(
    investor_profile,
    snapshot: dict,
    selected_card: dict,
    selected_strategy: str,
    selected_scope: str,
    scope_budget: dict,
    *,
    strategy_cards: list[dict] | None = None,
    flags: list[dict] | None = None,
    ai_summary: str | None = None,
    market_snapshot: dict | None = None,
    deal_id: int | None = None,
):
    address = (snapshot.get("address") or "").strip()
    if not investor_profile or not address or not selected_card or not selected_scope or not scope_budget:
        return None

    property_id = snapshot.get("property_id")
    zipcode = (snapshot.get("zip_code") or "").strip() or None
    city = (snapshot.get("city") or "").strip() or None
    state = (snapshot.get("state") or "").strip() or None
    sqft = snapshot.get("sqft") or snapshot.get("square_feet")

    try:
        sqft = int(float(sqft)) if sqft not in (None, "", "None") else None
    except Exception:
        sqft = None

    fk = _profile_id_filter(SavedProperty, investor_profile.id)
    saved_property = None

    if property_id:
        saved_property = SavedProperty.query.filter_by(
            **fk,
            property_id=str(property_id),
        ).first()

    if not saved_property:
        saved_property = SavedProperty.query.filter(
            getattr(SavedProperty, "investor_profile_id", SavedProperty.borrower_profile_id) == investor_profile.id,
            db.func.lower(SavedProperty.address) == address.lower(),
        ).first()

    if not saved_property:
        saved_property = SavedProperty(
            **fk,
            property_id=str(property_id) if property_id else None,
            address=address,
            price=str(snapshot.get("listing_price") or snapshot.get("price") or ""),
            sqft=sqft,
            zipcode=zipcode,
            saved_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
        db.session.add(saved_property)
        db.session.flush()
    else:
        saved_property.address = address
        saved_property.property_id = str(property_id) if property_id else saved_property.property_id
        saved_property.price = str(snapshot.get("listing_price") or snapshot.get("price") or saved_property.price or "")
        saved_property.sqft = sqft or saved_property.sqft
        saved_property.zipcode = zipcode or saved_property.zipcode
        saved_property.saved_at = datetime.utcnow()

    saved_property_payload = {
        "property": {
            **snapshot,
            "city": city,
            "state": state,
            "zip_code": zipcode,
        },
        "market_snapshot": market_snapshot or {},
        "ai_summary": ai_summary,
        "project_studio": {
            "selected_strategy": selected_strategy,
            "selected_scope": selected_scope,
            "scope_budget": scope_budget,
        },
    }

    if hasattr(saved_property, "resolved_json"):
        saved_property.resolved_json = json.dumps(saved_property_payload)
        saved_property.resolved_at = datetime.utcnow()

    deal = None
    if deal_id:
        deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first()

    if not deal:
        deal = (
            Deal.query
            .filter_by(user_id=current_user.id, saved_property_id=saved_property.id)
            .order_by(Deal.updated_at.desc(), Deal.id.desc())
            .first()
        )

    if not deal:
        deal = Deal.query.filter(
            Deal.user_id == current_user.id,
            db.func.lower(Deal.address) == address.lower(),
        ).order_by(Deal.updated_at.desc(), Deal.id.desc()).first()

    deal_score = snapshot.get("deal_score")
    try:
        deal_score = int(round(float(deal_score))) if deal_score not in (None, "", "None") else None
    except (TypeError, ValueError):
        deal_score = None

    budget_low = scope_budget.get("budget_low")
    budget_high = scope_budget.get("budget_high")
    budget_midpoint = None
    if budget_low not in (None, "", "None") and budget_high not in (None, "", "None"):
        budget_midpoint = (float(budget_low) + float(budget_high)) / 2

    results = _deal_results(deal) if deal else {}
    results["project_studio"] = {
        "selected_strategy": selected_strategy,
        "selected_scope": selected_scope,
        "scope_budget": copy.deepcopy(scope_budget or {}),
        "selected_card": copy.deepcopy(selected_card or {}),
        "strategy_cards": copy.deepcopy(strategy_cards or []),
        "flags": copy.deepcopy(flags or []),
        "snapshot": copy.deepcopy(snapshot or {}),
        "ai_summary": ai_summary,
        "saved_at": datetime.utcnow().isoformat(),
    }
    results["strategy_analysis"] = {
        "strategy": selected_strategy,
        "title": selected_card.get("title"),
        "reason": selected_card.get("why"),
        "risk_note": selected_card.get("risk_note"),
        "confidence": selected_card.get("confidence"),
        "timeline": scope_budget.get("timeline"),
        "outcome": scope_budget.get("outcome"),
        "outcome_label": scope_budget.get("outcome_label"),
    }
    results["workspace_analysis"] = {
        "selected_strategy": selected_strategy,
        "selected_scope": selected_scope,
        "planning_budget": copy.deepcopy(scope_budget or {}),
        "flags": copy.deepcopy(flags or []),
        "ai_summary": ai_summary,
    }

    if selected_strategy == "rehab":
        results["rehab_analysis"] = {
            "estimated_rehab_cost": budget_midpoint,
            "scope": {
                "strategy": selected_strategy,
                "selection": selected_scope,
                "label": selected_card.get("title"),
                "budget_low": budget_low,
                "budget_high": budget_high,
                "timeline": scope_budget.get("timeline"),
            },
        }
    else:
        results.pop("rehab_analysis", None)

    if deal:
        deal.investor_profile_id = investor_profile.id
        deal.saved_property_id = saved_property.id
        deal.property_id = str(property_id) if property_id else deal.property_id
        deal.title = deal.title or address
        deal.address = address
        deal.city = city
        deal.state = state
        deal.zip_code = zipcode
        deal.strategy = selected_strategy
        deal.recommended_strategy = selected_card.get("title") or selected_strategy
        deal.purchase_price = _safe_float(snapshot.get("listing_price") or snapshot.get("price")) or deal.purchase_price or 0
        deal.arv = _safe_float(selected_card.get("arv")) or deal.arv or 0
        deal.estimated_rent = _safe_float(snapshot.get("traditional_rent")) or deal.estimated_rent or 0
        deal.rehab_cost = budget_midpoint or deal.rehab_cost or 0
        deal.deal_score = deal_score if deal_score is not None else deal.deal_score
        deal.resolved_json = {
            "property": copy.deepcopy(snapshot or {}),
            "market_snapshot": copy.deepcopy(market_snapshot or {}),
        }
        if selected_strategy == "rehab":
            deal.rehab_scope_json = results["rehab_analysis"]["scope"]
        else:
            deal.rehab_scope_json = None
        _set_deal_results(deal, results)
    else:
        deal = Deal(
            user_id=current_user.id,
            investor_profile_id=investor_profile.id,
            saved_property_id=saved_property.id,
            property_id=str(property_id) if property_id else None,
            title=address,
            address=address,
            city=city,
            state=state,
            zip_code=zipcode,
            strategy=selected_strategy,
            recommended_strategy=selected_card.get("title") or selected_strategy,
            purchase_price=_safe_float(snapshot.get("listing_price") or snapshot.get("price")) or 0,
            arv=_safe_float(selected_card.get("arv")) or 0,
            estimated_rent=_safe_float(snapshot.get("traditional_rent")) or 0,
            rehab_cost=budget_midpoint or 0,
            deal_score=deal_score,
            results_json={},
            resolved_json={
                "property": copy.deepcopy(snapshot or {}),
                "market_snapshot": copy.deepcopy(market_snapshot or {}),
            },
            rehab_scope_json=(results.get("rehab_analysis") or {}).get("scope") if selected_strategy == "rehab" else None,
            status="active",
        )
        db.session.add(deal)
        db.session.flush()
        _set_deal_results(deal, results)

    db.session.commit()
    return deal