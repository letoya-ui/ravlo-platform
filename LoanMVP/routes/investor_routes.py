import os
import io
import json
import uuid
import base64
import hashlib
import requests
import zipfile
import copy


import mimetypes

import boto3

from datetime import datetime
from io import BytesIO
from openai import OpenAI

from PIL import Image, ImageOps
from werkzeug.utils import secure_filename
from werkzeug.datastructures import ImmutableMultiDict
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import or_
from sqlalchemy.orm.attributes import flag_modified
from urllib.parse import urlencode, urlparse
from collections import defaultdict
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    send_file,
    current_app,
    session,
    abort,
)

from flask_login import current_user, login_required

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import LETTER

from LoanMVP.extensions import db, stripe, csrf

from LoanMVP.utils.decorators import role_required


from LoanMVP.forms.investor_forms import InvestorSettingsForm, InvestorProfileForm, CapitalApplicationForm

# -------------------------
# Models (updated for Investor)
# -------------------------
from LoanMVP.models.activity_models import BorrowerActivity  # ok to keep for now (schema-safe filter)
from LoanMVP.models.loan_models import LoanApplication, LoanQuote, BorrowerProfile, LoanStatusEvent


from LoanMVP.models.document_models import (
    LoanDocument,
    DocumentRequest,
    ESignedDocument,
    ResourceDocument
)
from LoanMVP.models.crm_models import Message, Partner, FollowUpItem
from LoanMVP.models.payment_models import PaymentRecord
from LoanMVP.models.ai_models import AIAssistantInteraction
from LoanMVP.models.property import SavedProperty
from LoanMVP.models.underwriter_model import UnderwritingCondition
from LoanMVP.models.borrowers import (
    PropertyAnalysis,
    ProjectBudget,
    SubscriptionPlan,
    ProjectExpense,
    BorrowerMessage,
    BorrowerInteraction,
    Deal,
    DealShare,
)
from LoanMVP.models.loan_officer_model import LoanOfficerProfile
from LoanMVP.models.renovation_models import RenovationMockup, RehabJob, BuildProject
from LoanMVP.models.partner_models import PartnerConnectionRequest, ExternalPartnerLead
from LoanMVP.models.investor_models import InvestorProfile, Investment, InvestmentDocument, DealMessage, DealConversation, FundingRequest, Project # adjust import paths as needed
# -------------------------
# AI / Assistants
# -------------------------
from LoanMVP.ai.master_ai import master_ai
from LoanMVP.ai.base_ai import AIAssistant
from LoanMVP.ai.master_ai import CMAIEngine  # if you use it

# -------------------------
# Services
# -------------------------

from LoanMVP.services.attom_service import (
    build_attom_dealfinder_profile,
    AttomServiceError,
)
from LoanMVP.services.market_service import get_market_snapshot
from LoanMVP.services.comps_service import get_saved_property_comps
from LoanMVP.services.rehab_service import (
    estimate_rehab_cost,
    optimize_rehab_to_budget,
    optimize_rehab_for_roi,
    optimize_rehab_for_timeline,
    optimize_rehab_for_arv,
    generate_rehab_risk_flags,
    estimate_rehab_timeline,
    estimate_material_costs,
    generate_rehab_notes,
)
from LoanMVP.services.ai_insights import generate_ai_insights
from LoanMVP.services.unified_resolver import resolve_property_unified
from LoanMVP.services.property_tool import get_property_search_result, PropertyAPIError, build_property_card_data
from LoanMVP.services.notification_service import notify_team_on_conversion
from LoanMVP.services.blueprint_parser import extract_blueprint_structure, infer_room_type
from LoanMVP.services.prompt_builder import build_blueprint_prompt
from LoanMVP.services.concept_build_service import run_concept_build
from LoanMVP.services.renovation_engine_client import generate_concept, call_renovation_engine_upload, RenovationEngineError
# 🔥 Property intelligence (IMPORTANT)
from LoanMVP.services.property_service import resolve_property_unified, build_property_card_data, build_property_card
from LoanMVP.services.deal_copilot_service import build_deal_copilot_context, generate_deal_copilot_response
from LoanMVP.services.dealfinder_service import build_dealfinder_profile, extract_attom_fields, _extract_rentcast_fields, get_rentcast_data
from LoanMVP.services.mashvisor_client import MashvisorClient
from LoanMVP.utils.r2_storage import spaces_put_bytes


from LoanMVP.services.partner_marketplace_service import search_internal_partners, search_google_places
# ---------------------------------------------------------
# Blueprint (INVESTOR ONLY)
# ---------------------------------------------------------
investor_bp = Blueprint("investor", __name__, url_prefix="/investor")
deal_architect_api_bp = Blueprint("deal_architect_api", __name__, url_prefix="/")

client = OpenAI()


# -------------------------------------------------------------------
# DEAL ARCHITECT HELPERS
# -------------------------------------------------------------------

def _engine_base_url() -> str:
    return (current_app.config.get("RENOVATION_ENGINE_URL") or "").rstrip("/")


def _engine_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    api_key = current_app.config.get("RENOVATION_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key
    return headers

def _safe_engine_num(value):
    if value in (None, "", "—"):
        return None
    try:
        return float(str(value).replace("$", "").replace(",", "").strip())
    except Exception:
        return None


def _build_deal_architect_payload(result: dict, strategy: str = "flip") -> dict:
    address = (result.get("address") or result.get("address_line1") or "").strip()
    city = (result.get("city") or "").strip()
    state = (result.get("state") or "").strip()
    zip_code = (result.get("zip_code") or "").strip()

    beds = _safe_engine_num(result.get("beds"))
    baths = _safe_engine_num(result.get("baths"))
    sqft = _safe_engine_num(result.get("square_feet") or result.get("sqft"))
    lot_sqft = _safe_engine_num(result.get("lot_size_sqft"))
    assessed_value = _safe_engine_num(result.get("assessed_value"))
    tax_amount = _safe_engine_num(result.get("tax_amount"))
    market_value = _safe_engine_num(result.get("market_value") or result.get("display_value"))
    sale_price = _safe_engine_num(result.get("last_sale_price") or result.get("price"))
    monthly_rent = _safe_engine_num(result.get("traditional_rent"))
    property_type = (result.get("property_type") or "single family").strip()

    strategy_label = {
        "flip": "fix and flip candidate",
        "rental": "rental hold candidate",
        "all": "investment property candidate",
    }.get((strategy or "flip").lower(), "investment property candidate")

    description_parts = [
        f"{address}, {city}, {state} {zip_code}".strip(", ").strip(),
        f"{int(beds)} bed" if beds is not None else None,
        f"{baths} bath" if baths is not None else None,
        f"{int(sqft):,} sqft" if sqft else None,
        strategy_label,
    ]

    return {
        "project_name": address or "Deal Finder Property",
        "description": " • ".join([p for p in description_parts if p]),
        "property_type": property_type,
        "lot_size": f"{int(lot_sqft):,} sq ft lot" if lot_sqft else "",
        "zoning": result.get("zoning") or "",
        "asking_price": sale_price,
        "square_feet_target": sqft,
        "city": city,
        "state": state,
        "zip_code": zip_code,
        "arv": market_value,
        "monthly_rent": monthly_rent,
        "local_facts": {
            "bedrooms": beds,
            "bathrooms": baths,
            "year_built": _safe_engine_num(result.get("year_built")),
            "lot_sqft": lot_sqft,
            "assessed_value": assessed_value,
            "annual_tax_amount": tax_amount,
            "latitude": result.get("latitude"),
            "longitude": result.get("longitude"),
            "source": "deal_finder",
        },
    }


def _call_deal_architect(payload: dict) -> dict:
    engine_url = (current_app.config.get("RENOVATION_ENGINE_URL") or "").rstrip("/")
    if not engine_url:
        raise RuntimeError(
            "RENOVATION_ENGINE_URL is missing. Add it to your Flask app config or Render environment variables."
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

def _attach_deal_architect_signals(result: dict, engine_data: dict) -> dict:
    enriched = dict(result)
    meta = engine_data.get("meta") or {}

    enriched.update({
        "deal_score": engine_data.get("deal_score"),
        "opportunity_tier": engine_data.get("opportunity_tier"),
        "deal_finder_signal": meta.get("deal_finder_signal"),
        "primary_strengths": meta.get("primary_strengths") or [],
        "primary_risks": meta.get("primary_risks") or [],
        "dscr_estimate": meta.get("dscr_estimate"),
        "rent_yield": meta.get("rent_yield"),
        "monthly_rent_estimate": meta.get("monthly_rent_estimate"),
        "next_step": engine_data.get("next_step"),
        "engine_value": engine_data.get("estimated_value"),
        "valuation_source_label": meta.get("valuation_source_label"),
        "comp_confidence": meta.get("comp_confidence"),
        "engine_summary": engine_data.get("summary"),
        "engine_meta": meta,
    })
    return enriched



# =========================================================
# 🔢 SAFE NUMERIC HELPERS
# =========================================================

def safe_float(value, default=0.0):
    """Safely convert to float."""
    try:
        if value in (None, "", "None"):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def safe_decimal(value, default="0.00"):
    """Money-safe decimal conversion."""
    try:
        if value in (None, "", "None"):
            return Decimal(default)
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def safe_int(value, default=0, min_v=None, max_v=None):
    """Safe int conversion with optional clamping."""
    try:
        x = int(value)
        if min_v is not None:
            x = max(min_v, x)
        if max_v is not None:
            x = min(max_v, x)
        return x
    except (TypeError, ValueError):
        return default



# ----------------------------
# internal helpers
# ----------------------------

def _safe_float(v):
    try:
        if v in (None, "", "None"):
            return None
        if isinstance(v, (int, float)):
            return float(v)
        return float(str(v).replace("$", "").replace(",", "").strip())
    except Exception:
        return None


def _safe_int(v):
    try:
        n = _safe_float(v)
        return int(round(n)) if n is not None else None
    except Exception:
        return None


def _first_nonempty(*vals):
    for v in vals:
        if v not in (None, "", [], {}):
            return v
    return None


def _resolve_photo(raw):
    """
    Best-effort photo resolution from search payload.
    If the upstream search response has no usable photo,
    frontend will still fall back to placeholder_property.jpg.
    """
    photos = raw.get("photos") or []
    if isinstance(photos, list):
        for p in photos:
            if isinstance(p, str) and p.strip():
                return p
            if isinstance(p, dict):
                candidate = (
                    p.get("url")
                    or p.get("href")
                    or p.get("src")
                    or p.get("photo")
                    or p.get("thumbnail")
                )
                if candidate:
                    return candidate

    return _first_nonempty(
        raw.get("primary_photo"),
        raw.get("photo"),
        raw.get("thumbnail"),
        raw.get("image_url"),
        raw.get("image"),
    )


def _build_property_tool_result(raw_match, profile_bundle):
    """
    Convert normalized + scored dealfinder output into the shape
    expected by property_tool.html.
    """
    profile = profile_bundle.get("profile") or {}
    scoring = profile_bundle.get("scoring") or {}
    raw_sources = profile.get("raw_sources") or {}
    realtor_source = raw_sources.get("realtor") or {}
    photos = profile.get("photos") or raw_match.get("photos") or []

    listing_price = _safe_float(
        _first_nonempty(
            profile.get("listing_price"),
            realtor_source.get("price"),
            profile.get("price") if (
                profile.get("status")
                or profile.get("days_on_market")
                or profile.get("description")
            ) else None,
            raw_match.get("price"),
            raw_match.get("list_price"),
            raw_match.get("listPrice"),
            raw_match.get("listedPrice"),
        )
    )

    market_value = _safe_float(profile.get("market_value"))
    assessed_value = _safe_float(profile.get("assessed_value"))
    last_sale_price = _safe_float(profile.get("last_sale_price"))
    price = listing_price

    display_value = _first_nonempty(
        listing_price,
        market_value,
        assessed_value,
        last_sale_price,
    )

    if listing_price is not None:
        display_value_label = "List Price"
        display_value_secondary = market_value or assessed_value or last_sale_price
        display_value_secondary_label = (
            "Estimated Market Value" if market_value is not None else
            "Assessed Value" if assessed_value is not None else
            "Last Sale Price" if last_sale_price is not None else
            None
        )
    elif market_value is not None:
        display_value_label = "Market Value"
        display_value_secondary = assessed_value or last_sale_price
        display_value_secondary_label = (
            "Assessed Value" if assessed_value is not None else
            "Last Sale Price" if last_sale_price is not None else
            None
        )
    elif _safe_float(profile.get("price")) is not None:
        display_value_label = "Best Available Value"
        display_value_secondary = assessed_value or last_sale_price
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

    overall_score = scoring.get("overall_score")
    recommended_strategy = scoring.get("recommended_strategy")
    score_reasons = scoring.get("score_reasons") or []

    # normalized fields for current frontend
    return {
        "address": _first_nonempty(
            profile.get("address_line1"),
            profile.get("address"),
            raw_match.get("address"),
            raw_match.get("address_line1"),
        ),
        "address_line1": _first_nonempty(
            profile.get("address_line1"),
            raw_match.get("address_line1"),
            raw_match.get("address"),
        ),
        "city": _first_nonempty(profile.get("city"), raw_match.get("city")),
        "state": _first_nonempty(profile.get("state"), raw_match.get("state")),
        "zip_code": _first_nonempty(profile.get("zip_code"), raw_match.get("zip_code")),
        "attom_id": _first_nonempty(profile.get("attom_id"), raw_match.get("attom_id")),

        "property_type": _first_nonempty(
            profile.get("property_type"),
            raw_match.get("property_type"),
        ),
        "property_sub_type": profile.get("property_sub_type"),

        "beds": _safe_int(profile.get("beds")),
        "baths": _safe_float(profile.get("baths")),
        "square_feet": _safe_int(profile.get("sqft")),
        "sqft": _safe_int(profile.get("sqft")),
        "lot_size_sqft": _safe_int(
            _first_nonempty(profile.get("lot_sqft"), raw_match.get("lot_size_sqft"))
        ),
        "year_built": _safe_int(profile.get("year_built")),

        "display_value": display_value,
        "display_value_label": display_value_label,
        "display_value_secondary": display_value_secondary,
        "display_value_secondary_label": display_value_secondary_label,

        "price": price,
        "listing_price": listing_price,
        "market_value": market_value,
        "assessed_value": assessed_value,
        "last_sale_price": last_sale_price,
        "data_status": "enriched",
        "last_sale_date": profile.get("last_sale_date"),
        "tax_amount": _safe_float(profile.get("tax_amount")),
        "status": _first_nonempty(profile.get("status"), raw_match.get("status")),
        "days_on_market": _safe_int(
            _first_nonempty(profile.get("days_on_market"), raw_match.get("days_on_market"), raw_match.get("daysOnMarket"))
        ),
        "description": _first_nonempty(profile.get("description"), raw_match.get("description")),

        "traditional_rent": _safe_float(profile.get("traditional_rent")),
        "airbnb_rent": _safe_float(profile.get("airbnb_rent")),
        "traditional_cap_rate": _safe_float(profile.get("traditional_cap_rate")),
        "traditional_coc": _safe_float(profile.get("traditional_coc")),
        "airbnb_cap_rate": _safe_float(profile.get("airbnb_cap_rate")),
        "airbnb_coc": _safe_float(profile.get("airbnb_coc")),
        "occupancy_rate": _safe_float(profile.get("occupancy_rate")),

        "distressed": bool(profile.get("distressed")),
        "foreclosure_status": profile.get("foreclosure_status"),
        "owner_occupied": profile.get("owner_occupied"),

        "ravlo_score": overall_score,
        "recommended_strategy": recommended_strategy or "Hold / Review",
        "score_reasons": score_reasons,

        "primary_photo": _first_nonempty(profile.get("primary_photo"), _resolve_photo(raw_match)),
        "photo": _first_nonempty(profile.get("primary_photo"), _resolve_photo(raw_match)),
        "thumbnail": _first_nonempty(profile.get("primary_photo"), _resolve_photo(raw_match)),
        "photos": photos,

        "latitude": _safe_float(raw_match.get("latitude")),
        "longitude": _safe_float(raw_match.get("longitude")),

        "source_status": profile_bundle.get("source_status") or {},
        "provider_errors": profile_bundle.get("errors") or [],
    }

def _build_attom_fallback(raw):
    try:
        detail = get_property_detail(
            address=raw.get("address_line1") or raw.get("address"),
            city=raw.get("city"),
            state=raw.get("state"),
            postalcode=raw.get("zip_code"),
        )

        detail = extract_attom_fields(detail)

    except Exception:
        detail = {}

    market = detail.get("market_value") or raw.get("market_value")
    assessed = detail.get("assessed_value") or raw.get("assessed_value")
    sale = detail.get("last_sale_price") or raw.get("last_sale_price")
    listing_price = (
        raw.get("price")
        or raw.get("list_price")
        or raw.get("listPrice")
        or raw.get("listedPrice")
    )

    display_value = listing_price or market or assessed or sale

    return {
        "address": raw.get("address") or raw.get("address_line1"),
        "address_line1": raw.get("address_line1") or raw.get("address"),
        "city": raw.get("city"),
        "state": raw.get("state"),
        "zip_code": raw.get("zip_code"),
        "property_type": raw.get("property_type") or raw.get("propertyType"),

        "beds": detail.get("bedrooms") or raw.get("beds") or raw.get("bedrooms"),
        "baths": detail.get("bathrooms") or raw.get("baths") or raw.get("bathrooms"),
        "square_feet": detail.get("sqft") or raw.get("square_feet") or raw.get("sqft"),
        "sqft": detail.get("sqft") or raw.get("square_feet") or raw.get("sqft"),
        "lot_size_sqft": raw.get("lot_size_sqft") or raw.get("lotSizeSqft"),
        "year_built": detail.get("year_built") or raw.get("year_built") or raw.get("yearBuilt"),

        "price": listing_price,
        "listing_price": listing_price,
        "market_value": market,
        "assessed_value": assessed,
        "last_sale_price": sale,
        "status": raw.get("status"),
        "days_on_market": raw.get("days_on_market") or raw.get("daysOnMarket"),
        "description": raw.get("description"),

        "display_value": display_value,
        "display_value_label": (
            "List Price" if listing_price else
            "Market Value" if market else
            "Assessed Value" if assessed else
            "Last Sale"
        ),

        "primary_photo": _resolve_photo(raw),
        "photo": _resolve_photo(raw),
        "thumbnail": _resolve_photo(raw),
        "photos": raw.get("photos") or [],

        "ravlo_score": None,
        "recommended_strategy": "Review",
        "data_status": "attom_only"
    }


def _deal_finder_tag(result: dict, selected_strategy: str = "all") -> str:
    property_type = str(result.get("property_type") or "").lower()
    lot_size = _safe_float(result.get("lot_size_sqft")) or 0
    sqft = _safe_float(result.get("square_feet") or result.get("sqft")) or 0
    year_built = _safe_int(result.get("year_built")) or 0
    distressed = bool(result.get("distressed"))
    dom = _safe_int(result.get("days_on_market")) or 0
    score = _safe_float(result.get("deal_score") or result.get("ravlo_score")) or 0
    strengths_text = " ".join(result.get("primary_strengths") or []).lower()
    strategy_text = str(result.get("recommended_strategy") or "").lower()

    if any(term in property_type for term in ["vacant", "land", "lot"]):
        return "Vacant Land"

    if any(term in strengths_text for term in ["teardown", "redevelop", "development", "infill"]):
        return "Teardown / Rebuild"

    if lot_size >= 10000 and property_type in {"single_family", "single family", "single_family_residence", "sfr"}:
        if year_built and year_built <= 1965 and sqft and sqft <= 1500:
            return "Teardown / Rebuild"
        return "New Construction Opportunity"

    if distressed or any(term in strategy_text for term in ["rehab", "flip"]):
        if dom >= 45 or score < 55:
            return "Heavy Rehab"
        return "Standard Rehab"

    if selected_strategy == "rental":
        return "Standard Rehab"

    return "Standard Rehab"


def _deal_finder_best_use(result: dict, strategy_tag: str) -> str:
    market_value = _safe_float(result.get("market_value") or result.get("engine_value"))
    price = _safe_float(result.get("price") or result.get("listing_price"))
    rent = _safe_float(result.get("monthly_rent_estimate") or result.get("traditional_rent"))
    lot_size = _safe_float(result.get("lot_size_sqft")) or 0

    if strategy_tag == "Vacant Land":
        return "Treat this as a buildable land play instead of a rehab candidate."
    if strategy_tag == "Teardown / Rebuild":
        return "Highest and best use likely comes from the site more than the current structure."
    if strategy_tag == "New Construction Opportunity":
        return "Use the lot and layout potential to evaluate a ground-up or expansion path."
    if market_value and price and market_value > price:
        return "Acquire below current value signals, then improve and exit or refinance."
    if rent:
        return f"Review for hold economics with rent potential around ${rent:,.0f}/mo."
    if lot_size >= 10000:
        return "The oversized lot creates optionality beyond a simple cosmetic upgrade."
    return "Best use appears to be a focused value-add improvement plan."


def _deal_finder_upside(result: dict, strategy_tag: str) -> str:
    price = _safe_float(result.get("price") or result.get("listing_price"))
    market_value = _safe_float(result.get("market_value") or result.get("engine_value"))
    assessed = _safe_float(result.get("assessed_value"))
    rent = _safe_float(result.get("monthly_rent_estimate") or result.get("traditional_rent"))
    lot_size = _safe_float(result.get("lot_size_sqft")) or 0

    if price and market_value and market_value > price:
        return f"${market_value - price:,.0f} spread to current value estimate."
    if price and assessed and assessed > price:
        return f"${assessed - price:,.0f} spread to assessed value."
    if rent:
        return f"${rent:,.0f}/mo rental signal."
    if strategy_tag in {"Teardown / Rebuild", "New Construction Opportunity"} and lot_size:
        return f"{lot_size:,.0f} sq ft lot with redevelopment optionality."
    return "Upside depends on deeper scope and comp validation."


def _annotate_deal_finder_opportunity(result: dict, selected_strategy: str = "all") -> dict:
    strategy_tag = _deal_finder_tag(result, selected_strategy=selected_strategy)
    strengths = [str(x).strip() for x in (result.get("primary_strengths") or []) if str(x).strip()]
    risks = [str(x).strip() for x in (result.get("primary_risks") or []) if str(x).strip()]
    score_reasons = [str(x).strip() for x in (result.get("score_reasons") or []) if str(x).strip()]

    why_it_made_list = strengths[:2] or score_reasons[:2]
    if not why_it_made_list:
        fallback = []
        if _safe_float(result.get("price")):
            fallback.append("Live pricing is available for a fast first-pass review.")
        if _safe_float(result.get("market_value") or result.get("engine_value")):
            fallback.append("Value signals are present, so spread can be checked immediately.")
        if _safe_int(result.get("days_on_market")):
            fallback.append(f"{result.get('days_on_market')} days on market may create negotiating leverage.")
        why_it_made_list = fallback[:2] or ["Ravlo surfaced enough pricing and property data to evaluate this one quickly."]

    risk_notes = risks[:2]
    if not risk_notes:
        dom = _safe_int(result.get("days_on_market")) or 0
        if dom >= 60:
            risk_notes.append("Long time on market suggests demand friction or pricing issues.")
        elif result.get("engine_error"):
            risk_notes.append("AI scoring was only partially available, so validate the assumptions.")
        else:
            risk_notes.append("Validate scope, comps, and zoning before moving into execution.")

    result["strategy_tag"] = strategy_tag
    result["estimated_best_use"] = _deal_finder_best_use(result, strategy_tag)
    result["best_use"] = result["estimated_best_use"]
    result["why_it_made_list"] = why_it_made_list
    result["risk_notes"] = risk_notes
    result["rough_upside"] = _deal_finder_upside(result, strategy_tag)
    result["opportunity_summary"] = why_it_made_list[0]
    return result


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
        flags.append({"label": "Oversized Lot", "tone": "good", "detail": f"{lot_size:,.0f} sq ft creates extra optionality."})
    if lot_size >= 14000 or any(term in property_type for term in ["land", "lot", "vacant"]):
        flags.append({"label": "Development Potential", "tone": "good", "detail": "Lot size and property profile suggest a bigger site play."})
    if year_built and year_built <= 1965 and sqft and sqft <= 1500:
        flags.append({"label": "Teardown Potential", "tone": "watch", "detail": "Older, smaller structure may be less valuable than the site."})
    if dom >= 45:
        flags.append({"label": "Negotiation Window", "tone": "watch", "detail": f"{dom} days on market may create pricing flexibility."})
    if price and market_value and market_value > price:
        flags.append({"label": "Spread Detected", "tone": "good", "detail": f"${market_value - price:,.0f} gap between current price and value signals."})

    return flags[:4]


def _project_studio_strategy_cards(snapshot: dict, engine_data: dict | None) -> list[dict]:
    engine_data = engine_data or {}
    meta = engine_data.get("meta") or {}

    price = _safe_float(snapshot.get("price") or snapshot.get("listing_price") or snapshot.get("last_sale_price")) or 0
    market_value = _safe_float(snapshot.get("market_value") or engine_data.get("estimated_value") or snapshot.get("assessed_value")) or 0
    rent = _safe_float(snapshot.get("traditional_rent") or meta.get("monthly_rent_estimate")) or 0
    sqft = _safe_float(snapshot.get("square_feet") or snapshot.get("sqft")) or 0
    lot_size = _safe_float(snapshot.get("lot_size_sqft")) or 0
    dom = _safe_int(snapshot.get("days_on_market")) or 0
    comp_conf = str(meta.get("comp_confidence") or snapshot.get("comp_confidence") or "Moderate")
    primary_strengths = [str(x).strip() for x in (meta.get("primary_strengths") or snapshot.get("primary_strengths") or []) if str(x).strip()]
    primary_risks = [str(x).strip() for x in (meta.get("primary_risks") or snapshot.get("primary_risks") or []) if str(x).strip()]
    market_label = _project_studio_market_label(engine_data, snapshot)

    rehab_budget_low = max(25000, round(sqft * 28)) if sqft else 45000
    rehab_budget_high = max(rehab_budget_low + 25000, round(sqft * 62)) if sqft else 95000
    rehab_arv = max(market_value, price * 1.18) if price else market_value
    rehab_profit = rehab_arv - price - ((rehab_budget_low + rehab_budget_high) / 2) if price and rehab_arv else None
    rehab_confidence = "High" if market_value and dom <= 45 else "Moderate"

    build_budget_low = max(140000, round((sqft or 900) * 155))
    build_budget_high = max(build_budget_low + 60000, round((sqft or 1100) * 215))
    build_arv = max(rehab_arv * 1.08 if rehab_arv else 0, market_value * 1.12 if market_value else 0)
    build_outcome = build_arv - price - ((build_budget_low + build_budget_high) / 2) if price and build_arv else None
    build_confidence = "Moderate" if lot_size >= 7000 else "Watch"

    project_units = 4 if lot_size >= 18000 else 3 if lot_size >= 14000 else 2
    project_budget_low = max(260000, project_units * 180000)
    project_budget_high = max(project_budget_low + 140000, project_units * 255000)
    project_arv = max(build_arv * 1.35 if build_arv else 0, (market_value or rehab_arv or price) * 1.45 if (market_value or rehab_arv or price) else 0)
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
    cards.sort(key=lambda c: (_safe_float(c.get("outcome")) is not None, _safe_float(c.get("outcome")) or 0), reverse=True)

    if cards:
        cards[0]["badge"] = "Recommended Strategy"

    highest_profit = max(cards, key=lambda c: _safe_float(c.get("outcome")) or float("-inf")) if cards else None
    if highest_profit and highest_profit.get("badge") != "Recommended Strategy":
        highest_profit["badge"] = "Highest Profit"

    lowest_risk = max(cards, key=lambda c: {"High": 3, "Moderate": 2, "Watch": 1, "Low": 0}.get(c.get("confidence"), 0)) if cards else None
    if lowest_risk and not lowest_risk.get("badge"):
        lowest_risk["badge"] = "Lowest Risk"

    for card in cards:
        card["market_note"] = market_label
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
        current_app.logger.warning("project_studio engine enrichment failed for %s: %s", snapshot.get("address"), exc)
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
            "light": (0.85, 0.9, "4-6 months"),
            "medium": (1.0, 1.0, "5-8 months"),
            "heavy": (1.2, 1.3, "7-10 months"),
        },
        "build_studio": {
            "keep_structure": (0.9, 0.92, "8-12 months"),
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

def _project_studio_validate_with_mashvisor(snapshot, selected_strategy):
    client = MashvisorClient()

    try:
        result = client.get_airbnb_lookup(
            address=snapshot.get("address"),
            city=snapshot.get("city"),
            state=snapshot.get("state"),
            zip_code=snapshot.get("zip_code"),
            beds=snapshot.get("beds"),
            baths=snapshot.get("baths"),
            lat=snapshot.get("latitude"),
            lng=snapshot.get("longitude"),
        )

        return result

    except Exception as e:
        return {"error": str(e)}

def _run_mashvisor_validation(snapshot: dict) -> dict | None:
    """
    Lightweight STR validation for Project Studio.
    Use only after a property is loaded and a serious strategy path is in play.
    """
    if not snapshot:
        return None

    address = (snapshot.get("address") or "").strip()
    city = (snapshot.get("city") or "").strip()
    state = (snapshot.get("state") or "").strip()
    zip_code = (snapshot.get("zip_code") or "").strip()

    if not address or not city or not state or not zip_code:
        return None

    try:
        client = MashvisorClient()
        result = client.get_airbnb_lookup(
            address=address,
            city=city,
            state=state,
            zip_code=zip_code,
            beds=_safe_int(snapshot.get("beds")),
            baths=_safe_float(snapshot.get("baths")),
            lat=_safe_float(snapshot.get("latitude")),
            lng=_safe_float(snapshot.get("longitude")),
        )

        # Check for API-level errors before normalizing lookup fields
        if isinstance(result, dict) and result.get("errors"):
            current_app.logger.warning(
                "Mashvisor API returned errors for %s: %s",
                address, result["errors"],
            )
            return {"error": result["errors"]}

        lookup = result.get("content", result) if isinstance(result, dict) else {}

        return {
            "airbnb_revenue": (
                lookup.get("rental_income")
                or lookup.get("airbnb_rental_income")
                or lookup.get("monthly_revenue")
            ),
            "occupancy_rate": (
                lookup.get("occupancy_rate")
                or lookup.get("airbnb_occupancy_rate")
            ),
            "adr": (
                lookup.get("daily_rate")
                or lookup.get("adr")
                or lookup.get("average_daily_rate")
            ),
            "confidence": (
                lookup.get("data_quality")
                or lookup.get("confidence")
                or "Moderate"
            ),
            "raw": result,
        }

    except Exception as exc:
        current_app.logger.warning(
            "project_studio mashvisor validation failed for %s: %s",
            snapshot.get("address"),
            exc,
        )
        return {"error": str(exc)}


def _build_mashvisor_insight(scope_budget: dict | None, mashvisor_data: dict | None) -> str | None:
    """
    Compare Ravlo's rough planning outcome to Mashvisor STR signal.
    We use budget outcome as the internal reference only if available.
    """
    if not scope_budget or not mashvisor_data or mashvisor_data.get("error"):
        return None

    internal_reference = _safe_float(scope_budget.get("outcome"))
    mashvisor_revenue = _safe_float(mashvisor_data.get("airbnb_revenue"))

    if internal_reference is None or mashvisor_revenue is None or internal_reference == 0:
        return "Market validation is available, but there is not enough aligned data yet for a direct comparison."

    pct = ((mashvisor_revenue - internal_reference) / abs(internal_reference)) * 100

    if abs(pct) <= 10:
        return "Market data is generally aligned with Ravlo's current planning assumptions."
    if pct < 0:
        return "Market data is coming in below Ravlo's internal planning signal, so pressure-test the revenue assumptions."
    return "Market data is stronger than Ravlo's current planning signal, which may support more upside."

def _build_loan_sizing_from_budget(deal, budget=None) -> dict:
    """
    Build a lightweight financing summary from deal + budget.
    Conservative defaults for now; can be replaced with lender rules later.
    """
    purchase_price = float(getattr(deal, "purchase_price", 0) or 0)
    arv = float(getattr(deal, "arv", 0) or 0)

    if budget:
        construction_budget = float(getattr(budget, "total_budget", 0) or 0)
        estimated_budget = float(getattr(budget, "total_cost", 0) or 0)
        paid_amount = float(getattr(budget, "paid_amount", 0) or 0)
        contingency = float(getattr(budget, "contingency", 0) or 0)
    else:
        construction_budget = float(getattr(deal, "rehab_cost", 0) or 0)
        estimated_budget = construction_budget
        paid_amount = 0.0
        contingency = 0.0

    total_project_cost = purchase_price + construction_budget

    # Simple lender assumptions for v1
    max_purchase_ltc = 0.90
    max_construction_ltc = 1.00

    financeable_purchase = purchase_price * max_purchase_ltc
    financeable_construction = construction_budget * max_construction_ltc

    estimated_loan_request = financeable_purchase + financeable_construction
    estimated_cash_required = max(total_project_cost - estimated_loan_request, 0)

    ltc = (estimated_loan_request / total_project_cost * 100) if total_project_cost > 0 else 0
    arv_leverage = (estimated_loan_request / arv * 100) if arv > 0 else 0

    if ltc <= 75:
        leverage_note = "Conservative leverage profile."
    elif ltc <= 90:
        leverage_note = "Typical leverage for a strong deal."
    else:
        leverage_note = "High leverage — confirm lender appetite and reserves."

    return {
        "purchase_price": purchase_price,
        "construction_budget": construction_budget,
        "estimated_budget": estimated_budget,
        "paid_amount": paid_amount,
        "contingency": contingency,
        "total_project_cost": total_project_cost,
        "estimated_loan_request": estimated_loan_request,
        "estimated_cash_required": estimated_cash_required,
        "ltc": ltc,
        "arv_leverage": arv_leverage,
        "leverage_note": leverage_note,
    }

# =========================================================
# 🧾 JSON + FORM SAFETY
# =========================================================

def safe_json_loads(data, default=None):
    """Safe JSON parse that accepts dict/list or string."""
    if default is None:
        default = {}

    if not data:
        return default

    if isinstance(data, (dict, list)):
        return data

    try:
        return json.loads(data)
    except Exception:
        return default


def _normalize_percentage(value):
    if value in (None, "", "None"):
        return None

    try:
        number = float(str(value).replace("%", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return None

    if number > 1:
        number = number / 100.0

    return number

def search_external_partners_google(category=None, city=None, state=None):
    import os
    import requests
    from flask import current_app

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        current_app.logger.warning("GOOGLE_API_KEY is missing")
        return []

    query_parts = []
    if category:
        query_parts.append(category)
    else:
        query_parts.append("professional")

    location_bits = [x for x in [city, state] if x]
    if location_bits:
        query_parts.append("in " + ", ".join(location_bits))

    search_query = " ".join(query_parts).strip()

    current_app.logger.warning(f"External Google query: {search_query}")

    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": search_query,
        "key": api_key,
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()

        current_app.logger.warning(
            f"Google Places status={data.get('status')} results={len(data.get('results', []))}"
        )

        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            current_app.logger.warning(f"Google error: {data.get('error_message')}")
            return []

        results = []
        for item in data.get("results", [])[:8]:
            results.append({
                "name": item.get("name"),
                "address": item.get("formatted_address"),
                "rating": item.get("rating"),
                "external_id": item.get("place_id"),
            })

        return results

    except Exception as e:
        current_app.logger.exception(f"External Google search failed: {e}")
        return []
# =========================================================
# 💰 MONEY FORMATTER
# =========================================================

def fmt_money(value, blank="—"):
    try:
        if value in (None, "", "None"):
            return blank
        return f"${Decimal(str(value)):,.2f}"
    except Exception:
        return blank


# =========================================================
# 📦 CSV → UNIQUE INT LIST
# =========================================================

def split_ids(csv_string: str):
    """Convert comma/semicolon string to unique int list."""
    if not csv_string:
        return []

    parts = csv_string.replace(";", ",").split(",")
    cleaned = []

    for p in parts:
        p = p.strip()
        if not p:
            continue
        try:
            cleaned.append(int(p))
        except Exception:
            continue

    # remove duplicates while preserving order
    seen = set()
    result = []
    for i in cleaned:
        if i not in seen:
            seen.add(i)
            result.append(i)

    return result


# =========================================================
# 🌐 IMAGE UTILITIES
# =========================================================

def call_renovation_engine_upload(
    file_storage,
    prompt: str,
    api_url: str,
    style: str = "modern luxury",
    strength: float = 0.75,
    guidance_scale: float = 7.5,
    num_inference_steps: int = 30,
):
    endpoint = f"{api_url.rstrip('/')}/v1/renovate-upload"

    files = {
        "image": (
            file_storage.filename,
            file_storage.stream,
            file_storage.mimetype or "application/octet-stream"
        )
    }

    data = {
        "prompt": prompt,
        "style": style,
        "strength": str(strength),
        "guidance_scale": str(guidance_scale),
        "num_inference_steps": str(num_inference_steps),
    }

    response = requests.post(endpoint, files=files, data=data, timeout=300)
    response.raise_for_status()
    return response.json()

# =========================================================
# CONFIG
# =========================================================
GPU_BASE_URL = os.getenv("GPU_BASE_URL", "").rstrip("/")
RENOVATION_ENGINE_URL = os.getenv("RENOVATION_ENGINE_URL", "").rstrip("/")
RENOVATION_API_KEY = os.getenv("RENOVATION_API_KEY", "")

SCOPE_ENGINE_URL = os.getenv("SCOPE_ENGINE_URL", "").rstrip("/")
SCOPE_ENGINE_API_KEY = os.getenv("SCOPE_ENGINE_API_KEY", "")

GPU_TIMEOUT = int(os.getenv("GPU_TIMEOUT", "900"))

ENGINE_PRESETS = {"luxury_modern", "modern_farmhouse", "clean_minimal"}

STYLE_PRESET_MAP = {
    "luxury": "luxury_modern",
    "modern": "clean_minimal",
    "airbnb": "modern_farmhouse",
    "flip": "modern_farmhouse",
    "budget": "modern_farmhouse",
    "luxury_modern": "luxury_modern",
    "modern_farmhouse": "modern_farmhouse",
    "clean_minimal": "clean_minimal",
}

STYLE_PROMPT_MAP = {
    "luxury": "luxury remodel, upgraded cabinetry, quartz countertops, designer backsplash, premium fixtures, warm layered lighting",
    "modern": "modern remodel, clean cabinetry, stone countertops, simple backsplash, matte black fixtures, neutral palette",
    "airbnb": "guest-ready remodel, bright finishes, durable materials, warm lighting, clean styling, inviting modern design",
    "flip": "resale-focused remodel, bright neutral finishes, updated cabinets, durable countertops, clean modern presentation",
    "budget": "light remodel, painted cabinets, simple counters, fresh finishes, updated lighting, clean functional design",
    "dark_luxury": "upscale dark kitchen remodel, richer cabinetry, brighter quartz countertops, premium backsplash, elegant warm lighting, designer fixtures"
}

# =========================================================
# IMAGE HELPERS
# =========================================================

def get_spaces_client():
    return boto3.client(
        "s3",
        region_name=os.environ["DO_SPACES_REGION"],
        endpoint_url=os.environ["DO_SPACES_ENDPOINT"],
        aws_access_key_id=os.environ["DO_SPACES_KEY"],
        aws_secret_access_key=os.environ["DO_SPACES_SECRET"],
    )

def upload_listing_photos_to_spaces(photo_urls, deal_id=None, saved_property_id=None):
    if not photo_urls:
        return []

    bucket = os.environ["DO_SPACES_BUCKET"]
    cdn_base = os.environ.get("DO_SPACES_CDN_BASE", "").rstrip("/")
    s3 = get_spaces_client()

    uploaded = []

    for idx, source_url in enumerate(photo_urls, start=1):
        if not source_url:
            continue

        try:
            resp = requests.get(source_url, timeout=15, stream=True)
            resp.raise_for_status()

            parsed = urlparse(source_url)
            ext = os.path.splitext(parsed.path)[1].lower() or ".jpg"
            content_type = resp.headers.get("Content-Type") or mimetypes.guess_type(source_url)[0] or "image/jpeg"

            owner_part = f"deal-{deal_id}" if deal_id else f"saved-{saved_property_id or 'unknown'}"
            key = f"listing-photos/{owner_part}/{uuid.uuid4().hex}-{idx}{ext}"

            s3.upload_fileobj(
                resp.raw,
                bucket,
                key,
                ExtraArgs={
                    "ACL": "public-read",
                    "ContentType": content_type,
                },
            )

            final_url = f"{cdn_base}/{key}" if cdn_base else f"{os.environ['DO_SPACES_ENDPOINT'].rstrip('/')}/{bucket}/{key}"

            uploaded.append({
                "url": final_url,
                "source_url": source_url,
                "label": f"Listing Photo {idx}",
                "position": idx,
            })

        except Exception:
            continue

    return uploaded    

def download_image_bytes(url: str, timeout=10) -> bytes:
    """Secure image download with relaxed header check."""

    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("Invalid image URL.")

    response = requests.get(url, timeout=timeout, stream=True)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").lower()

    # Accept common CDN responses
    if not (
        content_type.startswith("image")
        or "octet-stream" in content_type
        or "binary" in content_type
    ):
        print("Warning: unexpected content type:", content_type)

    return response.content

def to_png_bytes(img_bytes: bytes, max_size: int = 1024) -> bytes:
    im = Image.open(BytesIO(img_bytes))
    im = ImageOps.exif_transpose(im)   # fix phone rotation first
    im = im.convert("RGB")
    im.thumbnail((max_size, max_size))

    out = BytesIO()
    im.save(out, format="PNG", optimize=True)
    return out.getvalue()


def to_webp_bytes(img_bytes: bytes, max_size: int = 1400, quality: int = 86) -> bytes:
    im = Image.open(BytesIO(img_bytes))
    im = ImageOps.exif_transpose(im)   # fix phone rotation first
    im = im.convert("RGB")
    im.thumbnail((max_size, max_size))

    out = BytesIO()
    im.save(out, format="WEBP", quality=int(quality), method=6)
    return out.getvalue()

# =========================================================
# STYLE HELPERS
# =========================================================

def _normalize_style_preset(style_preset: str) -> str:
    style_preset = (style_preset or "").strip().lower()
    return STYLE_PRESET_MAP.get(style_preset, "luxury_modern")


def _compose_style_prompt(style_prompt: str, style_preset: str, keep_layout: bool = True) -> str:
    preset_key = (style_preset or "").strip().lower()
    base = (STYLE_PROMPT_MAP.get(preset_key, "") or "").strip()
    user = (style_prompt or "").strip()

    layout_text = "preserve existing room layout and camera angle" if keep_layout else "allow moderate redesign"

    prompt_parts = [
        "photorealistic interior renovation",
        layout_text,
        "clear before-to-after remodel",
        base,
    ]

    if user:
        prompt_parts.append(user)

    prompt_parts.append("replace outdated finishes with upgraded modern materials")
    prompt_parts.append("realistic real estate after photo")

    prompt = ", ".join([p for p in prompt_parts if p])

    # keep prompt compact for CLIP
    words = prompt.split()
    if len(words) > 55:
        prompt = " ".join(words[:55])

    return prompt

def _extract_saved_blueprint_reference(deal=None, project=None):
    """
    Returns a usable blueprint reference from the project or deal.
    Can be a URL, storage path, or base64 data URI.
    """
    candidates = []

    # ---- project-level fields first ----
    if project:
        for attr in [
            "blueprint_image",
            "blueprint_image_url",
            "blueprint_url",
            "blueprint_path",
            "floorplan_image",
            "floorplan_url",
        ]:
            value = getattr(project, attr, None)
            if value:
                candidates.append(value)

        project_results = getattr(project, "results_json", None) or {}
        if isinstance(project_results, dict):
            candidates.extend([
                project_results.get("blueprint_image"),
                project_results.get("blueprint_url"),
                (project_results.get("blueprint_result") or {}).get("image"),
                (project_results.get("blueprint_result") or {}).get("image_url"),
                (project_results.get("blueprint_result") or {}).get("saved_path"),
            ])

    # ---- deal-level results_json ----
    if deal:
        results = getattr(deal, "results_json", None) or {}
        if isinstance(results, dict):
            build_project = results.get("build_project") or {}
            blueprint_result = results.get("blueprint_result") or {}

            candidates.extend([
                results.get("blueprint_image"),
                results.get("blueprint_url"),
                build_project.get("blueprint_image"),
                build_project.get("blueprint_url"),
                build_project.get("blueprint_path"),
                blueprint_result.get("image"),
                blueprint_result.get("image_url"),
                blueprint_result.get("saved_path"),
            ])

    # ---- first non-empty candidate wins ----
    for item in candidates:
        if isinstance(item, str) and item.strip():
            return item.strip()

    return None

def _clean_spaces_url_part(value):
    return (value or "").strip().rstrip("/")


def _get_spaces_client():
    return boto3.client(
        "s3",
        region_name=os.environ["DO_SPACES_REGION"],
        endpoint_url=_clean_spaces_url_part(os.environ["DO_SPACES_ENDPOINT"]),
        aws_access_key_id=os.environ["DO_SPACES_KEY"],
        aws_secret_access_key=os.environ["DO_SPACES_SECRET"],
    )


def _normalize_photo_url_list(payload):
    photo_urls = payload.get("listing_photos") or []
    if not isinstance(photo_urls, list):
        photo_urls = []

    primary = payload.get("image_url")
    if primary and primary not in photo_urls:
        photo_urls = [primary] + photo_urls

    cleaned = []
    seen = set()

    for item in photo_urls:
        if not item:
            continue
        url = str(item).strip()
        if not url or url in seen:
            continue
        seen.add(url)
        cleaned.append(url)

    return cleaned


def _safe_set_attr(obj, field_name, value):
    if hasattr(obj, field_name):
        setattr(obj, field_name, value)


def _public_spaces_url(bucket, key):
    cdn_base = _clean_spaces_url_part(os.environ.get("DO_SPACES_CDN_BASE"))
    endpoint = _clean_spaces_url_part(os.environ.get("DO_SPACES_ENDPOINT"))

    if cdn_base:
        return f"{cdn_base}/{key}"

    return f"{endpoint}/{bucket}/{key}"


def upload_listing_photos_to_spaces(photo_urls, saved_property_id=None, deal_id=None):
    """
    Downloads remote listing photos and stores them in DigitalOcean Spaces.
    Returns a list of photo metadata dictionaries.
    Never raises on per-photo failure; skips bad photos.
    """
    if not photo_urls:
        return []

    bucket = os.environ["DO_SPACES_BUCKET"]
    s3 = _get_spaces_client()

    uploaded = []
    owner_part = f"deal-{deal_id}" if deal_id else f"saved-{saved_property_id or 'unknown'}"

    for idx, source_url in enumerate(photo_urls, start=1):
        try:
            resp = requests.get(source_url, timeout=15, stream=True)
            resp.raise_for_status()

            parsed = urlparse(source_url)
            ext = os.path.splitext(parsed.path)[1].lower() or ".jpg"
            content_type = (
                resp.headers.get("Content-Type")
                or mimetypes.guess_type(source_url)[0]
                or "image/jpeg"
            )

            key = f"listing-photos/{owner_part}/{uuid.uuid4().hex}-{idx}{ext}"

            s3.upload_fileobj(
                resp.raw,
                bucket,
                key,
                ExtraArgs={
                    "ACL": "public-read",
                    "ContentType": content_type,
                },
            )

            uploaded.append({
                "url": _public_spaces_url(bucket, key),
                "source_url": source_url,
                "label": f"Listing Photo {idx}",
                "position": idx,
            })

        except Exception as e:
            current_app.logger.warning(
                "Failed listing photo upload for %s: %s",
                source_url,
                e,
            )
            continue

    return uploaded


def _persist_listing_photo_refs(saved_property, deal, uploaded_photos):
    """
    Persist uploaded photo refs on SavedProperty and Deal if supported.
    Defensive so it works with partial schema.
    """
    if not uploaded_photos:
        return

    primary_url = uploaded_photos[0]["url"]

    # SavedProperty-level
    _safe_set_attr(saved_property, "image_url", primary_url)
    _safe_set_attr(saved_property, "listing_photos_json", uploaded_photos)

    # Alternate possible field names
    _safe_set_attr(saved_property, "listing_photos", uploaded_photos)
    _safe_set_attr(saved_property, "primary_photo_url", primary_url)

    # Deal-level snapshot
    if deal:
        results_json = deal.results_json or {}
        results_json["listing_photos"] = uploaded_photos
        results_json["image_url"] = primary_url
        deal.results_json = results_json


def _try_upload_and_attach_listing_photos(payload, saved_property, deal=None):
    """
    Best-effort upload. Never raises to caller.
    """
    try:
        photo_urls = _normalize_photo_url_list(payload)
        if not photo_urls:
            return []

        uploaded_photos = upload_listing_photos_to_spaces(
            photo_urls=photo_urls,
            saved_property_id=getattr(saved_property, "id", None),
            deal_id=getattr(deal, "id", None) if deal else None,
        )

        if uploaded_photos:
            _persist_listing_photo_refs(saved_property, deal, uploaded_photos)

        return uploaded_photos
    except Exception as e:
        current_app.logger.warning("Listing photo attach failed: %s", e)
        return []
# =========================================================
# ENGINE HELPERS
# =========================================================

def _renovation_engine_url(path):
    base = (current_app.config.get("RENOVATION_ENGINE_URL") or "").rstrip("/")
    path = f"/{(path or '').lstrip('/')}"
    return f"{base}{path}"

def _engine_headers():
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "true",
    }

    api_key = (current_app.config.get("RENOVATION_API_KEY") or "").strip()
    if api_key:
        headers["X-API-Key"] = api_key

    return headers

def generate_renovation_images(before_url: str, prompt: str, n: int = 2) -> list[str]:
    if not before_url or not prompt:
        return []

    before_bytes = download_image_bytes(before_url)
    before_png = to_png_bytes(before_bytes, max_size=1024)
    before_b64 = base64.b64encode(before_png).decode("utf-8")

    try:
        resp = requests.post(
            f"{GPU_BASE_URL}/renovate",
            json={"image_b64": before_b64, "prompt": prompt, "n": n},
            timeout=120,
        )
        resp.raise_for_status()
    except Exception as e:
        current_app.logger.exception("GPU renovate failed: %s", e)
        return []

    data = resp.json()
    images_b64 = data.get("images", []) or []

    after_urls = []
    for b64 in images_b64:
        try:
            img_bytes = base64.b64decode(b64)
            img_webp = to_webp_bytes(img_bytes, max_size=1600, quality=86)
            up = spaces_put_bytes(
                img_webp,
                subdir=f"visualizer/{uuid.uuid4().hex}/after",
                content_type="image/webp",
                filename=f"{uuid.uuid4().hex}_after.webp",
            )
            after_urls.append(up["url"])
        except Exception as e:
            current_app.logger.warning("Upload after failed: %s", e)
            continue

    return after_urls


def process_pending_jobs():
    jobs = RehabJob.query.filter_by(status="pending").all()

    for job in jobs:
        job.status = "processing"
        db.session.commit()

        try:
            engine_url = f"{SCOPE_ENGINE_URL}/v1/rehab_scope"
            res = requests.post(
                engine_url,
                json={"image_url": job.plan_url},
                headers=_scope_engine_headers(),
                timeout=180,
            )
            res.raise_for_status()
            data = res.json()

            job.result_plan = data.get("plan")
            job.result_cost_low = data.get("cost_low")
            job.result_cost_high = data.get("cost_high")
            job.result_arv = data.get("arv")
            job.result_images = data.get("images")
            job.status = "complete"

        except Exception:
            current_app.logger.exception("Pending rehab job failed for job_id=%s", job.id)
            job.status = "failed"

        db.session.commit()

def _scope_engine_headers() -> dict:
    headers = {}
    if SCOPE_ENGINE_API_KEY:
        headers["X-API-Key"] = SCOPE_ENGINE_API_KEY
    return headers

def _renovation_engine_url(path=""):
    return f"{RENOVATION_ENGINE_URL.rstrip('/')}{path}"

def _scope_engine_url(path=""):
    return f"{SCOPE_ENGINE_URL.rstrip('/')}{path}"

def _deal_results(deal):
    return copy.deepcopy(deal.results_json or {})


def _set_deal_results(deal, results):
    deal.results_json = copy.deepcopy(results or {})
    flag_modified(deal, "results_json")

def _get_rehab_export_payload(deal):
    r = deal.results_json or {}

    rehab = (
        r.get("rehab_summary")
        or r.get("rehab_analysis")
        or {}
    )

    if not rehab and getattr(deal, "rehab_scope_json", None):
        rehab = {
            "estimated_rehab_cost": getattr(deal, "rehab_cost", None),
            "scope": getattr(deal, "rehab_scope_json", None),
        }

    return rehab or {}

def _safe_first_related(obj, attr_name):
    items = getattr(obj, attr_name, None) or []
    return items[0] if items else None

_fmt_money = fmt_money

def _build_budget_seed_from_results(results: dict) -> dict:
    results = results or {}

    rehab_scope = results.get("rehab_scope") or {}
    rehab_analysis = results.get("rehab_analysis") or {}
    build_analysis = results.get("build_analysis") or {}
    workspace_analysis = results.get("workspace_analysis") or {}
    strategy_analysis = results.get("strategy_analysis") or {}

    raw_items = (
        rehab_scope.get("line_items")
        or rehab_scope.get("budget_items")
        or rehab_scope.get("items")
        or build_analysis.get("line_items")
        or build_analysis.get("budget_items")
        or []
    )

    suggested_breakdown = []

    for item in raw_items:
        if not isinstance(item, dict):
            continue

        name = (
            item.get("description")
            or item.get("name")
            or item.get("item")
            or item.get("category")
            or "Budget Item"
        )

        cost = (
            item.get("estimated_amount")
            or item.get("cost")
            or item.get("amount")
            or item.get("estimate")
            or 0
        )

        try:
            cost = float(cost or 0)
        except (TypeError, ValueError):
            cost = 0.0

        suggested_breakdown.append({
            "name": str(name).strip() or "Budget Item",
            "cost": cost,
        })

    # Fallback from saved planning budget
    if not suggested_breakdown:
        planning_budget = workspace_analysis.get("planning_budget") or {}
        budget_low = planning_budget.get("budget_low")
        budget_high = planning_budget.get("budget_high")

        try:
            budget_low = float(budget_low or 0)
            budget_high = float(budget_high or 0)
        except (TypeError, ValueError):
            budget_low = 0.0
            budget_high = 0.0

        midpoint = 0.0
        if budget_low and budget_high:
            midpoint = (budget_low + budget_high) / 2
        elif budget_high:
            midpoint = budget_high
        elif budget_low:
            midpoint = budget_low

        if midpoint > 0:
            strategy_key = str(
                strategy_analysis.get("strategy")
                or workspace_analysis.get("selected_strategy")
                or "rehab"
            ).lower()

            if strategy_key == "project_build":
                suggested_breakdown = [
                    {"name": "Site Work / Prep", "cost": round(midpoint * 0.15, 2)},
                    {"name": "Core Construction", "cost": round(midpoint * 0.55, 2)},
                    {"name": "MEP / Systems", "cost": round(midpoint * 0.12, 2)},
                    {"name": "Finishes", "cost": round(midpoint * 0.10, 2)},
                    {"name": "Contingency", "cost": round(midpoint * 0.08, 2)},
                ]
            elif strategy_key == "build_studio":
                suggested_breakdown = [
                    {"name": "Demo / Prep", "cost": round(midpoint * 0.12, 2)},
                    {"name": "Structure / Framing", "cost": round(midpoint * 0.30, 2)},
                    {"name": "MEP / Utilities", "cost": round(midpoint * 0.18, 2)},
                    {"name": "Interior Finishes", "cost": round(midpoint * 0.25, 2)},
                    {"name": "Contingency", "cost": round(midpoint * 0.15, 2)},
                ]
            else:
                suggested_breakdown = [
                    {"name": "Kitchen / Bath", "cost": round(midpoint * 0.30, 2)},
                    {"name": "Flooring / Paint", "cost": round(midpoint * 0.18, 2)},
                    {"name": "Systems / Repairs", "cost": round(midpoint * 0.22, 2)},
                    {"name": "Exterior / Curb Appeal", "cost": round(midpoint * 0.12, 2)},
                    {"name": "Contingency", "cost": round(midpoint * 0.18, 2)},
                ]

    return {
        "suggested_breakdown": suggested_breakdown
    }
# =========================================================
# GENERIC HELPERS
# =========================================================

def _json_default():
    return {}


def _safe_json_loads_local(value, default=None):
    default = default if default is not None else {}
    if not value:
        return default
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _normalize_photo_urls(value) -> list[str]:
    normalized = []
    seen = set()

    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, list):
        candidates = value
    else:
        candidates = []

    for item in candidates:
        url = None
        if isinstance(item, str):
            url = item.strip()
        elif isinstance(item, dict):
            url = (
                item.get("url")
                or item.get("href")
                or item.get("src")
                or item.get("image_url")
            )
            url = str(url).strip() if url not in (None, "") else None

        if not url or not url.lower().startswith(("http://", "https://")):
            continue

        if url in seen:
            continue

        seen.add(url)
        normalized.append(url)

    return normalized


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


def _ingest_listing_photos_to_spaces(photo_urls: list[str], *, subdir: str, limit: int = 8) -> list[str]:
    stored = []

    for idx, url in enumerate(_normalize_photo_urls(photo_urls)[:limit], start=1):
        try:
            raw = download_image_bytes(url)
            if not raw:
                continue

            webp = to_webp_bytes(raw, max_size=1600, quality=86)
            uploaded = spaces_put_bytes(
                webp,
                subdir=subdir,
                content_type="image/webp",
                filename=f"listing_{idx:02d}_{uuid.uuid4().hex[:10]}.webp",
            )
            stored_url = uploaded.get("url")
            if stored_url:
                stored.append(stored_url)
        except Exception:
            current_app.logger.exception("Listing photo ingest failed for %s", url)

    return stored


def _store_saved_property_media(saved_property, payload, *, source: str = "listing_search") -> dict:
    existing_payload = _safe_json_loads_local(getattr(saved_property, "resolved_json", None), default={})
    incoming_payload = _safe_json_loads_local(payload, default={})
    incoming_prop = _property_payload_from_any(payload)
    existing_prop = _property_payload_from_any(existing_payload)

    merged_prop = _merge_nonempty_dict(existing_prop, incoming_prop)

    primary_candidate = (
        merged_prop.get("primary_photo")
        or merged_prop.get("photo")
        or merged_prop.get("image_url")
    )
    source_urls = _normalize_photo_urls(
        [primary_candidate] + _normalize_photo_urls(merged_prop.get("photos"))
    )

    stored_urls = _ingest_listing_photos_to_spaces(
        source_urls,
        subdir=f"properties/{current_user.id}/{saved_property.id or 'pending'}/listing_photos",
    ) if source_urls else []

    final_urls = stored_urls or source_urls
    final_primary = final_urls[0] if final_urls else None

    if final_urls:
        merged_prop["photos"] = final_urls
    if final_primary:
        merged_prop["primary_photo"] = final_primary
        merged_prop["image_url"] = merged_prop.get("image_url") or final_primary

    merged_prop["photo_source"] = source
    merged_prop["photo_count"] = len(final_urls)
    merged_prop["photo_ingested_at"] = datetime.utcnow().isoformat()

    merged_payload = existing_payload if isinstance(existing_payload, dict) else {}
    if isinstance(incoming_payload, dict):
        for key, value in incoming_payload.items():
            if key == "property":
                continue
            if value not in (None, "", [], {}):
                merged_payload[key] = value
    merged_payload["property"] = merged_prop

    if hasattr(saved_property, "resolved_json"):
        saved_property.resolved_json = json.dumps(merged_payload)
        saved_property.resolved_at = datetime.utcnow()

    return merged_payload


def _saved_property_media(saved_property) -> dict:
    payload = _safe_json_loads_local(getattr(saved_property, "resolved_json", None), default={})
    prop = _property_payload_from_any(payload)
    photos = _normalize_photo_urls(prop.get("photos"))
    primary_photo = (
        prop.get("primary_photo")
        or prop.get("image_url")
        or (photos[0] if photos else None)
    )
    return {
        "primary_photo": primary_photo,
        "photos": photos,
    }


def _normalize_int(value):
    try:
        return int(value) if value not in (None, "", "None") else None
    except Exception:
        return None


def _profile_id_filter(model, profile_id):
    if hasattr(model, "investor_profile_id"):
        return {"investor_profile_id": profile_id}
    if hasattr(model, "borrower_profile_id"):
        return {"borrower_profile_id": profile_id}
    return {}


# =========================================================
# DEAL / MOCKUP HELPERS
# =========================================================

def _get_owned_deal_or_404(deal_id: int):
    return Deal.query.filter_by(id=deal_id, user_id=current_user.id).first_or_404()


def _save_before_url_to_deal(deal, before_url: str):
    try:
        payload = deal.resolved_json or {}
        payload = payload if isinstance(payload, dict) else {}
        payload.setdefault("rehab", {})
        payload["rehab"]["before_url"] = before_url
        deal.resolved_json = payload
        db.session.commit()
    except Exception:
        db.session.rollback()


def _get_rehab_mockups_for_deal(deal):
    saved_property_id = getattr(deal, "saved_property_id", None)

    q = RenovationMockup.query.filter(
        RenovationMockup.user_id == current_user.id,
        (
            (RenovationMockup.deal_id == deal.id) |
            (
                (RenovationMockup.saved_property_id == saved_property_id)
                if saved_property_id is not None
                else False
            )
        )
    ).order_by(RenovationMockup.created_at.desc())

    mockups = q.all()

    valid_mockups = [
        m for m in mockups
        if getattr(m, "after_url", None)
        and not str(m.after_url).startswith("outputs/")
        and (
            str(m.after_url).startswith("http://")
            or str(m.after_url).startswith("https://")
        )
    ]

    return valid_mockups

def _save_mockups_for_deal(
    deal,
    before_url: str,
    after_urls: list,
    style_prompt: str = None,
    style_preset: str = None,
    mode: str = "photo",
    property_id=None,
    saved_property_id=None,
):
    if not after_urls:
        return 0

    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    ip_id = ip.id if ip else None
    saved = 0

    for after_url in after_urls:
        mockup_kwargs = {
            "user_id": current_user.id,
            "deal_id": deal.id,
            "saved_property_id": saved_property_id if saved_property_id is not None else getattr(deal, "saved_property_id", None),
            "property_id": property_id,
            "before_url": before_url,
            "after_url": after_url,
            "style_prompt": style_prompt,
            "style_preset": style_preset,
        }

        if hasattr(RenovationMockup, "investor_profile_id"):
            mockup_kwargs["investor_profile_id"] = ip_id

        if hasattr(RenovationMockup, "mode"):
            mockup_kwargs["mode"] = mode

        db.session.add(RenovationMockup(**mockup_kwargs))
        saved += 1

    db.session.commit()
    return saved

def _featured_rehab_data(deal):
    try:
        payload = deal.resolved_json or {}
        payload = payload if isinstance(payload, dict) else {}
        rehab = payload.get("rehab", {}) or {}
        return rehab.get("featured", {}) or {}
    except Exception:
        return {}


def _set_featured_rehab(deal, after_url: str, before_url: str = "", style_preset: str = "", style_prompt: str = ""):
    payload = deal.resolved_json or {}
    payload = payload if isinstance(payload, dict) else {}
    payload.setdefault("rehab", {})

    existing = payload["rehab"].get("featured", {}) or {}
    payload["rehab"]["featured"] = {
        "after_url": after_url,
        "before_url": before_url or existing.get("before_url"),
        "style_preset": style_preset or existing.get("style_preset"),
        "style_prompt": style_prompt or existing.get("style_prompt"),
        "featured_at": datetime.utcnow().isoformat(),
    }

    deal.resolved_json = payload
    deal.reveal_is_public = False
    db.session.commit()
    return payload["rehab"]["featured"]

def build_visualizer_helper_prompt(style_prompt: str, style_preset: str = "", room_focus: str = "kitchen") -> str:
    style_prompt = (style_prompt or "").strip().lower()
    style_preset = (style_preset or "").strip().lower()
    room_focus = (room_focus or "kitchen").strip().lower()

    preset_map = {
        "luxury": "luxury modern renovation",
        "modern": "clean modern renovation",
        "airbnb": "airbnb-ready renovation",
        "flip": "high-end resale renovation",
        "budget": "budget-friendly renovation",
        "luxury_modern": "luxury modern renovation",
    }

    parts = [
        "photorealistic real estate renovation",
        "same exact room layout",
        "preserve layout and geometry but allow full material replacement",
    ]

    if room_focus == "kitchen":
        parts.append("kitchen renovation")

    preset_text = preset_map.get(style_preset)
    if preset_text:
        parts.append(preset_text)

    if style_prompt:
        parts.append(
            f"completely replace cabinets, countertops, flooring, fixtures, and finishes with {style_prompt}"
        )

    return ", ".join(dict.fromkeys(parts))
# =========================================================
# ENGINE STABILITY HELPERS
# =========================================================

RENDER_TIMEOUT = 240
BLUEPRINT_RENDER_TIMEOUT = int(os.getenv("BLUEPRINT_RENDER_TIMEOUT", "90"))
FULL_BUILD_BLUEPRINT_TIMEOUT = int(os.getenv("FULL_BUILD_BLUEPRINT_TIMEOUT", "240"))
SCOPE_TIMEOUT = 45
UPLOAD_TIMEOUT = 240
RENDER_LOCK_SECONDS = 300


def _safe_engine_error_message(resp):
    content_type = (resp.headers.get("Content-Type") or "").lower()

    if "application/json" in content_type:
        try:
            payload = resp.json()
            if isinstance(payload, dict):
                return (
                    payload.get("detail")
                    or payload.get("message")
                    or payload.get("error")
                    or str(payload)[:300]
                )
        except Exception:
            pass

    return (resp.text or f"HTTP {resp.status_code}")[:300]


def _friendly_engine_timeout_message(url, timeout, error):
    host = (urlparse(url).netloc or url).strip()
    message = f"Renovation engine timed out after {timeout}s."
    if "ngrok" in host:
        message += " The ngrok tunnel or local render worker may be offline, sleeping, or still processing the image job."
    return f"{message} host={host} error={error}"


def _is_engine_timeout_error(error):
    text = str(error or "").lower()
    return "timed out" in text and "engine" in text


def _stable_render_seed(*parts):
    raw = "|".join([str(part or "").strip().lower() for part in parts if part is not None]).strip("|")
    if not raw:
        raw = uuid.uuid4().hex
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 2_147_483_647

def _post_renovation_engine_json(path, payload, timeout=RENDER_TIMEOUT):
    url = _renovation_engine_url(path)

    headers = dict(_engine_headers() or {})
    headers.setdefault("Content-Type", "application/json")
    headers["ngrok-skip-browser-warning"] = "true"

    current_app.logger.warning(
        "ENGINE REQUEST url=%s mode=%s timeout=%s",
        url,
        payload.get("mode"),
        timeout,
    )

    try:
        res = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=timeout,
        )
    except requests.Timeout as e:
        raise RuntimeError(_friendly_engine_timeout_message(url, timeout, e))
    except requests.RequestException as e:
        raise RuntimeError(f"Engine request failed. url={url} error={e}")

    content_type = (res.headers.get("Content-Type") or "").lower()
    body = res.text or ""
    snippet = body[:500]

    current_app.logger.warning(
        "ENGINE RESPONSE url=%s status=%s content_type=%s body_preview=%s",
        url,
        res.status_code,
        content_type,
        snippet,
    )

    # Handle HTTP errors first
    if not res.ok:
        # ngrok/browser interstitial or generic HTML error page
        if "text/html" in content_type or body.lstrip().lower().startswith("<!doctype html") or "<html" in body[:200].lower():
            raise RuntimeError(
                f"Engine returned HTML instead of JSON. "
                f"url={url} status={res.status_code} content_type={content_type} "
                f"body={snippet}"
            )

        raise RuntimeError(_safe_engine_error_message(res))

    # Successful HTTP status, but still not JSON
    if "application/json" not in content_type:
        if "text/html" in content_type or body.lstrip().lower().startswith("<!doctype html") or "<html" in body[:200].lower():
            raise RuntimeError(
                f"Engine returned HTML instead of JSON. "
                f"url={url} status={res.status_code} content_type={content_type} "
                f"body={snippet}"
            )

        raise RuntimeError(
            f"Engine returned non-JSON response. "
            f"url={url} status={res.status_code} content_type={content_type} "
            f"body={snippet}"
        )

    try:
        return res.json()
    except Exception as e:
        raise RuntimeError(
            f"Engine returned invalid JSON. "
            f"url={url} status={res.status_code} content_type={content_type} "
            f"error={e} body={snippet}"
        )

def _post_renovation_engine_multipart(path, files, data, timeout=UPLOAD_TIMEOUT):
    res = requests.post(
        _renovation_engine_url(path),
        files=files,
        data=data,
        headers=_engine_headers(),
        timeout=timeout,
    )
    if not res.ok:
        raise RuntimeError(_safe_engine_error_message(res))
    return res.json()


def _post_scope_engine_json(path, payload, timeout=SCOPE_TIMEOUT):
    res = requests.post(
        _scope_engine_url(path),
        json=payload,
        headers=_scope_engine_headers(),
        timeout=timeout,
    )
    if not res.ok:
        raise RuntimeError(_safe_engine_error_message(res))
    return res.json()


def _deal_render_lock_active(deal):
    started = getattr(deal, "render_started_at", None)
    status = getattr(deal, "render_status", None)

    if status != "processing" or not started:
        return False

    age = (datetime.utcnow() - started).total_seconds()
    return age < RENDER_LOCK_SECONDS


def _set_deal_render_processing(deal):
    if hasattr(deal, "render_status"):
        deal.render_status = "processing"
    if hasattr(deal, "render_started_at"):
        deal.render_started_at = datetime.utcnow()


def _clear_deal_render_processing(deal):
    if hasattr(deal, "render_status"):
        deal.render_status = "idle"
    if hasattr(deal, "render_started_at"):
        deal.render_started_at = None
# =========================================================
# STORAGE HELPERS
# =========================================================

def _upload_before_image(raw_bytes: bytes) -> str:
    before_webp = to_webp_bytes(raw_bytes, max_size=1600, quality=86)
    uploaded = spaces_put_bytes(
        before_webp,
        subdir=f"visualizer/{current_user.id}/before",
        content_type="image/webp",
        filename=f"{uuid.uuid4().hex}_before.webp",
    )
    return uploaded["url"]


def _upload_after_images_from_b64(images_b64, render_batch_id: str):
    after_urls = []

    for i, b64 in enumerate(images_b64 or [], start=1):
        try:
            raw_png = base64.b64decode(b64)
            img = Image.open(io.BytesIO(raw_png)).convert("RGB")

            buf = io.BytesIO()
            img.save(buf, format="WEBP", quality=90)

            uploaded = spaces_put_bytes(
                buf.getvalue(),
                subdir=f"visualizer/{current_user.id}/{render_batch_id}/after",
                content_type="image/webp",
                filename=f"{render_batch_id}_after_{i}.webp",
            )
            after_urls.append(uploaded["url"])
        except Exception as e:
            current_app.logger.warning("After image upload failed (%s): %s", i, e)

    return after_urls

def _upload_build_images_from_b64(images_b64, render_batch_id: str):
    build_urls = []

    for i, b64 in enumerate(images_b64 or [], start=1):
        try:
            raw_png = base64.b64decode(b64)
            img = Image.open(io.BytesIO(raw_png)).convert("RGB")

            buf = io.BytesIO()
            img.save(buf, format="WEBP", quality=90)

            uploaded = spaces_put_bytes(
                buf.getvalue(),
                subdir=f"builds/{current_user.id}/{render_batch_id}",
                content_type="image/webp",
                filename=f"{render_batch_id}_build_{i}.webp",
            )
            build_urls.append(uploaded["url"])
        except Exception as e:
            current_app.logger.warning("Build image upload failed (%s): %s", i, e)

    return build_urls

# ---------------------------------------------------------
# Investor Capital Timeline (used for progress UI)
# ---------------------------------------------------------
INVESTOR_TIMELINE = [
    {"step": 1, "title": "Capital Request Started", "key": "request_started"},
    {"step": 2, "title": "Documents Uploaded", "key": "docs_uploaded"},
    {"step": 3, "title": "Under Review", "key": "under_review"},
    {"step": 4, "title": "Conditions Issued", "key": "conditions_issued"},
    {"step": 5, "title": "Conditions Cleared", "key": "conditions_cleared"},
    {"step": 6, "title": "Final Review", "key": "final_review"},
    {"step": 7, "title": "Cleared to Close", "key": "ctc"},
]

TIMELINES = {
    "capital": INVESTOR_TIMELINE,
    "construction": [
        {"step": 1, "title": "Project Submitted", "key": "project_submitted"},
        {"step": 2, "title": "Budget Approved", "key": "budget_approved"},
        {"step": 3, "title": "Draw Schedule Created", "key": "draw_schedule"},
        {"step": 4, "title": "Construction Started", "key": "construction_started"},
        {"step": 5, "title": "Final Inspection", "key": "final_inspection"},
        {"step": 6, "title": "Project Completed", "key": "project_completed"},
    ]
}


# ---------------------------------------------------------
# Investor Command Center Routes
# ---------------------------------------------------------

@investor_bp.route("/debug/google-test")
@login_required
def debug_google_test():
    import os
    import requests

    key = os.getenv("GOOGLE_API_KEY")
    if not key:
        return {"ok": False, "error": "Missing GOOGLE_API_KEY"}, 500

    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": "contractor in Tampa FL",
        "key": key,
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        return {
            "ok": True,
            "status_code": resp.status_code,
            "google_status": data.get("status"),
            "results_found": len(data.get("results", [])),
            "sample_names": [r.get("name") for r in data.get("results", [])[:5]],
            "error_message": data.get("error_message"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500
        
@investor_bp.route("/", methods=["GET"], endpoint="command_center")
@investor_bp.route("/index", methods=["GET"])
@investor_bp.route("/command", methods=["GET"])
@investor_bp.route("/dashboard", methods=["GET"])
@investor_bp.route("/dashboard-home", methods=["GET"], endpoint="dashboard")
@login_required
@role_required("investor")
def command_center():
    """
    Investor Command Center — single source of truth.
    '/' '/index' '/command' '/dashboard' all land here.
    """

    # Respect ?next= if present
    next_page = (request.args.get("next") or "").strip()
    if next_page and next_page.startswith("/"):
        return redirect(next_page)

    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    capital_requests = []
    active_request = None
    conditions = []
    doc_requests = []
    saved_props = []
    primary_stage = None

    assistant = AIAssistant()
    next_step_ai = None
    next_step_text = "No active capital request. Start a new deal when ready."

    if ip:
        # Saved properties / watchlist
        saved_props = (
            SavedProperty.query
            .filter_by(investor_profile_id=ip.id)
            .order_by(SavedProperty.created_at.desc())
            .all()
        )

        # All capital requests
        capital_requests = (
            LoanApplication.query
            .filter_by(investor_profile_id=ip.id)
            .order_by(LoanApplication.created_at.desc())
            .all()
        )

        # Active capital request
        active_request = (
            LoanApplication.query
            .filter_by(investor_profile_id=ip.id, is_active=True)
            .order_by(LoanApplication.created_at.desc())
            .first()
        )

        # Document requests
        doc_requests = (
            LoanDocument.query
            .filter_by(investor_profile_id=ip.id)
            .order_by(LoanDocument.created_at.desc())
            .all()
        )

        if active_request:
            conditions = (
                UnderwritingCondition.query
                .filter_by(investor_profile_id=ip.id, loan_id=active_request.id)
                .order_by(UnderwritingCondition.created_at.desc())
                .all()
            )

            primary_stage = getattr(active_request, "status", None) or "Application"

            pending_conditions = [
                c for c in conditions
                if (c.status or "").strip().lower() not in {"submitted", "cleared", "completed"}
            ]

            if pending_conditions:
                next_step_text = (
                    f"You have {len(pending_conditions)} pending items. "
                    f"Next: {pending_conditions[0].description}."
                )
            else:
                next_step_text = "All items are in. Waiting on capital review."

    # Progress snapshot
    progress_percent = 0
    if active_request:
        total_conditions = len(conditions)
        cleared_conditions = len([
            c for c in conditions
            if (c.status or "").strip().lower() == "cleared"
        ])
        if total_conditions > 0:
            progress_percent = int((cleared_conditions / total_conditions) * 100)

    # Ravlo deal intelligence
    deals = []
    recent_deals = []
    total_deals = 0
    average_deal_score = 0
    ready_for_funding_count = 0
    funding_requested_count = 0

    if ip:
        deals = (
            Deal.query
            .filter_by(user_id=current_user.id)
            .order_by(Deal.updated_at.desc())
            .all()
        )

        total_deals = len(deals)

        scored_deals = [d.deal_score for d in deals if d.deal_score is not None]
        average_deal_score = round(sum(scored_deals) / len(scored_deals), 1) if scored_deals else 0

        ready_for_funding_count = len([
            d for d in deals
            if not d.submitted_for_funding
            and ((d.recommended_strategy or d.strategy) is not None)
            and (d.purchase_price or 0) > 0
        ])

        funding_requested_count = len([
            d for d in deals
            if d.submitted_for_funding
        ])

        recent_deals = deals[:5]

    snapshot = {
        "loan_type": getattr(active_request, "loan_type", None) if active_request else None,
        "amount": getattr(active_request, "amount", None) if active_request else None,
        "status": getattr(active_request, "status", None) if active_request else None,
        "address": getattr(active_request, "property_address", None) if active_request else None,
        "progress_percent": progress_percent,
    }

    try:
        next_step_ai = assistant.generate_reply(
            f"Create a calm, professional investor-facing next step message: {next_step_text}",
            "investor_next_step"
        )
    except Exception:
        next_step_ai = "Next step guidance is unavailable right now."

    now_str = datetime.now().strftime("%b %d, %Y • %I:%M %p")

    return render_template(
        "investor/dashboard.html",
        investor=ip,
        capital_requests=capital_requests,
        active_request=active_request,
        conditions=conditions,
        doc_requests=doc_requests,
        saved_props=saved_props,
        snapshot=snapshot,
        next_step_ai=next_step_ai,
        primary_stage=primary_stage,
        now_str=now_str,
        investor_profile=ip,
        active_tab="command",
        title="RAVLO • Command Center",
        total_deals=total_deals,
        average_deal_score=average_deal_score,
        ready_for_funding_count=ready_for_funding_count,
        funding_requested_count=funding_requested_count,
        recent_deals=recent_deals,
    )

@investor_bp.route("/test_blueprint", methods=["GET"])
@login_required
def test_blueprint():
    return render_template("test_blueprint.html")


@investor_bp.route("/resources", methods=["GET"])
@login_required
@role_required("investor")
def resource_center():
    """
    Investor Resource Center
    Tools, FAQs, Partners, AI Help
    """
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        flash("Please complete your investor profile first.", "warning")
        return redirect(url_for("investor.create_profile"))

    selected_category = (request.args.get("category") or "All").strip()

    partner_query = Partner.query.filter(
        Partner.active.is_(True),
        Partner.approved.is_(True)
    )

    if selected_category != "All":
        partner_query = partner_query.filter(Partner.category.ilike(f"%{selected_category}%"))

    partners = partner_query.order_by(
        Partner.featured.desc(),
        Partner.rating.desc().nullslast(),
        Partner.name.asc()
    ).limit(8).all()

    faqs = [
        {"q": "How long does approval take?", "a": "Most approvals are 5–10 business days."},
        {"q": "What documents are required?", "a": "Purchase contract, scope, bank statements."},
        {"q": "How do I request funding?", "a": "Open a deal and click Funding to launch the Capital Application."},
        {"q": "Can I request a contractor or partner?", "a": "Yes. Use the Partner Directory in the Resource Center to request a connection."},
    ]

    timeline = [
        {"title": "Capital Request Started", "status": "completed"},
        {"title": "File Review", "status": "current"},
        {"title": "Conditions Cleared", "status": "upcoming"},
        {"title": "Approval / Funding", "status": "upcoming"},
    ]

    loan = None
    loan_officer = None
    processor = None

    return render_template(
        "investor/resource_center.html",
        investor=ip,
        partners=partners,
        faqs=faqs,
        selected_category=selected_category,
        timeline=timeline,
        loan=loan,
        loan_officer=loan_officer,
        processor=processor,
        title="RAVLO Resource Center",
        active_tab="resources"
    )

@investor_bp.route("/resources/save", methods=["POST"])
@login_required
@role_required("investor")
def resource_center_save():
    payload = request.get_json(silent=True) or {}
    return jsonify({"success": True, "payload": payload})

@investor_bp.route("/search", methods=["GET"])
@login_required
@role_required("investor")
def search():
    """
    Investor Resource Center search
    Searches FAQs, partners, and built-in resource links.
    """

    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    q = (request.args.get("q") or "").strip()
    q_lower = q.lower()

    # -----------------------------
    # FAQ data
    # -----------------------------
    faqs = [
        {"q": "How long does approval take?", "a": "Most approvals are 5–10 business days."},
        {"q": "What documents are required?", "a": "Purchase contract, scope, bank statements."},
        {"q": "How do I request funding?", "a": "Open a deal and click Funding to launch the Capital Application."},
        {"q": "Can I request a contractor or partner?", "a": "Yes. Use the Partner Directory in the Resource Center to request a connection."},
    ]

    # -----------------------------
    # Static resource shortcuts
    # -----------------------------
    resources = [
        {
            "title": "Capital Application",
            "description": "Start a new funding request for your deal.",
            "url": url_for("investor.capital_application"),
            "category": "Capital"
        },
        {
            "title": "Conditions",
            "description": "Review items needed for underwriting and approval.",
            "url": url_for("investor.conditions"),
            "category": "Capital"
        },
        {
            "title": "Documents",
            "description": "View and manage your funding documents.",
            "url": url_for("investor.documents"),
            "category": "Capital"
        },
        {
            "title": "Deals List",
            "description": "Review your saved deals and move them into funding.",
            "url": url_for("investor.deals_list"),
            "category": "Deals"
        },
        {
            "title": "Deal Finder",
            "description": "Search for investment opportunities and fixer uppers.",
            "url": url_for("investor.property_tool"),
            "category": "Deals"
        },
        {
            "title": "Resource Center",
            "description": "Investor help hub for funding, team support, and partners.",
            "url": url_for("investor.resource_center"),
            "category": "Support"
        },
    ]

    # -----------------------------
    # Search partners
    # -----------------------------
    all_partners = Partner.query.order_by(Partner.name.asc()).all()
    partner_results = []

    if q_lower:
        for partner in all_partners:
            haystack = " ".join([
                str(getattr(partner, "name", "") or ""),
                str(getattr(partner, "category", "") or ""),
                str(getattr(partner, "service_area", "") or ""),
                str(getattr(partner, "description", "") or ""),
            ]).lower()

            if q_lower in haystack:
                partner_results.append(partner)

    # -----------------------------
    # Search FAQs
    # -----------------------------
    faq_results = []
    if q_lower:
        faq_results = [
            item for item in faqs
            if q_lower in item["q"].lower() or q_lower in item["a"].lower()
        ]

    # -----------------------------
    # Search resource shortcuts
    # -----------------------------
    resource_results = []
    if q_lower:
        resource_results = [
            item for item in resources
            if q_lower in item["title"].lower()
            or q_lower in item["description"].lower()
            or q_lower in item["category"].lower()
        ]

    # -----------------------------
    # Empty query behavior
    # -----------------------------
    if not q:
        faq_results = faqs
        resource_results = resources
        partner_results = all_partners[:8]

    total_results = len(faq_results) + len(resource_results) + len(partner_results)

    return render_template(
        "investor/search_results.html",
        investor=ip,
        query=q,
        faq_results=faq_results,
        resource_results=resource_results,
        partner_results=partner_results,
        total_results=total_results,
        title="Search Results",
        active_tab="resources"
    )

@investor_bp.route("/dismiss_dashboard_tour", methods=["POST"])
@login_required
@role_required("investor")
def dismiss_dashboard_tour():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if ip:
        ip.has_seen_dashboard_tour = True
        db.session.commit()
    return jsonify({"status": "ok"})


# =========================================================
# 👤 INVESTOR ACCOUNT (profile/settings/privacy/notifications)
# =========================================================
@investor_bp.route("/account", methods=["GET"])
@login_required
@role_required("investor")
def account():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    now_str = datetime.now().strftime("%b %d, %Y • %I:%M %p")

    return render_template(
        "investor/account.html",
        investor=current_user,
        investor_profile=ip,
        now_str=now_str,
        active_tab="account",
        title="RAVLO • Account"
    )

@investor_bp.route("/profile", methods=["GET"])
@login_required
@role_required("investor")
def profile():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    return render_template("investor/profile.html", investor=ip)


@investor_bp.route("/settings", methods=["GET", "POST"])
@login_required
@role_required("investor")
def settings():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    if request.method == "POST":
        current_user.first_name = (request.form.get("first_name") or "").strip() or current_user.first_name
        current_user.last_name = (request.form.get("last_name") or "").strip() or current_user.last_name
        current_user.email = (request.form.get("email") or "").strip() or current_user.email

        if ip:
            ip.strategy = (request.form.get("strategy") or "").strip() or None

        current_password = request.form.get("current_password") or ""
        new_password = request.form.get("new_password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if new_password or confirm_password or current_password:
            if not current_password:
                flash("Enter your current password to change it.", "danger")
                return redirect(url_for("investor.settings") + "#password")
            if not current_user.check_password(current_password):
                flash("Current password is incorrect.", "danger")
                return redirect(url_for("investor.settings") + "#password")
            if new_password != confirm_password:
                flash("New password and confirmation do not match.", "danger")
                return redirect(url_for("investor.settings") + "#password")
            if not new_password:
                flash("Enter a new password to complete the password change.", "danger")
                return redirect(url_for("investor.settings") + "#password")
            current_user.set_password(new_password)

        db.session.commit()
        flash("Settings updated successfully.", "success")
        return redirect(url_for("investor.settings"))

    return render_template(
        "investor/settings.html",
        investor=current_user,
        investor_profile=ip
    )

@investor_bp.route("/privacy", methods=["GET"])
@login_required
@role_required("investor")
def privacy():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    return render_template(
        "investor/privacy_launch.html",
        investor=current_user,
        investor_profile=ip,
    )


@investor_bp.route("/notifications-settings", methods=["GET"])
@login_required
@role_required("investor")
def notifications_settings():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    return render_template(
        "investor/notifications_settings.html",
        investor=current_user,
        investor_profile=ip,
    )


# =========================================================
# 🧾 INVESTOR PROFILE CREATE/UPDATE
# =========================================================

@investor_bp.route("/create_profile", methods=["GET", "POST"])
@login_required
@role_required("investor")
def create_profile():
    from LoanMVP.forms.investor_forms import InvestorProfileForm

    existing = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    if existing:
        form = InvestorProfileForm(obj=existing)
    else:
        form = InvestorProfileForm()

    if form.validate_on_submit():
        if existing:
            ip = existing
        else:
            ip = InvestorProfile(user_id=current_user.id)
            db.session.add(ip)

        ip.full_name = form.full_name.data
        ip.email = form.email.data
        ip.phone = form.phone.data
        ip.address = form.address.data
        ip.city = form.city.data
        ip.state = form.state.data
        ip.zip_code = form.zip_code.data
        ip.employment_status = form.employment_status.data
        ip.annual_income = form.annual_income.data
        ip.credit_score = form.credit_score.data

        ip.strategy = form.strategy.data
        ip.experience_level = form.experience_level.data
        ip.target_markets = form.target_markets.data
        ip.property_types = form.property_types.data
        ip.min_price = form.min_price.data
        ip.max_price = form.max_price.data
        ip.min_sqft = form.min_sqft.data
        ip.max_sqft = form.max_sqft.data
        ip.capital_available = form.capital_available.data
        ip.min_cash_on_cash = form.min_cash_on_cash.data
        ip.min_roi = form.min_roi.data
        ip.timeline_days = form.timeline_days.data
        ip.risk_tolerance = form.risk_tolerance.data

        db.session.commit()

        flash("Investor profile saved successfully!", "success")
        return redirect(url_for("investor.command_center"))

    return render_template(
        "investor/create_profile.html",
        form=form,
        title="Create Investor Profile"
    )

@investor_bp.route("/update_profile", methods=["POST"])
@login_required
@role_required("investor")
def update_profile():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        return jsonify({"status": "error", "message": "Profile not found."}), 404

    payload = request.get_json(silent=True) or request.form

    user_fields = {"first_name", "last_name", "email"}
    for field, value in payload.items():
        clean_value = (value or "").strip() if isinstance(value, str) else value
        if field in user_fields and clean_value:
            setattr(current_user, field, clean_value)

    for field, value in payload.items():
        clean_value = (value or "").strip() if isinstance(value, str) else value
        if hasattr(ip, field) and (value or "").strip():
            setattr(ip, field, clean_value)

    ip.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"status": "success", "message": "Profile updated successfully."})


@investor_bp.route("/prequal", methods=["GET", "POST"])
@investor_bp.route("/ai-prequal", methods=["GET", "POST"], endpoint="ai_prequal")
@login_required
@role_required("investor")
def prequal():
    result = None

    if request.method == "POST":
        income = safe_float(request.form.get("income")) or 0
        debts = safe_float(request.form.get("debts")) or 0
        loan_amount = safe_float(request.form.get("loan_amount")) or 0
        property_value = safe_float(request.form.get("property_value")) or 0
        credit_score = safe_float(request.form.get("credit_score")) or 0

        dti = round((debts / income) * 100, 2) if income > 0 else 0
        ltv = round((loan_amount / property_value) * 100, 2) if property_value > 0 else 0

        if dti <= 43 and ltv <= 80 and credit_score >= 680:
            status = "Approved"
        elif dti <= 50 and ltv <= 90 and credit_score >= 620:
            status = "Conditional"
        else:
            status = "Review"

        max_qual_amount = max((income * 45) - (debts * 12), 0)

        ai_summary = (
            f"DTI is {dti:.2f}% and LTV is {ltv:.2f}%. "
            f"Based on the submitted income, debts, leverage, and credit profile, "
            f"this scenario is currently marked {status.lower()}."
        )

        result = {
            "status": status,
            "dti": dti,
            "ltv": ltv,
            "max_qual_amount": max_qual_amount,
            "ai_summary": ai_summary,
        }

    return render_template(
        "investor/prequal.html",
        result=result,
        title="AI Pre-Qualification",
        active_tab="capital",
    )


@investor_bp.route("/start-loan", methods=["GET", "POST"], endpoint="start_loan")
@login_required
@role_required("investor")
def start_loan():
    if request.method == "POST":
        loan_type = (request.form.get("loan_type") or "Investor Capital").strip()
        amount = safe_float(request.form.get("amount")) or 0
        return redirect(
            url_for(
                "investor.capital_application",
                loan_type=loan_type,
                amount=amount if amount else None,
            )
        )

    return render_template(
        "investor/onboarding_start_loan.html",
        title="Start Loan",
        active_tab="capital",
    )
    
# =========================================================
# 📝 INVESTOR • CAPITAL APPLICATION + STATUS
# =========================================================

@investor_bp.route("/loans", methods=["GET"])
@login_required
@role_required("investor")
def loans():
    investor = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    if not investor:
        flash("Please complete your investor profile first.", "warning")
        return redirect(url_for("investor.create_profile"))

    profile_fk = _profile_id_filter(LoanApplication, investor.id) or {}

    loans = (
        LoanApplication.query
        .filter_by(**profile_fk)
        .order_by(LoanApplication.created_at.desc())
        .all()
    )

    return render_template(
        "investor/loans.html",
        investor=investor,
        loans=loans,
        title="Loan Center"
    )

@investor_bp.route("/loans/<int:loan_id>/summary", methods=["GET"])
@login_required
@role_required("investor")
def loan_summary(loan_id):
    investor = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    if not investor:
        flash("Please complete your investor profile first.", "warning")
        return redirect(url_for("investor.create_profile"))

    loan = LoanApplication.query.filter_by(
        id=loan_id,
        investor_profile_id=investor.id
    ).first()

    if not loan:
        flash("Loan not found.", "danger")
        return redirect(url_for("investor.loans"))

    conditions = (
        UnderwritingCondition.query
        .filter_by(loan_id=loan.id)
        .order_by(UnderwritingCondition.id.desc())
        .all()
    )

    ai_summary = getattr(loan, "ai_summary", None)

    return render_template(
        "investor/view_loan.html",
        investor=investor,
        loan=loan,
        conditions=conditions,
        ai_summary=ai_summary,
        title="Loan Details"
    )

@investor_bp.route("/loans/<int:loan_id>/timeline", methods=["GET"])
@login_required
@role_required("investor")
def loan_timeline(loan_id):
    investor = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    if not investor:
        flash("Please complete your investor profile first.", "warning")
        return redirect(url_for("investor.create_profile"))

    loan = LoanApplication.query.filter_by(
        id=loan_id,
        investor_profile_id=investor.id
    ).first()

    if not loan:
        flash("Loan not found.", "danger")
        return redirect(url_for("investor.loans"))

    events = (
        LoanStatusEvent.query
        .filter_by(loan_id=loan.id)
        .order_by(LoanStatusEvent.id.desc())
        .all()
    )

    return render_template(
        "investor/loan_timeline.html",
        investor=investor,
        loan=loan,
        events=events,
        title="Loan Timeline"
    )

@investor_bp.route("/capital_application", methods=["GET"])
@login_required
@role_required("investor")
def capital_application():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        flash("Please create your investor profile before applying for capital.", "warning")
        return redirect(url_for("investor.create_profile"))

    deal_id = request.args.get("deal_id", type=int)
    deal = None

    if deal_id:
        deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first()

    officers = LoanOfficerProfile.query.order_by(LoanOfficerProfile.name.asc()).all()
    initial_loan_type = (request.args.get("loan_type") or "").strip()
    initial_amount = request.args.get("amount", type=float)

    return render_template(
        "investor/capital_application.html",
        investor=ip,
        deal=deal,
        officers=officers,
        initial_loan_type=initial_loan_type,
        initial_amount=initial_amount,
        title="Apply for Capital"
    )

@investor_bp.route("/capital_application/submit", methods=["POST"])
@login_required
@role_required("investor")
def submit_capital_application():
    investor = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not investor:
        return jsonify({"success": False, "message": "No investor profile found."}), 404

    # -----------------------------
    # Deal lookup
    # -----------------------------
    deal_id = request.form.get("deal_id", type=int)
    deal = None

    if deal_id:
        deal = Deal.query.filter_by(
            id=deal_id,
            user_id=current_user.id
        ).first()

    # -----------------------------
    # Form fields
    # -----------------------------
    full_name = (request.form.get("full_name") or getattr(investor, "full_name", None) or "").strip()
    loan_type = (request.form.get("loan_type") or "Investor Capital").strip()

    project_address = (
        request.form.get("project_address")
        or (deal.address if deal else "")
        or ""
    ).strip()

    project_description = (
        request.form.get("project_description")
        or (deal.notes if deal else "")
        or ""
    ).strip()

    try:
        amount = float(request.form.get("amount") or 0)
    except (TypeError, ValueError):
        amount = 0

    try:
        property_value = float(request.form.get("property_value") or 0)
    except (TypeError, ValueError):
        property_value = 0

    preferred_loan_officer_id = request.form.get("preferred_loan_officer_id")

    # fallback values from deal
    if not amount and deal:
        amount = float((deal.purchase_price or 0) + (deal.rehab_cost or 0))

    if not property_value and deal:
        property_value = float(deal.arv or 0)

    # -----------------------------
    # Bridge: Investor -> BorrowerProfile
    # -----------------------------
    borrower = None

    if hasattr(investor, "borrower_profile_id") and investor.borrower_profile_id:
        borrower = BorrowerProfile.query.get(investor.borrower_profile_id)

    if not borrower and getattr(investor, "email", None):
        borrower = BorrowerProfile.query.filter_by(email=investor.email).first()

    if not borrower:
        borrower = BorrowerProfile(
            user_id=getattr(investor, "user_id", None),
            full_name=full_name or getattr(investor, "full_name", None),
            email=getattr(investor, "email", None),
            phone=getattr(investor, "phone", None),
            address=getattr(investor, "address", None),
            city=getattr(investor, "city", None),
            state=getattr(investor, "state", None),
            zip=getattr(investor, "zip", None),
            annual_income=getattr(investor, "annual_income", None),
            employment_status="Investor",
            created_at=datetime.utcnow(),
        )
        db.session.add(borrower)
        db.session.flush()

        if hasattr(investor, "borrower_profile_id"):
            investor.borrower_profile_id = borrower.id

    # -----------------------------
    # Optional investor FK mapping
    # -----------------------------
    profile_fk = _profile_id_filter(LoanApplication, investor.id)

    # -----------------------------
    # Loan officer assignment
    # -----------------------------
    assigned_officer_id = None

    if preferred_loan_officer_id:
        try:
            assigned_officer_id = int(preferred_loan_officer_id)
        except (TypeError, ValueError):
            assigned_officer_id = None

    if not assigned_officer_id:
        auto_officer = LoanOfficerProfile.query.order_by(LoanOfficerProfile.joined_at.asc()).first()
        if auto_officer:
            assigned_officer_id = auto_officer.id

    # -----------------------------
    # Create loan / capital request
    # -----------------------------
    loan = LoanApplication(
        investor_profile_id=investor.id,
        borrower_profile_id=borrower.id,
        loan_officer_id=assigned_officer_id,
        loan_type=loan_type,
        amount=amount,
        property_value=property_value,
        property_address=project_address,
        description=project_description,
        ai_summary=project_description,
        status="Capital Submitted",
        is_active=True,
        created_at=datetime.utcnow()
    )

    # optional link back to deal if your model supports it
    if hasattr(loan, "deal_id"):
        loan.deal_id = deal.id if deal else None

    db.session.add(loan)
    db.session.flush()

    # -----------------------------
    # Update deal funding status
    # -----------------------------
    if deal:
        if hasattr(deal, "submitted_for_funding"):
            deal.submitted_for_funding = True
        if hasattr(deal, "funding_requested_at"):
            deal.funding_requested_at = datetime.utcnow()
        if hasattr(deal, "funding_status"):
            deal.funding_status = "Capital Submitted"
        if hasattr(deal, "loan_application_id"):
            deal.loan_application_id = loan.id

    # -----------------------------
    # Timeline event
    # -----------------------------
    db.session.add(
        LoanStatusEvent(
            loan_id=loan.id,
            event_name="Capital Application Submitted",
            description="Investor submitted a capital request through Ravlo."
        )
    )

    # -----------------------------
    # Optional AI summary refresh
    # -----------------------------
    try:
        assistant = AIAssistant()
        client_name = getattr(investor, "full_name", None) or borrower.full_name or "Unknown Client"

        loan.ai_summary = assistant.generate_reply(
            f"Summarize this capital request for {client_name}: "
            f"{loan_type}, requested amount ${amount:,.0f}, "
            f"property value ${property_value:,.0f}, "
            f"project address {project_address}. "
            f"Project notes: {project_description}",
            "capital_application_summary"
        )
    except Exception:
        pass

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Application submitted successfully.",
        "loan_id": loan.id,
        "borrower_profile_id": borrower.id,
        "loan_officer_id": assigned_officer_id,
        "redirect_url": url_for("investor.loan_view", loan_id=loan.id)
    })

@investor_bp.route("/deals/<int:deal_id>/submit-funding", methods=["POST"])
@login_required
@role_required("investor")
def submit_deal_for_funding(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first()

    if not deal:
        flash("Deal not found.", "danger")
        return redirect(url_for("investor.deal_workspace"))

    deal.submitted_for_funding = True
    deal.funding_requested_at = datetime.utcnow()
    db.session.commit()

    flash("Deal submitted for funding review.", "success")
    return redirect(url_for("investor.capital_application", deal_id=deal.id))

@investor_bp.route("/capital/status", methods=["GET"])
@investor_bp.route("/status", methods=["GET"])
@login_required
@role_required("investor")
def status():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        flash("Please complete your investor profile first.", "warning")
        return redirect(url_for("investor.create_profile"))

    profile_fk = _profile_id_filter(LoanApplication, ip.id)
    doc_fk = _profile_id_filter(LoanDocument, ip.id)

    loans = LoanApplication.query.filter_by(**profile_fk).all()
    documents = LoanDocument.query.filter_by(**doc_fk).all()

    stats = {
        "total_loans": len(loans),
        "pending_docs": len([d for d in documents if (d.status or "").lower() in ["pending", "uploaded"]]),
        "verified_docs": len([d for d in documents if (d.status or "").lower() == "verified"]),
        "active_loans": len([l for l in loans if (l.status or "").lower() in ["active", "processing"]]),
        "completed_loans": len([l for l in loans if (l.status or "").lower() in ["closed", "funded"]]),
    }

    assistant = AIAssistant()
    try:
        ai_summary = assistant.generate_reply(
            f"Summarize investor capital status for {ip.full_name} with: {stats}",
            "investor_status",
        )
    except Exception:
        ai_summary = "⚠️ AI summary unavailable."

    return render_template(
        "investor/status.html",
        investor=ip,
        loans=loans,
        documents=documents,
        stats=stats,
        ai_summary=ai_summary,
        title="Capital Status",
    )


# =========================================================
# 📄 INVESTOR • LOAN VIEW / EDIT (security-safe)
# =========================================================

@investor_bp.route("/capital/loan/<int:loan_id>", methods=["GET"])
@investor_bp.route("/loan/<int:loan_id>", methods=["GET"])
@login_required
@role_required("investor")
def loan_view(loan_id):
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    loan = LoanApplication.query.get_or_404(loan_id)

    # Ownership check (supports both schemas)
    owns = False
    if ip:
        if hasattr(loan, "investor_profile_id") and loan.investor_profile_id == ip.id:
            owns = True
        if hasattr(loan, "borrower_profile_id") and loan.borrower_profile_id == ip.id:
            owns = True

    if not ip or not owns:
        return "Unauthorized", 403

    cond_fk = _profile_id_filter(UnderwritingCondition, ip.id)

    conditions = UnderwritingCondition.query.filter_by(
        **cond_fk,
        loan_id=loan.id
    ).all()

    assistant = AIAssistant()
    try:
        ai_summary = assistant.generate_reply(
            f"Summarize {len(conditions)} underwriting items for investor {ip.full_name}.",
            "investor_loan_conditions",
        )
    except Exception:
        ai_summary = None

    return render_template(
        "investor/view_loan.html",
        investor=ip,
        loan=loan,
        conditions=conditions,
        ai_summary=ai_summary,
        active_tab="capital",
        title=f"Loan #{loan.id}",
    )

@investor_bp.route("/capital/loan/<int:loan_id>/edit", methods=["GET", "POST"])
@investor_bp.route("/loan/<int:loan_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("investor")
def loan_edit(loan_id):
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    loan = LoanApplication.query.get_or_404(loan_id)

    owns = False
    if ip:
        if hasattr(loan, "investor_profile_id") and loan.investor_profile_id == ip.id:
            owns = True
        if hasattr(loan, "borrower_profile_id") and loan.borrower_profile_id == ip.id:
            owns = True

    if not ip or not owns:
        return "Unauthorized", 403

    if request.method == "POST":
        if hasattr(loan, "amount"):
            loan.amount = safe_float(request.form.get("amount"))
        if hasattr(loan, "loan_amount"):
            loan.loan_amount = safe_float(request.form.get("amount"))

        if hasattr(loan, "status"):
            loan.status = request.form.get("status")
        if hasattr(loan, "loan_type"):
            loan.loan_type = request.form.get("loan_type")
        if hasattr(loan, "property_address"):
            loan.property_address = request.form.get("property_address")
        if hasattr(loan, "interest_rate"):
            loan.interest_rate = safe_float(request.form.get("interest_rate"))
        if hasattr(loan, "term"):
            loan.term = request.form.get("term")
        if hasattr(loan, "property_value"):
            loan.property_value = safe_float(request.form.get("property_value"))
        if hasattr(loan, "description"):
            loan.description = request.form.get("description")

        db.session.commit()
        flash("✅ Capital request updated successfully!", "success")
        return redirect(url_for("investor.loan_view", loan_id=loan.id))

    return render_template(
        "investor/edit_loan.html",
        loan=loan,
        investor=ip,
        title="Edit Loan"
    )


# =========================================================
# 💰 INVESTOR • QUOTES + CONVERSION
# =========================================================

@investor_bp.route("/capital/quote", methods=["GET", "POST"])
@investor_bp.route("/quote", methods=["GET", "POST"])
@login_required
@role_required("investor")
def quote():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        flash("Please complete your investor profile before requesting a quote.", "warning")
        return redirect(url_for("investor.create_profile"))

    assistant = AIAssistant()

    if request.method == "POST":
        loan_amount = safe_float(request.form.get("loan_amount"))
        property_value = safe_float(request.form.get("property_value"))
        property_address = request.form.get("property_address", "")
        property_type = request.form.get("property_type", "")
        loan_type = request.form.get("loan_type", "Conventional")
        loan_category = request.form.get("loan_category", "Purchase")
        term_months = int(request.form.get("term_months", 360))
        fico_score = int(request.form.get("fico_score", 700))
        experience = request.form.get("experience", "New Investor")

        ltv = (loan_amount / property_value * 100) if property_value else 0

        try:
            prompt = (
                f"Generate up to 3 competitive loan quotes for an investor requesting "
                f"${loan_amount:,.0f} on a property valued at ${property_value:,.0f} "
                f"({ltv:.1f}% LTV). Loan type: {loan_type}, category: {loan_category}, "
                f"credit score {fico_score}, experience: {experience}. "
                f"Suggest lenders, estimated rates, and short commentary."
            )
            ai_suggestion = assistant.generate_reply(prompt, "investor_quote")
        except Exception:
            ai_suggestion = "⚠️ AI system unavailable. Displaying mock results."

        mock_lenders = [
            {"lender_name": "Lima One Capital", "rate": 6.20, "loan_type": "30-Year Fixed", "deal_type": "Conventional"},
            {"lender_name": "RCN Capital", "rate": 6.05, "loan_type": "FHA 30-Year", "deal_type": "Residential"},
            {"lender_name": "LendingOne", "rate": 5.90, "loan_type": "5/1 ARM", "deal_type": "Hybrid"},
        ]

        quote_fk = _profile_id_filter(LoanQuote, ip.id)

        created_quotes = []
        for lender in mock_lenders:
            quote_row = LoanQuote(
                **quote_fk,
                lender_name=lender["lender_name"],
                rate=lender["rate"],
                loan_type=lender["loan_type"],
                deal_type=lender["deal_type"],
                max_ltv=ltv,
                term_months=term_months,
                loan_amount=loan_amount,
                property_address=property_address,
                property_type=property_type,
                purchase_price=property_value,
                fico_score=fico_score,
                loan_category=loan_category,
                experience=experience,
                ai_suggestion=ai_suggestion,
                response_json=None,
                status="pending",
            )
            db.session.add(quote_row)
            created_quotes.append(quote_row)

        db.session.commit()
        flash("✅ Loan quotes generated successfully!", "success")

        return render_template(
            "investor/quote_results.html",
            investor=ip,
            quotes=created_quotes,
            property_address=property_address,
            property_value=property_value,
            loan_amount=loan_amount,
            fico_score=fico_score,
            ltv=ltv,
            ai_response=ai_suggestion,
            title="Loan Quote Results",
        )

    return render_template("investor/quote.html", investor=ip, title="Get a Loan Quote")


@investor_bp.route("/capital/quote/convert/<int:quote_id>", methods=["POST"])
@investor_bp.route("/quote/convert/<int:quote_id>", methods=["POST"])
@login_required
@role_required("investor")
def convert_quote_to_application(quote_id):
    quote = LoanQuote.query.get_or_404(quote_id)
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        flash("Please complete your investor profile before applying.", "warning")
        return redirect(url_for("investor.create_profile"))

    # Ensure quote belongs to current investor (supports both schemas)
    quote_owner_ok = False
    if hasattr(quote, "investor_profile_id") and quote.investor_profile_id == ip.id:
        quote_owner_ok = True
    if hasattr(quote, "borrower_profile_id") and quote.borrower_profile_id == ip.id:
        quote_owner_ok = True

    if not quote_owner_ok:
        return "Unauthorized", 403

    # Prevent duplicate conversion
    app_fk = _profile_id_filter(LoanApplication, ip.id)
    existing_app = LoanApplication.query.filter_by(
        **app_fk,
        loan_amount=quote.loan_amount,
        property_address=quote.property_address,
    ).first()

    if existing_app:
        flash("This quote has already been converted.", "info")
        return redirect(url_for("investor.status"))

    new_app = LoanApplication(
        **app_fk,
        loan_amount=quote.loan_amount,
        property_address=quote.property_address,
        loan_type=quote.loan_type,
        status="submitted",
        created_at=datetime.utcnow(),
        is_active=True
    )
    db.session.add(new_app)
    db.session.flush()

    quote.loan_application_id = new_app.id
    quote.status = "converted"
    db.session.add(quote)

    # Activity log (switch to InvestorActivity if you have it)
    activity_model = InvestorActivity if "InvestorActivity" in globals() else BorrowerActivity
    activity_fk = _profile_id_filter(activity_model, ip.id)

    db.session.add(activity_model(
        **activity_fk,
        category="Capital Conversion",
        description=f"Converted quote #{quote.id} into capital request #{new_app.id}.",
        timestamp=datetime.utcnow(),
    ))

    msg = (
        f"📢 Investor {ip.full_name} converted quote #{quote.id} into "
        f"Capital Request #{new_app.id} for {quote.property_address or 'a new property'}."
    )

    db.session.add(Message(
        sender_id=current_user.id,
        receiver_id=getattr(quote, "assigned_officer_id", None),
        content=msg,
        created_at=datetime.utcnow(),
        system_generated=True,
    ))

    db.session.commit()

    try:
        notify_team_on_conversion(ip, quote, new_app)
    except Exception as e:
        print("Notification error:", e)

    flash("🎯 Quote converted and team notified!", "success")
    return redirect(url_for("investor.status"))


@investor_bp.route("/ai/quote", methods=["POST"])
@investor_bp.route("/get_quote_ai", methods=["POST"])
@login_required
@role_required("investor")
def get_quote_ai():
    ai = CMAIEngine()
    data = request.json or {}

    msg = f"""
    Investor is requesting a loan quote.

    Loan Amount: {data.get('amount')}
    Property Value: {data.get('value')}
    Credit Score: {data.get('credit')}
    Purpose: {data.get('purpose')}
    Notes: {data.get('notes','')}
    """

    # If your engine uses generate_reply instead, swap here.
    ai_reply = (
        getattr(ai, "generate", None)(msg, role="investor")
        if getattr(ai, "generate", None)
        else ai.generate_reply(msg, role="investor")
    )

    return jsonify({"quote": ai_reply})

# =========================================================
# 📁 INVESTOR • DOCUMENTS + REQUESTS
# =========================================================

@investor_bp.route("/documents", methods=["GET"])
@login_required
@role_required("investor")
def documents():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    docs = LoanDocument.query.filter_by(**_profile_id_filter(LoanDocument, ip.id)).all() if ip else []

    assistant = AIAssistant()
    try:
        ai_summary = assistant.generate_reply(
            f"Summarize the investor’s {len(docs)} uploaded documents and highlight missing items.",
            "investor_documents"
        )
    except Exception:
        ai_summary = "⚠️ AI summary unavailable."

    return render_template(
        "investor/documents.html",
        investor=ip,
        documents=docs,
        ai_summary=ai_summary,
        title="Documents",
        active_tab="documents"
    )


@investor_bp.route("/document_requests", methods=["GET"])
@login_required
@role_required("investor")
def document_requests():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        return redirect(url_for("investor.create_profile"))

    # Document requests: supports DocumentRequest.borrower_id OR .investor_id
    req_fk = _profile_id_filter(DocumentRequest, ip.id)
    doc_requests = DocumentRequest.query.filter_by(**req_fk).all() if req_fk else []

    # Conditions tied to active request (supports ip.active_loan_id or ip.active_capital_id)
    active_loan_id = getattr(ip, "active_loan_id", None) or getattr(ip, "active_capital_id", None)

    cond_fk = _profile_id_filter(UnderwritingCondition, ip.id)
    conditions = UnderwritingCondition.query.filter_by(
        **cond_fk,
        loan_id=active_loan_id
    ).all() if (cond_fk and active_loan_id) else []

    unified = []
    for req in doc_requests:
        unified.append({
            "id": req.id,
            "type": "request",
            "document_name": getattr(req, "document_name", None),
            "requested_by": getattr(req, "requested_by", None),
            "notes": getattr(req, "notes", None),
            "status": getattr(req, "status", None),
            "file_path": getattr(req, "file_path", None),
        })

    for cond in conditions:
        unified.append({
            "id": cond.id,
            "type": "condition",
            "document_name": getattr(cond, "description", None),
            "requested_by": getattr(cond, "requested_by", None) or "Processor",
            "notes": getattr(cond, "notes", None),
            "status": getattr(cond, "status", None),
            "file_path": getattr(cond, "file_path", None),
        })

    assistant = AIAssistant()
    try:
        ai_summary = assistant.generate_reply(
            f"List {len(unified)} outstanding document requests/conditions for investor {ip.full_name}.",
            "investor_document_requests",
        )
    except Exception:
        ai_summary = "⚠️ AI summary unavailable."

    return render_template(
        "investor/document_requests.html",
        investor=ip,
        requests=unified,
        ai_summary=ai_summary,
        title="Document Requests",
        active_tab="documents"
    )


@investor_bp.route("/upload_document", methods=["GET", "POST"])
@login_required
@role_required("investor")
def upload_document():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    if request.method == "POST":
        file = request.files.get("file")
        document_type = request.form.get("doc_type")

        if file and ip:
            filename = secure_filename(file.filename)
            save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
            file.save(save_path)

            doc_fk = _profile_id_filter(LoanDocument, ip.id)

            db.session.add(LoanDocument(
                **doc_fk,
                file_path=filename,
                document_type=document_type,
                status="uploaded"
            ))
            db.session.commit()
            return redirect(url_for("investor.documents"))

    return render_template(
        "investor/upload_docs.html",
        investor=ip,
        title="Upload Document",
        active_tab="documents"
    )


@investor_bp.route("/upload_request", methods=["GET", "POST"])
@login_required
@role_required("investor")
def upload_request():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        return redirect(url_for("investor.create_profile"))

    item_id = request.values.get("item_id") or request.values.get("document_id")
    item_type = request.values.get("type") or request.values.get("item_type") or "request"

    item = None
    if item_id:
        item = DocumentRequest.query.get(item_id) if item_type == "request" else UnderwritingCondition.query.get(item_id)

    if not item:
        flash("Requested item not found.", "warning")
        return redirect(url_for("investor.document_requests"))

    # Basic ownership check for request/condition
    if item_type == "request" and item:
        ok = False
        if hasattr(item, "investor_id") and item.investor_id == ip.id:
            ok = True
        if hasattr(item, "borrower_id") and item.borrower_id == ip.id:
            ok = True
        if not ok:
            return "Unauthorized", 403

    if item_type == "condition" and item:
        ok = False
        if hasattr(item, "investor_profile_id") and item.investor_profile_id == ip.id:
            ok = True
        if hasattr(item, "borrower_profile_id") and item.borrower_profile_id == ip.id:
            ok = True
        if not ok:
            return "Unauthorized", 403

    if request.method == "POST":
        file = request.files.get("file")
        if file and ip and item:
            filename = secure_filename(file.filename)
            save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
            file.save(save_path)

            doc_fk = _profile_id_filter(LoanDocument, ip.id)

            db.session.add(LoanDocument(
                **doc_fk,
                file_path=filename,
                doc_type=getattr(item, "description", None) or getattr(item, "document_name", "Document"),
                status="submitted",
                request_id=item.id if item_type == "request" else None,
                condition_id=item.id if item_type == "condition" else None
            ))

            item.status = "submitted"
            db.session.commit()
            return redirect(url_for("investor.document_requests"))

    return render_template(
        "investor/upload_request.html",
        investor=ip,
        request_item=item,
        item_type=item_type,
        title="Upload Document",
        active_tab="documents"
    )


@investor_bp.route("/delete_document/<int:doc_id>", methods=["POST"])
@login_required
@role_required("investor")
def delete_document(doc_id):
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    doc = LoanDocument.query.get_or_404(doc_id)

    # Ownership check (supports both schemas)
    owns = False
    if ip:
        if hasattr(doc, "investor_profile_id") and doc.investor_profile_id == ip.id:
            owns = True
        if hasattr(doc, "borrower_profile_id") and doc.borrower_profile_id == ip.id:
            owns = True

    if not ip or not owns:
        return "Unauthorized", 403

    try:
        os.remove(os.path.join(current_app.config["UPLOAD_FOLDER"], doc.file_path))
    except Exception:
        pass

    db.session.delete(doc)
    db.session.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True, "status": "ok"})
    return redirect(url_for("investor.documents"))

@investor_bp.route("/documents/download/<int:doc_id>", methods=["GET"])
@login_required
def download_document(doc_id):
    doc = LoanDocument.query.filter_by(
        id=doc_id,
        user_id=current_user.id
    ).first()

    if not doc:
        abort(404)

    file_path = doc.file_path
    if file_path and not os.path.isabs(file_path):
        file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], file_path)

    if not file_path or not os.path.exists(file_path):
        abort(404)

    return send_file(
        file_path,
        as_attachment=True,
        download_name=os.path.basename(file_path)
    )


@investor_bp.route("/documents/view/<int:doc_id>", methods=["GET"])
@login_required
def view_document(doc_id):
    doc = LoanDocument.query.filter_by(
        id=doc_id,
        user_id=current_user.id
    ).first()

    if not doc:
        abort(404)

    file_path = doc.file_path
    if file_path and not os.path.isabs(file_path):
        file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], file_path)

    if not file_path or not os.path.exists(file_path):
        abort(404)

    return send_file(
        file_path,
        as_attachment=False,
        download_name=os.path.basename(file_path)
    )

@investor_bp.route("/documents/download-all/<int:deal_id>", methods=["GET"])
@login_required
def download_all_documents(deal_id):
    deal = Deal.query.filter_by(
        id=deal_id,
        user_id=current_user.id
    ).first_or_404()

    documents = LoanDocument.query.filter_by(
        deal_id=deal.id,
        user_id=current_user.id
    ).all()

    memory_file = BytesIO()

    with zipfile.ZipFile(memory_file, "w") as zf:
        for doc in documents:
            if doc.file_path and os.path.exists(doc.file_path):
                zf.write(doc.file_path, arcname=os.path.basename(doc.file_path))

    memory_file.seek(0)

    return send_file(
        memory_file,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"deal_{deal.id}_documents.zip"
    )
# =========================================================
# ✅ INVESTOR • CONDITIONS (capital requirements)
# =========================================================

@investor_bp.route("/capital/conditions", methods=["GET"])
@investor_bp.route("/conditions", methods=["GET"])
@login_required
@role_required("investor")
def conditions():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    loan = None
    if ip:
        loan_fk = _profile_id_filter(LoanApplication, ip.id)
        loan = LoanApplication.query.filter_by(**loan_fk, is_active=True).first() if loan_fk else None

    conds = []
    if loan and ip:
        cond_fk = _profile_id_filter(UnderwritingCondition, ip.id)
        conds = UnderwritingCondition.query.filter_by(**cond_fk, loan_id=loan.id).all() if cond_fk else []

    assistant = AIAssistant()
    try:
        ai_summary = assistant.generate_reply(
            f"Summarize {len(conds)} underwriting conditions and highlight what's still required.",
            "investor_conditions"
        )
    except Exception:
        ai_summary = "⚠️ AI summary unavailable."

    return render_template(
        "investor/conditions.html",
        investor=ip,
        loan=loan,
        conditions=conds,
        ai_summary=ai_summary,
        title="Conditions",
        active_tab="conditions"
    )


@investor_bp.route("/capital/conditions/<int:cond_id>", methods=["GET"])
@investor_bp.route("/condition/<int:cond_id>", methods=["GET"])
@login_required
@role_required("investor")
def view_condition(cond_id):
    cond = UnderwritingCondition.query.get_or_404(cond_id)
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    # Ownership check (supports both schemas)
    ok = False
    if ip:
        if hasattr(cond, "investor_profile_id") and cond.investor_profile_id == ip.id:
            ok = True
        if hasattr(cond, "borrower_profile_id") and cond.borrower_profile_id == ip.id:
            ok = True
    if not ip or not ok:
        return "Unauthorized", 403

    return render_template(
        "investor/condition_view.html",
        condition=cond,
        investor=ip,
        title="Condition Detail",
        active_tab="conditions"
    )


@investor_bp.route("/capital/conditions/<int:cond_id>/history", methods=["GET"])
@investor_bp.route("/condition/<int:cond_id>/history", methods=["GET"])
@login_required
@role_required("investor")
def condition_history(cond_id):
    cond = UnderwritingCondition.query.get_or_404(cond_id)
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    ok = False
    if ip:
        if hasattr(cond, "investor_profile_id") and cond.investor_profile_id == ip.id:
            ok = True
        if hasattr(cond, "borrower_profile_id") and cond.borrower_profile_id == ip.id:
            ok = True
    if not ip or not ok:
        return "Unauthorized", 403

    history = []
    if getattr(cond, "created_at", None):
        history.append({"timestamp": cond.created_at, "text": "Condition created"})
    if getattr(cond, "file_path", None):
        history.append({"timestamp": getattr(cond, "updated_at", None) or cond.created_at, "text": "Document uploaded"})
    if (getattr(cond, "status", "") or "").lower() == "submitted":
        history.append({"timestamp": getattr(cond, "updated_at", None) or cond.created_at, "text": "Document submitted"})
    if (getattr(cond, "status", "") or "").lower() == "cleared":
        history.append({"timestamp": getattr(cond, "updated_at", None) or cond.created_at, "text": "Condition cleared"})

    history = [h for h in history if h.get("timestamp")]
    history.sort(key=lambda x: x["timestamp"], reverse=True)

    return render_template(
        "investor/condition_history.html",
        investor=ip,
        condition=cond,
        history=history,
        title="Condition History",
        active_tab="conditions"
    )


@investor_bp.route("/conditions/ai/<int:condition_id>", methods=["GET"])
@login_required
@role_required("investor")
def investor_condition_ai(condition_id):
    cond = UnderwritingCondition.query.get_or_404(condition_id)

    ai_msg = master_ai.ask(
        f"""
        Explain this underwriting condition to an investor in simple terms:

        Condition: {getattr(cond, 'condition_type', None)}
        Description: {cond.description}
        Severity: {getattr(cond, 'severity', None)}
        """,
        role="underwriter",
    )
    return {"reply": ai_msg}


@investor_bp.route("/conditions/upload/<int:cond_id>", methods=["POST"])
@login_required
@role_required("investor")
def upload_condition(cond_id):
    cond = UnderwritingCondition.query.get_or_404(cond_id)
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    ok = False
    if ip:
        if hasattr(cond, "investor_profile_id") and cond.investor_profile_id == ip.id:
            ok = True
        if hasattr(cond, "borrower_profile_id") and cond.borrower_profile_id == ip.id:
            ok = True
    if not ip or not ok:
        return "Unauthorized", 403

    file = request.files.get("file")
    if not file:
        return "No file uploaded", 400

    filename = secure_filename(file.filename)
    filename = f"condition_{cond.id}_{uuid.uuid4().hex[:8]}_{filename}"
    filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    cond.status = "submitted"
    cond.file_path = filename
    db.session.commit()

    return redirect(url_for("investor.conditions"))

# =========================================================
# 🧠 INVESTOR • PROPERTY INTELLIGENCE (search/saved/tool/apis)
# =========================================================

@investor_bp.route("/intelligence", methods=["GET"])
@investor_bp.route("/property_search", methods=["GET"])
@login_required
@role_required("investor")
def property_search():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    query = (request.args.get("query") or "").strip()

    property_data = None
    valuation = {}
    rent_estimate = {}
    comps = {}
    market_snapshot = {}
    ai_summary = None
    error = None
    debug = None
    saved_id = None
    primary_photo = None
    photos = []

    if query:
        resolved = resolve_property_unified(query)

        if resolved.get("status") == "ok":
            raw_prop = resolved.get("property") or {}

            # Pull already-normalized bundle if your unified resolver now returns it
            property_data = raw_prop
            valuation = resolved.get("valuation") or raw_prop.get("valuation") or {}
            rent_estimate = resolved.get("rent_estimate") or raw_prop.get("rent_estimate") or raw_prop.get("rentEstimate") or {}
            comps = resolved.get("comps") or raw_prop.get("comps") or {}
            market_snapshot = resolved.get("market_snapshot") or raw_prop.get("market_snapshot") or {}
            ai_summary = resolved.get("ai_summary") or resolved.get("summary") or None

            photos = property_data.get("photos") or []
            primary_photo = property_data.get("primary_photo")

            if ip and property_data.get("address"):
                try:
                    existing = SavedProperty.query.filter(
                        getattr(SavedProperty, "investor_profile_id", SavedProperty.borrower_profile_id) == ip.id,
                        db.func.lower(SavedProperty.address) == property_data["address"].lower()
                    ).first()
                    if existing:
                        saved_id = existing.id
                except Exception:
                    saved_id = None

        else:
            error = resolved.get("error") or "unknown_error"
            debug = {
                "provider": resolved.get("provider"),
                "stage": resolved.get("stage")
            }

    return render_template(
        "investor/property_search.html",
        investor=ip,
        title="Property Search",
        active_page="property_search",
        query=query,
        error=error,
        debug=debug,
        property=property_data,
        valuation=valuation,
        rent_estimate=rent_estimate,
        comps=comps,
        market_snapshot=market_snapshot,
        ai_summary=ai_summary,
        saved_id=saved_id,
        photos=photos,
        primary_photo=primary_photo,
    )

@investor_bp.route("/intelligence/save", methods=["POST"])
@investor_bp.route("/save_property", methods=["POST"])
@login_required
@role_required("investor")
def save_property():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        return jsonify({"status": "error", "message": "Profile not found."}), 400

    raw_property_id = (request.form.get("property_id") or "").strip()
    raw_address = (request.form.get("address") or "").strip()
    raw_price = request.form.get("price")
    raw_zipcode = (request.form.get("zipcode") or "").strip() or None
    sqft_raw = request.form.get("sqft")

    if not raw_address:
        return jsonify({"status": "error", "message": "Address required."}), 400

    sqft = None
    try:
        if sqft_raw not in (None, "", "None"):
            sqft = int(float(sqft_raw))
    except Exception:
        sqft = None

    resolved = {}
    try:
        resolved = resolve_property_unified(raw_address)
    except Exception as e:
        print("SAVE_PROPERTY resolver error:", e)
        resolved = {}

    normalized_address = raw_address
    resolved_property_id = None

    if resolved.get("status") == "ok":
        p = resolved.get("property") or {}
        normalized_address = (p.get("address") or raw_address).strip()
        resolved_property_id = (p.get("property_id") or p.get("id") or p.get("propertyId"))
        resolved_property_id = str(resolved_property_id).strip() if resolved_property_id else None
        raw_zipcode = raw_zipcode or p.get("zip") or p.get("zipCode") or p.get("postalCode")
        if sqft is None:
            try:
                sqft_val = p.get("sqft") or p.get("squareFootage")
                sqft = int(float(sqft_val)) if sqft_val not in (None, "", "None") else None
            except Exception:
                sqft = None

    final_property_id = raw_property_id or resolved_property_id or None

    existing = None
    fk = _profile_id_filter(SavedProperty, ip.id)

    if final_property_id:
        existing = SavedProperty.query.filter_by(
            **fk,
            property_id=str(final_property_id)
        ).first()

    if not existing and normalized_address:
        existing = SavedProperty.query.filter(
            getattr(SavedProperty, "investor_profile_id", SavedProperty.borrower_profile_id) == ip.id,
            db.func.lower(SavedProperty.address) == normalized_address.lower()
        ).first()

    if existing:
        if not existing.address and normalized_address:
            existing.address = normalized_address
        if (not getattr(existing, "zipcode", None)) and raw_zipcode:
            existing.zipcode = raw_zipcode
        if (getattr(existing, "sqft", None) is None or getattr(existing, "sqft", 0) == 0) and sqft:
            existing.sqft = sqft
        if (not getattr(existing, "price", None)) and raw_price is not None:
            existing.price = str(raw_price)
        if (not getattr(existing, "property_id", None)) and final_property_id:
            existing.property_id = str(final_property_id)

        if resolved:
            _store_saved_property_media(existing, resolved, source="unified_resolver")

        db.session.commit()
        return jsonify({"status": "success", "message": "Already saved (updated details).", "saved_id": existing.id})

    saved = SavedProperty(
        **fk,
        property_id=str(final_property_id) if final_property_id else None,
        address=normalized_address,
        price=str(raw_price or ""),
        sqft=sqft,
        zipcode=raw_zipcode,
        saved_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )

    db.session.add(saved)
    db.session.flush()

    if resolved:
        _store_saved_property_media(saved, resolved, source="unified_resolver")

    db.session.commit()

    return jsonify({"status": "success", "message": "Saved.", "saved_id": saved.id})


@investor_bp.route("/intelligence/saved", methods=["GET"])
@investor_bp.route("/saved_properties", methods=["GET"])
@login_required
@role_required("investor")
def saved_properties():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    props = SavedProperty.query.filter_by(**_profile_id_filter(SavedProperty, ip.id)).all() if ip else []

    try:
        name = ip.full_name if ip else "this investor"
        ai_summary = AIAssistant().generate_reply(
            f"Summarize {len(props)} saved properties for {name}. Prioritize investment potential.",
            "investor_saved_properties",
        )
    except Exception:
        ai_summary = "⚠️ AI summary unavailable."

    return render_template(
        "investor/saved_properties.html",
        investor=ip,
        properties=props,
        ai_summary=ai_summary,
        title="Saved Properties",
        active_tab="property_search"
    )


@investor_bp.route("/intelligence/saved/manage", methods=["POST"])
@investor_bp.route("/saved_properties/manage", methods=["POST"])
@login_required
@role_required("investor")
def saved_properties_manage():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        flash("Profile not found.", "danger")
        return redirect(url_for("investor.saved_properties"))

    prop_id = request.form.get("prop_id")
    action = request.form.get("action")
    notes = request.form.get("notes", "")

    try:
        prop_id = int(prop_id)
    except Exception:
        flash("Invalid property id.", "warning")
        return redirect(url_for("investor.saved_properties"))

    prop = SavedProperty.query.filter_by(id=prop_id, **_profile_id_filter(SavedProperty, ip.id)).first()
    if not prop:
        flash("Saved property not found.", "warning")
        return redirect(url_for("investor.saved_properties"))

    if action == "edit":
        if hasattr(prop, "notes"):
            prop.notes = notes
            db.session.commit()
            flash("✅ Notes saved.", "success")
        else:
            flash("Notes column not added yet.", "info")

    elif action == "delete":
        db.session.delete(prop)
        db.session.commit()
        flash("🗑️ Saved property deleted.", "success")

    return redirect(url_for("investor.saved_properties"))


@investor_bp.route("/intelligence/save-and-analyze", methods=["POST"])
@investor_bp.route("/save_property_and_analyze", methods=["POST"])
@login_required
@role_required("investor")
def save_property_and_analyze():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        flash("Profile not found.", "danger")
        return redirect(url_for("investor.property_search"))

    raw_address = (request.form.get("address") or "").strip()
    if not raw_address:
        flash("Address required.", "warning")
        return redirect(url_for("investor.property_search"))

    zipcode = (request.form.get("zipcode") or "").strip() or None
    price = request.form.get("price")
    sqft_raw = request.form.get("sqft")

    sqft = None
    try:
        sqft = int(float(sqft_raw)) if sqft_raw not in (None, "", "None") else None
    except Exception:
        sqft = None

    resolved = {}
    normalized_address = raw_address
    resolved_property_id = None

    try:
        resolved = resolve_property_unified(raw_address)
    except Exception as e:
        print("SAVE_PROPERTY_AND_ANALYZE resolver error:", e)
        resolved = {}

    if resolved.get("status") == "ok":
        p = resolved.get("property") or {}
        normalized_address = (p.get("address") or raw_address).strip()

        resolved_property_id = (p.get("property_id") or p.get("id") or p.get("propertyId"))
        resolved_property_id = str(resolved_property_id).strip() if resolved_property_id else None

        zipcode = zipcode or p.get("zip") or p.get("zipCode") or p.get("postalCode")

        if sqft is None:
            try:
                sqft_val = p.get("sqft") or p.get("squareFootage")
                sqft = int(float(sqft_val)) if sqft_val not in (None, "", "None") else None
            except Exception:
                sqft = None

        if (price in (None, "", "None")) and (p.get("price") is not None):
            try:
                price = str(p.get("price"))
            except Exception:
                pass

    form_pid = (request.form.get("property_id") or "").strip()
    final_property_id = form_pid or resolved_property_id or None
    final_property_id = str(final_property_id).strip() if final_property_id else None

    fk = _profile_id_filter(SavedProperty, ip.id)

    existing = None
    if final_property_id:
        existing = SavedProperty.query.filter_by(**fk, property_id=final_property_id).first()

    if not existing and normalized_address:
        existing = SavedProperty.query.filter(
            getattr(SavedProperty, "investor_profile_id", SavedProperty.borrower_profile_id) == ip.id,
            db.func.lower(SavedProperty.address) == normalized_address.lower()
        ).first()

    if existing:
        flash("✅ Property already saved — opening Deal Studio.", "info")
        return redirect(url_for("investor.deal_workspace", prop_id=existing.id, mode="flip"))

    saved = SavedProperty(
        **fk,
        property_id=final_property_id,
        address=normalized_address,
        price=str(price or ""),
        sqft=sqft,
        zipcode=zipcode,
        saved_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )
    db.session.add(saved)
    db.session.commit()

    flash("🏠 Property saved! Opening Deal Studio…", "success")
    return redirect(url_for("investor.deal_workspace", prop_id=saved.id, mode="flip"))


        
@investor_bp.route("/intelligence/saved/<int:prop_id>", methods=["GET"])
@investor_bp.route("/property_explore_plus/<int:prop_id>", methods=["GET"])
@login_required
@role_required("investor")
def property_explore_plus(prop_id):
    source = request.args.get("source", "property_tool")
    fallback_endpoint = "investor.property_search" if source == "property_search" else "investor.property_tool"

    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        flash("Profile not found.", "danger")
        return redirect(url_for(fallback_endpoint))

    prop = SavedProperty.query.filter_by(
        id=prop_id,
        **_profile_id_filter(SavedProperty, ip.id)
    ).first()

    if not prop:
        flash("Property not found.", "danger")
        return redirect(url_for(fallback_endpoint))

    resolved = resolve_property_unified(prop.address)

    if resolved.get("status") != "ok":
        current_app.logger.warning(
            "Property explore fallback for prop_id=%s address=%s: %s",
            prop_id,
            prop.address,
            resolved.get("error") or resolved.get("stage") or "unknown_error",
        )
        resolved = {
            "status": "partial",
            "property": {
                "address": prop.address,
                "address_line1": prop.address,
                "city": getattr(prop, "city", None),
                "state": getattr(prop, "state", None),
                "zip_code": getattr(prop, "zipcode", None),
                "zip": getattr(prop, "zipcode", None),
                "property_id": prop.property_id,
                "price": None,
                "beds": getattr(prop, "bedrooms", None),
                "baths": getattr(prop, "bathrooms", None),
                "sqft": prop.sqft,
                "square_feet": prop.sqft,
                "property_type": getattr(prop, "property_type", None),
                "photos": [],
                "primary_photo": None,
                "status": "Saved Property",
                "days_on_market": None,
                "description": None,
            },
            "valuation": {
                "estimate": None,
                "market_value": None,
                "assessed_value": None,
                "last_sale_price": None,
            },
            "rent_estimate": {
                "rent": None,
                "traditional_rent": None,
                "estimated_rent": None,
            },
            "comps": {"sales": [], "rentals": [], "meta": {}},
            "market_snapshot": {},
            "ai_summary": "Live property enrichment is temporarily unavailable. You can still review the saved property and send it to Deal Workspace.",
        }
        flash("Live property intelligence is temporarily unavailable. Showing saved property details instead.", "warning")

    resolved_property = resolved.get("property") or {}
    valuation = resolved.get("valuation") or {}
    rent_estimate = resolved.get("rent_estimate") or {}
    comps = resolved.get("comps") or {}
    market_snapshot = resolved.get("market_snapshot") or {}
    ai_summary = resolved.get("ai_summary") or resolved.get("summary") or None

    photos = resolved_property.get("photos") or []
    primary_photo = (
        resolved_property.get("primary_photo")
        or (photos[0] if photos else None)
    )

    address = (
        resolved_property.get("address")
        or prop.address
    )

    city = (
        resolved_property.get("city")
        or getattr(prop, "city", None)
    )

    state = (
        resolved_property.get("state")
        or getattr(prop, "state", None)
    )

    zip_code = (
        resolved_property.get("zip")
        or resolved_property.get("zip_code")
        or getattr(prop, "zipcode", None)
    )

    property_type = resolved_property.get("property_type")
    beds = resolved_property.get("beds")
    baths = resolved_property.get("baths")

    sqft = (
        resolved_property.get("sqft")
        or resolved_property.get("square_feet")
        or prop.sqft
    )

    year_built = resolved_property.get("year_built")
    lot_size_sqft = (
        resolved_property.get("lot_size_sqft")
        or resolved_property.get("lot_sqft")
        or resolved_property.get("lot_size")
    )

    latitude = resolved_property.get("latitude")
    longitude = resolved_property.get("longitude")

    price = (
        valuation.get("price")
        or valuation.get("value")
        or valuation.get("estimated_value")
        or valuation.get("last_sale_price")
    )

    if price in (None, "", "None"):
        try:
            price = float(prop.price) if getattr(prop, "price", None) not in (None, "", "None") else None
        except Exception:
            price = None

    assessed_value = (
        valuation.get("assessed_value")
        or resolved_property.get("assessed_value")
    )

    property_id = (
        resolved_property.get("property_id")
        or resolved_property.get("attom_id")
        or prop.property_id
    )

    photo = primary_photo

    return render_template(
        "investor/property_explore_plus.html",
        investor=ip,
        prop=prop,

        # flat template fields
        address=address,
        city=city,
        state=state,
        zip_code=zip_code,
        property_type=property_type,
        beds=beds,
        baths=baths,
        sqft=sqft,
        year_built=year_built,
        lot_size_sqft=lot_size_sqft,
        price=price,
        assessed_value=assessed_value,
        latitude=latitude,
        longitude=longitude,
        photo=photo,
        property_id=property_id,

        # keep these available in case you still want them later
        resolved=resolved_property,
        valuation=valuation,
        rent_estimate=rent_estimate,
        ai_summary=ai_summary,
        comps=comps,
        market=market_snapshot,
        photos=photos,
        primary_photo=primary_photo,

        active_page="property_search" if source == "property_search" else "property_tool",
        source=source,
        back_url=url_for(fallback_endpoint),
    )
    
  


# ----------------------------
# pages
# ----------------------------

@investor_bp.route("/property_tool", methods=["GET"])
@login_required
@role_required("investor")
def property_tool():
    return render_template("investor/property_tool.html")


@investor_bp.route("/project-studio", methods=["GET"])
@login_required
@role_required("investor")
def project_studio():
    address = (request.args.get("address") or "").strip()
    city = (request.args.get("city") or "").strip()
    state = (request.args.get("state") or "").strip()
    zip_code = (request.args.get("zip") or request.args.get("zip_code") or "").strip()

    deal_id = request.args.get("deal_id", type=int)
    selected_strategy = (request.args.get("strategy") or "").strip().lower()
    selected_scope = (request.args.get("scope") or "").strip().lower()

    snapshot = None
    flags = []
    strategy_cards = []
    ai_summary = None
    engine_error = None
    market_snapshot = {}
    selected_card = None
    scope_options = []
    scope_budget = None
    workspace_deal = None

    mashvisor_data = None
    mashvisor_insight = None

    if address:
        try:
            studio_context = _project_studio_lookup(
                address=address,
                city=city,
                state=state,
                zip_code=zip_code,
            )

            snapshot = studio_context.get("snapshot")
            flags = studio_context.get("flags") or []
            strategy_cards = studio_context.get("strategy_cards") or []
            ai_summary = studio_context.get("ai_summary")
            engine_error = studio_context.get("engine_error")
            market_snapshot = studio_context.get("market_snapshot") or {}

            if strategy_cards:
                valid_keys = {
                    str(card.get("key") or "").lower()
                    for card in strategy_cards
                }

                if selected_strategy not in valid_keys:
                    selected_strategy = str(
                        (strategy_cards[0].get("key") or "")
                    ).lower()

                selected_card = next(
                    (
                        card for card in strategy_cards
                        if str(card.get("key") or "").lower() == selected_strategy
                    ),
                    None
                )

                scope_options = _project_studio_scope_options(selected_strategy)
                valid_scopes = {
                    str(opt.get("value") or "").lower()
                    for opt in scope_options
                }

                if selected_scope not in valid_scopes and scope_options:
                    selected_scope = str(
                        scope_options[0].get("value") or ""
                    ).lower()

                scope_budget = _project_studio_scope_budget(
                    selected_card,
                    selected_strategy,
                    selected_scope,
                )

                if selected_card and selected_scope and scope_budget:
                    ip = InvestorProfile.query.filter_by(
                        user_id=current_user.id
                    ).first()

                    workspace_deal = _project_studio_upsert_deal(
                        ip,
                        snapshot,
                        selected_card,
                        selected_strategy,
                        selected_scope,
                        scope_budget,
                        strategy_cards=strategy_cards,
                        flags=flags,
                        ai_summary=ai_summary,
                        market_snapshot=market_snapshot,
                        deal_id=deal_id,
                    )

                    # Final validation layer:
                    # only after property + strategy + scope exist
                    mashvisor_data = _run_mashvisor_validation(snapshot)
                    mashvisor_insight = _build_mashvisor_insight(
                        scope_budget,
                        mashvisor_data,
                    )

        except Exception as exc:
            engine_error = str(exc)
            current_app.logger.warning(
                "project_studio lookup failed for %s: %s",
                address,
                exc,
            )

    return render_template(
        "investor/project_studio.html",
        title="Investor OS • Project Studio",
        active_tab="project_studio",
        address=address,
        city=city,
        state=state,
        zip_code=zip_code,
        snapshot=snapshot,
        flags=flags,
        strategy_cards=strategy_cards,
        ai_summary=ai_summary,
        engine_error=engine_error,
        market_snapshot=market_snapshot,
        selected_strategy=selected_strategy,
        selected_card=selected_card,
        selected_scope=selected_scope,
        scope_options=scope_options,
        scope_budget=scope_budget,
        workspace_deal=workspace_deal,
        mashvisor=mashvisor_data,
        mashvisor_insight=mashvisor_insight,
    )

# -------------------------------------------------------------------
# PROXY ROUTE FOR UI
# -------------------------------------------------------------------

@investor_bp.route("/api/deal-architect-proxy", methods=["POST"])
@login_required
@role_required("investor")
def api_deal_architect_proxy():
    payload = request.get_json(force=True) or {}

    try:
        data = _call_deal_architect(payload)
        return jsonify(data), 200
    except Exception as e:
        current_app.logger.exception("Deal Architect proxy failed")
        return jsonify({
            "ok": False,
            "message": f"Deal Architect proxy failed: {e}",
        }), 500


# -------------------------------------------------------------------
# UPDATED PROPERTY TOOL SEARCH
# -------------------------------------------------------------------



            



def _clean_str(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _clean_num(value):
    if value in (None, "", "None"):
        return None
    try:
        if isinstance(value, str):
            value = value.replace("$", "").replace(",", "").strip()
        return float(value)
    except Exception:
        return None


def _clean_int(value):
    num = _clean_num(value)
    if num is None:
        return None
    try:
        return int(round(num))
    except Exception:
        return None


def _safe_json_list(value):
    if isinstance(value, list):
        return value
    return []


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

    price = _clean_num(payload.get("price") or payload.get("purchase_price") or payload.get("display_value"))
    arv = _clean_num(payload.get("arv") or payload.get("estimated_value_engine") or payload.get("market_value"))
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

    if address:
        saved.address = address

    if property_id:
        _assign_if_has_attr(saved, "property_id", property_id)

    # keep your existing core fields in sync
    if price is not None:
        _assign_if_has_attr(saved, "price", str(int(price)) if float(price).is_integer() else str(price))

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

    _assign_if_has_attr(saved, "image_url", image_url)
    _assign_if_has_attr(saved, "description", description)

    # optional JSON/meta fields if your model supports them
    _assign_if_has_attr(saved, "primary_strengths", _safe_json_list(payload.get("primary_strengths")))
    _assign_if_has_attr(saved, "primary_risks", _safe_json_list(payload.get("primary_risks")))
    _assign_if_has_attr(saved, "risk_notes", _safe_json_list(payload.get("risk_notes")))
    _assign_if_has_attr(saved, "why_it_made_list", _safe_json_list(payload.get("why_it_made_list")))

    # status / timestamps if present on model
    _assign_if_has_attr(saved, "analysis_status", "pending")
    _assign_if_has_attr(saved, "budget_status", "pending")
    _assign_if_has_attr(saved, "last_synced_at", datetime.utcnow())
    _assign_if_has_attr(saved, "updated_at", datetime.utcnow())


def _upsert_saved_property_from_payload(ip, payload):
    address = _clean_str(payload.get("address"))
    if not address:
        raise ValueError("Address is required.")

    price = payload.get("price") or payload.get("purchase_price") or payload.get("display_value")
    sqft = _clean_int(payload.get("sqft") or payload.get("square_feet"))
    zipcode = _clean_str(payload.get("zip") or payload.get("zip_code"))
    property_id = _clean_str(payload.get("property_id") or payload.get("attom_id"))

    existing = _find_existing_saved_property(ip, payload)
    fk = _profile_id_filter(SavedProperty, ip.id)

    if not existing:
        existing = SavedProperty(
            **fk,
            property_id=property_id if property_id else None,
            address=address,
            price=str(price or ""),
            sqft=sqft,
            zipcode=zipcode,
            saved_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
        db.session.add(existing)
        db.session.flush()

    _persist_property_core_fields(existing, payload)
    _store_saved_property_media(existing, payload, source="property_tool")
    return existing


@investor_bp.route("/api/property_tool_search", methods=["POST"])
@login_required
@role_required("investor")
def api_property_tool_search():
    payload = request.get_json(force=True) or {}

    address = (payload.get("address") or "").strip()
    zip_code = (payload.get("zip") or "").strip()
    city = (payload.get("city") or "").strip()
    state = (payload.get("state") or "").strip()
    strategy = (payload.get("strategy") or "flip").strip().lower()

    if not address and not zip_code:
        return jsonify({
            "status": "error",
            "message": "Address or ZIP code is required.",
            "results": [],
        }), 400

    page_size = min(int(payload.get("limit") or 20), 20)
    enrich_limit = min(page_size, 8)
    top_pick_limit = 4

    try:
        search_result = get_property_search_result(
            address=address or None,
            postalcode=zip_code or None,
            city=city or None,
            state=state or None,
            page=1,
            page_size=page_size,
        )

        raw_matches = search_result.get("properties", []) or []
        results = []

        for idx, raw in enumerate(raw_matches[:page_size]):
            raw_address = (
                raw.get("address_line1")
                or raw.get("address")
                or raw.get("address_one_line")
                or ""
            ).strip()

            raw_city = (raw.get("city") or city or "").strip()
            raw_state = (raw.get("state") or state or "").strip()
            raw_zip = (raw.get("zip_code") or zip_code or "").strip()
            raw_property_type = (raw.get("property_type") or "single_family")

            if not raw_address:
                continue

            if idx < enrich_limit and raw_city and raw_state:
                bundle = build_dealfinder_profile(
                    address=raw_address,
                    city=raw_city,
                    state=raw_state,
                    zip_code=raw_zip,
                    property_type=raw_property_type,
                )

                if bundle.get("ok"):
                    result = _build_property_tool_result(raw, bundle)
                else:
                    result = _build_attom_fallback(raw)
            else:
                result = _build_attom_fallback(raw)

            if idx < enrich_limit:
                try:
                    engine_payload = {
                        "project_name": raw_address,
                        "description": f"{raw_address}, {raw_city}, {raw_state}",
                        "property_type": result.get("property_type"),
                        "asking_price": result.get("last_sale_price") or result.get("price"),
                        "square_feet_target": result.get("square_feet"),
                        "city": raw_city,
                        "state": raw_state,
                        "zip_code": raw_zip,
                        "arv": result.get("market_value"),
                        "monthly_rent": result.get("traditional_rent"),
                        "local_facts": {
                            "bedrooms": result.get("beds"),
                            "bathrooms": result.get("baths"),
                            "year_built": result.get("year_built"),
                            "lot_sqft": result.get("lot_size_sqft"),
                            "assessed_value": result.get("assessed_value"),
                            "annual_tax_amount": result.get("tax_amount"),
                            "latitude": result.get("latitude"),
                            "longitude": result.get("longitude"),
                        }
                    }

                    engine_resp = requests.post(
                        current_app.config["RENOVATION_ENGINE_URL"].rstrip("/") + "/v1/deal_architect",
                        json=engine_payload,
                        headers={"X-API-Key": current_app.config["RENOVATION_ENGINE_API_KEY"]},
                        timeout=12
                    )

                    if engine_resp.ok:
                        engine = engine_resp.json()
                        meta = engine.get("meta", {}) or {}

                        result.update({
                            "deal_score": engine.get("deal_score"),
                            "opportunity_tier": engine.get("opportunity_tier"),
                            "deal_finder_signal": meta.get("deal_finder_signal"),
                            "primary_strengths": meta.get("primary_strengths", []),
                            "primary_risks": meta.get("primary_risks", []),
                            "dscr_estimate": meta.get("dscr_estimate"),
                            "rent_yield": meta.get("rent_yield"),
                            "monthly_rent_estimate": meta.get("monthly_rent_estimate"),
                            "next_step": engine.get("next_step"),
                            "engine_value": engine.get("estimated_value"),
                            "estimated_value_engine": engine.get("estimated_value"),
                            "valuation_source_label": meta.get("valuation_source_label"),
                            "comp_confidence": meta.get("comp_confidence"),
                        })
                    else:
                        result["engine_error"] = "Deal Architect failed"
                except Exception as e:
                    result["engine_error"] = str(e)

            results.append(_annotate_deal_finder_opportunity(result, strategy))

        results = sorted(
            results,
            key=lambda r: (r.get("deal_score") is not None, r.get("deal_score") or 0),
            reverse=True,
        )

        top_results = results[:top_pick_limit]
        engine_ready = any(r.get("deal_score") is not None for r in top_results)

        return jsonify({
            "status": "ok",
            "results": top_results,
            "count": len(top_results),
            "total_matches": len(results),
            "strategy": strategy,
            "zip": zip_code,
            "address": address,
            "engine_ready": engine_ready,
        })

    except Exception as e:
        current_app.logger.exception("Property Tool search failed")
        return jsonify({
            "status": "error",
            "message": str(e),
            "results": [],
        }), 500


@investor_bp.route("/api/property_detail", methods=["POST"])
@login_required
@role_required("investor")
def api_property_detail():
    payload = request.get_json(force=True) or {}
    address = (payload.get("address") or "").strip()

    if not address:
        return jsonify({
            "status": "error",
            "message": "Address is required.",
        }), 400

    result = resolve_property_unified(address=address)

    if result.get("status") != "ok":
        return jsonify({
            "status": "error",
            "message": result.get("error") or "Lookup failed.",
            "stage": result.get("stage"),
            "source": result.get("source"),
        }), 400

    property_data = result.get("property") or {}
    valuation = result.get("valuation") or {}
    rent_estimate = result.get("rent_estimate") or {}

    engine = None
    engine_error = None

    try:
        detail_for_engine = {
            "address": property_data.get("address") or address,
            "city": property_data.get("city"),
            "state": property_data.get("state"),
            "zip_code": property_data.get("zip_code"),
            "beds": property_data.get("beds"),
            "baths": property_data.get("baths"),
            "square_feet": property_data.get("square_feet") or property_data.get("sqft"),
            "lot_size_sqft": property_data.get("lot_size_sqft"),
            "year_built": property_data.get("year_built"),
            "property_type": property_data.get("property_type"),
            "assessed_value": valuation.get("assessed_value"),
            "market_value": valuation.get("market_value"),
            "last_sale_price": valuation.get("last_sale_price"),
            "traditional_rent": rent_estimate.get("traditional_rent"),
            "tax_amount": valuation.get("tax_amount"),
            "latitude": property_data.get("latitude"),
            "longitude": property_data.get("longitude"),
        }
        engine_payload = _build_deal_architect_payload(detail_for_engine, strategy="all")
        engine = _call_deal_architect(engine_payload)
    except Exception as e:
        current_app.logger.warning("property_detail engine enrichment failed: %s", e)
        engine_error = str(e)

    return jsonify({
        "status": "ok",
        "source": result.get("source"),
        "property": property_data,
        "valuation": valuation,
        "rent_estimate": rent_estimate,
        "comps": result.get("comps"),
        "market_snapshot": result.get("market_snapshot"),
        "ai_summary": result.get("ai_summary"),
        "raw": result.get("raw"),
        "engine": engine,
        "engine_error": engine_error,
    })


@investor_bp.route("/api/intelligence/save", methods=["POST"])
@investor_bp.route("/api/intelligence/save", methods=["POST"])
@investor_bp.route("/api/property_tool_save", methods=["POST"])
@login_required
@role_required("investor")
def api_property_tool_save():
    payload = request.get_json(force=True) or {}
    address = (payload.get("address") or "").strip()

    if not address:
        return jsonify({
            "status": "error",
            "message": "Address is required to save."
        }), 400

    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        return jsonify({
            "status": "error",
            "message": "Profile not found."
        }), 400

    try:
        saved = _upsert_saved_property_from_payload(ip, payload)

        uploaded_photos = _try_upload_and_attach_listing_photos(
            payload=payload,
            saved_property=saved,
            deal=None,
        )

        db.session.commit()

        return jsonify({
            "status": "ok",
            "message": "Saved.",
            "saved_id": saved.id,
            "listing_photos_count": len(uploaded_photos),
            "primary_photo_url": uploaded_photos[0]["url"] if uploaded_photos else getattr(saved, "image_url", None),
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Property Tool save failed")
        return jsonify({
            "status": "error",
            "message": f"Could not save property: {e}"
        }), 500


@investor_bp.route("/api/intelligence/save-and-analyze", methods=["POST"])
@investor_bp.route("/api/property_tool_save_and_analyze", methods=["POST"])
@login_required
@role_required("investor")
def api_property_tool_save_and_analyze():
    payload = request.get_json(force=True) or {}
    address = (payload.get("address") or "").strip()

    if not address:
        return jsonify({
            "status": "error",
            "message": "Address is required to analyze."
        }), 400

    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        return jsonify({
            "status": "error",
            "message": "Profile not found."
        }), 400

    def to_float(val):
        try:
            if val in (None, "", "None"):
                return 0.0
            if isinstance(val, str):
                val = val.replace("$", "").replace(",", "").strip()
            return float(val)
        except (TypeError, ValueError):
            return 0.0

    try:
        # 1) Upsert saved property
        saved = _upsert_saved_property_from_payload(ip, payload)

        # 2) Find or create linked deal
        deal = (
            Deal.query
            .filter_by(user_id=current_user.id, saved_property_id=saved.id)
            .order_by(Deal.updated_at.desc(), Deal.id.desc())
            .first()
        )

        strategy = (payload.get("strategy") or "flip").strip().lower()
        if strategy not in ("flip", "rental", "airbnb"):
            strategy = "flip"

        title = (
            payload.get("title")
            or payload.get("address")
            or f"Deal {saved.id}"
        )

        purchase_price = to_float(
            payload.get("purchase_price")
            or payload.get("price")
            or payload.get("display_value")
            or payload.get("last_sale_price")
        )

        arv = to_float(
            payload.get("arv")
            or payload.get("estimated_value_engine")
            or payload.get("market_value")
            or payload.get("engine_value")
        )

        estimated_rent = to_float(
            payload.get("estimated_rent")
            or payload.get("monthly_rent")
            or payload.get("monthly_rent_estimate")
        )

        raw_score = payload.get("deal_score")
        try:
            deal_score = int(round(float(raw_score))) if raw_score not in (None, "", "None") else None
        except (TypeError, ValueError):
            deal_score = None

        results_json = {
            "strategy_analysis": {},
            "rehab_analysis": {},
            "workspace_analysis": {
                "address": payload.get("address"),
                "city": payload.get("city"),
                "state": payload.get("state"),
                "zip_code": payload.get("zip") or payload.get("zip_code"),
                "purchase_price": purchase_price,
                "arv": arv,
                "estimated_rent": estimated_rent,
                "square_feet": payload.get("sqft") or payload.get("square_feet"),
                "beds": payload.get("beds"),
                "baths": payload.get("baths"),
                "year_built": payload.get("year_built"),
                "property_type": payload.get("property_type"),
                "strategy": strategy,
                "strategy_tag": payload.get("strategy_tag"),
                "recommended_strategy": payload.get("recommended_strategy"),
                "estimated_best_use": payload.get("estimated_best_use"),
                "deal_score": deal_score,
                "opportunity_tier": payload.get("opportunity_tier"),
                "deal_finder_signal": payload.get("deal_finder_signal"),
                "next_step": payload.get("next_step"),
                "comp_confidence": payload.get("comp_confidence"),
                "primary_strengths": payload.get("primary_strengths") or [],
                "primary_risks": payload.get("primary_risks") or [],
                "risk_notes": payload.get("risk_notes") or [],
                "why_it_made_list": payload.get("why_it_made_list") or [],
            },
            "optimization": {},
        }

        notes_parts = []

        if payload.get("estimated_best_use"):
            notes_parts.append(f"Best Use: {payload.get('estimated_best_use')}")
        if payload.get("next_step"):
            notes_parts.append(f"Next Step: {payload.get('next_step')}")

        primary_strengths = payload.get("primary_strengths") or []
        if primary_strengths:
            notes_parts.append("Strengths: " + ", ".join(str(x) for x in primary_strengths))

        primary_risks = payload.get("primary_risks") or []
        if primary_risks:
            notes_parts.append("Risks: " + ", ".join(str(x) for x in primary_risks))

        notes = "\n".join(notes_parts).strip() or None

        if deal:
            deal.investor_profile_id = ip.id
            deal.saved_property_id = saved.id
            deal.property_id = payload.get("property_id") or payload.get("attom_id")
            deal.title = title
            deal.address = payload.get("address")
            deal.city = payload.get("city")
            deal.state = payload.get("state")
            deal.zip_code = payload.get("zip") or payload.get("zip_code")
            deal.strategy = strategy
            deal.recommended_strategy = payload.get("recommended_strategy") or strategy
            deal.purchase_price = purchase_price
            deal.arv = arv
            deal.estimated_rent = estimated_rent
            deal.deal_score = deal_score
            deal.inputs_json = {
                "address": payload.get("address"),
                "city": payload.get("city"),
                "state": payload.get("state"),
                "zip_code": payload.get("zip") or payload.get("zip_code"),
                "strategy": strategy,
                "purchase_price": purchase_price,
                "arv": arv,
                "estimated_rent": estimated_rent,
            }
            deal.results_json = results_json
            deal.notes = notes
            deal.status = deal.status or "active"
            deal.updated_at = datetime.utcnow()
        else:
            deal = Deal(
                user_id=current_user.id,
                investor_profile_id=ip.id,
                saved_property_id=saved.id,
                property_id=payload.get("property_id") or payload.get("attom_id"),
                title=title,
                address=payload.get("address"),
                city=payload.get("city"),
                state=payload.get("state"),
                zip_code=payload.get("zip") or payload.get("zip_code"),
                strategy=strategy,
                recommended_strategy=payload.get("recommended_strategy") or strategy,
                purchase_price=purchase_price,
                arv=arv,
                estimated_rent=estimated_rent,
                rehab_cost=0,
                deal_score=deal_score,
                inputs_json={
                    "address": payload.get("address"),
                    "city": payload.get("city"),
                    "state": payload.get("state"),
                    "zip_code": payload.get("zip") or payload.get("zip_code"),
                    "strategy": strategy,
                    "purchase_price": purchase_price,
                    "arv": arv,
                    "estimated_rent": estimated_rent,
                },
                results_json=results_json,
                notes=notes,
                status="active",
            )
            db.session.add(deal)
            db.session.flush()

        # 3) Best-effort upload to DO Spaces and attach URLs
        uploaded_photos = _try_upload_and_attach_listing_photos(
            payload=payload,
            saved_property=saved,
            deal=deal,
        )

        db.session.commit()

        deal_url = url_for(
            "investor.deal_workspace",
            deal_id=deal.id,
            mode=strategy
        )

        return jsonify({
            "status": "ok",
            "saved_id": saved.id,
            "deal_id": deal.id,
            "deal_url": deal_url,
            "listing_photos_count": len(uploaded_photos),
            "primary_photo_url": uploaded_photos[0]["url"] if uploaded_photos else None,
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Property Tool save-and-analyze failed")
        return jsonify({
            "status": "error",
            "message": f"Could not create deal: {e}"
        }), 500
        
            


@investor_bp.route("/api/intelligence/card", methods=["POST"])
@investor_bp.route("/api/property_tool_card", methods=["POST"])
@login_required
@role_required("investor")
def api_property_tool_card():
    payload = request.get_json(force=True) or {}

    address = (payload.get("address") or "").strip()
    city = (payload.get("city") or "").strip()
    state = (payload.get("state") or "").strip()
    zip_code = (payload.get("zip") or payload.get("zip_code") or "").strip()
    property_type = (payload.get("property_type") or "single_family").strip()

    if not address:
        return jsonify({
            "status": "error",
            "message": "Address is required."
        }), 400

    try:
        bundle = build_dealfinder_profile(
            address=address,
            city=city,
            state=state,
            zip_code=zip_code,
            property_type=property_type,
        )

        if not bundle.get("ok"):
            return jsonify({
                "status": "error",
                "message": "; ".join(bundle.get("errors") or ["Unable to load property card."])
            }), 400

        card = _build_property_tool_result(payload, bundle)

        return jsonify({
            "status": "ok",
            "property": bundle.get("profile") or {},
            "scoring": bundle.get("scoring") or {},
            "source_status": bundle.get("source_status") or {},
            "errors": bundle.get("errors") or [],
            "card": card,
        })

    except Exception as e:
        current_app.logger.exception("Property Tool card failed")
        return jsonify({
            "status": "error",
            "message": f"Unable to load property card: {e}"
        }), 500


@investor_bp.route("/api/property_tool_view_details", methods=["POST"])
@login_required
@role_required("investor")
def api_property_tool_view_details():
    payload = request.get_json(force=True) or {}
    address = (payload.get("address") or "").strip()

    if not address:
        return jsonify({
            "status": "error",
            "message": "Address is required."
        }), 400

    ip, error = _get_investor_profile_or_error()
    if error:
        return error

    try:
        saved = _upsert_saved_property_from_payload(ip, payload)
        db.session.commit()

        detail_url = url_for(
            "investor.property_explore_plus",
            prop_id=saved.id,
            source="property_tool"
        )

        return jsonify({
            "status": "ok",
            "saved_id": saved.id,
            "detail_url": detail_url
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Property Tool detail handoff failed")
        return jsonify({
            "status": "error",
            "message": f"Could not open property details: {e}"
        }), 500






         
# =========================================================
# 💼 INVESTOR • DEAL STUDIO (workspace + deals + visualizer + exports)
# =========================================================

@investor_bp.route("/deal-studio", methods=["GET"])
@login_required
@role_required("investor")
def deal_studio():
    return redirect(url_for("investor.project_studio"))

    """
    Deal Studio is the investor workspace where users can:

    • Find deals
    • Analyze opportunities
    • Plan rehabs
    • Design new builds
    • Prepare deals for funding
    """

    tools = [
        {
            "name": "Deal Finder",
            "description": "Search properties by ZIP, strategy, or market signals.",
            "icon": "search",
            "endpoint": "investor.property_tool"
        },
        {
            "name": "AI Deal Architect",
            "description": "Generate strategy insights, risk scoring, and execution guidance.",
            "icon": "brain-circuit",
            "endpoint": "investor.deal_architect"
        },

        # 🔵 NEW — BUDGET STUDIO
        {
            "name": "Budget Studio",
            "description": "Build renovation budgets, define scope, and pressure-test deal assumptions.",
            "icon": "calculator",
            "endpoint": "investor.budget_studio"
        },

        # 🟠 FIXED — REHAB STUDIO
        {
            "name": "Rehab Studio",
            "description": "Visualize before-and-after transformations and bring your renovation vision to life.",
            "icon": "image",
            "endpoint": "investor.deals_list"
        },

        {
            "name": "Build Studio",
            "description": "Design ground-up development scenarios and construction plans.",
            "icon": "home",
            "endpoint": "investor.build_studio"
        },
        {
            "name": "Deal Copilot",
            "description": "AI assistant for deal analysis, structuring, and funding preparation.",
            "icon": "bot",
            "endpoint": "investor.ask_ai_page"  # (adjust if different)
        }
    ]

    return render_template(
        "investor/deal_studio.html",
        user=current_user,
        tools=tools,
        page_title="Deal Studio",
        page_subtitle="Analyze opportunities, design projects, and prepare deals for funding."
    )

@investor_bp.route("/deals/workspace", methods=["GET"])
@investor_bp.route("/deal_workspace", methods=["GET"])
@investor_bp.route("/deal_workspace/<int:deal_id>", methods=["GET"])
@login_required
@role_required("investor")
def deal_workspace(deal_id=None):
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        flash("Profile not found.", "danger")
        return redirect(url_for("investor.command_center"))

    saved_props = (
        SavedProperty.query
        .filter_by(**_profile_id_filter(SavedProperty, ip.id))
        .order_by(SavedProperty.created_at.desc())
        .all()
    )

    selected_prop = None
    deal = None
    budget = None

    comps = {}
    resolved = None
    comparison = {}
    recommendation = {}
    ai_summary = None

    workspace_analysis = {}
    strategy_analysis = {}
    rehab_analysis = {}
    optimization = {}

    mode = (request.args.get("mode") or "flip").lower()
    if mode not in ("flip", "rental", "airbnb"):
        mode = "flip"

    # -----------------------------------------
    # 1) Load by route param deal_id
    # -----------------------------------------
    if deal_id:
        deal = (
            Deal.query
            .filter_by(id=deal_id, user_id=current_user.id)
            .first_or_404()
        )

        if getattr(deal, "saved_property_id", None):
            selected_prop = (
                SavedProperty.query
                .filter_by(
                    id=deal.saved_property_id,
                    **_profile_id_filter(SavedProperty, ip.id)
                )
                .first()
            )

    # -----------------------------------------
    # 2) Fallback: querystring deal_id
    # -----------------------------------------
    if not deal:
        query_deal_id = request.args.get("deal_id", type=int)
        if query_deal_id:
            deal = (
                Deal.query
                .filter_by(id=query_deal_id, user_id=current_user.id)
                .first()
            )

            if deal and getattr(deal, "saved_property_id", None):
                selected_prop = (
                    SavedProperty.query
                    .filter_by(
                        id=deal.saved_property_id,
                        **_profile_id_filter(SavedProperty, ip.id)
                    )
                    .first()
                )

    # -----------------------------------------
    # 3) Fallback: property selection by prop_id
    # -----------------------------------------
    if not selected_prop:
        prop_id = request.args.get("prop_id", type=int)
        if prop_id:
            selected_prop = (
                SavedProperty.query
                .filter_by(
                    id=prop_id,
                    **_profile_id_filter(SavedProperty, ip.id)
                )
                .first()
            )

            if selected_prop and not deal:
                deal = (
                    Deal.query
                    .filter_by(
                        user_id=current_user.id,
                        saved_property_id=selected_prop.id
                    )
                    .order_by(Deal.updated_at.desc(), Deal.id.desc())
                    .first()
                )

    # -----------------------------------------
    # 4) If deal exists but prop not loaded, try FK
    # -----------------------------------------
    if deal and not selected_prop and getattr(deal, "saved_property_id", None):
        selected_prop = (
            SavedProperty.query
            .filter_by(
                id=deal.saved_property_id,
                **_profile_id_filter(SavedProperty, ip.id)
            )
            .first()
        )

    # -----------------------------------------
    # 5) Load real linked budget for this deal
    # -----------------------------------------
    if deal:
        budget = (
            ProjectBudget.query
            .filter_by(
                deal_id=deal.id,
                investor_profile_id=ip.id
            )
            .order_by(ProjectBudget.id.desc())
            .first()
        )
    loan_sizing = None

    if deal:
        loan_sizing = _build_loan_sizing_from_budget(deal, budget)

    # -----------------------------------------
    # 6) Load comps / property intelligence
    # -----------------------------------------
    if selected_prop:
        try:
            comps = get_saved_property_comps(
                user_id=current_user.id,
                saved_property_id=selected_prop.id,
                rentometer_api_key=None,
            ) or {}
        except Exception as e:
            current_app.logger.warning("Workspace comps error: %s", e)
            comps = {}

        if comps:
            try:
                from LoanMVP.services.unified_property_resolver import resolve_property_intelligence
                resolved = resolve_property_intelligence(selected_prop.id, comps)
            except Exception as e:
                current_app.logger.warning("Resolver error: %s", e)
                resolved = None

            try:
                from LoanMVP.services.deal_workspace_calcs import (
                    calculate_flip_budget,
                    calculate_rental_budget,
                    calculate_airbnb_budget,
                    recommend_strategy,
                )

                empty_form = ImmutableMultiDict()

                comparison = {
                    "flip": calculate_flip_budget(empty_form, comps),
                    "rental": calculate_rental_budget(empty_form, comps),
                    "airbnb": calculate_airbnb_budget(empty_form, comps),
                }

                recommendation = recommend_strategy(comparison) or {}
            except Exception as e:
                current_app.logger.warning("Workspace calculation error: %s", e)
                comparison = {}
                recommendation = {}

    # -----------------------------------------
    # 7) Load saved deal results
    # -----------------------------------------
    if deal:
        results_json = deal.results_json or {}
        strategy_analysis = results_json.get("strategy_analysis", {}) or {}
        rehab_analysis = results_json.get("rehab_analysis", {}) or {}
        workspace_analysis = results_json.get("workspace_analysis", {}) or {}
        optimization = results_json.get("optimization", {}) or {}

    # -----------------------------------------
    # 8) AI summary
    # -----------------------------------------
    try:
        if comparison:
            selected_metrics = comparison.get(mode) or comparison.get("flip") or {}
            ai_summary = generate_ai_deal_summary(selected_metrics)
    except Exception as e:
        current_app.logger.warning("AI summary error: %s", e)
        ai_summary = None

    return render_template(
        "investor/deal_workspace.html",
        investor=ip,
        saved_props=saved_props,
        selected_prop=selected_prop,
        prop_id=(selected_prop.id if selected_prop else None),
        property_id=(selected_prop.id if selected_prop else None),
        deal=deal,
        deal_id=(deal.id if deal else None),
        budget=budget,
        loan_sizing=loan_sizing,
        mode=mode,
        comps=comps,
        resolved=resolved,
        comparison=comparison,
        recommendation=recommendation,
        ai_summary=ai_summary,
        strategy_analysis=strategy_analysis,
        rehab_analysis=rehab_analysis,
        workspace_analysis=workspace_analysis,
        optimization=optimization,
        active_page="deal_workspace",
    )

@investor_bp.route("/deals", methods=["GET"])
@investor_bp.route("/deals/list", methods=["GET"])
@login_required
@role_required("investor")
def deals_list():
    status = request.args.get("status", "active")
    q = request.args.get("q", "").strip()

    query = Deal.query.filter_by(user_id=current_user.id)
    if status in ("active", "archived"):
        query = query.filter_by(status=status)

    if q:
        like = f"%{q}%"
        query = query.filter(
            (Deal.title.ilike(like)) |
            (Deal.property_id.ilike(like)) |
            (Deal.strategy.ilike(like))
        )

    deals = query.order_by(Deal.updated_at.desc()).all()
    return render_template("investor/deals_list.html", deals=deals, status=status, q=q)


@investor_bp.route("/deals/<int:deal_id>", methods=["GET"])
@login_required
@role_required("investor")
def deal_detail(deal_id):

    deal = Deal.query.get_or_404(deal_id)

    if deal.user_id != current_user.id:
        abort(403)

    mockups = (
        RenovationMockup.query
        .filter_by(deal_id=deal_id, user_id=current_user.id)
        .order_by(RenovationMockup.created_at.desc())
        .all()
    )

    partners = (
        Partner.query
        .filter_by(user_id=current_user.id)
        .order_by(Partner.created_at.desc())
        .all()
    )

    results = deal.results_json or {}
    strategy_analysis = results.get("strategy_analysis", {})
    rehab_analysis = results.get("rehab_analysis", {})

    return render_template(
        "investor/deal_detail.html",
        deal=deal,
        mockups=mockups,
        partners=partners,
        strategy_analysis=strategy_analysis,
        rehab_analysis=rehab_analysis
    )

@investor_bp.route("/deal-comparison", methods=["GET"])
@login_required
@role_required("investor")
def deal_comparison():
    deals = (
        Deal.query
        .filter_by(user_id=current_user.id)
        .order_by(Deal.created_at.desc())
        .all()
    )
    return render_template("investor/deal_comparison.html", deals=deals)

@investor_bp.route("/deal-comparison/run", methods=["POST"])
@login_required
@role_required("investor")
def run_deal_comparison():
    data = request.get_json(silent=True) or request.form
    deal_ids = data.get("deal_ids", [])

    if not deal_ids:
        return jsonify({"error": "Please select at least one deal."}), 400

    deals = (
        Deal.query
        .filter(Deal.id.in_(deal_ids), Deal.user_id == current_user.id)
        .all()
    )

    if not deals:
        return jsonify({"error": "No deals found."}), 404

    comparison = []
    best_profit_deal = None
    best_roi_deal = None
    best_rental_deal = None
    best_score_deal = None

    for deal in deals:
        total_cost = (deal.purchase_price or 0) + (deal.rehab_cost or 0)
        projected_profit = (deal.arv or 0) - total_cost
        projected_roi = round((projected_profit / total_cost) * 100, 2) if total_cost > 0 else 0

        item = {
            "id": deal.id,
            "title": deal.title or deal.address or f"Deal {deal.id}",
            "address": deal.address,
            "purchase_price": deal.purchase_price or 0,
            "arv": deal.arv or 0,
            "rehab_cost": deal.rehab_cost or 0,
            "estimated_rent": deal.estimated_rent or 0,
            "total_cost": total_cost,
            "projected_profit": projected_profit,
            "projected_roi": projected_roi,
            "recommended_strategy": deal.recommended_strategy or deal.strategy,
            "deal_score": deal.deal_score or 0,
        }
        comparison.append(item)

    if comparison:
        best_profit_deal = max(comparison, key=lambda x: x["projected_profit"])
        best_roi_deal = max(comparison, key=lambda x: x["projected_roi"])
        best_score_deal = max(comparison, key=lambda x: x["deal_score"])
        rental_candidates = [d for d in comparison if d["estimated_rent"] > 0]
        if rental_candidates:
            best_rental_deal = max(rental_candidates, key=lambda x: x["estimated_rent"])

    summary = {
        "best_profit_deal": best_profit_deal,
        "best_roi_deal": best_roi_deal,
        "best_score_deal": best_score_deal,
        "best_rental_deal": best_rental_deal,
    }

    return jsonify({
        "success": True,
        "comparison": comparison,
        "summary": summary
    })
    
@investor_bp.route("/deals/<int:deal_id>/dealbook", methods=["GET"])
@login_required
@role_required("investor")
def deal_book(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first_or_404()

    results = deal.results_json or {}
    comps = deal.comps_json or {}
    resolved = deal.resolved_json or {}

    rehab = (resolved.get("rehab") or {})
    featured = rehab.get("featured") or {}

    # Optional convenience pulls
    prop = (resolved.get("property") or {})
    address = prop.get("address") or deal.title or f"Deal #{deal.id}"
    
    saved_property_id=deal.saved_property_id
   
    mockups = RenovationMockup.query.filter_by(
        deal_id=deal_id,
        user_id=current_user.id
    ).order_by(RenovationMockup.created_at.desc()).all()

   
    return render_template(
        "investor/deal_book.html",
        deal=deal,
        results=results,
        comps=comps,
        resolved=resolved,
        rehab=rehab,
        mockups=mockups,
        featured=featured,
        address=address,
    )

# =========================================================
# DEAL CRUD
# =========================================================
@investor_bp.route("/deals/cards")
@login_required
def deals_cards():
    deals = (
        Deal.query
        .filter_by(user_id=current_user.id)
        .order_by(Deal.created_at.desc())
        .all()
    )

    return render_template(
        "investor/deals.html",
        deals=deals
    )
    
@investor_bp.route("/deals/create", methods=["GET", "POST"])
@login_required
@role_required("investor")
def create_deal():
    investor_profile = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        address = (request.form.get("address") or "").strip()
        city = (request.form.get("city") or "").strip()
        state = (request.form.get("state") or "").strip()
        zip_code = (request.form.get("zip_code") or "").strip()
        strategy = (request.form.get("strategy") or "flip").strip().lower()

        purchase_price = float(request.form.get("purchase_price") or 0)
        arv = float(request.form.get("arv") or 0)
        estimated_rent = float(request.form.get("estimated_rent") or 0)
        rehab_cost = float(request.form.get("rehab_cost") or 0)

        notes = (request.form.get("notes") or "").strip()

        if not title and not address:
            flash("Please add at least a deal title or property address.", "error")
            return redirect(url_for("investor.create_deal"))

        deal = Deal(
            user_id=current_user.id,
            investor_profile_id=investor_profile.id if investor_profile else None,
            title=title or address or "Untitled Deal",
            address=address or None,
            city=city or None,
            state=state or None,
            zip_code=zip_code or None,
            strategy=strategy,
            purchase_price=purchase_price,
            arv=arv,
            estimated_rent=estimated_rent,
            rehab_cost=rehab_cost,
            notes=notes,
            status="active",
            inputs_json={
                "title": title,
                "address": address,
                "city": city,
                "state": state,
                "zip_code": zip_code,
                "strategy": strategy,
                "purchase_price": purchase_price,
                "arv": arv,
                "estimated_rent": estimated_rent,
                "rehab_cost": rehab_cost,
                "notes": notes,
            },
        )

        db.session.add(deal)
        db.session.commit()

        flash("Deal created successfully.", "success")
        return redirect(url_for("investor.deal_detail", deal_id=deal.id))

    return render_template("investor/create_deal.html")
    
@investor_bp.route("/deals/save", methods=["POST"])
@investor_bp.route("/deals/save_deal", methods=["POST"])
@login_required
@role_required("investor")
def save_deal():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        flash("Investor profile not found.", "danger")
        return redirect(url_for("investor.command_center"))

    property_id = request.form.get("property_id") or None
    strategy = request.form.get("mode") or request.form.get("strategy") or None
    title = request.form.get("title") or None
    saved_property_id = _normalize_int(request.form.get("saved_property_id"))
    deal_id = _normalize_int(request.form.get("deal_id"))

    results_json = _safe_json_loads_local(request.form.get("results_json"), default={})
    inputs_json = _safe_json_loads_local(request.form.get("inputs_json"), default={})
    comps_json = _safe_json_loads_local(request.form.get("comps_json"), default={})
    resolved_json = _safe_json_loads_local(request.form.get("resolved_json"), default={})

    prop = (resolved_json or {}).get("property") or {}
    comp_prop = (comps_json or {}).get("property") or {}

    address = prop.get("address") or title
    city = prop.get("city")
    state = prop.get("state")
    zip_code = prop.get("zip") or prop.get("zipCode") or prop.get("postalCode")

    purchase_price = (
        inputs_json.get("purchase_price")
        or comp_prop.get("price")
        or prop.get("price")
        or 0
    )

    rehab_cost = (
        (results_json.get("rehab_total") if isinstance(results_json, dict) else 0)
        or 0
    )

    arv = (
        comp_prop.get("arv_estimate")
        or ((prop.get("valuation") or {}).get("value") if isinstance(prop.get("valuation"), dict) else None)
        or 0
    )

    estimated_rent = (
        comp_prop.get("market_rent_estimate")
        or ((prop.get("rent_estimate") or {}).get("value") if isinstance(prop.get("rent_estimate"), dict) else None)
        or 0
    )

    recommended_strategy = strategy
    rehab_scope_json = None
    deal_score = None

    if isinstance(results_json, dict):
        rehab_scope_json = results_json.get("rehab_summary") or None
        raw_score = results_json.get("deal_score")
        try:
            deal_score = int(round(float(raw_score))) if raw_score not in (None, "", "None") else None
        except (TypeError, ValueError):
            deal_score = None

    notes_parts = []

    if isinstance(results_json, dict):
        rehab_summary = results_json.get("rehab_summary") or {}
        risk_flags = results_json.get("risk_flags") or []
        rehab_notes = results_json.get("rehab_notes") or {}

        if rehab_summary:
            notes_parts.append(f"Rehab Scope: {rehab_summary.get('scope') or 'N/A'}")
            if rehab_summary.get("total") is not None:
                try:
                    notes_parts.append(f"Estimated Rehab Total: ${float(rehab_summary.get('total')):,.0f}")
                except (TypeError, ValueError):
                    notes_parts.append("Estimated Rehab Total: N/A")

        if risk_flags:
            notes_parts.append("Risk Flags: " + ", ".join(str(x) for x in risk_flags))

        if rehab_notes:
            for k, v in rehab_notes.items():
                notes_parts.append(f"{str(k).replace('_', ' ').title()}: {v}")

    notes = "\n".join(notes_parts).strip() or None

    if not title:
        title = address or (property_id and f"Deal {property_id}") or "Saved Deal"

    def to_float(val):
        try:
            return float(val)
        except (TypeError, ValueError):
            return 0.0

    purchase_price = to_float(purchase_price)
    rehab_cost = to_float(rehab_cost)
    arv = to_float(arv)
    estimated_rent = to_float(estimated_rent)

    deal = None
    if deal_id:
        deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first()

    if deal:
        deal.investor_profile_id = ip.id
        deal.saved_property_id = saved_property_id
        deal.property_id = property_id
        deal.title = title
        deal.address = address
        deal.city = city
        deal.state = state
        deal.zip_code = zip_code
        deal.strategy = strategy
        deal.recommended_strategy = recommended_strategy
        deal.purchase_price = purchase_price
        deal.arv = arv
        deal.estimated_rent = estimated_rent
        deal.rehab_cost = rehab_cost
        deal.deal_score = deal_score
        deal.inputs_json = inputs_json or None
        deal.results_json = results_json or None
        deal.comps_json = comps_json or None
        deal.resolved_json = resolved_json or None
        deal.rehab_scope_json = rehab_scope_json
        deal.notes = notes
        deal.status = deal.status or "active"
    else:
        deal = Deal(
            user_id=current_user.id,
            investor_profile_id=ip.id,
            saved_property_id=saved_property_id,
            property_id=property_id,
            title=title,
            address=address,
            city=city,
            state=state,
            zip_code=zip_code,
            strategy=strategy,
            recommended_strategy=recommended_strategy,
            purchase_price=purchase_price,
            arv=arv,
            estimated_rent=estimated_rent,
            rehab_cost=rehab_cost,
            deal_score=deal_score,
            inputs_json=inputs_json or None,
            results_json=results_json or None,
            comps_json=comps_json or None,
            resolved_json=resolved_json or None,
            rehab_scope_json=rehab_scope_json,
            notes=notes,
            status="active",
        )
        db.session.add(deal)

    db.session.commit()

    flash("Deal saved.", "success")
    return redirect(url_for("investor.deal_detail", deal_id=deal.id))
    
@investor_bp.route("/deals/<int:deal_id>/edit", methods=["POST"])
@login_required
@role_required("investor")
def deal_edit(deal_id):
    deal = _get_owned_deal_or_404(deal_id)

    deal.title = request.form.get("title", deal.title)
    if hasattr(deal, "notes"):
        deal.notes = request.form.get("notes", getattr(deal, "notes", None))

    status = request.form.get("status")
    if status in ("active", "archived"):
        deal.status = status

    db.session.commit()
    flash("Deal updated.", "success")
    return redirect(url_for("investor.deal_detail", deal_id=deal.id))

@investor_bp.route("/deals/<int:deal_id>/delete", methods=["POST"])
@login_required
@role_required("investor")
def deal_delete(deal_id):
    deal = _get_owned_deal_or_404(deal_id)
    db.session.delete(deal)
    db.session.commit()
    flash("Deal deleted.", "success")
    return redirect(url_for("investor.deals_list"))

@investor_bp.route("/deals/<int:deal_id>/open", methods=["GET"])
@login_required
@role_required("investor")
def deal_open(deal_id):
    deal = _get_owned_deal_or_404(deal_id)

    return redirect(url_for(
        "investor.deal_workspace",
        deal_id=deal.id,
        mode=deal.strategy or "flip"
    ))

@investor_bp.route("/deals/<int:deal_id>/report", methods=["GET"])
@login_required
def deal_report(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first_or_404()

    total_cost = (deal.purchase_price or 0) + (deal.rehab_cost or 0)
    projected_profit = (deal.arv or 0) - total_cost
    projected_roi = 0

    if total_cost > 0:
        projected_roi = round((projected_profit / total_cost) * 100, 2)

    strategy_analysis = (deal.results_json or {}).get("strategy_analysis", {})
    rehab_analysis = (deal.results_json or {}).get("rehab_analysis", {})

    report = {
        "title": deal.title or "Deal Report",
        "address": deal.address,
        "strategy": deal.recommended_strategy or deal.strategy,
        "purchase_price": deal.purchase_price or 0,
        "arv": deal.arv or 0,
        "estimated_rent": deal.estimated_rent or 0,
        "rehab_cost": deal.rehab_cost or 0,
        "total_cost": total_cost,
        "projected_profit": projected_profit,
        "projected_roi": projected_roi,
        "deal_score": deal.deal_score,
        "status": deal.status,
        "notes": deal.notes,
        "strategy_reason": strategy_analysis.get("reason"),
        "rehab_scope": deal.rehab_scope_json or rehab_analysis.get("scope", {})
    }

    return render_template(
        "investor/deal_report.html",
        deal=deal,
        report=report
    )

@investor_bp.route("/deals/<int:deal_id>/request-funding", methods=["POST"])
@login_required
def request_funding(deal_id):
    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first_or_404()

    if deal.submitted_for_funding:
        return jsonify({
            "success": False,
            "message": "Funding has already been requested for this deal."
        }), 400

    requested_amount = (deal.purchase_price or 0) + (deal.rehab_cost or 0)

    deal.submitted_for_funding = True
    deal.funding_requested_at = datetime.utcnow()
    deal.status = "funding_requested"

    existing_results = deal.results_json or {}
    existing_results["funding_request"] = {
        "requested_amount": requested_amount,
        "requested_at": deal.funding_requested_at.isoformat(),
        "status": "submitted"
    }
    deal.results_json = existing_results

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Funding request submitted successfully.",
        "deal_id": deal.id,
        "requested_amount": requested_amount
    })

# =========================================================
# REHAB STUDIO PAGE
# =========================================================

@investor_bp.route("/deals/<int:deal_id>/rehab", methods=["GET"])
@investor_bp.route("/deal-studio/rehab-studio", methods=["GET"])
@login_required
@role_required("investor")
def deal_rehab(deal_id=None):
    deal = None
    saved_property = None

    if deal_id is None:
        query_deal_id = request.args.get("deal_id", type=int)
        if query_deal_id:
            deal_id = query_deal_id

    if deal_id is not None:
        deal = _get_owned_deal_or_404(deal_id)

    results = (deal.results_json or {}) if deal else {}
    rehab_project = results.get("rehab_project", {}) or {}
    rehab_scope = results.get("rehab_scope") or (getattr(deal, "rehab_scope_json", None) if deal else None) or {}

    rehab_before = rehab_project.get("before", {}) or {}
    rehab_latest = rehab_project.get("latest", {}) or {}
    rehab_concepts = rehab_project.get("concepts", []) or []

    if deal and getattr(deal, "saved_property_id", None):
        saved_property = SavedProperty.query.filter_by(id=deal.saved_property_id).first()

    property_media = _saved_property_media(saved_property) if saved_property else {"primary_photo": None, "photos": []}

    if property_media.get("primary_photo") and not rehab_before.get("image_url"):
        rehab_before = {
            **rehab_before,
            "image_url": property_media["primary_photo"],
            "source": "saved_listing_photo",
        }

    if property_media.get("photos") and not rehab_before.get("gallery"):
        rehab_before = {
            **rehab_before,
            "gallery": property_media["photos"],
        }

    return render_template(
        "investor/deal_rehab_studio.html",
        deal=deal,
        rehab_project=rehab_project,
        rehab_scope=rehab_scope,
        rehab_before=rehab_before,
        rehab_latest=rehab_latest,
        rehab_concepts=rehab_concepts,
        property_photo_gallery=property_media.get("photos") or [],
        page_title="Renovation Studio",
        page_subtitle="Visualize renovation concepts before execution.",
    )
@investor_bp.route("/deal-studio/rehab-studio/generate-variant", methods=["POST"])
@login_required
@role_required("investor")
def deal_rehab_generate_variant():
    deal = None

    try:
        data = request.form.to_dict() or {}

        deal_id = _normalize_int(data.get("deal_id"))
        if not deal_id:
            return jsonify({
                "status": "error",
                "message": "Deal ID is required."
            }), 400

        deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first()
        if not deal:
            return jsonify({
                "status": "error",
                "message": "Deal not found or not authorized."
            }), 404

        if _deal_render_lock_active(deal):
            return jsonify({
                "status": "error",
                "message": "A rehab render is already in progress for this deal."
            }), 409

        _set_deal_render_processing(deal)
        db.session.commit()

        results = _deal_results(deal)
        rehab_project = results.get("rehab_project", {}) or {}
        rehab_before = rehab_project.get("before", {}) or {}

        before_url = (rehab_before.get("image_url") or "").strip()
        if not before_url:
            raise RuntimeError("Before image is required before generating another concept.")

        try:
            raw_before = download_image_bytes(before_url)
        except Exception:
            raw_before = None

        if not raw_before:
            raise RuntimeError("Unable to load saved before image.")

        image_base64 = base64.b64encode(raw_before).decode("utf-8")

        preset = (data.get("preset") or "luxury").strip()
        mode = (data.get("mode") or "hgtv").strip()
        room_type = (data.get("room_type") or "living room").strip()
        notes = (data.get("notes") or "").strip()

        payload = {
            "preset": preset,
            "mode": mode,
            "room_type": room_type,
            "image_base64": image_base64,
            "image_url": "",
            "count": 1,
            "steps": 22,
            "guidance": 7.2,
            "strength": 0.58,
            "width": 768,
            "height": 768,
            "notes": notes,
        }

        engine_json = _post_renovation_engine_json(
            "/v1/renovate",
            payload,
            timeout=RENDER_TIMEOUT,
        )

        images_b64 = engine_json.get("images_base64") or []
        if not images_b64:
            raise RuntimeError("Variant generation returned no images.")

        render_batch_id = uuid.uuid4().hex
        after_urls = _upload_after_images_from_b64(images_b64, render_batch_id)

        if not after_urls:
            raise RuntimeError("Variant generated but uploads failed.")

        concept_entry = {
            "image_url": after_urls[0],
            "images": after_urls,
            "preset": preset,
            "mode": mode,
            "room_type": room_type,
            "notes": notes,
            "seed": engine_json.get("seed"),
            "job_id": engine_json.get("job_id"),
            "meta": engine_json.get("meta") or {},
        }

        concepts = rehab_project.get("concepts", []) or []
        concepts = [
            c for c in concepts
            if not (
                (c.get("preset") or "").strip().lower() == preset.lower()
                and (c.get("mode") or "").strip().lower() == mode.lower()
            )
        ]
        concepts.append(concept_entry)

        rehab_project["latest"] = concept_entry
        rehab_project["concepts"] = concepts
        results["rehab_project"] = rehab_project
        _set_deal_results(deal, results)

        _clear_deal_render_processing(deal)
        db.session.commit()

        return jsonify({
            "status": "ok",
            "concept_result": concept_entry,
            "concepts": concepts,
            "deal_id": deal.id,
            "saved_to_deal": True,
        })

    except Exception as e:
        current_app.logger.exception("Rehab variant generation error")

        if deal is not None:
            try:
                _clear_deal_render_processing(deal)
                db.session.commit()
            except Exception:
                db.session.rollback()

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# =========================================================
# 🏗️ BUILD STUDIO — PAGE
# =========================================================

@investor_bp.route("/deals/<int:deal_id>/build", methods=["GET"])
@investor_bp.route("/deal-studio/build-studio", methods=["GET"])
@login_required
@role_required("investor")
def build_studio(deal_id=None):
    deal = None
    project = None
    saved_property = None

    project_id = request.args.get("project_id", type=int)

    if deal_id is None:
        query_deal_id = request.args.get("deal_id", type=int)
        if query_deal_id:
            deal_id = query_deal_id

    if deal_id is not None:
        deal = _get_owned_deal_or_404(deal_id)

    if project_id is not None:
        project = BuildProject.query.filter_by(
            id=project_id,
            user_id=current_user.id
        ).first()

    if project is None and deal is not None:
        project = _safe_first_related(deal, "projects")

    # -----------------------------
    # Canonical source: deal.results_json
    # -----------------------------
    results = deal.results_json or {} if deal else {}
    build_project = results.get("build_project", {}) or {}
    build_analysis = results.get("build_analysis", {}) or {}

    # -----------------------------
    # Optional fallback from project
    # only if deal has no build_project yet
    # -----------------------------
    if not build_project and project is not None:
        project_results = getattr(project, "results_json", None) or {}

        if isinstance(project_results, dict):
            build_project = project_results.get("build_project", {}) or {}

        if not build_project:
            project_blueprint_url = (getattr(project, "blueprint_url", None) or "").strip()
            project_concept_url = (getattr(project, "concept_render_url", None) or "").strip()
            project_site_plan_url = (getattr(project, "site_plan_url", None) or "").strip()

            if project_blueprint_url or project_concept_url or project_site_plan_url:
                build_project = {
                    "blueprint": {
                        "image_url": project_blueprint_url,
                        "blueprint_url": project_blueprint_url,
                    },
                    "exterior": {
                        "image_url": project_concept_url,
                    },
                }

    blueprint_result = build_project.get("blueprint", {}) or {}
    exterior_result = build_project.get("exterior", {}) or {}

    interior_block = build_project.get("interior", {}) or {}
    interior_result = interior_block.get("latest", {}) or {}
    interior_rooms = interior_block.get("rooms", []) or []

    package_result = {
        "blueprint": blueprint_result.get("image_url") or blueprint_result.get("blueprint_url") or "",
        "exterior": exterior_result.get("image_url") or "",
        "interior": interior_result.get("image_url") or "",
    }

    has_saved_package = any([
        package_result["blueprint"],
        package_result["exterior"],
        package_result["interior"],
    ])

    current_app.logger.warning(
        "BUILD STUDIO LOAD deal_id=%s project_id=%s result_keys=%s build_project_keys=%s",
        deal.id if deal else None,
        project.id if project else None,
        list((results or {}).keys()) if isinstance(results, dict) else [],
        list((build_project or {}).keys()) if isinstance(build_project, dict) else [],        
    )

    if deal and getattr(deal, "saved_property_id", None):
        saved_property = SavedProperty.query.filter_by(id=deal.saved_property_id).first()

    property_media = _saved_property_media(saved_property) if saved_property else {"primary_photo": None, "photos": []}

    if property_media.get("primary_photo") and not exterior_result.get("build_reference_image"):
        exterior_result = {
            **exterior_result,
            "build_reference_image": property_media["primary_photo"],
        }

    return render_template(
        "investor/build_studio.html",
        deal=deal,
        project=project,
        build_analysis=build_analysis,
        build_project=build_project,
        blueprint_result=blueprint_result,
        exterior_result=exterior_result,
        interior_result=interior_result,
        interior_rooms=interior_rooms,
        property_photo_gallery=property_media.get("photos") or [],
        package_result=package_result,
        has_saved_package=has_saved_package,
        page_title="Build Studio",
        page_subtitle="Design and visualize new construction projects.",
    )

# =========================================================
# 🏗️ BUILD STUDIO — GENERATE CONCEPT
# =========================================================

@investor_bp.route("/deal-studio/build-studio/generate", methods=["POST"])
@login_required
@role_required("investor")
def generate_build_studio_legacy():
    return jsonify({
        "status": "error",
        "message": "Use the mode-specific build generation routes."
    }), 400

# 🔥 ADD THIS HELPER ABOVE ROUTE
def _is_probably_blueprint(url: str) -> bool:
    url = (url or "").lower()
    return any(x in url for x in ["blueprint", "floorplan", "layout"])


@investor_bp.route("/deal-studio/build-studio/generate-exterior", methods=["POST"])
@login_required
@role_required("investor")
def generate_build_exterior():
    deal = None

    try:
        deal_id = _normalize_int(request.form.get("deal_id"))
        project_id = _normalize_int(request.form.get("project_id"))

        if deal_id:
            deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first()
            if not deal:
                return jsonify({"status": "error", "message": "Deal not found"}), 404

            if _deal_render_lock_active(deal):
                return jsonify({"status": "error", "message": "Render in progress"}), 409

            _set_deal_render_processing(deal)
            db.session.commit()

        # ---------------- DATA ----------------
        project_name = (request.form.get("project_name") or "").strip()
        property_type = (request.form.get("property_type") or "single_family").strip()
        description = (request.form.get("description") or "").strip()
        lot_size = (request.form.get("lot_size") or "").strip()
        zoning = (request.form.get("zoning") or "").strip()
        location = (request.form.get("location") or "").strip()
        notes = (request.form.get("notes") or "").strip()
        style = (request.form.get("style") or "modern_farmhouse").strip()
        save_to_deal = (request.form.get("save_to_deal") or "").lower() in ("1", "true", "yes", "on")

        land_image = request.files.get("land_image")
        reference_image_url = (request.form.get("reference_image_url") or "").strip()

        image_base64 = ""
        raw = None

        # ---------------- IMAGE INPUT ----------------
        if land_image:
            raw = land_image.read()
            image_base64 = base64.b64encode(raw).decode("utf-8")
            reference_image_url = _upload_before_image(raw)

        # ---------------- FALLBACKS ----------------
        if not image_base64 and not reference_image_url and deal:
            results = deal.results_json or {}
            build_project = results.get("build_project", {}) or {}
            exterior = build_project.get("exterior", {}) or {}

            reference_image_url = (
                exterior.get("image_url")
                or exterior.get("build_reference_image")
                or ""
            ).strip()

        if not image_base64 and not reference_image_url and project_id:
            project = BuildProject.query.filter_by(
                id=project_id,
                user_id=current_user.id
            ).first()

            if project:
                reference_image_url = ""

        # ---------------- CLEAN BAD INPUT ----------------
        use_conditioning = True

        if _is_probably_blueprint(reference_image_url):
            # ❌ DO NOT use blueprint for exterior
            reference_image_url = ""
            use_conditioning = False

        # ---------------- PROMPT ----------------
        exterior_prompt = f"""
        photorealistic exterior of a {style} {property_type},
        front elevation view,
        realistic architecture, natural lighting,
        driveway, landscaping, curb appeal,
        high detail, real estate photography,
        {description}
        """

        # ---------------- PAYLOAD ----------------
        payload = {
            "mode": "exterior",
            "project_name": project_name,
            "property_type": property_type,
            "style": style,
            "description": description,
            "prompt": exterior_prompt,
            "lot_size": lot_size,
            "zoning": zoning,
            "count": 1,
            "steps": 22,
            "guidance": 7.5,
            "width": 768,
            "height": 768,
        }

        # 🔥 ONLY CONDITION WHEN VALID
        if use_conditioning and (image_base64 or reference_image_url):
            payload["strength"] = 0.45

            if image_base64:
                payload["image_base64"] = image_base64
            else:
                payload["image_url"] = reference_image_url

        current_app.logger.warning(f"EXTERIOR FINAL PAYLOAD: {payload}")

        result = _post_renovation_engine_json(
            "/v1/build_concept",
            payload,
            timeout=UPLOAD_TIMEOUT,
        )

        images_b64 = result.get("images_base64") or []
        if not images_b64:
            raise RuntimeError("No images returned")

        render_batch_id = uuid.uuid4().hex
        build_urls = _upload_after_images_from_b64(images_b64, render_batch_id)

        if not build_urls:
            raise RuntimeError("Upload failed")

        # ---------------- SAVE ----------------
        if save_to_deal and deal:
            results = _deal_results(deal)
            build_project = results.get("build_project", {}) or {}

            build_project["exterior"] = {
                "project_name": project_name,
                "property_type": property_type,
                "style": style,
                "description": description,
                "lot_size": lot_size,
                "zoning": zoning,
                "location": location,
                "notes": notes,
                "image_url": build_urls[0],
                "images": build_urls,
                "meta": result.get("meta") or {},
                "seed": result.get("seed"),
                "job_id": result.get("job_id"),

                # 🔥 ALWAYS USE GENERATED IMAGE
                "build_reference_image": build_urls[0],
            }

            results["build_project"] = build_project
            results["build_reference_image"] = build_urls[0]

            _set_deal_results(deal, results)

        if deal:
            _clear_deal_render_processing(deal)

        db.session.commit()

        return jsonify({
            "status": "ok",
            "mode": "exterior",
            "images": build_urls,
            "image_url": build_urls[0],
        })

    except Exception as e:
        current_app.logger.exception("Build exterior generation error")

        if deal:
            try:
                _clear_deal_render_processing(deal)
                db.session.commit()
            except:
                db.session.rollback()

        return jsonify({"status": "error", "message": str(e)}), 500

@investor_bp.route("/deal-studio/build-studio/generate-interior", methods=["POST"])
@login_required
@role_required("investor")
def generate_build_interior():
    deal = None

    try:
        data = request.form.to_dict() or {}

        deal_id = _normalize_int(data.get("deal_id"))
        if deal_id:
            deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first()
            if not deal:
                return jsonify({
                    "status": "error",
                    "message": "Deal not found or not authorized."
                }), 404

            if _deal_render_lock_active(deal):
                return jsonify({
                    "status": "error",
                    "message": "A build render is already in progress for this deal."
                }), 409

            _set_deal_render_processing(deal)
            db.session.commit()

        project_name = (data.get("project_name") or "").strip()
        property_type = (data.get("property_type") or "single_family").strip()
        style = (data.get("style") or "modern_luxury").strip()
        description = (data.get("description") or "").strip()
        lot_size = (data.get("lot_size") or "").strip()
        zoning = (data.get("zoning") or "").strip()
        location = (data.get("location") or "").strip()
        notes = (data.get("notes") or "").strip()
        room_type = (data.get("room_type") or "living room").strip()
        floor = (data.get("floor") or "main").strip()
        save_to_deal = str(data.get("save_to_deal") or "true").lower() in ("1", "true", "yes", "on")

        interior_image = request.files.get("interior_image")

        image_url = (
            data.get("image_url")
            or data.get("reference_image_url")
            or ""
        ).strip()

        image_base64 = (data.get("image_base64") or "").strip()

        if interior_image:
            raw = interior_image.read()
            if raw:
                image_base64 = base64.b64encode(raw).decode("utf-8")
                image_url = ""

        # Do NOT fall back to exterior for interior generation
        # If no interior reference is provided, leave image_url empty
        if not image_url and not image_base64:
            image_url = ""


        payload = {
            "mode": "interior",
            "project_name": project_name,
            "property_type": property_type,
            "style": style,
            "description": description,
            "lot_size": lot_size,
            "zoning": zoning,
            "room_type": room_type,
            "floor": floor,
            "count": 1,
            "steps": 20,
            "guidance": 7.0,
            "strength": 0.65,
            "width": 768,
            "height": 768,
        }

        current_app.logger.warning(f"BUILD INTERIOR ENGINE PAYLOAD: {payload}")

        engine_json = _post_renovation_engine_json(
            "/v1/build_concept",
            payload,
            timeout=BLUEPRINT_RENDER_TIMEOUT,
        )

        current_app.logger.warning(f"BUILD INTERIOR ENGINE JSON: {engine_json}")

        images_b64 = engine_json.get("images_base64", []) or []
        if not images_b64:
            return jsonify({
                "status": "error",
                "message": "Build engine returned no images."
            }), 502

        render_batch_id = uuid.uuid4().hex
        build_urls = _upload_after_images_from_b64(images_b64, render_batch_id)

        if not build_urls:
            return jsonify({
                "status": "error",
                "message": "Build render completed but uploads failed."
            }), 500

        meta = engine_json.get("meta") or {}
        seed = engine_json.get("seed")
        job_id = engine_json.get("job_id")

        if save_to_deal and deal is not None:
            results = _deal_results(deal)
            build_project = results.get("build_project", {}) or {}

            interior_block = build_project.get("interior", {}) or {}
            rooms = interior_block.get("rooms", []) or []

            room_entry = {
                "project_name": project_name,
                "property_type": property_type,
                "style": style,
                "description": description,
                "lot_size": lot_size,
                "zoning": zoning,
                "location": location,
                "notes": notes,
                "room_type": room_type,
                "floor": floor,
                "image_url": build_urls[0] if build_urls else "",
                "images": build_urls,
                "meta": meta,
                "seed": seed,
                "job_id": job_id,
                "build_reference_image": image_url,
            }

            rooms.append(room_entry)
            interior_block["rooms"] = rooms
            interior_block["latest"] = room_entry

            build_project["interior"] = interior_block
            results["build_project"] = build_project
            _set_deal_results(deal, results)

        if deal is not None:
            _clear_deal_render_processing(deal)

        db.session.commit()

        return jsonify({
            "status": "ok",
            "mode": "interior",
            "images": build_urls,
            "image_url": build_urls[0] if build_urls else "",
            "meta": meta,
            "seed": seed,
            "job_id": job_id,
            "deal_id": deal.id if deal else None,
            "saved_to_deal": bool(save_to_deal and deal is not None),
        })

    except Exception as e:
        current_app.logger.exception("Build interior generation error")

        if deal is not None:
            try:
                _clear_deal_render_processing(deal)
                db.session.commit()
            except Exception:
                db.session.rollback()

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# =========================================================
# BLUEPRINT TO CONCEPT
# =========================================================
@investor_bp.route("/deal-studio/build-studio/generate-blueprint", methods=["POST"])
@investor_bp.route("/blueprint_to_room", methods=["POST"])
@login_required
@role_required("investor")
def generate_build_blueprint():
    deal = None

    try:
        blueprint_file = request.files.get("blueprint_file")
        blueprint_url = (request.form.get("blueprint_url") or "").strip()
        reference_image_url = (request.form.get("reference_image_url") or "").strip()

        requested_style_preset = (
            request.form.get("style_preset") or "luxury_modern"
        ).strip().lower()
        renovation_level = (
            request.form.get("renovation_level") or "medium"
        ).strip().lower()

        project_name = (request.form.get("project_name") or "").strip()
        property_type = (request.form.get("property_type") or "single_family").strip()
        style = (request.form.get("style") or "modern_farmhouse").strip()
        description = (request.form.get("description") or "").strip()
        lot_size = (request.form.get("lot_size") or "").strip()
        zoning = (request.form.get("zoning") or "").strip()
        location = (request.form.get("location") or "").strip()
        notes = (request.form.get("notes") or "").strip()

        bedrooms = (request.form.get("bedrooms") or "").strip()
        bathrooms = (request.form.get("bathrooms") or "").strip()
        square_feet = (request.form.get("square_feet") or "").strip()

        deal_id = _normalize_int(request.form.get("deal_id"))
        saved_property_id = _normalize_int(request.form.get("saved_property_id"))
        project_id = _normalize_int(request.form.get("project_id"))

        project = None
        raw = None
        blueprint_image_base64 = ""

        # Keep defined so nothing blows up later
        stored_blueprint_url = ""

        # ---------------- DEAL ----------------
        if deal_id:
            deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first()
            if not deal:
                return jsonify({
                    "status": "error",
                    "message": "Deal not found."
                }), 404

            if _deal_render_lock_active(deal):
                return jsonify({
                    "status": "error",
                    "message": "Blueprint render in progress."
                }), 409

            _set_deal_render_processing(deal)
            db.session.commit()

            if saved_property_id is None and getattr(deal, "saved_property_id", None):
                saved_property_id = deal.saved_property_id

        # ---------------- OPTIONAL PROJECT ----------------
        if project_id:
            project = BuildProject.query.filter_by(
                id=project_id,
                user_id=current_user.id
            ).first()

        # ---------------- IMAGE INPUT ----------------
        if blueprint_file:
            raw = blueprint_file.read()

        elif blueprint_url:
            try:
                raw = download_image_bytes(blueprint_url)
                stored_blueprint_url = blueprint_url
            except Exception:
                raw = None

        elif reference_image_url:
            try:
                raw = download_image_bytes(reference_image_url)
                stored_blueprint_url = reference_image_url
            except Exception:
                raw = None

        elif project:
            project_blueprint_url = (getattr(project, "blueprint_url", None) or "").strip()
            if project_blueprint_url:
                try:
                    raw = download_image_bytes(project_blueprint_url)
                    stored_blueprint_url = project_blueprint_url
                except Exception:
                    raw = None

        elif deal is not None:
            results = _deal_results(deal)
            build_project = results.get("build_project", {}) or {}
            blueprint_block = build_project.get("blueprint", {}) or {}

            prior_blueprint_url = (
                blueprint_block.get("image_url")
                or blueprint_block.get("blueprint_url")
                or results.get("build_reference_image")
                or ""
            ).strip()

            if prior_blueprint_url:
                try:
                    raw = download_image_bytes(prior_blueprint_url)
                    stored_blueprint_url = prior_blueprint_url
                except Exception:
                    raw = None

        if raw:
            blueprint_image_base64 = base64.b64encode(raw).decode("utf-8")

        # ---------------- VALIDATION ----------------
        has_text_seed = any([
            project_name,
            property_type,
            description,
            lot_size,
            zoning,
            bedrooms,
            bathrooms,
            square_feet,
        ])

        if not blueprint_image_base64 and not has_text_seed:
            return jsonify({
                "status": "error",
                "message": "Provide blueprint or enough details."
            }), 400

        # ---------------- ENGINE ----------------
        style_preset = _normalize_style_preset(requested_style_preset)
        render_batch_id = uuid.uuid4().hex

        style_prompt = build_blueprint_prompt("room", style_preset, renovation_level)

        payload = {
            "mode": "blueprint",
            "project_name": project_name,
            "property_type": property_type,
            "style": style,
            "description": description,
            "lot_size": lot_size,
            "zoning": zoning,
            "prompt": style_prompt,
            "count": 1,
            "steps": 20,
            "strength": 0.28,
            "guidance": 6.0,
            "width": 768,
            "height": 768,
        }

        if blueprint_image_base64:
            payload["image_base64"] = blueprint_image_base64

        current_app.logger.warning(
            "BUILD BLUEPRINT ENGINE PAYLOAD deal_id=%s payload=%s",
            deal.id if deal else None,
            payload,
        )

        engine_json = _post_renovation_engine_json(
            "/v1/build_concept",
            payload,
            timeout=RENDER_TIMEOUT,
        )

        current_app.logger.warning(
            "BUILD BLUEPRINT ENGINE JSON deal_id=%s engine_json=%s",
            deal.id if deal else None,
            engine_json,
        )

        images_b64 = engine_json.get("images_base64") or []
        if not images_b64:
            if deal is not None:
                _clear_deal_render_processing(deal)
                db.session.commit()

            return jsonify({
                "status": "error",
                "message": "No blueprint images returned."
            }), 502

        after_urls = _upload_after_images_from_b64(images_b64, render_batch_id)
        if not after_urls:
            if deal is not None:
                _clear_deal_render_processing(deal)
                db.session.commit()

            return jsonify({
                "status": "error",
                "message": "Upload failed."
            }), 500

        # ---------------- USE GENERATED BLUEPRINT AS PRIMARY ----------------
        primary_blueprint = after_urls[0]
        fallback_reference = primary_blueprint

        # ---------------- OPTIONAL MOCKUP SAVE ----------------
        saved_count = 0
        if deal is not None and stored_blueprint_url:
            try:
                saved_count = _save_mockups_for_deal(
                    deal=deal,
                    before_url=stored_blueprint_url,
                    after_urls=after_urls,
                    style_prompt=style_prompt,
                    style_preset=style_preset,
                    mode="blueprint",
                    saved_property_id=saved_property_id,
                )
            except Exception as save_mockup_err:
                current_app.logger.warning(
                    "BUILD BLUEPRINT mockup save warning deal_id=%s error=%s",
                    deal.id,
                    save_mockup_err,
                )

        # ---------------- SAVE TO DEAL ----------------
        if deal is not None:
            results = _deal_results(deal)
            build_project = results.get("build_project", {}) or {}

            build_project["blueprint"] = {
                "project_name": project_name,
                "property_type": property_type,
                "style": style,
                "description": description,
                "lot_size": lot_size,
                "zoning": zoning,
                "location": location,
                "notes": notes,
                "bedrooms": bedrooms,
                "bathrooms": bathrooms,
                "square_feet": square_feet,
                "image_url": primary_blueprint,
                "blueprint_url": fallback_reference,
                "images": after_urls,
                "build_reference_image": primary_blueprint,
                "style_prompt": style_prompt,
                "style_preset": style_preset,
                "renovation_level": renovation_level,
                "meta": engine_json.get("meta") or {},
                "seed": engine_json.get("seed"),
                "job_id": engine_json.get("job_id"),
                "saved_count": saved_count,
                "source_reference_image": stored_blueprint_url,
            }

            results["build_project"] = build_project
            results["build_reference_image"] = primary_blueprint

            _set_deal_results(deal, results)

            current_app.logger.warning(
                "BLUEPRINT SAVE BEFORE COMMIT deal_id=%s results_keys=%s build_project_keys=%s",
                deal.id,
                list(results.keys()),
                list(build_project.keys()),
            )

        if deal is not None:
            _clear_deal_render_processing(deal)

        db.session.commit()

        if deal is not None:
            db.session.refresh(deal)
            current_app.logger.warning(
                "BLUEPRINT SAVE AFTER COMMIT deal_id=%s results_json=%s",
                deal.id,
                deal.results_json,
            )

        return jsonify({
            "status": "ok",
            "mode": "blueprint",
            "images": after_urls,
            "image_url": primary_blueprint,
            "blueprint_url": fallback_reference,
            "style_prompt": style_prompt,
            "style_preset": style_preset,
            "renovation_level": renovation_level,
            "meta": engine_json.get("meta") or {},
            "seed": engine_json.get("seed"),
            "job_id": engine_json.get("job_id"),
            "deal_id": deal.id if deal else None,
            "saved_to_deal": bool(deal is not None),
        })

    except Exception as e:
        current_app.logger.exception("Build blueprint generation error")

        if deal is not None:
            try:
                _clear_deal_render_processing(deal)
                db.session.commit()
            except Exception:
                db.session.rollback()

        error_message = str(e)
        status_code = 504 if _is_engine_timeout_error(e) else 500

        return jsonify({
            "status": "error",
            "code": "engine_timeout" if status_code == 504 else "blueprint_generation_failed",
            "message": error_message,
        }), status_code

@investor_bp.route("/deal-studio/build-studio/generate-full", methods=["POST"])
@login_required
@role_required("investor")
def generate_full_build():
    deal = None
    build_analysis = {}

    try:
        data = request.form.to_dict() or {}

        deal_id = _normalize_int(data.get("deal_id"))
        project_id = _normalize_int(data.get("project_id"))
        save_to_deal = str(data.get("save_to_deal") or "true").lower() in ("1", "true", "yes", "on")

        if deal_id:
            deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first()
            if not deal:
                return jsonify({
                    "status": "error",
                    "message": "Deal not found or not authorized."
                }), 404

            if _deal_render_lock_active(deal):
                return jsonify({
                    "status": "error",
                    "message": "A build render is already in progress for this deal."
                }), 409

            _set_deal_render_processing(deal)
            db.session.commit()

        project = None
        if project_id:
            project = BuildProject.query.filter_by(
                id=project_id,
                user_id=current_user.id
            ).first()

        # --------------------------------------------------
        # SHARED INPUTS
        # --------------------------------------------------
        project_name = (data.get("project_name") or "").strip()
        property_type = (data.get("property_type") or "single_family").strip()
        style = (data.get("style") or "modern_farmhouse").strip()
        description = (data.get("description") or "").strip()
        lot_size = (data.get("lot_size") or "").strip()
        zoning = (data.get("zoning") or "").strip()
        location = (data.get("location") or "").strip()
        notes = (data.get("notes") or "").strip()

        room_type = (data.get("room_type") or "living room").strip()
        floor = (data.get("floor") or "main").strip()

        if SCOPE_ENGINE_URL and description:
            try:
                build_analysis = _post_scope_engine_json(
                    "/v1/build_scope",
                    {
                        "project_name": project_name or None,
                        "description": description,
                        "property_type": property_type or None,
                        "lot_size": lot_size or None,
                        "zoning": zoning or None,
                    },
                    timeout=60,
                ) or {}
            except Exception:
                current_app.logger.exception("Full build scope analysis failed")
                build_analysis = {}

        blueprint_file = request.files.get("blueprint_file")
        land_image = request.files.get("land_image")

        blueprint_url = (data.get("blueprint_url") or "").strip()
        reference_image_url = (data.get("reference_image_url") or "").strip()

        blueprint_image_base64 = ""
        exterior_image_base64 = ""
        raw_blueprint = None
        raw_land = None

        # --------------------------------------------------
        # BLUEPRINT SOURCE RESOLUTION
        # --------------------------------------------------
        if blueprint_file:
            raw_blueprint = blueprint_file.read()
            if raw_blueprint:
                blueprint_image_base64 = base64.b64encode(raw_blueprint).decode("utf-8")

        elif blueprint_url:
            try:
                raw_blueprint = download_image_bytes(blueprint_url)
                if raw_blueprint:
                    blueprint_image_base64 = base64.b64encode(raw_blueprint).decode("utf-8")
            except Exception:
                raw_blueprint = None

        elif project and getattr(project, "blueprint_url", None):
            blueprint_url = (project.blueprint_url or "").strip()
            try:
                raw_blueprint = download_image_bytes(blueprint_url)
                if raw_blueprint:
                    blueprint_image_base64 = base64.b64encode(raw_blueprint).decode("utf-8")
            except Exception:
                raw_blueprint = None

        elif deal is not None:
            results = deal.results_json or {}
            build_project = results.get("build_project", {}) or {}
            saved_blueprint = build_project.get("blueprint", {}) or {}
            blueprint_url = (
                saved_blueprint.get("blueprint_url")
                or saved_blueprint.get("image_url")
                or ""
            ).strip()

            if blueprint_url:
                try:
                    raw_blueprint = download_image_bytes(blueprint_url)
                    if raw_blueprint:
                        blueprint_image_base64 = base64.b64encode(raw_blueprint).decode("utf-8")
                except Exception:
                    raw_blueprint = None

        # --------------------------------------------------
        # If no blueprint image, allow text-only blueprint generation
        # --------------------------------------------------
        has_text_seed = any([
            project_name,
            property_type,
            description,
            lot_size,
            zoning,
        ])

        if not blueprint_image_base64 and not has_text_seed:
            return jsonify({
                "status": "error",
                "message": "Provide a blueprint file, saved blueprint, or enough project details to generate a blueprint."
            }), 400

        # --------------------------------------------------
        # EXTERIOR SOURCE RESOLUTION
        # --------------------------------------------------
        if land_image:
            raw_land = land_image.read()
            if raw_land:
                exterior_image_base64 = base64.b64encode(raw_land).decode("utf-8")
                if not reference_image_url:
                    try:
                        reference_image_url = _upload_before_image(raw_land)
                    except Exception:
                        reference_image_url = ""

        if not exterior_image_base64 and not reference_image_url and deal is not None:
            results = deal.results_json or {}
            build_project = results.get("build_project", {}) or {}
            saved_exterior = build_project.get("exterior", {}) or {}
            reference_image_url = (
                saved_exterior.get("image_url")
                or saved_exterior.get("build_reference_image")
                or ""
            ).strip()

        if not exterior_image_base64 and not reference_image_url and project:
            reference_image_url = (
                (project.concept_render_url or "").strip()
                or (project.site_plan_url or "").strip()
                or ""
            )

        # --------------------------------------------------
        # 1. GENERATE BLUEPRINT
        # --------------------------------------------------
        blueprint_payload = {
            "mode": "blueprint",
            "project_name": project_name,
            "property_type": property_type,
            "style": style,
            "description": description,
            "lot_size": lot_size,
            "zoning": zoning,
            "width": 1024,
            "height": 1024,
            "steps": 22,
            "guidance": 6.0,
            "strength": 0.28,
            "count": 1,
        }

        if blueprint_image_base64:
            blueprint_payload["image_base64"] = blueprint_image_base64
            blueprint_payload["image_url"] = ""

        current_app.logger.warning(f"FULL BUILD BLUEPRINT PAYLOAD: {blueprint_payload}")

        blueprint_json = _post_renovation_engine_json(
            "/v1/build_concept",
            blueprint_payload,
            timeout=FULL_BUILD_BLUEPRINT_TIMEOUT,
        )

        current_app.logger.warning(f"FULL BUILD BLUEPRINT JSON: {blueprint_json}")

        blueprint_images_b64 = blueprint_json.get("images_base64") or []
        if not blueprint_images_b64:
            return jsonify({
                "status": "error",
                "message": "Blueprint step returned no images."
            }), 502

        blueprint_batch_id = uuid.uuid4().hex
        blueprint_urls = _upload_after_images_from_b64(blueprint_images_b64, blueprint_batch_id)

        if not blueprint_urls:
            return jsonify({
                "status": "error",
                "message": "Blueprint generated but uploads failed."
            }), 500

        blueprint_primary_url = blueprint_urls[0]
        blueprint_primary_b64 = blueprint_images_b64[0]

        blueprint_meta = blueprint_json.get("meta") or {}
        blueprint_seed = blueprint_json.get("seed")
        blueprint_job_id = blueprint_json.get("job_id")

        # --------------------------------------------------
        # 2. GENERATE EXTERIOR
        # Prefer land image if supplied, otherwise blueprint output
        # --------------------------------------------------
        exterior_payload = {
            "mode": "exterior",
            "project_name": project_name,
            "property_type": property_type,
            "style": style,
            "description": description,
            "lot_size": lot_size,
            "zoning": zoning,
            "image_base64": exterior_image_base64 or blueprint_primary_b64,
            "image_url": "" if (exterior_image_base64 or blueprint_primary_b64) else reference_image_url,
            "width": 640,
            "height": 640,
            "steps": 20,
            "guidance": 7.5,
            "strength": 0.68,
            "count": 1,
        }

        current_app.logger.warning(f"FULL BUILD EXTERIOR PAYLOAD: {exterior_payload}")

        exterior_json = _post_renovation_engine_json(
            "/v1/build_concept",
            exterior_payload,
            timeout=UPLOAD_TIMEOUT,
        )

        current_app.logger.warning(f"FULL BUILD EXTERIOR JSON: {exterior_json}")

        exterior_images_b64 = exterior_json.get("images_base64") or []
        if not exterior_images_b64:
            return jsonify({
                "status": "error",
                "message": "Exterior step returned no images."
            }), 502

        exterior_batch_id = uuid.uuid4().hex
        exterior_urls = _upload_after_images_from_b64(exterior_images_b64, exterior_batch_id)

        if not exterior_urls:
            return jsonify({
                "status": "error",
                "message": "Exterior generated but uploads failed."
            }), 500

        exterior_primary_url = exterior_urls[0]
        exterior_meta = exterior_json.get("meta") or {}
        exterior_seed = exterior_json.get("seed")
        exterior_job_id = exterior_json.get("job_id")

        # --------------------------------------------------
        # 3. GENERATE INTERIOR
        # text-only
        # --------------------------------------------------
        interior_payload = {
            "mode": "interior",
            "project_name": project_name,
            "property_type": property_type,
            "style": style,
            "description": description,
            "lot_size": lot_size,
            "zoning": zoning,
            "room_type": room_type,
            "floor": floor,
            "image_base64": blueprint_primary_b64,
            "image_url": "",
            "count": 1,
            "steps": 22,
            "guidance": 7.0,
            "strength": 0.42,
            "width": 768,
            "height": 768,
        }

        current_app.logger.warning(f"FULL BUILD INTERIOR PAYLOAD: {interior_payload}")

        interior_json = _post_renovation_engine_json(
            "/v1/build_concept",
            interior_payload,
            timeout=RENDER_TIMEOUT,
        )

        current_app.logger.warning(f"FULL BUILD INTERIOR JSON: {interior_json}")

        interior_images_b64 = interior_json.get("images_base64") or []
        interior_urls = []
        interior_primary_url = ""

        if interior_images_b64:
            interior_batch_id = uuid.uuid4().hex
            interior_urls = _upload_after_images_from_b64(interior_images_b64, interior_batch_id)
            if interior_urls:
                interior_primary_url = interior_urls[0]

        interior_meta = interior_json.get("meta") or {}
        interior_seed = interior_json.get("seed")
        interior_job_id = interior_json.get("job_id")

        # --------------------------------------------------
        # SAVE TO DEAL
        # --------------------------------------------------
        if save_to_deal and deal is not None:
            results = _deal_results(deal)
            build_project = results.get("build_project", {}) or {}

            build_project["blueprint"] = {
                "project_name": project_name,
                "property_type": property_type,
                "description": description,
                "lot_size": lot_size,
                "zoning": zoning,
                "location": location,
                "notes": notes,
                "style": style,
                "image_url": blueprint_primary_url,
                "images": blueprint_urls,
                "blueprint_url": blueprint_primary_url,
                "meta": blueprint_meta,
                "seed": blueprint_seed,
                "job_id": blueprint_job_id,
            }

            build_project["exterior"] = {
                "project_name": project_name,
                "property_type": property_type,
                "description": description,
                "lot_size": lot_size,
                "zoning": zoning,
                "location": location,
                "notes": notes,
                "style": style,
                "image_url": exterior_primary_url,
                "images": exterior_urls,
                "meta": exterior_meta,
                "seed": exterior_seed,
                "job_id": exterior_job_id,
                "build_reference_image": reference_image_url or blueprint_primary_url,
            }

            existing_interior = build_project.get("interior", {}) or {}
            existing_rooms = existing_interior.get("rooms", []) or []

            room_entry = {
                "project_name": project_name,
                "property_type": property_type,
                "style": style,
                "description": description,
                "lot_size": lot_size,
                "zoning": zoning,
                "location": location,
                "notes": notes,
                "room_type": room_type,
                "floor": floor,
                "image_url": interior_primary_url,
                "images": interior_urls,
                "meta": interior_meta,
                "seed": interior_seed,
                "job_id": interior_job_id,
                "build_reference_image": blueprint_primary_url,
            }

            if interior_primary_url:
                existing_rooms.append(room_entry)

            build_project["interior"] = {
                "latest": room_entry,
                "rooms": existing_rooms,
            }

            if build_analysis:
                results["build_analysis"] = build_analysis
            results["build_project"] = build_project
            results["build_reference_image"] = reference_image_url or blueprint_primary_url
            _set_deal_results(deal, results)

        if deal is not None:
            _clear_deal_render_processing(deal)

        db.session.commit()

        return jsonify({
            "status": "ok",
            "mode": "full",
            "package": {
                "blueprint": blueprint_primary_url,
                "exterior": exterior_primary_url,
                "interior": interior_primary_url,
            },
            "blueprint_result": {
                "image_url": blueprint_primary_url,
                "images": blueprint_urls,
                "meta": blueprint_meta,
                "seed": blueprint_seed,
                "job_id": blueprint_job_id,
            },
            "exterior_result": {
                "image_url": exterior_primary_url,
                "images": exterior_urls,
                "meta": exterior_meta,
                "seed": exterior_seed,
                "job_id": exterior_job_id,
            },
            "interior_result": {
                "image_url": interior_primary_url,
                "images": interior_urls,
                "meta": interior_meta,
                "seed": interior_seed,
                "job_id": interior_job_id,
                "room_type": room_type,
                "floor": floor,
            },
            "build_analysis": build_analysis,
            "deal_id": deal.id if deal else None,
            "saved_to_deal": bool(save_to_deal and deal is not None),
        })

    except Exception as e:
        current_app.logger.exception("Full build generation error")

        if deal is not None:
            try:
                _clear_deal_render_processing(deal)
                db.session.commit()
            except Exception:
                db.session.rollback()

        error_message = str(e)
        status_code = 504 if _is_engine_timeout_error(e) else 500

        return jsonify({
            "status": "error",
            "code": "engine_timeout" if status_code == 504 else "full_build_generation_failed",
            "message": error_message,
        }), status_code

@investor_bp.route("/deal-studio/build-studio/generate-room", methods=["POST"])
@login_required
@role_required("investor")
def generate_build_room():
    deal = None

    def _clean_str(value):
        return (value or "").strip()

    def _first_nonempty(*values):
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _safe_dict(value):
        return value if isinstance(value, dict) else {}

    def _extract_blueprint_reference(results, build_project):
        """
        Find the best saved blueprint reference from current or legacy locations.
        """
        results = _safe_dict(results)
        build_project = _safe_dict(build_project)

        blueprint_block = _safe_dict(build_project.get("blueprint"))
        interior_block = _safe_dict(build_project.get("interior"))
        interior_latest = _safe_dict(interior_block.get("latest"))
        exterior_block = _safe_dict(build_project.get("exterior"))

        # legacy/top-level blocks sometimes used by older saves
        blueprint_result = _safe_dict(results.get("blueprint_result"))
        build_blueprint = _safe_dict(results.get("blueprint"))
        concept_block = _safe_dict(results.get("concept"))
        latest_build = _safe_dict(results.get("latest_build"))

        blueprint_url = _first_nonempty(
            blueprint_block.get("image_url"),
            blueprint_block.get("blueprint_url"),
            blueprint_block.get("url"),
            blueprint_block.get("saved_url"),
            blueprint_block.get("saved_path"),

            blueprint_result.get("image_url"),
            blueprint_result.get("blueprint_url"),
            blueprint_result.get("url"),
            blueprint_result.get("saved_path"),

            build_blueprint.get("image_url"),
            build_blueprint.get("blueprint_url"),
            build_blueprint.get("url"),

            interior_latest.get("build_reference_image"),
            interior_latest.get("blueprint_url"),
            interior_latest.get("image_url"),

            exterior_block.get("build_reference_image"),
            exterior_block.get("blueprint_url"),

            concept_block.get("blueprint_url"),
            concept_block.get("image_url"),

            latest_build.get("blueprint_url"),
            latest_build.get("image_url"),

            results.get("build_reference_image"),
            results.get("blueprint_url"),
            results.get("blueprint_image"),
        )

        current_app.logger.warning(
            "BUILD ROOM LOOKUP deal_id=%s blueprint_url=%s result_keys=%s build_project_keys=%s blueprint_keys=%s",
            getattr(deal, "id", None),
            blueprint_url,
            list(results.keys()),
            list(build_project.keys()),
            list(blueprint_block.keys()),
        )

        return blueprint_url, blueprint_block, interior_block, interior_latest, exterior_block

    try:
        data = request.form.to_dict() or {}

        deal_id = _normalize_int(data.get("deal_id"))
        if not deal_id:
            return jsonify({
                "status": "error",
                "message": "Deal ID is required."
            }), 400

        deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first()
        if not deal:
            return jsonify({
                "status": "error",
                "message": "Deal not found or not authorized."
            }), 404

        if _deal_render_lock_active(deal):
            return jsonify({
                "status": "error",
                "message": "A build render is already in progress for this deal."
            }), 409

        _set_deal_render_processing(deal)
        db.session.commit()

        results = _safe_dict(_deal_results(deal))
        build_project = _safe_dict(results.get("build_project"))

        blueprint_url, blueprint_block, interior_block, interior_latest, exterior_block = _extract_blueprint_reference(
            results, build_project
        )

        if not blueprint_url:
            _clear_deal_render_processing(deal)
            db.session.commit()
            return jsonify({
                "status": "error",
                "message": "Generate and save a blueprint first before creating additional rooms."
            }), 400

        try:
            raw_blueprint = download_image_bytes(blueprint_url)
        except Exception as download_err:
            current_app.logger.exception(
                "BUILD ROOM blueprint download failed for deal_id=%s url=%s",
                deal.id,
                blueprint_url,
            )
            raw_blueprint = None

        if not raw_blueprint:
            _clear_deal_render_processing(deal)
            db.session.commit()
            return jsonify({
                "status": "error",
                "message": f"Unable to load saved blueprint from: {blueprint_url}"
            }), 400

        blueprint_b64 = base64.b64encode(raw_blueprint).decode("utf-8")

        project_name = _first_nonempty(
            data.get("project_name"),
            blueprint_block.get("project_name"),
            interior_latest.get("project_name"),
            exterior_block.get("project_name"),
        )

        property_type = _first_nonempty(
            data.get("property_type"),
            blueprint_block.get("property_type"),
            interior_latest.get("property_type"),
            exterior_block.get("property_type"),
            "single_family",
        )

        style = _first_nonempty(
            data.get("style"),
            blueprint_block.get("style"),
            interior_latest.get("style"),
            exterior_block.get("style"),
            "modern_farmhouse",
        )

        description = _first_nonempty(
            data.get("description"),
            blueprint_block.get("description"),
            interior_latest.get("description"),
            exterior_block.get("description"),
        )

        lot_size = _first_nonempty(
            data.get("lot_size"),
            blueprint_block.get("lot_size"),
            interior_latest.get("lot_size"),
            exterior_block.get("lot_size"),
        )

        zoning = _first_nonempty(
            data.get("zoning"),
            blueprint_block.get("zoning"),
            interior_latest.get("zoning"),
            exterior_block.get("zoning"),
        )

        location = _first_nonempty(
            data.get("location"),
            blueprint_block.get("location"),
            interior_latest.get("location"),
            exterior_block.get("location"),
        )

        notes = _clean_str(data.get("notes"))
        room_type = _clean_str(data.get("room_type")) or "kitchen"
        floor = _clean_str(data.get("floor")) or "main"

        payload = {
            "mode": "interior",
            "project_name": project_name,
            "property_type": property_type,
            "style": style,
            "description": description,
            "lot_size": lot_size,
            "zoning": zoning,
            "room_type": room_type,
            "floor": floor,
            "image_base64": blueprint_b64,
            "image_url": "",
            "count": 1,
            "steps": 22,
            "guidance": 7.0,
            "strength": 0.42,
            "width": 768,
            "height": 768,
        }

        engine_json = _post_renovation_engine_json(
            "/v1/build_concept",
            payload,
            timeout=RENDER_TIMEOUT,
        )

        images_b64 = engine_json.get("images_base64") or []
        if not images_b64:
            raise RuntimeError("Room generation returned no images.")

        render_batch_id = uuid.uuid4().hex
        room_urls = _upload_after_images_from_b64(images_b64, render_batch_id)

        if not room_urls:
            raise RuntimeError("Room generated but uploads failed.")

        interior_block = _safe_dict(build_project.get("interior"))
        rooms = interior_block.get("rooms", []) or []

        room_entry = {
            "project_name": project_name,
            "property_type": property_type,
            "style": style,
            "description": description,
            "lot_size": lot_size,
            "zoning": zoning,
            "location": location,
            "notes": notes,
            "room_type": room_type,
            "floor": floor,
            "image_url": room_urls[0],
            "images": room_urls,
            "meta": engine_json.get("meta") or {},
            "seed": engine_json.get("seed"),
            "job_id": engine_json.get("job_id"),
            "build_reference_image": blueprint_url,
        }

        rooms = [
            r for r in rooms
            if not (
                _clean_str(r.get("room_type")).lower() == room_type.lower()
                and _clean_str(r.get("floor")).lower() == floor.lower()
            )
        ]
        rooms.append(room_entry)

        interior_block["latest"] = room_entry
        interior_block["rooms"] = rooms
        build_project["interior"] = interior_block

        # preserve blueprint reference in a standard place for future room generations
        if "blueprint" not in build_project or not isinstance(build_project.get("blueprint"), dict):
            build_project["blueprint"] = {}

        build_project["blueprint"]["image_url"] = _first_nonempty(
            build_project["blueprint"].get("image_url"),
            blueprint_url,
        )
        build_project["blueprint"]["blueprint_url"] = _first_nonempty(
            build_project["blueprint"].get("blueprint_url"),
            blueprint_url,
        )

        results["build_project"] = build_project
        results["build_reference_image"] = blueprint_url

        _set_deal_results(deal, results)
        _clear_deal_render_processing(deal)
        db.session.commit()

        return jsonify({
            "status": "ok",
            "room_result": room_entry,
            "rooms": rooms,
            "deal_id": deal.id,
            "saved_to_deal": True,
        })

    except Exception as e:
        current_app.logger.exception("Build room generation error")

        if deal is not None:
            try:
                _clear_deal_render_processing(deal)
                db.session.commit()
            except Exception:
                db.session.rollback()

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
     
@investor_bp.route("/ai/build-scope/analyze", methods=["POST"])
@login_required
@role_required("investor")
def ai_build_scope():
    data = request.get_json(silent=True) or {}

    payload = {
        "project_name": (data.get("project_name") or "").strip() or None,
        "description": (data.get("description") or "").strip(),
        "property_type": (data.get("property_type") or "").strip() or None,
        "lot_size": (data.get("lot_size") or "").strip() or None,
        "zoning": (data.get("zoning") or "").strip() or None,
        "asking_price": safe_float(data.get("asking_price"), default=None) if data.get("asking_price") not in (None, "", "None") else None,
        "square_feet_target": safe_int(data.get("square_feet_target"), default=None) if data.get("square_feet_target") not in (None, "", "None") else None,
    }

    if not payload["description"]:
        return jsonify({"status": "error", "message": "description is required."}), 400

    try:
        if not SCOPE_ENGINE_URL:
            return jsonify({"status": "error", "message": "Scope engine is not configured."}), 500

        engine_data = _post_scope_engine_json("/v1/build_scope", payload, timeout=60) or {}
        return jsonify(engine_data)

    except Exception as e:
        current_app.logger.exception("ai_build_scope failed")
        return jsonify({"status": "error", "message": str(e)}), 500

       
@investor_bp.route("/deal-studio/build-studio/generate-upload", methods=["POST"])
@login_required
@role_required("investor")
def generate_build_studio_upload():
    deal = None

    try:
        deal_id = _normalize_int(request.form.get("deal_id"))

        # 🔒 This route is EXTERIOR ONLY by design
        mode = "exterior"

        if deal_id:
            deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first()
            if not deal:
                return jsonify({
                    "status": "error",
                    "message": "Deal not found or not authorized."
                }), 404

            if _deal_render_lock_active(deal):
                return jsonify({
                    "status": "error",
                    "message": "A build render is already in progress for this deal."
                }), 409

            _set_deal_render_processing(deal)
            db.session.commit()

        # -----------------------------
        # FORM DATA
        # -----------------------------
        project_name = (request.form.get("project_name") or "").strip()
        property_type = (request.form.get("property_type") or "single_family").strip()
        description = (request.form.get("description") or "").strip()
        lot_size = (request.form.get("lot_size") or "").strip()
        zoning = (request.form.get("zoning") or "").strip()
        location = (request.form.get("location") or "").strip()
        notes = (request.form.get("notes") or "").strip()
        style = (request.form.get("style") or "modern_farmhouse").strip()

        save_to_deal = (request.form.get("save_to_deal") or "").lower() in ("1", "true", "yes", "on")

        # -----------------------------
        # REQUIRED IMAGE
        # -----------------------------
        land_image = request.files.get("land_image")

        if not land_image:
            return jsonify({
                "status": "error",
                "message": "land_image is required."
            }), 400

        raw = land_image.read()
        if not raw:
            return jsonify({
                "status": "error",
                "message": "Empty land image."
            }), 400

        # Upload original reference (before image)
        reference_image_url = _upload_before_image(raw)

        # -----------------------------
        # ENGINE PAYLOAD
        # -----------------------------
        payload = {
            "mode": "exterior",
            "project_name": project_name,
            "property_type": property_type,
            "style": style,
            "description": description,
            "lot_size": lot_size,
            "zoning": zoning,

            # ALWAYS use uploaded image for exterior
            "image_base64": base64.b64encode(raw).decode("utf-8"),
            "image_url": "",

            "width": 640,
            "height": 640,
            "steps": 22,
            "guidance": 7.5,
            "strength": 0.65,  # slight tweak from 0.68
            "count": 1,
        }

        seed = request.form.get("seed")
        if seed not in (None, "", "None"):
            payload["seed"] = int(seed)

        current_app.logger.warning(f"BUILD UPLOAD ENGINE PAYLOAD: {payload}")

        # -----------------------------
        # CALL ENGINE
        # -----------------------------
        result = _post_renovation_engine_json(
            "/v1/build_concept",
            payload,
            timeout=UPLOAD_TIMEOUT,
        )

        current_app.logger.warning(f"BUILD UPLOAD ENGINE JSON: {result}")

        images_b64 = result.get("images_base64") or []
        if not images_b64:
            return jsonify({
                "status": "error",
                "message": "Build engine returned no images."
            }), 502

        # -----------------------------
        # SAVE OUTPUT IMAGES
        # -----------------------------
        render_batch_id = uuid.uuid4().hex
        build_urls = _upload_after_images_from_b64(images_b64, render_batch_id)

        if not build_urls:
            return jsonify({
                "status": "error",
                "message": "Build render completed but uploads failed."
            }), 500

        meta = result.get("meta") or {}
        seed = result.get("seed")
        job_id = result.get("job_id")

        # -----------------------------
        # SAVE TO DEAL
        # -----------------------------
        if save_to_deal and deal is not None:
            results = _deal_results(deal)
            build_project = results.get("build_project", {}) or {}

            build_project["exterior"] = {
                "primary": {
                    "project_name": project_name,
                    "property_type": property_type,
                    "description": description,
                    "lot_size": lot_size,
                    "zoning": zoning,
                    "location": location,
                    "notes": notes,
                    "style": style,
                    "image_url": build_urls[0],
                    "images": build_urls,
                    "meta": meta,
                    "seed": seed,
                    "job_id": job_id,
                    "build_reference_image": reference_image_url,
                },
                "gallery": build_urls,
            }

            results["build_project"] = build_project
            results["build_reference_image"] = reference_image_url  # legacy support

            _set_deal_results(deal, results)

        if deal is not None:
            _clear_deal_render_processing(deal)

        db.session.commit()

        return jsonify({
            "status": "ok",
            "mode": "exterior",
            "images": build_urls,
            "image_url": build_urls[0],
            "meta": meta,
            "seed": seed,
            "job_id": job_id,
            "deal_id": deal.id if deal else None,
            "saved_to_deal": bool(save_to_deal and deal is not None),
            "reference_image_url": reference_image_url,
        })

    except Exception as e:
        current_app.logger.exception("Build Studio upload generation error")

        if deal is not None:
            try:
                _clear_deal_render_processing(deal)
                db.session.commit()
            except Exception:
                db.session.rollback()

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# =========================================================
# 🏗️ BUILD STUDIO — SAVE PROJECT
# =========================================================

@investor_bp.route("/deal-studio/build-studio/save", methods=["POST"])
@login_required
@role_required("investor")
def save_build_studio():
    data = request.get_json(silent=True) or {}

    deal_id = _normalize_int(data.get("deal_id"))
    deal = None

    if deal_id:
        deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first()
        if not deal:
            return jsonify({"status": "error", "message": "Deal not found or not authorized."}), 404

    investor_profile = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    # 🔥 Pull all modes
    exterior_url = (data.get("concept_render_url") or "").strip()
    blueprint_url = (data.get("blueprint_url") or "").strip()
    site_plan_url = (data.get("site_plan_url") or "").strip()

    project = BuildProject(
        user_id=current_user.id,
        project_name=data.get("project_name"),
        property_type=data.get("property_type"),
        description=data.get("description"),
        lot_size=data.get("lot_size"),
        zoning=data.get("zoning"),
        location=data.get("location"),
        notes=data.get("notes"),

        # 🔥 Main outputs
        concept_render_url=exterior_url,
        blueprint_url=blueprint_url,
        site_plan_url=site_plan_url,

        presentation_url=data.get("presentation_url")
    )

    if hasattr(project, "investor_profile_id"):
        project.investor_profile_id = investor_profile.id if investor_profile else None

    if hasattr(project, "deal_id"):
        project.deal_id = deal.id if deal else None

    db.session.add(project)
    db.session.flush()

    # 🔥 Sync deal with structured build_project
    if deal is not None:
        results = _deal_results(deal)
        build_project = results.get("build_project", {}) or {}

        results["build_project"] = {
            "project_id": project.id,
            "project_name": project.project_name,
            "property_type": project.property_type,
            "description": project.description,
            "lot_size": project.lot_size,
            "zoning": project.zoning,
            "location": project.location,
            "notes": project.notes,

            # 🔥 preserve modes
            "exterior": build_project.get("exterior", {}),
            "interior": build_project.get("interior", {}),
            "blueprint": build_project.get("blueprint", {}),

            # 🔥 quick access
            "concept_render_url": exterior_url,
            "blueprint_url": blueprint_url,
            "site_plan_url": site_plan_url,
        }

        _set_deal_results(deal, results)

    db.session.commit()

    return jsonify({
        "status": "ok",
        "project_id": project.id,
        "deal_id": deal.id if deal else None,
    })

# =========================================================
# 🏗️ BUILD PROJECTS — LIST
# =========================================================

@investor_bp.route("/build-projects", methods=["GET"])
@login_required
@role_required("investor")
def build_projects():
    projects = BuildProject.query.filter_by(
        user_id=current_user.id
    ).order_by(BuildProject.created_at.desc()).all()

    return render_template(
        "investor/build_projects.html",
        projects=projects,
        page_title="Build Projects"
    )


@investor_bp.route("/build-projects/<int:project_id>", methods=["GET"])
@login_required
@role_required("investor")
def build_project_detail(project_id):
    project = BuildProject.query.filter_by(
        id=project_id,
        user_id=current_user.id
    ).first_or_404()

    return render_template(
        "investor/build_project_detail.html",
        project=project,
        page_title="Build Project",
        page_subtitle="Review your saved development concept."
    )

@investor_bp.route("/build-projects/<int:project_id>/open-studio", methods=["GET"])
@login_required
@role_required("investor")
def open_build_project_in_studio(project_id):
    project = BuildProject.query.filter_by(
        id=project_id,
        user_id=current_user.id
    ).first_or_404()

    deal_id = request.args.get("deal_id", type=int)

    if deal_id:
        return redirect(url_for("investor.build_studio", deal_id=deal_id, project_id=project.id))

    return redirect(url_for("investor.build_studio", project_id=project.id))

@investor_bp.route("/build-projects/<int:project_id>/convert-to-deal", methods=["POST"])
@login_required
@role_required("investor")
def convert_build_project_to_deal(project_id):
    project = BuildProject.query.filter_by(
        id=project_id,
        user_id=current_user.id
    ).first_or_404()

    investor_profile = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    deal = Deal(
        user_id=current_user.id,
        investor_profile_id=investor_profile.id if investor_profile else None,
        title=project.project_name or "Build Project Deal",
        address=project.location or None,
        strategy="development",
        notes=project.notes or project.description or "",
        status="active",
        inputs_json={
            "source": "build_project",
            "build_project_id": project.id,
            "project_name": project.project_name,
            "property_type": project.property_type,
            "description": project.description,
            "lot_size": project.lot_size,
            "zoning": project.zoning,
            "location": project.location,
            "notes": project.notes,
        },
        results_json={
            "build_project": {
                "project_id": project.id,
                "project_name": project.project_name,
                "property_type": project.property_type,
                "description": project.description,
                "lot_size": project.lot_size,
                "zoning": project.zoning,
                "location": project.location,
                "notes": project.notes,
                "concept_render_url": project.concept_render_url,
                "blueprint_url": project.blueprint_url,
                "site_plan_url": project.site_plan_url,
                "presentation_url": project.presentation_url,
            }
        }
    )

    db.session.add(deal)
    db.session.commit()

    flash("Build project converted into a deal.", "success")
    return jsonify({
        "status": "ok",
        "deal_id": deal.id,
        "redirect_url": url_for("investor.deal_detail", deal_id=deal.id)
    })


# =========================================================
# 🧭 AI DEAL ARCHITECT
# =========================================================


        

@investor_bp.route("/deal-architect", methods=["GET", "POST"])
@investor_bp.route("/deal-architect/<int:deal_id>", methods=["GET", "POST"])
@login_required
@role_required("investor")
def deal_architect(deal_id=None):
    selected_deal = None

    # -------------------------------------------------
    # LOAD DEAL
    # -------------------------------------------------
    if deal_id:
        selected_deal = Deal.query.filter_by(
            id=deal_id,
            user_id=current_user.id
        ).first_or_404()
    else:
        query_deal_id = request.args.get("deal_id", type=int)
        if query_deal_id:
            selected_deal = Deal.query.filter_by(
                id=query_deal_id,
                user_id=current_user.id
            ).first()

    # -------------------------------------------------
    # DEFAULT DISPLAY VALUES
    # -------------------------------------------------
    property_address = ""
    city = ""
    state = ""
    zip_code = ""
    property_type = ""
    bedrooms = None
    bathrooms = None
    sqft = None
    year_built = None

    purchase_price = None
    arv = None
    estimated_rent = None
    rehab_cost = None
    lot_size = None
    zoning = None
    strategy = ""
    notes = ""

    strategy_analysis = {}
    rehab_analysis = {}
    build_analysis = {}
    build_preview_url = ""
    build_mockups = []

    # -------------------------------------------------
    # LOAD DEAL DATA
    # -------------------------------------------------
    if selected_deal:
        property_address = (
            getattr(selected_deal, "property_address", None)
            or getattr(selected_deal, "address", None)
            or getattr(selected_deal, "street_address", None)
            or ""
        )
        city = getattr(selected_deal, "city", "") or ""
        state = getattr(selected_deal, "state", "") or ""
        zip_code = (
            getattr(selected_deal, "zip_code", None)
            or getattr(selected_deal, "zip", None)
            or ""
        )
        property_type = (
            getattr(selected_deal, "property_type", None)
            or getattr(selected_deal, "asset_type", None)
            or ""
        )
        bedrooms = getattr(selected_deal, "bedrooms", None) or getattr(selected_deal, "beds", None)
        bathrooms = getattr(selected_deal, "bathrooms", None) or getattr(selected_deal, "baths", None)
        sqft = getattr(selected_deal, "square_feet", None) or getattr(selected_deal, "sqft", None)
        year_built = getattr(selected_deal, "year_built", None)

        purchase_price = getattr(selected_deal, "purchase_price", None)
        arv = getattr(selected_deal, "arv", None)
        estimated_rent = getattr(selected_deal, "estimated_rent", None)
        rehab_cost = (
            getattr(selected_deal, "rehab_cost", None)
            or getattr(selected_deal, "estimated_rehab_cost", None)
        )
        lot_size = getattr(selected_deal, "lot_size", None)
        zoning = getattr(selected_deal, "zoning", None)
        strategy = getattr(selected_deal, "strategy", "") or ""
        notes = getattr(selected_deal, "notes", "") or ""

        results = _deal_results(selected_deal)
        strategy_analysis = results.get("strategy_analysis", {}) or {}
        rehab_analysis = results.get("rehab_analysis", {}) or {}
        build_analysis = results.get("build_analysis", {}) or {}
        build_preview_url = results.get("build_preview_url", "") or ""
        build_mockups = results.get("build_mockups", []) or []

    # -------------------------------------------------
    # SMALL HELPERS
    # -------------------------------------------------
    def _to_float(val):
        if val in (None, "", "None"):
            return None
        try:
            return float(str(val).replace(",", "").replace("$", "").strip())
        except Exception:
            return None

    def _to_int(val):
        if val in (None, "", "None"):
            return None
        try:
            return int(float(str(val).replace(",", "").strip()))
        except Exception:
            return None

    # -------------------------------------------------
    # HANDLE FORM SUBMIT
    # -------------------------------------------------
    if request.method == "POST":
        if not selected_deal:
            flash("Select a deal before updating Deal Architect.", "warning")
            return redirect(url_for("investor.property_tool"))

        selected_deal.purchase_price = _to_float(request.form.get("purchase_price")) or selected_deal.purchase_price
        selected_deal.arv = _to_float(request.form.get("arv")) or selected_deal.arv
        selected_deal.estimated_rent = _to_float(request.form.get("estimated_rent")) or selected_deal.estimated_rent
        selected_deal.rehab_cost = _to_float(request.form.get("rehab_cost")) or getattr(selected_deal, "rehab_cost", None)

        if hasattr(selected_deal, "property_type"):
            selected_deal.property_type = request.form.get("property_type") or selected_deal.property_type

        if hasattr(selected_deal, "bedrooms"):
            selected_deal.bedrooms = _to_int(request.form.get("bedrooms")) or selected_deal.bedrooms

        if hasattr(selected_deal, "bathrooms"):
            selected_deal.bathrooms = _to_float(request.form.get("bathrooms")) or selected_deal.bathrooms

        if hasattr(selected_deal, "square_feet"):
            selected_deal.square_feet = _to_int(request.form.get("sqft")) or selected_deal.square_feet
        elif hasattr(selected_deal, "sqft"):
            selected_deal.sqft = _to_int(request.form.get("sqft")) or selected_deal.sqft

        if hasattr(selected_deal, "year_built"):
            selected_deal.year_built = _to_int(request.form.get("year_built")) or selected_deal.year_built

        if hasattr(selected_deal, "lot_size"):
            selected_deal.lot_size = request.form.get("lot_size") or selected_deal.lot_size

        if hasattr(selected_deal, "zoning"):
            selected_deal.zoning = request.form.get("zoning") or selected_deal.zoning

        selected_deal.strategy = request.form.get("strategy") or selected_deal.strategy
        selected_deal.notes = request.form.get("notes") or selected_deal.notes

        db.session.commit()
        flash("Deal Architect inputs updated.", "success")

        return redirect(url_for("investor.deal_architect", deal_id=selected_deal.id))

    # -------------------------------------------------
    # RENDER
    # -------------------------------------------------
    return render_template(
        "investor/deal_architect.html",
        page_title="Deal Architect",
        page_subtitle="Analyze the opportunity, score the risk, and shape the best strategy.",
        deal=selected_deal,
        deal_id=selected_deal.id if selected_deal else None,
        property_address=property_address,
        city=city,
        state=state,
        zip_code=zip_code,
        property_type=property_type,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        sqft=sqft,
        year_built=year_built,
        purchase_price=purchase_price,
        arv=arv,
        estimated_rent=estimated_rent,
        rehab_cost=rehab_cost,
        lot_size=lot_size,
        zoning=zoning,
        strategy=strategy,
        notes=notes,
        strategy_analysis=strategy_analysis,
        rehab_analysis=rehab_analysis,
        build_analysis=build_analysis,
        build_preview_url=build_preview_url,
        build_mockups=build_mockups,
    )


@deal_architect_api_bp.route("v1/deal_architect", methods=["POST"])
@login_required
@role_required("investor", "admin", "platform_admin", "master_admin", "lending_admin")
def v1_deal_architect_underwrite():
    """
    Source-of-truth underwriting endpoint for Deal Architect UI.
    Frontend should only assemble this request and render this response.
    """
    payload = request.get_json(silent=True) or {}

    def _num(key, default=None):
        raw = payload.get(key, default)
        if raw in (None, "", "None"):
            return default
        try:
            return float(raw)
        except (TypeError, ValueError):
            return default

    def _text(key, default=""):
        return str(payload.get(key) or default).strip()

    asking_price = _num("asking_price", 0.0) or 0.0
    if asking_price <= 0:
        return jsonify({"error": "asking_price must be greater than zero."}), 400

    arv = _num("arv", 0.0) or 0.0
    monthly_rent = _num("monthly_rent", 0.0) or 0.0
    down_payment_pct = _num("down_payment_pct", 20.0) or 20.0
    interest_rate = _num("interest_rate", 8.5) or 8.5
    hold_years = _num("hold_years", 5.0) or 5.0
    annual_tax_rate = _num("annual_tax_rate", 0.012)
    annual_insurance_rate = _num("annual_insurance_rate", 0.005)

    comps_in = payload.get("comps") or []
    if not isinstance(comps_in, list):
        comps_in = []

    normalized_comps = []
    for comp in comps_in:
        if not isinstance(comp, dict):
            continue
        normalized_comps.append(
            {
                "address": (comp.get("address") or "").strip(),
                "price": safe_float(comp.get("price"), 0.0),
                "sqft": _normalize_int(comp.get("sqft")),
                "beds": _normalize_int(comp.get("beds")),
                "baths": safe_float(comp.get("baths"), 0.0),
                "distance_miles": safe_float(comp.get("distance_miles"), 0.0),
                "months_ago": _normalize_int(comp.get("months_ago")),
                "notes": (comp.get("notes") or "").strip(),
            }
        )

    comp_prices = [c["price"] for c in normalized_comps if (c.get("price") or 0) > 0]
    comp_avg = (sum(comp_prices) / len(comp_prices)) if comp_prices else None
    valuation_source = "comp_based" if comp_avg else "model_fallback"
    estimated_value = comp_avg if comp_avg else (arv or asking_price * 1.15)

    base_cost_low = asking_price * 1.05
    base_cost_high = asking_price * 1.20
    cost_low = round(base_cost_low, 2)
    cost_high = round(base_cost_high, 2)

    all_in_low = round(cost_low * (1 + down_payment_pct / 100 * 0.05), 2)
    all_in_high = round(cost_high * (1 + down_payment_pct / 100 * 0.05), 2)

    estimated_margin_low = round((estimated_value or 0) - all_in_high, 2)
    estimated_margin_high = round((estimated_value or 0) - all_in_low, 2)

    annual_taxes = (asking_price or 0) * (annual_tax_rate or 0)
    annual_insurance = (asking_price or 0) * (annual_insurance_rate or 0)
    annual_debt_service = (asking_price or 0) * 0.70 * ((interest_rate or 0) / 100)
    noi_estimate = round((monthly_rent * 12) - annual_taxes - annual_insurance, 2)
    dscr_estimate = round((noi_estimate / annual_debt_service), 2) if annual_debt_service > 0 else None

    subscores = {
        "valuation": max(0, min(100, round((estimated_margin_high / max((estimated_value or 1), 1)) * 100 + 50))),
        "cashflow": max(0, min(100, round(((dscr_estimate or 0) / 1.25) * 100))),
        "market": 65,
        "execution": 60 if hold_years <= 5 else 55,
    }
    deal_score = round(sum(subscores.values()) / len(subscores))

    if deal_score >= 78:
        opportunity_tier = "A"
        verdict = "Strong proceed"
    elif deal_score >= 62:
        opportunity_tier = "B"
        verdict = "Proceed with conditions"
    else:
        opportunity_tier = "C"
        verdict = "Caution"

    strengths = []
    risks = []

    if estimated_margin_low > 0:
        strengths.append("Positive downside margin on all-in basis.")
    if (dscr_estimate or 0) >= 1.25:
        strengths.append("Debt coverage is above typical DSCR threshold.")
    if len(normalized_comps) >= 3:
        strengths.append("Comp set has enough observations for directional valuation.")

    if len(normalized_comps) == 0:
        risks.append("No comps were provided; valuation uses fallback assumptions.")
    if len(normalized_comps) > 0 and len(normalized_comps) < 3:
        risks.append("Limited comps reduce confidence in comp-based valuation.")
    if (dscr_estimate or 0) < 1.10:
        risks.append("DSCR is thin and may fail tighter underwriting lanes.")
    if estimated_margin_low <= 0:
        risks.append("Downside margin is negative on all-in high case.")

    recommended_type = "Buy & Hold" if (dscr_estimate or 0) >= 1.15 else "Value-Add / Flip"
    summary = (
        f"{recommended_type} is currently favored based on valuation spread, "
        f"cash-flow coverage, and comp support."
    )

    comp_confidence = 0.0
    if len(normalized_comps) >= 5:
        comp_confidence = 0.85
    elif len(normalized_comps) >= 3:
        comp_confidence = 0.65
    elif len(normalized_comps) > 0:
        comp_confidence = 0.35

    response = {
        "summary": summary,
        "recommended_type": recommended_type,
        "deal_score": deal_score,
        "opportunity_tier": opportunity_tier,
        "cost_low": cost_low,
        "cost_high": cost_high,
        "estimated_value": round(estimated_value or 0, 2),
        "next_step": "Validate underwriting docs and confirm rent/comp assumptions.",
        "meta": {
            "all_in_low": all_in_low,
            "all_in_high": all_in_high,
            "estimated_margin_low": estimated_margin_low,
            "estimated_margin_high": estimated_margin_high,
            "monthly_rent_estimate": round(monthly_rent, 2),
            "noi_estimate": noi_estimate,
            "dscr_estimate": dscr_estimate,
            "valuation_source": valuation_source,
            "market": {
                "city": _text("city"),
                "state": _text("state"),
                "zip_code": _text("zip_code"),
                "interest_rate": interest_rate,
                "hold_years": hold_years,
                "annual_tax_rate": annual_tax_rate,
                "annual_insurance_rate": annual_insurance_rate,
                "market_multipliers": payload.get("market_multipliers") or {},
            },
            "comp_analysis": {
                "normalized_comps": normalized_comps,
                "comp_confidence": round(comp_confidence, 2),
            },
            "verdict_breakdown": {
                "verdict": verdict,
                "subscores": subscores,
                "strengths": strengths,
                "risks": risks,
            },
        },
    }
    return jsonify(response)
    
@investor_bp.route("/deal-architect/analyze", methods=["POST"])
@login_required
@role_required("investor")
def deal_architect_analyze():
    try:
        data = request.get_json(silent=True) or request.form.to_dict() or {}
        deal_id = _normalize_int(data.get("deal_id"))
        deal = None

        if deal_id:
            deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first()
            if not deal:
                return jsonify({"status": "error", "message": "Deal not found"}), 404

        if not RENOVATION_ENGINE_URL:
            return jsonify({"status": "error", "message": "Renovation engine is not configured"}), 500

        def _pick_str(name, *deal_attrs, fallback=""):
            raw = data.get(name)
            if raw is not None and str(raw).strip():
                return str(raw).strip()
            if deal is not None:
                for attr in deal_attrs:
                    existing = getattr(deal, attr, None)
                    if existing is not None and str(existing).strip():
                        return str(existing).strip()
            return fallback

        def _pick_float(name, *deal_attrs):
            raw = data.get(name)
            if raw not in (None, "", "None"):
                try:
                    return float(str(raw).replace(",", "").replace("$", "").strip())
                except (TypeError, ValueError):
                    return None
            if deal is not None:
                for attr in deal_attrs:
                    existing = getattr(deal, attr, None)
                    if existing not in (None, "", "None"):
                        try:
                            return float(existing)
                        except (TypeError, ValueError):
                            continue
            return None

        def _pick_int(name, *deal_attrs):
            raw = data.get(name)
            if raw not in (None, "", "None"):
                try:
                    return int(float(str(raw).replace(",", "").strip()))
                except (TypeError, ValueError):
                    return None
            if deal is not None:
                for attr in deal_attrs:
                    existing = getattr(deal, attr, None)
                    if existing not in (None, "", "None"):
                        try:
                            return int(float(existing))
                        except (TypeError, ValueError):
                            continue
            return None

        comps = data.get("comps")
        if not isinstance(comps, list):
            comps = safe_json_loads(data.get("comps_json"), default=[])
        comps = comps if isinstance(comps, list) else []

        payload = {
            "project_name": _pick_str("project_name", "title", "address", "property_address") or None,
            "description": _pick_str("description", "notes"),
            "property_type": _pick_str("property_type", "asset_type", fallback="single_family") or None,
            "lot_size": _pick_str("lot_size") or None,
            "zoning": _pick_str("zoning") or None,
            "asking_price": _pick_float("asking_price", "purchase_price"),
            "square_feet_target": _pick_int("square_feet_target", "square_feet", "sqft"),
            "city": _pick_str("city") or None,
            "state": _pick_str("state") or None,
            "zip_code": _pick_str("zip_code", "zip") or None,
            "arv": _pick_float("arv"),
            "monthly_rent": _pick_float("monthly_rent", "estimated_rent"),
            "down_payment_pct": _normalize_percentage(data.get("down_payment_pct")) or 0.25,
            "interest_rate": _normalize_percentage(data.get("interest_rate")) or 0.08,
            "hold_years": _pick_int("hold_years") or 1,
            "annual_tax_rate": _normalize_percentage(data.get("annual_tax_rate")),
            "annual_insurance_rate": _normalize_percentage(data.get("annual_insurance_rate")),
            "market_cost_multiplier": _pick_float("market_cost_multiplier"),
            "market_value_multiplier": _pick_float("market_value_multiplier"),
            "market_rent_multiplier": _pick_float("market_rent_multiplier"),
            "market_risk_adjustment": _pick_int("market_risk_adjustment"),
            "comps": comps,
        }

        if not payload["description"]:
            return jsonify({"status": "error", "message": "description is required"}), 400

        engine_data = _post_renovation_engine_json("/v1/deal_architect", payload, timeout=60) or {}

        if deal is not None:
            results = _deal_results(deal)
            results["strategy_analysis"] = engine_data
            _set_deal_results(deal, results)

            if hasattr(deal, "recommended_strategy"):
                deal.recommended_strategy = engine_data.get("recommended_type") or getattr(deal, "recommended_strategy", None)
            if hasattr(deal, "strategy") and not getattr(deal, "strategy", None):
                deal.strategy = engine_data.get("recommended_type") or getattr(deal, "strategy", None)
            if hasattr(deal, "deal_score"):
                deal.deal_score = engine_data.get("deal_score") or getattr(deal, "deal_score", None)
            if hasattr(deal, "purchase_price") and payload.get("asking_price") is not None:
                deal.purchase_price = payload["asking_price"]
            if hasattr(deal, "arv") and payload.get("arv") is not None:
                deal.arv = payload["arv"]
            if hasattr(deal, "estimated_rent") and payload.get("monthly_rent") is not None:
                deal.estimated_rent = payload["monthly_rent"]
            if hasattr(deal, "lot_size") and payload.get("lot_size"):
                deal.lot_size = payload["lot_size"]
            if hasattr(deal, "zoning") and payload.get("zoning"):
                deal.zoning = payload["zoning"]

            db.session.commit()

        return jsonify(engine_data)

    except Exception as e:
        current_app.logger.exception("deal_architect_analyze failed")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@investor_bp.route("/deal-architect/strategy", methods=["POST"])
@login_required
@role_required("investor")
def deal_architect_strategy():
    try:
        data = request.get_json(silent=True) or request.form

        deal_id = _normalize_int(data.get("deal_id"))
        if not deal_id:
            return jsonify({"success": False, "error": "deal_id is required"}), 400

        deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first()
        if not deal:
            return jsonify({"success": False, "error": "Deal not found"}), 404

        purchase_price = float(data.get("purchase_price") or deal.purchase_price or 0)
        arv = float(data.get("arv") or deal.arv or 0)
        estimated_rent = float(data.get("estimated_rent") or deal.estimated_rent or 0)
        rehab_cost = float(data.get("rehab_cost") or deal.rehab_cost or 0)

        total_cost = purchase_price + rehab_cost
        projected_profit = (arv - total_cost) if arv else 0
        rent_ratio = (estimated_rent / purchase_price) if purchase_price > 0 else 0

        recommended_strategy = "Flip"
        reason = "Projected resale spread makes this best suited for a flip."

        if estimated_rent > 0 and rent_ratio >= 0.009:
            recommended_strategy = "Rental"
            reason = "Rental income appears strong relative to acquisition cost."
        elif arv > 0 and total_cost > 0 and arv >= total_cost * 1.25:
            recommended_strategy = "BRRRR"
            reason = "Value spread supports rehab and refinance potential."
        elif (deal.strategy or "").lower() == "development":
            recommended_strategy = "Development"
            reason = "Deal is positioned as a development opportunity."

        deal_score = 50

        if projected_profit > 75000:
            deal_score += 20
        elif projected_profit > 40000:
            deal_score += 12
        elif projected_profit > 20000:
            deal_score += 6

        if rent_ratio >= 0.01:
            deal_score += 10
        elif rent_ratio >= 0.008:
            deal_score += 5

        rehab_ratio = (rehab_cost / purchase_price) if purchase_price > 0 else 0
        if rehab_ratio and rehab_ratio < 0.15:
            deal_score += 10
        elif rehab_ratio and rehab_ratio < 0.30:
            deal_score += 5
        elif rehab_ratio >= 0.30:
            deal_score -= 8

        deal_score = max(1, min(100, deal_score))

        deal.purchase_price = purchase_price
        deal.arv = arv
        deal.estimated_rent = estimated_rent
        deal.rehab_cost = rehab_cost
        deal.recommended_strategy = recommended_strategy
        deal.deal_score = deal_score

        results = _deal_results(deal)
        results["strategy_analysis"] = {
            "recommended_strategy": recommended_strategy,
            "reason": reason,
            "purchase_price": purchase_price,
            "arv": arv,
            "estimated_rent": estimated_rent,
            "rehab_cost": rehab_cost,
            "projected_profit": round(projected_profit, 2),
            "deal_score": deal_score,
        }
        _set_deal_results(deal, results)

        db.session.commit()

        return jsonify({
            "success": True,
            "recommended_strategy": recommended_strategy,
            "reason": reason,
            "projected_profit": round(projected_profit, 2),
            "deal_score": deal_score,
        })

    except Exception as e:
        current_app.logger.exception("Deal strategy analysis failed")
        return jsonify({
            "success": False,
            "error": f"Analysis failed: {str(e)}"
        }), 500


@investor_bp.route("/rehab-architect/generate-scope", methods=["POST"])
@login_required
@role_required("investor")
def rehab_architect_generate_scope():
    data = request.get_json(silent=True) or request.form

    deal_id = data.get("deal_id")
    if not deal_id:
        return jsonify({"error": "deal_id is required"}), 400

    deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first()
    if not deal:
        return jsonify({"error": "Deal not found"}), 404

    sqft = int(float(data.get("sqft") or 1500))
    rehab_level = (data.get("rehab_level") or "medium").lower()
    image_url = (data.get("image_url") or getattr(deal, "image_url", "") or "").strip()

    cost_per_sqft = {
        "light": 20,
        "medium": 35,
        "heavy": 60
    }

    selected_cost_per_sqft = cost_per_sqft.get(rehab_level, 35)
    estimated_rehab_cost = sqft * selected_cost_per_sqft

    scope = {
        "rehab_level": rehab_level,
        "sqft": sqft,
        "cost_per_sqft": selected_cost_per_sqft,
        "line_items": {
            "kitchen": 18000 if rehab_level != "light" else 9000,
            "bathroom": 9000 if rehab_level != "light" else 4500,
            "flooring": 6500 if rehab_level != "light" else 3200,
            "paint": 3000,
            "exterior": 4500 if rehab_level == "heavy" else 2000,
        }
    }

    external_scope_result = None

    if image_url:
        try:
            if SCOPE_ENGINE_URL:
                external_scope_result = _post_scope_engine_json(
                    "/v1/rehab_scope",
                    {"image_url": image_url},
                    timeout=SCOPE_TIMEOUT,
                )

                estimated_rehab_cost = (
                    external_scope_result.get("cost_high")
                    or external_scope_result.get("cost_low")
                    or estimated_rehab_cost
                )

                scope = {
                    "rehab_level": rehab_level,
                    "sqft": sqft,
                    "cost_per_sqft": round(estimated_rehab_cost / sqft, 2) if sqft else selected_cost_per_sqft,
                    "rooms": external_scope_result.get("rooms", []),
                    "plan": external_scope_result.get("plan", ""),
                    "line_items": scope.get("line_items", {})
                }

        except Exception:
            current_app.logger.exception("Scope engine rehab call failed")

    deal.rehab_cost = estimated_rehab_cost
    deal.rehab_scope_json = scope

    existing_results = _deal_results(deal)
    existing_results["rehab_analysis"] = {
        "estimated_rehab_cost": estimated_rehab_cost,
        "scope": scope
    }
    existing_results["rehab_summary"] = {
        "scope": rehab_level,
        "total": estimated_rehab_cost,
        "cost_per_sqft": round(estimated_rehab_cost / sqft, 2) if sqft else 0,
        "items": scope.get("line_items", {})
    }

    if external_scope_result:
        existing_results["rehab_analysis_external"] = external_scope_result

        external_arv = external_scope_result.get("arv")
        if external_arv and not deal.arv:
            deal.arv = external_arv

    _set_deal_results(deal, existing_results)
    db.session.commit()

    return jsonify({
        "success": True,
        "deal_id": deal.id,
        "estimated_rehab_cost": estimated_rehab_cost,
        "scope": scope,
        "external_scope_used": bool(external_scope_result),
        "external_scope_result": external_scope_result
    })

# =========================================================
# REHAB IMAGE UPLOAD
# =========================================================

@investor_bp.route("/renovation_upload", methods=["POST"])
@login_required
@role_required("investor")
def renovation_upload():
    file = request.files.get("photo")
    deal_id = _normalize_int(request.form.get("deal_id"))

    if not file or not deal_id:
        return jsonify({"status": "error", "message": "Missing photo or deal_id."}), 400

    deal = _get_owned_deal_or_404(deal_id)

    try:
        raw = file.read()
        if not raw:
            return jsonify({"status": "error", "message": "Empty file."}), 400

        before_url = _upload_before_image(raw)
        _save_before_url_to_deal(deal, before_url)

        return jsonify({
            "status": "ok",
            "url": before_url,
            "deal_id": deal.id,
        })

    except Exception as e:
        current_app.logger.exception("renovation_upload failed")
        return jsonify({"status": "error", "message": str(e)}), 500


# =========================================================
# PHOTO RENOVATION VISUALIZER
# =========================================================

@investor_bp.route("/deal-studio/rehab-studio/generate", methods=["POST"])
@login_required
@role_required("investor")
def deal_rehab_generate():
    deal = None
    rehab_scope_result = {}

    try:
        data = request.form.to_dict() or {}

        deal_id = _normalize_int(data.get("deal_id"))
        if deal_id:
            deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first()
            if not deal:
                return jsonify({
                    "status": "error",
                    "message": "Deal not found or not authorized."
                }), 404

            if _deal_render_lock_active(deal):
                return jsonify({
                    "status": "error",
                    "message": "A rehab render is already in progress for this deal."
                }), 409

            _set_deal_render_processing(deal)
            db.session.commit()

        preset = (data.get("preset") or "luxury").strip()
        mode = (data.get("mode") or "hgtv").strip()
        room_type = (data.get("room_type") or "living room").strip()
        notes = (data.get("notes") or "").strip()
        rehab_level = (data.get("rehab_level") or "medium").strip().lower()
        save_to_deal = str(data.get("save_to_deal") or "true").lower() in ("1", "true", "yes", "on")

        before_image = request.files.get("before_image")
        image_url = (data.get("image_url") or "").strip()
        image_base64 = ""

        raw_before = None
        before_uploaded_url = ""

        if before_image:
            raw_before = before_image.read()
            if not raw_before:
                raise RuntimeError("Empty before image upload.")

            image_base64 = base64.b64encode(raw_before).decode("utf-8")

            try:
                before_uploaded_url = _upload_before_image(raw_before)
            except Exception:
                before_uploaded_url = ""

        elif image_url:
            try:
                raw_before = download_image_bytes(image_url)
                if raw_before:
                    image_base64 = base64.b64encode(raw_before).decode("utf-8")
                    before_uploaded_url = image_url
            except Exception:
                raw_before = None

        elif deal is not None:
            results = _deal_results(deal)
            rehab_project = results.get("rehab_project", {}) or {}
            rehab_before = rehab_project.get("before", {}) or {}

            saved_before_url = (rehab_before.get("image_url") or "").strip()
            if saved_before_url:
                try:
                    raw_before = download_image_bytes(saved_before_url)
                    if raw_before:
                        image_base64 = base64.b64encode(raw_before).decode("utf-8")
                        before_uploaded_url = saved_before_url
                except Exception:
                    raw_before = None

        if not image_base64:
            raise RuntimeError("Provide a before photo or saved rehab before image.")

        property_type = (
            (data.get("property_type") or "").strip()
            or (getattr(deal, "resolved_json", {}) or {}).get("property", {}).get("property_type", "")
            or "residential property"
        )
        stable_seed = _stable_render_seed(
            "rehab",
            getattr(deal, "id", None),
            before_uploaded_url or image_url,
            preset,
            mode,
            room_type,
            rehab_level,
            notes,
        )

        payload = {
            "preset": preset,
            "mode": mode,
            "room_type": room_type,
            "room_focus": room_type,
            "rehab_level": rehab_level,
            "property_type": property_type,
            "design_style": preset,
            "desired_updates": notes,
            "keep_layout": True,
            "preserve_structure": True,
            "image_base64": image_base64,
            "image_url": "",
            "count": 1,
            "steps": 22,
            "guidance": 7.2,
            "strength": float(data.get("strength") or 0.58),
            "width": 768,
            "height": 768,
            "notes": notes,
            "seed": stable_seed,
        }

        engine_json = _post_renovation_engine_json(
            "/v1/renovate",
            payload,
            timeout=RENDER_TIMEOUT,
        )

        images_b64 = engine_json.get("images_base64") or []
        if not images_b64:
            raise RuntimeError("Renovation engine returned no images.")

        render_batch_id = uuid.uuid4().hex
        after_urls = _upload_after_images_from_b64(images_b64, render_batch_id)

        if not after_urls:
            raise RuntimeError("Renovation generated but uploads failed.")

        concept_entry = {
            "image_url": after_urls[0],
            "images": after_urls,
            "preset": preset,
            "mode": mode,
            "room_type": room_type,
            "rehab_level": rehab_level,
            "notes": notes,
            "seed": engine_json.get("seed") or stable_seed,
            "job_id": engine_json.get("job_id"),
            "meta": engine_json.get("meta") or {},
        }

        before_result = {
            "image_url": before_uploaded_url,
        }

        scope_image_url = before_uploaded_url or image_url
        if scope_image_url and SCOPE_ENGINE_URL:
            try:
                rehab_scope_result = _post_scope_engine_json(
                    "/v1/rehab_scope",
                    {"image_url": scope_image_url},
                    timeout=60,
                ) or {}
            except Exception:
                current_app.logger.exception("Rehab Studio scope analysis failed")
                rehab_scope_result = {}

        if save_to_deal and deal is not None:
            results = _deal_results(deal)
            rehab_project = results.get("rehab_project", {}) or {}

            rehab_project["before"] = before_result

            concepts = rehab_project.get("concepts", []) or []
            concepts = [
                c for c in concepts
                if not (
                    (c.get("preset") or "").strip().lower() == preset.lower()
                    and (c.get("mode") or "").strip().lower() == mode.lower()
                    and (c.get("room_type") or "").strip().lower() == room_type.lower()
                )
            ]
            concepts.append(concept_entry)

            rehab_project["latest"] = concept_entry
            rehab_project["concepts"] = concepts

            if rehab_scope_result:
                results["rehab_scope"] = rehab_scope_result
                if hasattr(deal, "rehab_scope_json"):
                    deal.rehab_scope_json = rehab_scope_result
                if hasattr(deal, "rehab_cost") and rehab_scope_result.get("cost_high") is not None:
                    deal.rehab_cost = rehab_scope_result.get("cost_high")
                if hasattr(deal, "arv") and rehab_scope_result.get("arv") and not getattr(deal, "arv", None):
                    deal.arv = rehab_scope_result.get("arv")

            results["rehab_project"] = rehab_project
            _set_deal_results(deal, results)

        if deal is not None:
            _clear_deal_render_processing(deal)

        db.session.commit()

        return jsonify({
            "status": "ok",
            "before_result": before_result,
            "concept_result": concept_entry,
            "rehab_scope": rehab_scope_result,
            "deal_id": deal.id if deal else None,
            "saved_to_deal": bool(save_to_deal and deal is not None),
        })

    except Exception as e:
        current_app.logger.exception("Rehab Studio generation error")

        if deal is not None:
            try:
                _clear_deal_render_processing(deal)
                db.session.commit()
            except Exception:
                db.session.rollback()

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# =========================================================
# SAVE MOCKUPS MANUALLY
# =========================================================

@investor_bp.route("/deals/<int:deal_id>/mockups/save", methods=["POST"])
@investor_bp.route("/deals/<int:deal_id>/mockups/save_legacy", methods=["POST"])
@login_required
@role_required("investor")
def save_renovation_mockups(deal_id):
    deal = _get_owned_deal_or_404(deal_id)
    data = request.get_json(silent=True) or {}

    before_url = (data.get("before_url") or "").strip()
    images = data.get("images") or []
    style_preset = (data.get("style_preset") or data.get("preset") or "").strip()
    style_prompt = (data.get("style_prompt") or data.get("prompt") or "").strip()

    if not images or not isinstance(images, list):
        return jsonify({"status": "error", "message": "No images provided."}), 400

    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    ip_id = ip.id if ip else None

    saved = 0
    for img in images[:8]:
        img = (img or "").strip()
        if not img:
            continue

        row = RenovationMockup(
            user_id=current_user.id,
            deal_id=deal.id,
            saved_property_id=getattr(deal, "saved_property_id", None),
            before_url=before_url or None,
            after_url=img,
            style_preset=style_preset or None,
            style_prompt=style_prompt or None,
        )

        if hasattr(row, "investor_profile_id"):
            row.investor_profile_id = ip_id

        if hasattr(row, "property_id"):
            row.property_id = getattr(deal, "property_id", None)

        db.session.add(row)
        saved += 1

    db.session.commit()
    return jsonify({"status": "ok", "saved": saved})


# =========================================================
# SELECT DESIGN / FEATURE DESIGN
# =========================================================

@investor_bp.route("/deals/<int:deal_id>/design/select", methods=["POST"])
@investor_bp.route("/deals/<int:deal_id>/select_design", methods=["POST"])
@login_required
@role_required("investor")
def deal_select_design(deal_id):
    deal = _get_owned_deal_or_404(deal_id)

    after_url = (request.form.get("after_url") or "").strip()
    before_url = (request.form.get("before_url") or "").strip()

    if not after_url:
        return jsonify({"status": "error", "message": "Missing after_url."}), 400

    owned = RenovationMockup.query.filter_by(
        user_id=current_user.id,
        deal_id=deal.id,
        after_url=after_url
    ).first()

    if not owned and getattr(deal, "saved_property_id", None):
        owned = RenovationMockup.query.filter_by(
            user_id=current_user.id,
            saved_property_id=deal.saved_property_id,
            after_url=after_url
        ).first()

    if not owned:
        return jsonify({"status": "error", "message": "Design not found for this deal."}), 404

    if hasattr(deal, "final_after_url"):
        deal.final_after_url = after_url
    if before_url and hasattr(deal, "final_before_url"):
        deal.final_before_url = before_url

    db.session.commit()
    return jsonify({"status": "ok", "after_url": after_url})


@investor_bp.route("/deals/<int:deal_id>/rehab/feature", methods=["POST"])
@login_required
@role_required("investor")
def deal_feature_reveal(deal_id):
    deal = _get_owned_deal_or_404(deal_id)

    after_url = (request.form.get("after_url") or "").strip()
    before_url = (request.form.get("before_url") or "").strip()
    style_preset = (request.form.get("style_preset") or "").strip()
    style_prompt = (request.form.get("style_prompt") or "").strip()

    if not after_url:
        return jsonify({"status": "error", "message": "after_url is required."}), 400

    featured = _set_featured_rehab(
        deal=deal,
        after_url=after_url,
        before_url=before_url,
        style_preset=style_preset,
        style_prompt=style_prompt,
    )

    return jsonify({
        "status": "ok",
        "deal_id": deal.id,
        "featured": featured,
    })


# =========================================================
# SHARE DESIGN TO PARTNERS
# =========================================================

@investor_bp.route("/deals/<int:deal_id>/design/share", methods=["POST"])
@investor_bp.route("/deals/<int:deal_id>/share_design", methods=["POST"])
@login_required
@role_required("investor")
def deal_share_design(deal_id):
    deal = _get_owned_deal_or_404(deal_id)

    image_url = (request.form.get("image_url") or "").strip() or (getattr(deal, "final_after_url", "") or "")
    note = (request.form.get("note") or "").strip()

    raw_partner_ids = request.form.get("partner_ids") or ""
    partner_ids = split_ids(raw_partner_ids) if "split_ids" in globals() else [
        _normalize_int(x) for x in raw_partner_ids.split(",") if _normalize_int(x)
    ]

    if not image_url:
        return jsonify({"status": "error", "message": "Select a design first."}), 400
    if not partner_ids:
        return jsonify({"status": "error", "message": "Choose at least one partner."}), 400

    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    ip_id = ip.id if ip else None

    now = datetime.utcnow()
    partners = (
        Partner.query
        .filter(Partner.id.in_(partner_ids))
        .filter(Partner.active == True)
        .filter(Partner.approved == True)
        .filter(Partner.paid_until >= now)
        .all()
    )

    if not partners:
        return jsonify({"status": "error", "message": "No valid partners selected."}), 400

    deal_link = url_for("investor.deal_detail", deal_id=deal.id, _external=True)
    rehab_link = url_for("investor.deal_rehab", deal_id=deal.id, _external=True)
    reveal_link = url_for("investor.deal_reveal", deal_id=deal.id, _external=True)

    sent = 0
    for p in partners:
        msg = (
            (note + "\n\n" if note else "") +
            f"Selected renovation design:\n{image_url}\n\n"
            f"Rehab Studio:\n{rehab_link}\n"
            f"Deal:\n{deal_link}\n"
            f"Reveal:\n{reveal_link}\n"
        )

        existing_q = PartnerConnectionRequest.query.filter_by(
            partner_id=p.id,
            status="pending"
        )

        if hasattr(PartnerConnectionRequest, "investor_user_id"):
            existing_q = existing_q.filter_by(investor_user_id=current_user.id)
        else:
            existing_q = existing_q.filter_by(borrower_user_id=current_user.id)

        existing = existing_q.order_by(PartnerConnectionRequest.created_at.desc()).first()

        if existing and (getattr(existing, "message", "") or "").strip() == msg.strip():
            continue

        req = PartnerConnectionRequest(
            partner_id=p.id,
            category=getattr(p, "category", None),
            message=msg,
            status="pending",
        )

        if "_set_if_attr" in globals():
            if not _set_if_attr(req, "investor_user_id", current_user.id):
                _set_if_attr(req, "borrower_user_id", current_user.id)

            if ip_id is not None:
                if not _set_if_attr(req, "investor_profile_id", ip_id):
                    _set_if_attr(req, "borrower_profile_id", ip_id)

        db.session.add(req)
        sent += 1

    db.session.commit()
    return jsonify({"status": "ok", "sent": sent, "failed": 0})


# =========================================================
# REVEAL
# =========================================================

@investor_bp.route("/deals/<int:deal_id>/reveal", methods=["GET"])
@investor_bp.route("/deal/<int:deal_id>/reveal", methods=["GET"])
@login_required
@role_required("investor")
def deal_reveal(deal_id):
    deal = _get_owned_deal_or_404(deal_id)
    selected_after_url = (request.args.get("after_url") or "").strip()

    mockups = _get_rehab_mockups_for_deal(deal)
    featured = _featured_rehab_data(deal)
    featured_after = (featured.get("after_url") or "").strip()

    selected_mockup = None
    featured_mockup = None

    for m in mockups:
        if selected_after_url and (m.after_url or "").strip() == selected_after_url:
            selected_mockup = m
        if featured_after and (m.after_url or "").strip() == featured_after:
            featured_mockup = m

    return render_template(
        "investor/deal_reveal.html",
        deal=deal,
        deal_id=deal.id,
        mockups=mockups,
        selected_mockup=selected_mockup,
        featured_mockup=featured_mockup,
        featured=featured,
    )


@investor_bp.route("/deals/<int:deal_id>/reveal/publish", methods=["POST"])
@login_required
@role_required("investor")
def publish_reveal(deal_id):
    deal = _get_owned_deal_or_404(deal_id)

    if not getattr(deal, "reveal_public_id", None):
        deal.reveal_public_id = uuid.uuid4().hex[:16]

    deal.reveal_is_public = True
    deal.reveal_published_at = datetime.utcnow()
    db.session.commit()

    public_url = url_for("investor.public_reveal", public_id=deal.reveal_public_id, _external=True)
    return jsonify({"status": "ok", "public_url": public_url})


@investor_bp.route("/reveal/<string:public_id>", methods=["GET"])
def public_reveal(public_id):
    deal = Deal.query.filter_by(reveal_public_id=public_id, reveal_is_public=True).first_or_404()

    mockups = (
        RenovationMockup.query
        .filter_by(deal_id=deal.id)
        .order_by(RenovationMockup.created_at.desc())
        .all()
    )

    featured = _featured_rehab_data(deal)

    return render_template(
        "public/deal_reveal_public.html",
        deal=deal,
        mockups=mockups,
        featured=featured,
    )


# =========================================================
# AI REHAB SCOPE
# =========================================================

@investor_bp.route("/ai/rehab-scope/jobs", methods=["POST"])
@login_required
@role_required("investor")
def create_rehab_scope_job():
    data = request.get_json(silent=True) or {}
    plan_url = (data.get("image_url") or "").strip()
    deal_id = _normalize_int(data.get("deal_id"))

    if not plan_url:
        return jsonify({"status": "error", "message": "image_url is required."}), 400

    job = RehabJob(
        deal_id=deal_id,
        user_id=current_user.id,
        plan_url=plan_url,
        status="pending"
    )
    db.session.add(job)
    db.session.commit()

    return jsonify({"status": "ok", "job_id": job.id})


@investor_bp.route("/ai/rehab-scope/jobs/<int:job_id>", methods=["GET"])
@login_required
@role_required("investor")
def get_rehab_scope_job(job_id):
    job = RehabJob.query.filter_by(id=job_id, user_id=current_user.id).first_or_404()

    return jsonify({
        "status": job.status,
        "plan": getattr(job, "result_plan", None),
        "cost_low": getattr(job, "result_cost_low", None),
        "cost_high": getattr(job, "result_cost_high", None),
        "arv": getattr(job, "result_arv", None),
        "images": getattr(job, "result_images", None),
    })


@investor_bp.route("/ai/rehab-scope/analyze", methods=["POST"])
@login_required
@role_required("investor")
def ai_rehab_scope():
    data = request.get_json(silent=True) or {}
    image_url = (data.get("image_url") or "").strip()

    if not image_url:
        return jsonify({"status": "error", "message": "image_url is required."}), 400

    try:
        if not SCOPE_ENGINE_URL:
            return jsonify({"status": "error", "message": "Scope engine is not configured."}), 500

        return jsonify(_post_scope_engine_json("/v1/rehab_scope", {"image_url": image_url}, timeout=60))

    except Exception as e:
        current_app.logger.exception("ai_rehab_scope failed")
        return jsonify({"status": "error", "message": str(e)}), 500


# =========================================================
# EXPORTS
# =========================================================

@investor_bp.route("/deals/<int:deal_id>/export/report", methods=["GET"])
@investor_bp.route("/deals/<int:deal_id>/export-report", methods=["GET"])
@login_required
@role_required("investor")
def export_deal_report_pro(deal_id):
    deal = _get_owned_deal_or_404(deal_id)

    r = deal.results_json or {}
    resolved = deal.resolved_json or {}
    rehab = _get_rehab_export_payload(deal)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER
    y = height - 50

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "RAVLO Deal Report")
    y -= 22

    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Title: {deal.title or '—'}"); y -= 14
    c.drawString(50, y, f"Property ID: {getattr(deal, 'property_id', None) or '—'}"); y -= 14
    c.drawString(50, y, f"Strategy: {getattr(deal, 'strategy', None) or '—'}"); y -= 14
    if getattr(deal, "created_at", None):
        c.drawString(50, y, f"Created: {deal.created_at.strftime('%Y-%m-%d %H:%M')}"); y -= 22
    else:
        y -= 22

    prop = (resolved.get("property") or {}) if isinstance(resolved, dict) else {}
    addr = prop.get("address")
    city = prop.get("city")
    state = prop.get("state")
    zipc = prop.get("zip")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Property Summary"); y -= 16
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Address: {addr or '—'}"); y -= 14
    c.drawString(50, y, f"City/State/Zip: {city or '—'}, {state or '—'} {zipc or ''}"); y -= 18

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Key Results"); y -= 16
    c.setFont("Helvetica", 10)

    if "profit" in r:
        c.drawString(50, y, f"Flip Profit: {_fmt_money(r.get('profit'))}")
        y -= 14
    if "net_cashflow" in r:
        c.drawString(50, y, f"Rental Net Cashflow (mo): {_fmt_money(r.get('net_cashflow'))}")
        y -= 14
    if "net_monthly" in r:
        c.drawString(50, y, f"Airbnb Net Monthly: {_fmt_money(r.get('net_monthly'))}")
        y -= 14

    y -= 10

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Rehab Summary"); y -= 16
    c.setFont("Helvetica", 10)

    if isinstance(rehab, dict) and rehab:
        total_rehab = rehab.get("total") or rehab.get("estimated_rehab_cost")
        scope_value = rehab.get("scope")
        cpsf = rehab.get("cost_per_sqft")

        if isinstance(scope_value, dict):
            scope_label = scope_value.get("rehab_level") or "Detailed scope"
        else:
            scope_label = scope_value or "—"

        c.drawString(50, y, f"Scope: {scope_label}"); y -= 14
        c.drawString(50, y, f"Total Rehab: {_fmt_money(total_rehab)}"); y -= 14
        c.drawString(50, y, f"Cost per Sqft: {_fmt_money(cpsf)}"); y -= 14
    else:
        c.drawString(50, y, "No rehab summary available."); y -= 14

    c.showPage()
    c.save()

    buffer.seek(0)
    filename = f"ravlo_deal_report_{deal.id}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")


@investor_bp.route("/deals/<int:deal_id>/export/rehab-scope", methods=["GET"])
@investor_bp.route("/deals/<int:deal_id>/export-rehab-scope", methods=["GET"])
@login_required
@role_required("investor")
def export_rehab_scope(deal_id):
    deal = _get_owned_deal_or_404(deal_id)

    rehab = _get_rehab_export_payload(deal)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER
    y = height - 50

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "RAVLO Rehab Scope"); y -= 22

    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Deal: {deal.title or '—'}"); y -= 14
    c.drawString(50, y, f"Property ID: {getattr(deal, 'property_id', None) or '—'}"); y -= 14
    c.drawString(50, y, f"Strategy: {getattr(deal, 'strategy', None) or '—'}"); y -= 22

    if not isinstance(rehab, dict) or not rehab:
        c.drawString(50, y, "No rehab summary available for this deal.")
        c.showPage()
        c.save()
        buffer.seek(0)
        filename = f"ravlo_rehab_scope_{deal.id}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
        return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")

    total_rehab = rehab.get("total") or rehab.get("estimated_rehab_cost")
    cpsf = rehab.get("cost_per_sqft")

    scope_value = rehab.get("scope")
    if isinstance(scope_value, dict):
        scope_label = scope_value.get("rehab_level") or "Detailed scope"
        items = scope_value.get("line_items") or {}
    else:
        scope_label = scope_value or "—"
        items = rehab.get("items") or {}

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Summary"); y -= 16
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Scope: {scope_label}"); y -= 14
    c.drawString(50, y, f"Total Rehab: {_fmt_money(total_rehab)}"); y -= 14
    c.drawString(50, y, f"Cost per Sqft: {_fmt_money(cpsf)}"); y -= 18

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Selected Items"); y -= 16
    c.setFont("Helvetica", 10)

    if isinstance(items, dict) and items:
        for k, v in items.items():
            if y < 80:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 10)

            if isinstance(v, dict):
                level = v.get("level")
                cost = v.get("cost")
                line = f"- {str(k).capitalize()}: {str(level).capitalize() if level else '—'} | {_fmt_money(cost)}"
            else:
                line = f"- {str(k).capitalize()}: {_fmt_money(v)}"

            c.drawString(50, y, line)
            y -= 14
    else:
        c.drawString(50, y, "No item selections found.")
        y -= 14

    c.showPage()
    c.save()

    buffer.seek(0)
    filename = f"ravlo_rehab_scope_{deal.id}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")

# =========================================================
# 💬 INVESTOR • MESSAGES
# =========================================================

@investor_bp.route("/messages", methods=["GET"])
@login_required
@role_required("investor")
def messages():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    from LoanMVP.models.user_model import User

    officers = User.query.filter(
        User.role.in_(["loan_officer", "processor", "underwriter"])
    ).order_by(User.first_name.asc(), User.last_name.asc()).all()

    allowed_receiver_ids = {u.id for u in officers}

    receiver_id = request.args.get("receiver_id", type=int)
    msgs = []

    if receiver_id:
        if receiver_id not in allowed_receiver_ids:
            flash("⚠️ You are not allowed to view that conversation.", "warning")
            return redirect(url_for("investor.messages"))

        msgs = Message.query.filter(
            (
                (Message.sender_id == current_user.id) &
                (Message.receiver_id == receiver_id)
            ) |
            (
                (Message.sender_id == receiver_id) &
                (Message.receiver_id == current_user.id)
            )
        ).order_by(Message.created_at.asc()).all()

    return render_template(
        "investor/messages.html",
        investor=ip,
        officers=officers,
        messages=msgs,
        selected_receiver=receiver_id,
        title="Messages",
        active_tab="messages"
    )


@investor_bp.route("/messages/send", methods=["POST"])
@investor_bp.route("/messages/send", methods=["POST"])
@login_required
@role_required("investor")
def send_message():
    content = (request.form.get("content") or "").strip()
    receiver_id = request.form.get("receiver_id", type=int)

    from LoanMVP.models.user_model import User

    if not receiver_id or not content:
        flash("⚠️ Please select a recipient and enter a message.", "warning")
        return redirect(url_for("investor.messages"))

    allowed_receiver = User.query.filter(
        User.id == receiver_id,
        User.role.in_(["loan_officer", "processor", "underwriter"])
    ).first()

    if not allowed_receiver:
        flash("⚠️ Invalid message recipient.", "danger")
        return redirect(url_for("investor.messages"))

    db.session.add(Message(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content=content,
        created_at=datetime.utcnow(),
    ))
    db.session.commit()

    flash("📩 Message sent!", "success")
    return redirect(url_for("investor.messages", receiver_id=receiver_id))


# =========================================================
# 🤖 INVESTOR • AI HUB / ASK AI
# =========================================================

@investor_bp.route("/ai", methods=["GET"])
@investor_bp.route("/ask-ai", methods=["GET"])
@login_required
@role_required("investor")
def ask_ai_page():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    interactions = (AIAssistantInteraction.query
        .filter_by(user_id=current_user.id)
        .order_by(AIAssistantInteraction.timestamp.desc())
        .all())

    prefill = request.args.get("prefill", "")

    class DummyForm:
        def hidden_tag(self): return ""

    dummy_question = type("obj", (), {"data": prefill})()
    form = DummyForm()
    form.question = dummy_question
    form.submit = None

    return render_template(
        "investor/ask_ai.html",
        investor=ip,
        prefill=prefill,
        form=form,
        interactions=interactions,
        title="Ravlo AI",
        active_tab="ai"
    )


@investor_bp.route("/ai", methods=["POST"])
@investor_bp.route("/ask-ai", methods=["POST"])
@login_required
@role_required("investor")
def ask_ai_post():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    payload = request.get_json(silent=True) if request.is_json else None
    question = ((payload or {}).get("question") if payload is not None else request.form.get("question")) or ""
    parent_id = ((payload or {}).get("parent_id") if payload is not None else request.form.get("parent_id"))

    assistant = AIAssistant()
    ai_reply = assistant.generate_reply(question, "investor_ai")

    chat = AIAssistantInteraction(
        user_id=current_user.id,
        question=question,
        response=ai_reply,
        parent_id=parent_id,
        timestamp=datetime.utcnow(),
    )

    # schema-safe: store investor_profile_id if exists, else borrower_profile_id
    if ip:
        if hasattr(chat, "investor_profile_id"):
            chat.investor_profile_id = ip.id
        elif hasattr(chat, "borrower_profile_id"):
            chat.borrower_profile_id = ip.id

    db.session.add(chat)
    db.session.commit()

    next_steps = assistant.generate_reply(
        f"Suggest next steps after answering: {question}.",
        "investor_next_steps",
    )
    upload_trigger = "document" in question.lower() or "upload" in question.lower()

    interactions = (AIAssistantInteraction.query
        .filter_by(user_id=current_user.id)
        .order_by(AIAssistantInteraction.timestamp.desc())
        .all())

    if request.is_json:
        return jsonify({
            "reply": ai_reply,
            "steps": next_steps,
            "upload_trigger": upload_trigger,
            "chat_id": chat.id,
        })

    return render_template(
        "investor/ai_response.html",
        form=request.form,
        response=ai_reply,
        steps=next_steps,
        upload_trigger=upload_trigger,
        interactions=interactions,
        chat=chat,
        investor=ip,
        title="Ravlo AI Response",
        active_tab="ai"
    )


@investor_bp.route("/ai/hub", methods=["GET"])
@investor_bp.route("/ai_hub", methods=["GET"])
@login_required
@role_required("investor")
def ai_hub():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    interactions = (AIAssistantInteraction.query
        .filter_by(user_id=current_user.id)
        .order_by(AIAssistantInteraction.timestamp.desc())
        .limit(5)
        .all())

    assistant = AIAssistant()
    try:
        ai_summary = assistant.generate_reply(
            f"Provide an overview of the investor’s AI activity ({len(interactions)} items).",
            "investor_ai_hub",
        )
    except Exception:
        ai_summary = "⚠️ AI summary unavailable."

    return render_template(
        "investor/ai_hub.html",
        investor=ip,
        interactions=interactions,
        ai_summary=ai_summary,
        title="AI Hub",
        active_tab="ai"
    )


@investor_bp.route("/ai/response/<int:chat_id>", methods=["GET"])
@investor_bp.route("/ask-ai/response/<int:chat_id>", methods=["GET"])
@login_required
@role_required("investor")
def ask_ai_response(chat_id):
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    chat = AIAssistantInteraction.query.get_or_404(chat_id)

    # Security: only owner can view
    if chat.user_id != current_user.id:
        return "Unauthorized", 403

    interactions = (AIAssistantInteraction.query
        .filter_by(user_id=current_user.id)
        .order_by(AIAssistantInteraction.timestamp.desc())
        .limit(10)
        .all())

    class DummyForm:
        def hidden_tag(self): return ""

    form = DummyForm()
    form.question = type("obj", (), {"data": chat.question})()
    form.submit = None

    return render_template(
        "investor/ai_response.html",
        investor=ip,
        response=chat.response,
        chat=chat,
        form=form,
        interactions=interactions,
        title="AI Assistant Response",
        active_tab="ai"
    )


@investor_bp.route("/deal-studio/copilot", methods=["GET"])
@login_required
@role_required("investor")
def deal_copilot():
    return render_template(
        "investor/deal_copilot.html",
        page_title="Deal Copilot",
        page_subtitle="Ask Ravlo what to do next with any property, lot, or investment idea."
    )


@investor_bp.route("/deal-studio/copilot/chat", methods=["POST"])
@login_required
@role_required("investor")
def deal_copilot_chat():
    try:
        data = request.get_json(silent=True) or {}

        user_message = (data.get("message") or "").strip()
        property_address = (data.get("property_address") or "").strip()
        zip_code = (data.get("zip_code") or "").strip()
        strategy_hint = (data.get("strategy_hint") or "").strip()
        lot_size = (data.get("lot_size") or "").strip()
        zoning = (data.get("zoning") or "").strip()
        notes = (data.get("notes") or "").strip()
        workspace = (data.get("workspace") or "deal").strip().lower()

        if not user_message:
            return jsonify({
                "success": False,
                "message": "Please enter a message for Deal Copilot."
            }), 400

        deal_context = build_deal_copilot_context(
            property_address=property_address,
            zip_code=zip_code,
            strategy_hint=strategy_hint,
            lot_size=lot_size,
            zoning=zoning,
            notes=notes,
            workspace=workspace,
            user_id=getattr(current_user, "id", None)
        )

        # -----------------------------------------
        # Replace this with your real AI call later
        # -----------------------------------------
        ai_result = generate_deal_copilot_response(
            user_message=user_message,
            context=deal_context
        )

        return jsonify({
            "success": True,
            "reply": ai_result.get("reply"),
            "actions": ai_result.get("actions", []),
            "context_summary": ai_result.get("context_summary", ""),
            "timestamp": datetime.utcnow().isoformat()
        })

    except Exception as e:
        current_app.logger.exception("Deal Copilot chat error")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

# =========================================================
# 📈 INVESTOR • ANALYTICS + ACTIVITY + BUDGET
# =========================================================

@investor_bp.route("/intelligence/analysis", methods=["GET"])
@investor_bp.route("/analysis", methods=["GET"])
@login_required
@role_required("investor")
def analysis():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    loans = LoanApplication.query.filter_by(**_profile_id_filter(LoanApplication, ip.id)).all() if ip else []
    total_loan_amount = sum([getattr(loan, "loan_amount", 0) or 0 for loan in loans])

    # NOTE: your statuses are inconsistent elsewhere ("Verified"/"Pending" vs "verified"/"pending")
    verified_docs = LoanDocument.query.filter_by(**_profile_id_filter(LoanDocument, ip.id), status="Verified").count() if ip else 0
    pending_docs  = LoanDocument.query.filter_by(**_profile_id_filter(LoanDocument, ip.id), status="Pending").count() if ip else 0

    assistant = AIAssistant()
    try:
        ai_summary = assistant.generate_reply(
            f"Summarize investor analytics: {len(loans)} loans totaling ${total_loan_amount}, "
            f"{verified_docs} verified docs, {pending_docs} pending.",
            "investor_analysis",
        )
    except Exception:
        ai_summary = "⚠️ AI summary unavailable."

    stats = {
        "total_loans": len(loans),
        "total_amount": f"${total_loan_amount:,.2f}",
        "verified_docs": verified_docs,
        "pending_docs": pending_docs,
    }

    return render_template(
        "investor/analysis.html",
        investor=ip,
        loans=loans,
        stats=stats,
        ai_summary=ai_summary,
        title="Investor Analytics",
        active_tab="analysis"
    )


@investor_bp.route("/intelligence/activity", methods=["GET"])
@investor_bp.route("/activity", methods=["GET"])
@login_required
@role_required("investor")
def activity():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        flash("Profile not found.", "danger")
        return redirect(url_for("investor.command_center"))

    # BorrowerActivity model name kept for now (schema-safe)
    activities = (BorrowerActivity.query
        .filter_by(**_profile_id_filter(BorrowerActivity, ip.id))
        .order_by(BorrowerActivity.timestamp.desc())
        .all())

    assistant = AIAssistant()
    try:
        ai_summary = assistant.generate_reply(
            f"Generate investor activity summary of {len(activities)} recent actions.",
            "investor_activity",
        )
    except Exception:
        ai_summary = "⚠️ AI summary unavailable."

    return render_template(
        "investor/activity.html",
        investor=ip,
        activities=activities,
        ai_summary=ai_summary,
        title="Activity",
        active_tab="activity"
    )


@investor_bp.route("/planning/budget", methods=["GET", "POST"])
@investor_bp.route("/budget", methods=["GET", "POST"])
@login_required
@role_required("investor")
def budget():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    assistant = AIAssistant()
    budget_data = None
    ai_tip = None

    if request.method == "POST":
        expenses = request.form.to_dict()
        income = safe_float(request.form.get("income")) or 0
        expenses_total = safe_float(request.form.get("expenses")) or 0
        budget_data = {
            "income": income,
            "expenses": expenses_total,
            "savings": income - expenses_total,
        }
        ai_tip = assistant.generate_reply(
            f"Analyze investor expenses: {expenses}",
            "investor_budget",
        )

    return render_template(
        "investor/budget.html",
        investor=ip,
        budget_data=budget_data,
        ai_tip=ai_tip,
        title="Budget Planner",
        active_tab="budget"
    )

@investor_bp.route("/deal-studio/budget", methods=["GET"])
@investor_bp.route("/deal-studio/budget/<int:deal_id>", methods=["GET"])
@login_required
@role_required("investor")
def budget_studio(deal_id=None):
    deal = None
    results = {}
    existing_budget = None

    if deal_id is None:
        query_deal_id = request.args.get("deal_id", type=int)
        if query_deal_id:
            deal_id = query_deal_id

    if deal_id:
        deal = Deal.query.filter_by(
            id=deal_id,
            user_id=current_user.id
        ).first_or_404()

        results = copy.deepcopy(deal.results_json or {})
        results["budget_seed"] = _build_budget_seed_from_results(results)

        ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
        if ip:
            existing_budget = (
                ProjectBudget.query
                .filter_by(
                    deal_id=deal.id,
                    investor_profile_id=ip.id
                )
                .order_by(ProjectBudget.id.desc())
                .first()
            )

    purchase_price = float(getattr(deal, "purchase_price", 0) or 0) if deal else 0
    arv = float(getattr(deal, "arv", 0) or 0) if deal else 0
    rehab_cost = float(getattr(deal, "rehab_cost", 0) or 0) if deal else 0

    return render_template(
        "investor/budget_studio.html",
        deal=deal,
        results=results,
        existing_budget=existing_budget,
        purchase_price=purchase_price,
        arv=arv,
        rehab_cost=rehab_cost,
        page_title="Budget Studio",
        page_subtitle="Control your numbers, track execution, and stay profitable."
    )

@investor_bp.route("/budget-studio/create", methods=["GET", "POST"])
@login_required
@role_required("investor")
def create_budget():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first_or_404()

    if request.method == "POST":
        deal_id = request.form.get("deal_id") or None
        build_project_id = request.form.get("build_project_id") or None
        budget_type = request.form.get("budget_type") or "rehab"
        contingency = float(request.form.get("contingency") or 0)

        if build_project_id:
            budget_type = "build"

        budget = ProjectBudget(
            borrower_profile_id=None,
            investor_profile_id=ip.id,
            loan_app_id=None,
            deal_id=deal_id,
            build_project_id=build_project_id,
            budget_type=budget_type,
            name=request.form.get("name") or "Untitled Budget",
            project_name=request.form.get("project_name") or None,
            total_amount=0,
            total_budget=contingency,
            total_cost=0.0,
            materials_cost=0.0,
            labor_cost=0.0,
            contingency=contingency,
            paid_amount=0.0,
            notes=request.form.get("notes") or None,
        )
        db.session.add(budget)
        db.session.commit()

        flash("Budget created.", "success")
        return redirect(url_for("investor.budget_detail", budget_id=budget.id))

    deals = Deal.query.filter_by(
        investor_profile_id=ip.id
    ).order_by(Deal.updated_at.desc()).all()

    build_projects = BuildProject.query.filter_by(
        user_id=current_user.id
    ).all()

    return render_template(
        "investor/budget_studio/create.html",
        investor=ip,
        deals=deals,
        build_projects=build_projects,
        title="Create Budget",
        active_tab="budget"
    )

@investor_bp.route("/deals/<int:deal_id>/budget/create-from-studio", methods=["POST"])
@login_required
@role_required("investor")
def create_budget_from_studio(deal_id):
    deal = _get_owned_deal_or_404(deal_id)
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first_or_404()

    existing_budget = ProjectBudget.query.filter_by(
        deal_id=deal.id,
        investor_profile_id=ip.id
    ).order_by(ProjectBudget.id.desc()).first()

    if existing_budget:
        flash("A budget already exists for this deal.", "info")
        return redirect(url_for("investor.budget_detail", budget_id=existing_budget.id))

    raw_payload = request.form.get("budget_payload") or "{}"

    try:
        payload = json.loads(raw_payload)
    except Exception:
        payload = {}

    items = payload.get("items") or []
    strategy = (
        payload.get("strategy")
        or ((deal.results_json or {}).get("workspace_analysis") or {}).get("selected_strategy")
        or ((deal.results_json or {}).get("strategy_analysis") or {}).get("strategy")
        or "rehab"
    )

    budget_type = "build" if str(strategy).lower() in {"build_studio", "project_build", "build"} else "rehab"

    budget = ProjectBudget(
        borrower_profile_id=None,
        investor_profile_id=ip.id,
        loan_app_id=None,
        deal_id=deal.id,
        build_project_id=None,
        budget_type=budget_type,
        name=f"Budget - {deal.title or deal.address or f'Deal #{deal.id}'}",
        project_name=deal.title or deal.address,
        total_amount=0.0,
        total_budget=0.0,
        total_cost=0.0,
        materials_cost=0.0,
        labor_cost=0.0,
        contingency=0.0,
        paid_amount=0.0,
        notes="Created from Budget Studio.",
    )
    db.session.add(budget)
    db.session.flush()

    created_count = 0
    estimated_total = 0.0

    for item in items:
        if not isinstance(item, dict):
            continue

        description = str(item.get("name") or item.get("description") or "Budget Item").strip() or "Budget Item"

        try:
            estimated_amount = float(item.get("cost") or item.get("estimated_amount") or 0)
        except (TypeError, ValueError):
            estimated_amount = 0.0

        category = str(item.get("category") or "General").strip() or "General"

        expense = ProjectExpense(
            budget_id=budget.id,
            category=category,
            description=description,
            vendor=None,
            estimated_amount=estimated_amount,
            actual_amount=0.0,
            paid_amount=0.0,
            status="planned",
            notes="Imported from Budget Studio.",
        )
        db.session.add(expense)
        created_count += 1
        estimated_total += estimated_amount

    budget.total_cost = estimated_total
    budget.total_amount = estimated_total
    budget.total_budget = estimated_total + float(budget.contingency or 0)

    if hasattr(budget, "recalculate_totals"):
        budget.recalculate_totals()

    db.session.commit()

    if created_count:
        flash(f"Budget tracker created with {created_count} line item(s).", "success")
    else:
        flash("Budget tracker created, but no line items were added.", "warning")

    return redirect(url_for("investor.budget_detail", budget_id=budget.id))

@investor_bp.route("/budget-studio/<int:budget_id>")
@login_required
@role_required("investor")
def budget_detail(budget_id):
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first_or_404()

    budget = ProjectBudget.query.filter_by(
        id=budget_id,
        investor_profile_id=ip.id
    ).first_or_404()

    category_totals = defaultdict(lambda: {
        "estimated": 0.0,
        "actual": 0.0,
        "paid": 0.0,
        "count": 0,
    })

    for item in budget.expenses:
        cat = (item.category or "General").strip() or "General"
        category_totals[cat]["estimated"] += float(item.estimated_amount or 0)
        category_totals[cat]["actual"] += float(item.actual_amount or 0)
        category_totals[cat]["paid"] += float(item.paid_amount or 0)
        category_totals[cat]["count"] += 1

    category_rows = []
    for category, vals in category_totals.items():
        variance = vals["actual"] - vals["estimated"]
        category_rows.append({
            "category": category,
            "estimated": vals["estimated"],
            "actual": vals["actual"],
            "paid": vals["paid"],
            "variance": variance,
            "count": vals["count"],
        })

    category_rows.sort(key=lambda x: x["estimated"], reverse=True)

    return render_template(
        "investor/budget_studio/detail.html",
        investor=ip,
        budget=budget,
        category_rows=category_rows,
        title=budget.name,
        active_tab="budget"
    )

@investor_bp.route("/deals/<int:deal_id>/budget/generate-from-ai", methods=["POST"])
@login_required
@role_required("investor")
def generate_budget_from_ai(deal_id):
    deal = _get_owned_deal_or_404(deal_id)
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first_or_404()

    existing_budget = ProjectBudget.query.filter_by(
        deal_id=deal.id,
        investor_profile_id=ip.id,
        budget_type="rehab"
    ).first()

    if existing_budget:
        flash("A rehab budget already exists for this deal.", "info")
        return redirect(url_for("investor.budget_detail", budget_id=existing_budget.id))

    results = deal.results_json or {}
    rehab_scope = results.get("rehab_scope") or {}
    build_analysis = results.get("build_analysis") or {}

    # Try a few likely places for line items
    raw_items = (
        rehab_scope.get("line_items")
        or rehab_scope.get("budget_items")
        or rehab_scope.get("items")
        or build_analysis.get("line_items")
        or []
    )

    budget_type = "build" if build_analysis and not rehab_scope else "rehab"

    budget = ProjectBudget(
        borrower_profile_id=None,
        investor_profile_id=ip.id,
        loan_app_id=None,
        deal_id=deal.id,
        build_project_id=None,
        budget_type=budget_type,
        name=f"AI Budget - {deal.title or deal.address or f'Deal #{deal.id}'}",
        project_name=deal.title or deal.address,
        total_amount=0,
        total_budget=0,
        total_cost=0.0,
        materials_cost=0.0,
        labor_cost=0.0,
        contingency=0.0,
        paid_amount=0.0,
        notes="Auto-generated from Deal Architect / AI analysis.",
    )
    db.session.add(budget)
    db.session.flush()

    created_count = 0
    estimated_total = 0.0

    for item in raw_items:
        if not isinstance(item, dict):
            continue

        category = (
            item.get("category")
            or item.get("section")
            or "General"
        )

        description = (
            item.get("description")
            or item.get("name")
            or item.get("item")
            or "Budget Item"
        )

        amount = (
            item.get("estimated_amount")
            or item.get("cost")
            or item.get("amount")
            or item.get("estimate")
            or 0
        )

        try:
            amount = float(amount or 0)
        except (TypeError, ValueError):
            amount = 0.0

        expense = ProjectExpense(
            budget_id=budget.id,
            category=str(category).strip() or "General",
            description=str(description).strip() or "Budget Item",
            vendor=None,
            estimated_amount=amount,
            actual_amount=0,
            paid_amount=0,
            status="planned",
            notes="Imported from AI deal analysis.",
        )
        db.session.add(expense)
        created_count += 1
        estimated_total += amount

    # Fallback: if no line items, try total rehab estimate only
    if created_count == 0:
        fallback_total = (
            rehab_scope.get("estimated_total")
            or rehab_scope.get("total_estimated_cost")
            or rehab_scope.get("rehab_total")
            or results.get("rehab_cost")
            or deal.rehab_cost
            or 0
        )

        try:
            fallback_total = float(fallback_total or 0)
        except (TypeError, ValueError):
            fallback_total = 0.0

        if fallback_total > 0:
            expense = ProjectExpense(
                budget_id=budget.id,
                category="General",
                description="AI Estimated Rehab Budget",
                vendor=None,
                estimated_amount=fallback_total,
                actual_amount=0,
                paid_amount=0,
                status="planned",
                notes="Fallback total imported from AI analysis.",
            )
            db.session.add(expense)
            created_count = 1
            estimated_total = fallback_total

    budget.total_cost = estimated_total
    budget.total_amount = estimated_total
    budget.total_budget = estimated_total + float(budget.contingency or 0)

    db.session.commit()

    if created_count:
        flash(f"AI budget created with {created_count} imported item(s).", "success")
    else:
        flash("Budget created, but no AI line items were found to import.", "warning")

    return redirect(url_for("investor.budget_detail", budget_id=budget.id))

@investor_bp.route("/budget-studio/<int:budget_id>/expense/add", methods=["POST"])
@login_required
@role_required("investor")
def add_budget_expense(budget_id):
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first_or_404()

    budget = ProjectBudget.query.filter_by(
        id=budget_id,
        investor_profile_id=ip.id
    ).first_or_404()

    expense = ProjectExpense(
        budget_id=budget.id,
        category=request.form.get("category") or "General",
        description=(
            request.form.get("description")
            or request.form.get("item_name")
            or "New Expense"
        ),
        vendor=request.form.get("vendor") or None,
        estimated_amount=float(request.form.get("estimated_amount") or request.form.get("estimated_cost") or 0),
        actual_amount=float(request.form.get("actual_amount") or request.form.get("actual_cost") or 0),
        paid_amount=float(request.form.get("paid_amount") or 0),
        status=request.form.get("status") or "planned",
        notes=request.form.get("notes") or None,
    )

    db.session.add(expense)
    db.session.flush()

    budget.recalculate_totals()
    db.session.commit()

    flash("Expense added.", "success")
    return redirect(url_for("investor.budget_detail", budget_id=budget.id))
    
@investor_bp.route("/deals/<int:deal_id>/rehab/budget", methods=["GET", "POST"])
@login_required
@role_required("investor")
def rehab_budget_tracker(deal_id):
    deal = _get_owned_deal_or_404(deal_id)
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first_or_404()

    budget = ProjectBudget.query.filter_by(
        deal_id=deal.id,
        investor_profile_id=ip.id,
        budget_type="rehab"
    ).first()

    if not budget:
        budget = ProjectBudget(
            borrower_profile_id=None,
            investor_profile_id=ip.id,
            loan_app_id=None,
            deal_id=deal.id,
            build_project_id=None,
            budget_type="rehab",
            name=f"Rehab Budget - {deal.title or deal.address or f'Deal #{deal.id}'}",
            project_name=deal.title or deal.address,
            total_amount=0.0,
            total_budget=0.0,
            total_cost=0.0,
            materials_cost=0.0,
            labor_cost=0.0,
            contingency=0.0,
            paid_amount=0.0,
            notes="Auto-created rehab budget."
        )
        db.session.add(budget)
        db.session.commit()

    if request.method == "POST":
        expense = ProjectExpense(
            budget_id=budget.id,
            category=(request.form.get("category") or "General").strip(),
            description=(request.form.get("item_name") or request.form.get("description") or "New Expense").strip(),
            vendor=(request.form.get("vendor") or "").strip() or None,
            estimated_amount=float(request.form.get("estimated_cost") or request.form.get("estimated_amount") or 0),
            actual_amount=float(request.form.get("actual_cost") or request.form.get("actual_amount") or 0),
            paid_amount=float(request.form.get("paid_amount") or 0),
            status=(request.form.get("status") or "planned").strip(),
            notes=(request.form.get("notes") or "").strip() or None,
        )
        db.session.add(expense)
        db.session.flush()

        budget.recalculate_totals()
        db.session.commit()

        flash("Budget expense added.", "success")
        return redirect(url_for("investor.rehab_budget_tracker", deal_id=deal.id))

    items = ProjectExpense.query.filter_by(
        budget_id=budget.id
    ).order_by(ProjectExpense.created_at.desc()).all()

    summary = {
        "estimated_total": budget.estimated_subtotal,
        "actual_total": budget.actual_total,
        "paid_total": budget.paid_total,
        "contingency": budget.contingency_amount,
        "total_budget": budget.estimated_total_with_contingency,
        "remaining_balance": budget.remaining_balance,
        "variance": budget.actual_total - budget.estimated_subtotal,
    }

    return render_template(
        "investor/rehab_budget_tracker.html",
        deal=deal,
        budget=budget,
        items=items,
        summary=summary,
        page_title="Rehab Budget Tracker",
        page_subtitle="Track projected vs actual renovation spend."
    )

@investor_bp.route("/build-projects/<int:project_id>/budget", methods=["GET", "POST"])
@login_required
@role_required("investor")
def build_budget_tracker(project_id):
    project = BuildProject.query.filter_by(
        id=project_id,
        user_id=current_user.id
    ).first_or_404()

    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first_or_404()

    budget = ProjectBudget.query.filter_by(
        build_project_id=project.id,
        investor_profile_id=ip.id,
        budget_type="build"
    ).first()

    if not budget:
        budget = ProjectBudget(
            borrower_profile_id=None,
            investor_profile_id=ip.id,
            loan_app_id=None,
            deal_id=None,
            build_project_id=project.id,
            budget_type="build",
            name=f"Build Budget - {getattr(project, 'project_name', None) or getattr(project, 'name', None) or f'Project #{project.id}'}",
            project_name=getattr(project, "project_name", None) or getattr(project, "name", None),
            total_amount=0.0,
            total_budget=0.0,
            total_cost=0.0,
            materials_cost=0.0,
            labor_cost=0.0,
            contingency=0.0,
            paid_amount=0.0,
            notes="Auto-created build budget."
        )
        db.session.add(budget)
        db.session.commit()

    if request.method == "POST":
        expense = ProjectExpense(
            budget_id=budget.id,
            category=(request.form.get("category") or "General").strip(),
            description=(request.form.get("item_name") or request.form.get("description") or "New Expense").strip(),
            vendor=(request.form.get("vendor") or "").strip() or None,
            estimated_amount=float(request.form.get("estimated_cost") or request.form.get("estimated_amount") or 0),
            actual_amount=float(request.form.get("actual_cost") or request.form.get("actual_amount") or 0),
            paid_amount=float(request.form.get("paid_amount") or 0),
            status=(request.form.get("status") or "planned").strip(),
            notes=(request.form.get("notes") or "").strip() or None,
        )
        db.session.add(expense)
        db.session.flush()

        budget.recalculate_totals()
        db.session.commit()

        flash("Build budget expense added.", "success")
        return redirect(url_for("investor.build_budget_tracker", project_id=project.id))

    items = ProjectExpense.query.filter_by(
        budget_id=budget.id
    ).order_by(ProjectExpense.created_at.desc()).all()

    summary = {
        "estimated_total": budget.estimated_subtotal,
        "actual_total": budget.actual_total,
        "paid_total": budget.paid_total,
        "contingency": budget.contingency_amount,
        "total_budget": budget.estimated_total_with_contingency,
        "remaining_balance": budget.remaining_balance,
        "variance": budget.actual_total - budget.estimated_subtotal,
    }

    return render_template(
        "investor/build_budget_tracker.html",
        project=project,
        budget=budget,
        items=items,
        summary=summary,
        page_title="Build Budget Tracker",
        page_subtitle="Track projected vs actual construction spend."
    )


@investor_bp.route("/ai_deal_insight", methods=["POST"])
@login_required
@role_required("investor")
def ai_deal_insight():
    data = request.get_json() or {}
    name = data.get("name", "Unnamed Deal")
    roi = data.get("roi", 0)
    profit = data.get("profit", 0)
    total = data.get("total", 0)
    message = data.get("message", "")

    assistant = AIAssistant()
    ai_reply = assistant.generate_reply(
        f"Evaluate deal '{name}' with ROI {roi}%, profit {profit}, total cost {total}. {message}",
        "investor_ai_deal_insight",
    )
    return jsonify({"reply": ai_reply})


# =========================================================
# ✍️ INVESTOR • E-SIGN
# =========================================================

@investor_bp.route("/sign", methods=["GET"])
@investor_bp.route("/esign", methods=["GET"])
@login_required
@role_required("investor")
def investor_esign():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    docs = ESignedDocument.query.filter_by(**_profile_id_filter(ESignedDocument, ip.id)).all() if ip else []
    return render_template("investor/esign.html", investor=ip, docs=docs, title="E-Sign", active_tab="esign")

# =========================================================
# ✍️ INVESTOR • E-SIGN SIGN ACTION
# =========================================================




@investor_bp.route("/sign/<int:doc_id>", methods=["POST"])
@investor_bp.route("/esign/sign/<int:doc_id>", methods=["POST"])
@login_required
@role_required("investor")
def investor_esign_sign(doc_id):
    doc = ESignedDocument.query.get_or_404(doc_id)

    # Security: ensure this doc belongs to the current investor (schema-safe)
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if ip:
        owner_ok = False
        if hasattr(doc, "investor_profile_id") and doc.investor_profile_id == ip.id:
            owner_ok = True
        elif hasattr(doc, "borrower_profile_id") and doc.borrower_profile_id == ip.id:
            owner_ok = True
        if not owner_ok:
            return "Unauthorized", 403

    signature_data = request.form.get("signature_data")
    signature_image_path = f"signatures/sign_{doc_id}.png"

    if signature_data:
        header, encoded = signature_data.split(",", 1)
        img_bytes = base64.b64decode(encoded)
        os.makedirs(os.path.dirname(signature_image_path), exist_ok=True)
        with open(signature_image_path, "wb") as f:
            f.write(img_bytes)

    signed_path = f"signed_docs/{doc_id}_signed.pdf"
    os.makedirs(os.path.dirname(signed_path), exist_ok=True)
    add_signature_to_pdf(doc.file_path, signature_image_path, signed_path)

    doc.file_path = signed_path
    doc.status = "Signed"
    db.session.commit()

    # Attach signed doc into LoanDocument (schema-safe)
    ip_id = ip.id if ip else (getattr(doc, "investor_profile_id", None) or getattr(doc, "borrower_profile_id", None))

    ld = LoanDocument(
        name=f"{doc.name} (Signed)",
        file_path=signed_path,
        status="Uploaded",
        uploaded_at=datetime.utcnow(),
    )
    # Prefer investor_profile_id if available, else borrower_profile_id
    if hasattr(ld, "investor_profile_id"):
        ld.investor_profile_id = ip_id
    else:
        ld.borrower_profile_id = ip_id

    db.session.add(ld)
    db.session.commit()

    return redirect(url_for("investor.investor_esign"))


# =========================================================
# 💳 INVESTOR • PAYMENTS / BILLING
# =========================================================

def _stripe_subscription_catalog():
    cfg = current_app.config
    plans = [
        ("individual_loan_officer", "Individual Loan Officer", "LendingOS", 149, cfg.get("STRIPE_PRICE_INDIVIDUAL_LOAN_OFFICER")),
        ("brokerage_small_team", "Brokerage / Small Team", "LendingOS", 799, cfg.get("STRIPE_PRICE_BROKERAGE_SMALL_TEAM")),
        ("explorer", "Explorer", "Investor", 29, cfg.get("STRIPE_PRICE_EXPLORER")),
        ("operator", "Operator", "Investor", 99, cfg.get("STRIPE_PRICE_OPERATOR")),
        ("basic_listing", "Basic Listing", "Partner", 49, cfg.get("STRIPE_PRICE_BASIC_LISTING")),
        ("preferred_partner", "Preferred Partner", "Partner", 99, cfg.get("STRIPE_PRICE_PREFERRED_PARTNER")),
        ("featured_partner", "Featured Partner", "Partner", 199, cfg.get("STRIPE_PRICE_FEATURED_PARTNER")),
        # Legacy tiers kept for compatibility
        ("core", "Core", "Legacy", 149, cfg.get("STRIPE_PRICE_CORE")),
        ("pro", "Pro", "Legacy", 299, cfg.get("STRIPE_PRICE_PRO")),
        ("enterprise", "Enterprise", "Legacy", 799, cfg.get("STRIPE_PRICE_ENTERPRISE")),
    ]
    return [
        {
            "slug": slug,
            "label": label,
            "family": family,
            "monthly_price": monthly_price,
            "price_id": price_id or "",
            "configured": bool(price_id),
        }
        for slug, label, family, monthly_price, price_id in plans
    ]


def _stripe_subscription_price_for_plan(plan: str):
    normalized = (plan or "").strip().lower()
    for item in _stripe_subscription_catalog():
        if item["slug"] == normalized:
            return normalized, item["price_id"]
    return normalized, None


@investor_bp.route("/billing/subscription/<string:plan>", methods=["GET"])
@login_required
@role_required("investor")
def start_subscription_checkout(plan):
    if not current_app.config.get("STRIPE_BILLING_ENABLED", False):
        flash("Stripe billing is not enabled yet.", "warning")
        return redirect(url_for("investor.payments"))

    normalized, price_id = _stripe_subscription_price_for_plan(plan)
    if not price_id:
        flash("Invalid plan or missing Stripe price id.", "danger")
        return redirect(url_for("investor.payments"))

    session_obj = stripe.checkout.Session.create(
        mode="subscription",
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=url_for("investor.subscription_checkout_success", _external=True) + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=url_for("investor.payments", _external=True),
        customer_email=current_user.email,
        metadata={
            "user_id": str(current_user.id),
            "subscription_plan": normalized,
        },
    )
    return redirect(session_obj.url, code=303)


@investor_bp.route("/billing/subscription/success", methods=["GET"])
@login_required
@role_required("investor")
def subscription_checkout_success():
    session_id = request.args.get("session_id")
    if not session_id:
        flash("Missing Stripe session id.", "warning")
        return redirect(url_for("investor.payments"))

    try:
        session_obj = stripe.checkout.Session.retrieve(session_id)
    except Exception:
        current_app.logger.exception("Stripe subscription checkout verification failed")
        flash("Unable to verify Stripe checkout session.", "danger")
        return redirect(url_for("investor.payments"))

    # Verify payment was actually completed
    if session_obj.payment_status != "paid":
        current_app.logger.warning(
            "Stripe checkout session %s has payment_status=%s",
            session_id, session_obj.payment_status,
        )
        flash("Payment has not been completed.", "danger")
        return redirect(url_for("investor.payments"))

    metadata = session_obj.get("metadata") or {}

    # Verify the checkout session belongs to the current user
    if str(metadata.get("user_id")) != str(current_user.id):
        current_app.logger.warning(
            "Stripe checkout user_id mismatch: session=%s current_user=%s",
            metadata.get("user_id"), current_user.id,
        )
        flash("This checkout session does not belong to your account.", "danger")
        return redirect(url_for("investor.payments"))

    plan = (metadata.get("subscription_plan") or "").strip().lower()
    allowed = {item["slug"] for item in _stripe_subscription_catalog() if item["configured"]}
    if plan in allowed:
        current_user.subscription = plan
        db.session.commit()
        flash(f"Subscription updated to {plan.title()}.", "success")
    else:
        flash("Subscription checkout completed, but plan metadata was missing.", "warning")

    return redirect(url_for("investor.payments"))

@investor_bp.route("/billing", methods=["GET"])
@investor_bp.route("/payments", methods=["GET"])
@login_required
@role_required("investor")
def payments():
    user = current_user
    subscription_plan = getattr(user, "subscription", "free")
    subscription_catalog = _stripe_subscription_catalog()
    subscription_groups = {
        "LendingOS": [p for p in subscription_catalog if p.get("family") == "LendingOS"],
        "Investor": [p for p in subscription_catalog if p.get("family") == "Investor"],
        "Partner": [p for p in subscription_catalog if p.get("family") == "Partner"],
        "Legacy": [p for p in subscription_catalog if p.get("family") == "Legacy"],
    }

    payments = (PaymentRecord.query
        .filter_by(user_id=user.id)
        .order_by(PaymentRecord.timestamp.desc())
        .all())

    return render_template(
        "investor/payments.html",
        user=user,
        subscription_plan=subscription_plan,
        subscription_catalog=subscription_catalog,
        subscription_groups=subscription_groups,
        payments=payments,
        title="Billing",
        active_tab="billing"
    )


@investor_bp.route("/subscription", methods=["GET"])
@login_required
@role_required("investor")
def subscription():
    return redirect(url_for("investor.payments"))


@investor_bp.route("/subscription/upgrade", methods=["POST"])
@login_required
@role_required("investor")
def upgrade_plan():
    if hasattr(current_user, "subscription_plan"):
        current_user.subscription_plan = "Pro"
        db.session.commit()
        flash("Subscription updated to Pro.", "success")
    else:
        flash("Subscription upgrades are not available for this account yet.", "warning")
    return redirect(url_for("investor.subscription"))


@investor_bp.route("/subscription/downgrade", methods=["POST"])
@login_required
@role_required("investor")
def downgrade_plan():
    if hasattr(current_user, "subscription_plan"):
        current_user.subscription_plan = "Free"
        db.session.commit()
        flash("Subscription updated to Free.", "success")
    else:
        flash("Subscription changes are not available for this account yet.", "warning")
    return redirect(url_for("investor.subscription"))


@investor_bp.route("/billing/checkout/<int:payment_id>", methods=["GET"])
@investor_bp.route("/payments/checkout/<int:payment_id>", methods=["GET"])
@login_required
@role_required("investor")
def checkout(payment_id):
    payment = PaymentRecord.query.get_or_404(payment_id)

    # Security: payment must belong to current user
    if getattr(payment, "user_id", None) != current_user.id:
        return "Unauthorized", 403

    borrower = getattr(payment, "borrower", None)

    checkout_session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": payment.payment_type},
                "unit_amount": int(float(payment.amount) * 100),
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=url_for("investor.payment_success", _external=True) + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=url_for("investor.payments", _external=True),
        metadata={"payment_id": payment.id, "borrower_id": getattr(borrower, "id", None)},
    )

    payment.stripe_payment_intent = checkout_session.payment_intent
    db.session.commit()
    return redirect(checkout_session.url, code=303)


@investor_bp.route("/billing/success", methods=["GET"])
@investor_bp.route("/payments/success", methods=["GET"])
@login_required
@role_required("investor")
def payment_success():
    session_id = request.args.get("session_id")
    if not session_id:
        flash("Payment session missing.", "warning")
        return redirect(url_for("investor.payments"))

    try:
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        payment_intent = checkout_session.get("payment_intent")
    except Exception as e:
        print("Stripe error:", e)
        flash("Unable to verify payment.", "danger")
        return redirect(url_for("investor.payments"))

    payment = PaymentRecord.query.filter_by(stripe_payment_intent=payment_intent).first()
    if not payment:
        flash("Payment record not found.", "warning")
        return redirect(url_for("investor.payments"))

    # Security: ensure payment belongs to this user
    if getattr(payment, "user_id", None) != current_user.id:
        return "Unauthorized", 403

    payment.status = "Paid"
    payment.paid_at = datetime.utcnow()
    db.session.commit()

    receipt_dir = "stripe_receipts"
    os.makedirs(receipt_dir, exist_ok=True)
    receipt_path = os.path.join(receipt_dir, f"{payment.id}_receipt.txt")
    with open(receipt_path, "w") as f:
        f.write(f"Payment of ${payment.amount} received for {payment.payment_type}.")

    # attach receipt as LoanDocument (schema-safe)
    ld = LoanDocument(
        loan_application_id=getattr(payment, "loan_id", None),
        name=f"{payment.payment_type} Receipt",
        file_path=receipt_path,
        doc_type="Receipt",
        status="Uploaded",
        uploaded_at=datetime.utcnow(),
    )

    pid = getattr(payment, "investor_profile_id", None) or getattr(payment, "borrower_profile_id", None)

    if hasattr(ld, "investor_profile_id"):
        ld.investor_profile_id = pid
    else:
        ld.borrower_profile_id = pid

    db.session.add(ld)
    db.session.commit()

    return render_template("investor/payment_success.html", payment=payment, title="Payment Success", active_tab="billing")


# =========================================================
# 📊 INVESTOR • MARKET SNAPSHOT
# =========================================================

@investor_bp.route("/intelligence/market", methods=["GET"])
@investor_bp.route("/market", methods=["GET"])
@login_required
@role_required("investor")
def market_snapshot_page():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        return redirect(url_for("investor.command_center"))

    active_property = (SavedProperty.query
        .filter_by(**_profile_id_filter(SavedProperty, ip.id))
        .order_by(SavedProperty.created_at.desc())
        .first())

    zipcode = active_property.zipcode if active_property else None
    market_snapshot = get_market_snapshot(zipcode) if zipcode else None

    return render_template(
        "investor/market_snapshot.html",
        investor=ip,
        active_property=active_property,
        market_snapshot=market_snapshot,
        title="Market Snapshot",
        active_tab="market"
    )



PARTNER_CATEGORIES = [
    "Contractor",
    "General Contractor",
    "Subcontractor",
    "Realtor",
    "Real Estate Agent",
    "Broker",
    "Lender",
    "Loan Officer",
    "Mortgage Broker",
    "Hard Money Lender",
    "Private Lender",
    "Inspector",
    "Appraiser",
    "Insurance Agent",
    "Title Company",
    "Closing Attorney",
    "Property Manager",
    "Cleaner",
    "Janitorial",
    "Designer",
    "Architect",
    "Engineer",
    "Photographer",
    "Videographer",
    "Stager",
    "Handyman",
    "Electrician",
    "Plumber",
    "HVAC",
    "Roofing",
    "Flooring",
    "Painter",
    "Landscaper",
    "Pool Contractor",
    "Cabinet Supplier",
    "Kitchen & Bath",
    "Demolition",
    "Restoration",
    "Solar",
    "Window & Door",
    "Security",
    "Moving Company",
    "Attorney",
    "CPA",
    "Bookkeeper",
    "Notary",
    "Credit Specialist",
    "Surveyor",
    "Permit Expeditor",
]

@investor_bp.route("/partners", methods=["GET"])
@login_required
@role_required("investor")
def partners():
    selected_company = (request.args.get("company") or "").strip()
    selected_category = (request.args.get("category") or "").strip()
    selected_city = (request.args.get("city") or "").strip()
    selected_state = (request.args.get("state") or "").strip()
    include_external = request.args.get("include_external") == "1"

    query = Partner.query.filter(
        Partner.active.is_(True),
        Partner.approved.is_(True)
    )

    if selected_company:
        query = query.filter(
            or_(
                Partner.company.ilike(f"%{selected_company}%"),
                Partner.name.ilike(f"%{selected_company}%")
            )
        )

    if selected_category:
        query = query.filter(
            or_(
                Partner.category.ilike(f"%{selected_category}%"),
                Partner.type.ilike(f"%{selected_category}%")
            )
        )

    if selected_city:
        query = query.filter(Partner.city.ilike(f"%{selected_city}%"))

    if selected_state:
        query = query.filter(Partner.state.ilike(f"%{selected_state}%"))

    partners = query.order_by(
        Partner.featured.desc(),
        Partner.is_verified.desc(),
        Partner.rating.desc().nullslast(),
        Partner.review_count.desc().nullslast(),
        Partner.company.asc().nullslast(),
        Partner.name.asc()
    ).all()

    categories = [
        row[0]
        for row in db.session.query(Partner.category)
        .filter(Partner.category.isnot(None))
        .distinct()
        .order_by(Partner.category.asc())
        .all()
        if row[0]
    ]

    external_partners = []
    fallback_used = False

    if include_external and not partners:
        external_partners = search_external_partners_google(
            category=selected_category,
            city=selected_city,
            state=selected_state,
        )
        fallback_used = bool(external_partners)

    return render_template(
        "investor/partners.html",
        partners=partners,
        external_partners=external_partners,
        fallback_used=fallback_used,
        categories=categories,
        selected_company=selected_company,
        selected_category=selected_category,
        selected_city=selected_city,
        selected_state=selected_state,
        include_external=include_external,
    )

@investor_bp.route("/partners/<int:partner_id>", methods=["GET"])
@login_required
@role_required("investor")
def partner_detail(partner_id):
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        flash("Please complete your investor profile first.", "warning")
        return redirect(url_for("investor.create_profile"))

    partner = Partner.query.get_or_404(partner_id)

    if not partner.active or not partner.approved:
        flash("This partner is not currently available.", "warning")
        return redirect(url_for("investor.partners"))

    return render_template(
        "investor/partner_detail.html",
        investor=ip,
        partner=partner,
        title="Partner Details",
        active_tab="partners",
    )



@investor_bp.route("/partners/<int:partner_id>/request-intro", methods=["POST"])
@login_required
@role_required("investor")
def request_partner_intro(partner_id):
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        flash("Please complete your investor profile first.", "warning")
        return redirect(url_for("investor.create_profile"))

    partner = Partner.query.get_or_404(partner_id)

    if not partner.active or not partner.approved:
        flash("This partner is not currently available.", "warning")
        return redirect(url_for("investor.partners"))

    message = (request.form.get("message") or "").strip()
    property_id = request.form.get("property_id", type=int)
    lead_id = request.form.get("lead_id", type=int)

    req = PartnerConnectionRequest(
        borrower_user_id=None,
        investor_user_id=current_user.id,
        borrower_profile_id=None,
        investor_profile_id=ip.id,
        property_id=property_id if property_id else None,
        lead_id=lead_id if lead_id else None,
        partner_id=partner.id,
        category=partner.category,
        message=message or f"Investor requested connection with {partner.company or partner.name}.",
        status="pending",
    )
    db.session.add(req)

    followup = FollowUpItem(
        investor_profile_id=ip.id,
        description=(
            f"Partner intro requested: {partner.company or partner.name}"
            + (f" | Message: {message}" if message else "")
        ),
        is_done=False,
        created_by=current_user.id,
    )
    db.session.add(followup)

    db.session.commit()

    flash(f"Intro request sent for {partner.company or partner.name}.", "success")
    return redirect(url_for("investor.partner_detail", partner_id=partner.id))


@investor_bp.route("/partners/<int:partner_id>/request-connection", methods=["POST"], endpoint="request_partner_connection")
@login_required
@role_required("investor")
def request_partner_connection(partner_id):
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        flash("Please complete your investor profile first.", "warning")
        return redirect(url_for("investor.create_profile"))

    partner = Partner.query.get_or_404(partner_id)

    req = PartnerConnectionRequest(
        investor_user_id=current_user.id,
        investor_profile_id=ip.id,
        partner_id=partner.id,
        category=getattr(partner, "category", None),
        message=f"Investor requested connection with {partner.company or partner.name}.",
        source="internal",
        status="pending",
    )

    db.session.add(req)
    db.session.commit()

    flash(f"Connection request sent for {partner.company or partner.name}.", "success")
    return redirect(url_for("investor.partners"))
    
@investor_bp.route("/resources/request-connection", methods=["POST"])
@login_required
@role_required("investor")
def request_connection():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        return jsonify({
            "success": False,
            "message": "Please complete your investor profile first."
        }), 400

    data = request.get_json(silent=True) or {}

    partner_id = data.get("partner_id")
    message = (data.get("message") or "").strip()
    property_id = data.get("property_id")
    lead_id = data.get("lead_id")

    if not partner_id:
        return jsonify({
            "success": False,
            "message": "Missing partner_id."
        }), 400

    partner = Partner.query.get_or_404(partner_id)

    if not partner.active or not partner.approved:
        return jsonify({
            "success": False,
            "message": "This partner is not currently available."
        }), 400

    req = PartnerConnectionRequest(
        borrower_user_id=None,
        investor_user_id=current_user.id,
        borrower_profile_id=None,
        investor_profile_id=ip.id,
        property_id=property_id if property_id else None,
        lead_id=lead_id if lead_id else None,
        partner_id=partner.id,
        category=partner.category,
        message=message or f"Investor requested connection with {partner.company or partner.name}.",
        status="pending",
    )

    db.session.add(req)

    followup = FollowUpItem(
        investor_profile_id=ip.id,
        description=f"Partner connection requested: {partner.company or partner.name}",
        is_done=False,
        created_by=current_user.id,
    )
    db.session.add(followup)

    db.session.commit()

    return jsonify({
        "success": True,
        "message": f"Request sent for {partner.company or partner.name}."
    }), 200

@investor_bp.route("/resources/partners/filter", methods=["GET"])
@login_required
@role_required("investor")
def partners_filter():
    category = (request.args.get("category") or "All").strip()
    return redirect(url_for("investor.resource_center", category=category))

@investor_bp.route("/partners/marketplace", methods=["GET"])
@login_required
@role_required("investor")
def partner_marketplace():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    service_type = (
        request.args.get("service_type")
        or request.args.get("category")
        or ""
    ).strip()
    city = (request.args.get("city") or "").strip()
    state = (request.args.get("state") or "").strip()
    zip_code = (request.args.get("zip_code") or "").strip()
    deal_id = request.args.get("deal_id", type=int)
    saved_property_id = request.args.get("saved_property_id", type=int)

    internal_results = []
    external_results = []
    fallback_used = False

    def _pick(item, *names, default=None):
        for name in names:
            if isinstance(item, dict) and name in item and item.get(name) not in (None, ""):
                return item.get(name)
            if hasattr(item, name):
                value = getattr(item, name)
                if value not in (None, ""):
                    return value
        return default

    if service_type and (city or state or zip_code):
        internal_results = search_internal_partners(
            Partner,
            category=service_type,
            city=city,
            state=state,
            zip_code=zip_code,
        )

        if not internal_results:
            fallback_used = True
            location_text = ", ".join([x for x in [city, state, zip_code] if x])
            external_results = search_google_places(location_text, service_type)

    partners = []

    for partner in internal_results:
        partners.append({
            "id": _pick(partner, "id"),
            "name": _pick(partner, "company", "business_name", "name", default="Partner"),
            "service_type": _pick(partner, "category", default=service_type),
            "address": _pick(partner, "address"),
            "city": _pick(partner, "city"),
            "state": _pick(partner, "state"),
            "zip_code": _pick(partner, "zip_code", "zip"),
            "rating": _pick(partner, "rating"),
            "reviews": _pick(partner, "review_count", "reviews"),
            "phone": _pick(partner, "phone"),
            "email": _pick(partner, "email"),
            "website": _pick(partner, "website"),
            "bio": _pick(partner, "listing_description", "bio"),
            "score": _pick(partner, "score"),
            "distance_miles": _pick(partner, "distance_miles"),
            "is_internal": True,
            "is_verified": bool(_pick(partner, "approved", default=False)),
            "is_preferred": bool(_pick(partner, "featured", default=False)),
        })

    for partner in external_results:
        partners.append({
            "name": _pick(partner, "name", default="External Provider"),
            "service_type": service_type,
            "address": _pick(partner, "address"),
            "city": _pick(partner, "city", default=city),
            "state": _pick(partner, "state", default=state),
            "zip_code": _pick(partner, "zip_code", default=zip_code),
            "rating": _pick(partner, "rating"),
            "reviews": _pick(partner, "review_count", "reviews"),
            "phone": _pick(partner, "phone"),
            "email": _pick(partner, "email"),
            "website": _pick(partner, "website"),
            "bio": _pick(partner, "description", "bio"),
            "score": _pick(partner, "score"),
            "distance_miles": _pick(partner, "distance_miles"),
            "source": _pick(partner, "source", default="external"),
            "place_id": _pick(partner, "place_id", "external_id"),
            "is_internal": False,
            "is_verified": False,
            "is_preferred": False,
        })

    recent_requests = []
    if ip:
        connection_requests = (
            PartnerConnectionRequest.query
            .filter_by(investor_profile_id=ip.id)
            .order_by(PartnerConnectionRequest.created_at.desc())
            .limit(10)
            .all()
        )
        recent_requests = [
            {
                "created_at": getattr(req, "created_at", None),
                "service_type": getattr(req, "category", None) or "Partner Connection",
                "city": getattr(req, "city", None),
                "state": getattr(req, "state", None),
                "zip_code": getattr(req, "zip_code", None),
                "request_status": getattr(req, "status", None) or "pending",
            }
            for req in connection_requests
        ]

        if "PartnerRequest" in globals():
            marketplace_requests = (
                PartnerRequest.query
                .filter_by(investor_profile_id=ip.id)
                .order_by(PartnerRequest.created_at.desc())
                .limit(10)
                .all()
            )
            recent_requests.extend([
                {
                    "created_at": getattr(req, "created_at", None),
                    "service_type": getattr(req, "service_type", None) or "Partner Request",
                    "city": getattr(req, "city", None),
                    "state": getattr(req, "state", None),
                    "zip_code": getattr(req, "zip_code", None),
                    "request_status": getattr(req, "request_status", None) or "requested",
                }
                for req in marketplace_requests
            ])

        recent_requests.sort(
            key=lambda item: item.get("created_at") or datetime.min,
            reverse=True
        )
        recent_requests = recent_requests[:10]

    return render_template(
        "investor/partner_marketplace.html",
        category=service_type,
        service_type=service_type,
        city=city,
        state=state,
        zip_code=zip_code,
        deal_id=deal_id,
        saved_property_id=saved_property_id,
        internal_results=internal_results,
        external_results=external_results,
        partners=partners,
        result_source="external" if fallback_used else "internal",
        fallback_used=fallback_used,
        recent_requests=recent_requests,
        active_tab="partners",
        title="Ravlo Partner Marketplace",
    )


@investor_bp.route("/partners/request", methods=["POST"])
@login_required
@role_required("investor")
def create_partner_request():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    service_type = (request.form.get("service_type") or "").strip()
    city = (request.form.get("city") or "").strip()
    state = (request.form.get("state") or "").strip()
    zip_code = (request.form.get("zip_code") or "").strip()
    notes = (request.form.get("notes") or "").strip()

    deal_id = request.form.get("deal_id", type=int)
    saved_property_id = request.form.get("saved_property_id", type=int)
    partner_id = request.form.get("partner_id", type=int)

    if not service_type:
        flash("Service type is required.", "danger")
        return redirect(url_for("investor.partner_marketplace"))

    req = PartnerRequest(
        investor_user_id=current_user.id,
        investor_profile_id=ip.id if ip else None,
        deal_id=deal_id,
        saved_property_id=saved_property_id,
        service_type=service_type,
        city=city,
        state=state,
        zip_code=zip_code,
        notes=notes,
        partner_id=partner_id,
        request_status="matched" if partner_id else "requested",
    )

    db.session.add(req)
    db.session.commit()

    flash("Partner request submitted successfully.", "success")
    return redirect(
        url_for(
            "investor.partner_marketplace",
            service_type=service_type,
            city=city,
            state=state,
            zip_code=zip_code,
            deal_id=deal_id,
            saved_property_id=saved_property_id,
        )
    )


@investor_bp.route("/partners/save-external", methods=["POST"])
@login_required
@role_required("investor")
def save_external_partner():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    name = (request.form.get("name") or "").strip()
    service_type = (request.form.get("service_type") or "").strip()
    address = (request.form.get("address") or "").strip()
    city = (request.form.get("city") or "").strip()
    state = (request.form.get("state") or "").strip()
    zip_code = (request.form.get("zip_code") or "").strip()
    website = (request.form.get("website") or "").strip()
    source = (request.form.get("source") or "external").strip()
    external_id = (request.form.get("external_id") or "").strip()

    rating = request.form.get("rating", type=float)
    review_count = request.form.get("review_count", type=int)

    if not name:
        flash("External partner name is required.", "danger")
        return redirect(url_for("investor.partner_marketplace"))

    existing = None
    if external_id:
        existing = ExternalPartnerLead.query.filter_by(external_id=external_id).first()

    if existing:
        flash("This external partner is already saved.", "info")
        return redirect(url_for("investor.partner_marketplace"))

    lead = ExternalPartnerLead(
        created_by_user_id=current_user.id,
        investor_profile_id=ip.id if ip else None,
        name=name,
        service_type=service_type,
        source=source,
        address=address,
        city=city,
        state=state,
        zip_code=zip_code,
        website=website,
        external_id=external_id,
        rating=rating,
        review_count=review_count,
        invite_status="new",
        raw_json={
            "name": name,
            "service_type": service_type,
            "address": address,
            "city": city,
            "state": state,
            "zip_code": zip_code,
            "website": website,
            "external_id": external_id,
            "rating": rating,
            "review_count": review_count,
            "source": source,
        },
    )

    db.session.add(lead)
    db.session.commit()

    flash("External provider saved to Ravlo lead pipeline.", "success")
    return redirect(url_for("investor.partner_marketplace"))


@investor_bp.route("/partners/invite-external/<int:lead_id>", methods=["POST"])
@login_required
@role_required("investor", "admin")
def invite_external_partner(lead_id):
    lead = ExternalPartnerLead.query.get_or_404(lead_id)
    lead.invite_status = "invited"

    if lead.notes:
        lead.notes += "\nInvited to Ravlo marketplace."
    else:
        lead.notes = "Invited to Ravlo marketplace."

    db.session.commit()

    flash("External provider marked as invited.", "success")
    return redirect(url_for("investor.partner_marketplace"))

@investor_bp.route("/partners/request-legacy", methods=["POST"])
@login_required
@role_required("investor")
def create_partner_connection_request_legacy():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    partner_id = request.form.get("partner_id", type=int)
    category = (request.form.get("category") or "").strip()
    message = (request.form.get("message") or "").strip()

    if not partner_id:
        flash("Partner selection is required.", "danger")
        return redirect(url_for("investor.partner_marketplace"))

    req = PartnerConnectionRequest(
        investor_user_id=current_user.id,
        investor_profile_id=ip.id if ip else None,
        partner_id=partner_id,
        category=category,
        message=message,
        source="internal",
        status="pending",
    )

    db.session.add(req)
    db.session.commit()

    flash("Partner request sent successfully.", "success")
    return redirect(url_for("investor.partner_marketplace"))

@investor_bp.route("/partners/save-external-lead", methods=["POST"])
@login_required
@role_required("investor")
def save_external_partner_lead():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    name = (request.form.get("name") or "").strip()
    category = (request.form.get("category") or "").strip()
    address = (request.form.get("address") or "").strip()
    city = (request.form.get("city") or "").strip()
    state = (request.form.get("state") or "").strip()
    zip_code = (request.form.get("zip_code") or "").strip()
    external_id = (request.form.get("external_id") or "").strip()
    source = (request.form.get("source") or "google").strip()

    rating = request.form.get("rating", type=float)
    review_count = request.form.get("review_count", type=int)

    if not name:
        flash("Provider name is required.", "danger")
        return redirect(url_for("investor.partner_marketplace"))

    existing = None
    if external_id:
        existing = ExternalPartnerLead.query.filter_by(external_id=external_id).first()

    if existing:
        flash("That provider is already saved.", "info")
        return redirect(url_for("investor.partner_marketplace"))

    lead = ExternalPartnerLead(
        created_by_user_id=current_user.id,
        investor_profile_id=ip.id if ip else None,
        name=name,
        business_name=name,
        category=category,
        address=address,
        city=city,
        state=state,
        zip_code=zip_code,
        external_id=external_id,
        source=source,
        rating=rating,
        review_count=review_count or 0,
        invite_status="saved",
        raw_json={
            "name": name,
            "category": category,
            "address": address,
            "city": city,
            "state": state,
            "zip_code": zip_code,
            "external_id": external_id,
            "source": source,
            "rating": rating,
            "review_count": review_count or 0,
        }
    )

    db.session.add(lead)
    db.session.commit()

    flash("External provider saved to the Ravlo lead pipeline.", "success")
    return redirect(url_for("investor.partner_marketplace"))

@investor_bp.route("/partners/request-external/<int:lead_id>", methods=["POST"])
@login_required
@role_required("investor")
def create_external_partner_request(lead_id):
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    lead = ExternalPartnerLead.query.get_or_404(lead_id)

    req = PartnerConnectionRequest(
        investor_user_id=current_user.id,
        investor_profile_id=ip.id if ip else None,
        external_partner_lead_id=lead.id,
        category=lead.category,
        message=f"Fallback marketplace request for external provider: {lead.name}",
        source="external",
        status="awaiting_match",
    )

    db.session.add(req)
    db.session.commit()

    flash("External partner request created.", "success")
    return redirect(url_for("investor.partner_marketplace"))
