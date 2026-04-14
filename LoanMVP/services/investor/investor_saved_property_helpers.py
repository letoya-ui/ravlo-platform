from __future__ import annotations

import json
from datetime import datetime

from flask import jsonify
from flask_login import current_user

from LoanMVP.extensions import db
from LoanMVP.models.investor_models import InvestorProfile
from LoanMVP.models.property import SavedProperty
from LoanMVP.services.investor.investor_helpers import (
    _clean_str,
    _clean_num,
    _clean_int,
    _safe_json_list,
    _safe_json_loads_local,
)


def _profile_id_filter(model, profile_id):
    if hasattr(model, "investor_profile_id"):
        return {"investor_profile_id": profile_id}
    if hasattr(model, "borrower_profile_id"):
        return {"borrower_profile_id": profile_id}
    return {}


def _property_payload_from_any(payload) -> dict:
    raw = _safe_json_loads_local(payload, default={})
    if not isinstance(raw, dict):
        return {}

    prop = raw.get("property")
    if isinstance(prop, dict):
        return prop

    return raw


def _merge_nonempty_dict(target: dict, source: dict) -> dict:
    target = target if isinstance(target, dict) else {}
    if not isinstance(source, dict):
        return target

    for key, value in source.items():
        if value not in (None, "", [], {}):
            target[key] = value
    return target


def _get_investor_profile_or_error():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        return None, (
            jsonify({
                "status": "error",
                "message": "Profile not found."
            }),
            400,
        )
    return ip, None


def _find_existing_saved_property(ip, payload):
    address = _clean_str(payload.get("address"))
    property_id = _clean_str(payload.get("property_id") or payload.get("attom_id"))

    fk = _profile_id_filter(SavedProperty, ip.id)
    existing = None

    if property_id:
        existing = SavedProperty.query.filter_by(
            **fk,
            property_id=property_id
        ).first()

    if not existing and address:
        existing = SavedProperty.query.filter(
            getattr(SavedProperty, "investor_profile_id", SavedProperty.borrower_profile_id) == ip.id,
            db.func.lower(SavedProperty.address) == address.lower()
        ).first()

    return existing


def _assign_if_has_attr(model_obj, field_name, value):
    if hasattr(model_obj, field_name) and value is not None:
        setattr(model_obj, field_name, value)


def _clean_string_list(value):
    if not value:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        value = value.strip()
        return [value] if value else []
    return [str(value).strip()] if str(value).strip() else []


def _persist_property_core_fields(saved, payload):
    """
    Persist richer canonical fields when the SavedProperty model supports them.
    This is intentionally defensive so it works with your current schema.
    """
    address = _clean_str(payload.get("address"))
    city = _clean_str(payload.get("city"))
    state = _clean_str(payload.get("state"))
    zipcode = _clean_str(payload.get("zip") or payload.get("zip_code"))
    property_id = _clean_str(payload.get("property_id") or payload.get("attom_id"))

    purchase_price = _clean_num(
        payload.get("purchase_price")
        or payload.get("price")
        or payload.get("display_value")
        or payload.get("last_sale_price")
    )
    arv = _clean_num(
        payload.get("arv")
        or payload.get("estimated_value_engine")
        or payload.get("market_value")
        or payload.get("engine_value")
    )
    market_value = _clean_num(payload.get("market_value"))
    assessed_value = _clean_num(payload.get("assessed_value"))
    monthly_rent = _clean_num(payload.get("monthly_rent") or payload.get("monthly_rent_estimate"))
    last_sale_price = _clean_num(payload.get("last_sale_price"))

    sqft = _clean_int(payload.get("sqft") or payload.get("square_feet"))
    lot_size_sqft = _clean_int(payload.get("lot_size_sqft"))
    beds = _clean_num(payload.get("beds"))
    baths = _clean_num(payload.get("baths"))
    year_built = _clean_int(payload.get("year_built"))

    latitude = _clean_num(payload.get("latitude"))
    longitude = _clean_num(payload.get("longitude"))

    strategy = _clean_str(payload.get("strategy"))
    strategy_tag = _clean_str(payload.get("strategy_tag"))
    recommended_strategy = _clean_str(payload.get("recommended_strategy"))
    estimated_best_use = _clean_str(payload.get("estimated_best_use"))
    property_type = _clean_str(payload.get("property_type"))

    deal_score = _clean_num(payload.get("deal_score"))
    opportunity_tier = _clean_str(payload.get("opportunity_tier"))
    deal_finder_signal = _clean_str(payload.get("deal_finder_signal"))
    next_step = _clean_str(payload.get("next_step"))
    comp_confidence = _clean_str(payload.get("comp_confidence"))
    image_url = _clean_str(payload.get("image_url"))
    description = _clean_str(payload.get("description"))
    listing_photos = _clean_string_list(payload.get("listing_photos"))

    if address:
        saved.address = address

    if property_id:
        _assign_if_has_attr(saved, "property_id", property_id)

    # keep your existing core fields in sync
    if purchase_price is not None:
        price_as_string = str(int(purchase_price)) if float(purchase_price).is_integer() else str(purchase_price)
        _assign_if_has_attr(saved, "price", price_as_string)
        _assign_if_has_attr(saved, "purchase_price", purchase_price)

    if sqft is not None:
        _assign_if_has_attr(saved, "sqft", sqft)

    if zipcode:
        if hasattr(saved, "zipcode"):
            saved.zipcode = zipcode
        elif hasattr(saved, "zip_code"):
            saved.zip_code = zipcode

    # richer optional fields
    _assign_if_has_attr(saved, "city", city)
    _assign_if_has_attr(saved, "state", state)
    _assign_if_has_attr(saved, "property_type", property_type)
    _assign_if_has_attr(saved, "beds", beds)
    _assign_if_has_attr(saved, "baths", baths)
    _assign_if_has_attr(saved, "year_built", year_built)
    _assign_if_has_attr(saved, "square_feet", sqft)
    _assign_if_has_attr(saved, "lot_size_sqft", lot_size_sqft)
    _assign_if_has_attr(saved, "assessed_value", assessed_value)
    _assign_if_has_attr(saved, "market_value", market_value)
    _assign_if_has_attr(saved, "arv", arv)
    _assign_if_has_attr(saved, "monthly_rent", monthly_rent)
    _assign_if_has_attr(saved, "monthly_rent_estimate", monthly_rent)
    _assign_if_has_attr(saved, "last_sale_price", last_sale_price)
    _assign_if_has_attr(saved, "latitude", latitude)
    _assign_if_has_attr(saved, "longitude", longitude)

    _assign_if_has_attr(saved, "strategy", strategy)
    _assign_if_has_attr(saved, "strategy_tag", strategy_tag)
    _assign_if_has_attr(saved, "recommended_strategy", recommended_strategy)
    _assign_if_has_attr(saved, "estimated_best_use", estimated_best_use)

    _assign_if_has_attr(saved, "deal_score", deal_score)
    _assign_if_has_attr(saved, "opportunity_tier", opportunity_tier)
    _assign_if_has_attr(saved, "deal_finder_signal", deal_finder_signal)
    _assign_if_has_attr(saved, "next_step", next_step)
    _assign_if_has_attr(saved, "comp_confidence", comp_confidence)
    listing_photos = _clean_string_list(payload.get("listing_photos"))

    best_image_url = None
    if listing_photos:
        best_image_url = listing_photos[0]
    elif image_url:
        best_image_url = image_url

    _assign_if_has_attr(saved, "image_url", best_image_url)
    _assign_if_has_attr(saved, "image_url", image_url)
    _assign_if_has_attr(saved, "description", description)

    # optional JSON/meta fields if your model supports them
    _assign_if_has_attr(saved, "primary_strengths", _safe_json_list(payload.get("primary_strengths")))
    _assign_if_has_attr(saved, "primary_risks", _safe_json_list(payload.get("primary_risks")))
    _assign_if_has_attr(saved, "risk_notes", _safe_json_list(payload.get("risk_notes")))
    _assign_if_has_attr(saved, "why_it_made_list", _safe_json_list(payload.get("why_it_made_list")))

    # photo collections if your model supports them
    if listing_photos:
        _assign_if_has_attr(saved, "listing_photos_json", listing_photos)
        _assign_if_has_attr(saved, "photos_json", listing_photos)

    # status / timestamps if present on model
    _assign_if_has_attr(saved, "analysis_status", "pending")
    _assign_if_has_attr(saved, "budget_status", "pending")
    _assign_if_has_attr(saved, "last_synced_at", datetime.utcnow())
    _assign_if_has_attr(saved, "updated_at", datetime.utcnow())


def _upsert_saved_property_from_payload(ip, payload):
    address = _clean_str(payload.get("address"))
    if not address:
        raise ValueError("Address is required.")

    purchase_price = (
        payload.get("purchase_price")
        or payload.get("price")
        or payload.get("display_value")
        or payload.get("last_sale_price")
    )
    sqft = _clean_int(payload.get("sqft") or payload.get("square_feet"))
    zipcode = _clean_str(payload.get("zip") or payload.get("zip_code"))
    property_id = _clean_str(payload.get("property_id") or payload.get("attom_id"))
    image_url = _clean_str(payload.get("image_url"))

    existing = _find_existing_saved_property(ip, payload)
    fk = _profile_id_filter(SavedProperty, ip.id)

    if not existing:
        create_kwargs = {
            **fk,
            "property_id": property_id if property_id else None,
            "address": address,
            "price": str(purchase_price or ""),
            "sqft": sqft,
            "saved_at": datetime.utcnow(),
            "created_at": datetime.utcnow(),
        }

        if hasattr(SavedProperty, "zipcode"):
            create_kwargs["zipcode"] = zipcode
        elif hasattr(SavedProperty, "zip_code"):
            create_kwargs["zip_code"] = zipcode

        if hasattr(SavedProperty, "image_url"):
            create_kwargs["image_url"] = image_url

        existing = SavedProperty(**create_kwargs)
        db.session.add(existing)
        db.session.flush()

    _persist_property_core_fields(existing, payload)
    return existing