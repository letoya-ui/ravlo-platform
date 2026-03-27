import os
import io
import json
import uuid
import base64
import requests
import zipfile
from datetime import datetime
from io import BytesIO
from openai import OpenAI

from PIL import Image, ImageOps
from werkzeug.utils import secure_filename
from werkzeug.datastructures import ImmutableMultiDict
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import or_
from urllib.parse import urlencode
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
from LoanMVP.services.property_tool import search_deals_for_zip
from LoanMVP.services.notification_service import notify_team_on_conversion
from LoanMVP.services.blueprint_parser import extract_blueprint_structure, infer_room_type
from LoanMVP.services.prompt_builder import build_blueprint_prompt
from LoanMVP.services.concept_build_service import run_concept_build
from LoanMVP.services.renovation_engine_client import generate_concept, call_renovation_engine_upload, RenovationEngineError
# 🔥 Property intelligence (IMPORTANT)
from LoanMVP.services.property_service import resolve_rentcast_investor_bundle, build_ravlo_property_card
from LoanMVP.services.deal_copilot_service import build_deal_copilot_context, generate_deal_copilot_response

from LoanMVP.utils.r2_storage import spaces_put_bytes


from LoanMVP.services.partner_marketplace_service import search_internal_partners, search_google_places
# ---------------------------------------------------------
# Blueprint (INVESTOR ONLY)
# ---------------------------------------------------------
investor_bp = Blueprint("investor", __name__, url_prefix="/investor")

client = OpenAI()

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

# =========================================================
# ENGINE HELPERS
# =========================================================

def _engine_headers() -> dict:
    headers = {}
    if RENOVATION_API_KEY:
        headers["X-API-Key"] = RENOVATION_API_KEY
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
    return deal.results_json or {}

def _set_deal_results(deal, results):
    deal.results_json = results or {}

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
# =========================================================
# GENERIC HELPERS
# =========================================================

def _json_default():
    return {}


def _safe_json_loads_local(value, default=None):
    default = default if default is not None else {}
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


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


# =========================================================
# ENGINE STABILITY HELPERS
# =========================================================

RENDER_TIMEOUT = 180
SCOPE_TIMEOUT = 45
UPLOAD_TIMEOUT = 180
RENDER_LOCK_SECONDS = 180


def _safe_engine_error_message(resp):
    try:
        payload = resp.json()
        if isinstance(payload, dict):
            return (
                payload.get("detail")
                or payload.get("message")
                or payload.get("error")
                or resp.text[:300]
            )
    except Exception:
        pass
    return resp.text[:300] or f"HTTP {resp.status_code}"


def _post_renovation_engine_json(path, payload, timeout=RENDER_TIMEOUT):
    res = requests.post(
        _renovation_engine_url(path),
        json=payload,
        headers=_engine_headers(),
        timeout=timeout,
    )
    if not res.ok:
        raise RuntimeError(_safe_engine_error_message(res))
    return res.json()


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
@csrf.exempt
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
@csrf.exempt
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
@investor_bp.route("/account", methods=["GET", "POST"])
@csrf.exempt
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
@csrf.exempt
@login_required
@role_required("investor")
def settings():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()

    if request.method == "POST":
        current_user.first_name = request.form.get("first_name")
        current_user.last_name = request.form.get("last_name")
        current_user.email = request.form.get("email")

    form = InvestorSettingsForm()

    if form.validate_on_submit():
        db.session.commit()
        flash("Settings updated successfully.", "success")
        return redirect(url_for("investor.settings"))

    return render_template(
        "investor/settings.html",
        investor=current_user,
        investor_profile=ip
    )

@investor_bp.route("/privacy", methods=["GET", "POST"])
@csrf.exempt
@login_required
@role_required("investor")
def privacy():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if ip and request.method == "POST":
        ip.subscription_plan = request.form.get("subscription_plan")
        db.session.commit()
        flash("Privacy preferences updated.", "success")
        return redirect(url_for("investor.privacy"))
    return render_template("investor/privacy.html", investor=ip)


@investor_bp.route("/notifications-settings", methods=["GET", "POST"])
@csrf.exempt
@login_required
@role_required("investor")
def notifications_settings():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if ip and request.method == "POST":
        ip.email_notifications = True if request.form.get("email_notifications") else False
        ip.sms_notifications = True if request.form.get("sms_notifications") else False
        db.session.commit()
        flash("Notification settings updated.", "success")
        return redirect(url_for("investor.notifications_settings"))
    return render_template("investor/notifications_settings.html", investor=ip)


# =========================================================
# 🧾 INVESTOR PROFILE CREATE/UPDATE
# =========================================================

@investor_bp.route("/create_profile", methods=["GET", "POST"])
@csrf.exempt
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
@csrf.exempt
@login_required
@role_required("investor")
def update_profile():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        return jsonify({"status": "error", "message": "Profile not found."}), 404

    for field, value in request.form.items():
        if hasattr(ip, field) and (value or "").strip():
            setattr(ip, field, value)

    ip.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"status": "success", "message": "Profile updated successfully."})
    
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

    return render_template(
        "investor/capital_application.html",
        investor=ip,
        deal=deal,
        officers=officers,
        title="Apply for Capital"
    )

@investor_bp.route("/capital_application/submit", methods=["POST"])
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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

        for lender in mock_lenders:
            db.session.add(LoanQuote(
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
            ))

        db.session.commit()
        flash("✅ Loan quotes generated successfully!", "success")

        return render_template(
            "investor/quote_results.html",
            investor=ip,
            lenders=mock_lenders,
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
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
@login_required
@role_required("investor")
def upload_request():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        return redirect(url_for("investor.create_profile"))

    item_id = request.args.get("item_id")
    item_type = request.args.get("type")  # request|condition

    item = DocumentRequest.query.get(item_id) if item_type == "request" else UnderwritingCondition.query.get(item_id)

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
        item=item,
        item_type=item_type,
        title="Upload Document",
        active_tab="documents"
    )


@investor_bp.route("/delete_document/<int:doc_id>", methods=["POST"])
@csrf.exempt
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

    file_path = doc.file_path  # make sure this is stored in DB

    if not file_path or not os.path.exists(file_path):
        abort(404)

    return send_file(
        file_path,
        as_attachment=True,
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
@csrf.exempt
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
@csrf.exempt
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

        if hasattr(existing, "resolved_json"):
            existing.resolved_json = json.dumps(resolved) if resolved else None
            existing.resolved_at = datetime.utcnow() if resolved else None

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

    if hasattr(saved, "resolved_json"):
        saved.resolved_json = json.dumps(resolved) if resolved else None
        saved.resolved_at = datetime.utcnow() if resolved else None

    db.session.add(saved)
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
@csrf.exempt
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
@csrf.exempt
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
        flash("Could not load property intelligence.", "warning")
        return redirect(url_for(fallback_endpoint))

    resolved_property = resolved.get("property") or {}
    valuation = resolved.get("valuation") or {}
    rent_estimate = resolved.get("rent_estimate") or {}
    comps = resolved.get("comps") or {}
    market_snapshot = resolved.get("market_snapshot") or {}
    ai_summary = resolved.get("ai_summary") or resolved.get("summary") or None
    photos = resolved_property.get("photos") or []
    primary_photo = resolved_property.get("primary_photo")

    return render_template(
        "investor/property_explore_plus.html",
        investor=ip,
        prop=prop,
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

@investor_bp.route("/intelligence/tool", methods=["GET"])
@investor_bp.route("/property_tool", methods=["GET"])
@login_required
@role_required("investor")
def property_tool():
    return render_template(
        "investor/property_tool.html",
        title="Ravlo Deal Finder",
        active_page="property_tool",
        page_name="Deal Finder",
        page_subline="Search by ZIP, review investment potential, and send opportunities straight into Deal Workspace."
    )

# =========================================================
# 🔌 INVESTOR • APIs (Property Tool)
# =========================================================

@investor_bp.route("/api/intelligence/zip-search", methods=["POST"])
@investor_bp.route("/api/property_tool_search", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
def api_property_tool_search():
    payload = request.get_json(force=True) or {}
    zip_code = (payload.get("zip") or "").strip()
    strategy = (payload.get("strategy") or "flip").strip().lower()

    if not zip_code:
        return jsonify({"status": "error", "message": "ZIP code is required."}), 400

    def _num(v):
        try:
            if v in (None, "", "None"):
                return None
            return float(v)
        except Exception:
            return None

    results = search_deals_for_zip(
        zip_code=zip_code,
        strategy=strategy,
        price_min=_num(payload.get("price_min")),
        price_max=_num(payload.get("price_max")),
        beds_min=_num(payload.get("beds_min")),
        baths_min=_num(payload.get("baths_min")),
        min_roi=_num(payload.get("min_roi")),
        min_cashflow=_num(payload.get("min_cashflow")),
        limit=int(payload.get("limit") or 20),
    )

    return jsonify({"status": "ok", "zip": zip_code, "strategy": strategy, "results": results})


@investor_bp.route("/api/intelligence/save", methods=["POST"])
@investor_bp.route("/api/property_tool_save", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
def api_property_tool_save():
    payload = request.get_json(force=True) or {}
    address = (payload.get("address") or "").strip()
    if not address:
        return jsonify({"status": "error", "message": "Address is required to save."}), 400

    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        return jsonify({"status": "error", "message": "Profile not found."}), 400

    zipcode = (payload.get("zip") or "").strip() or None
    price = payload.get("price")
    sqft = payload.get("sqft")
    property_id = payload.get("property_id")

    try:
        sqft = int(float(sqft)) if sqft not in (None, "", "None") else None
    except Exception:
        sqft = None

    fk = _profile_id_filter(SavedProperty, ip.id)

    existing = None
    if property_id:
        existing = SavedProperty.query.filter_by(**fk, property_id=str(property_id)).first()

    if not existing:
        existing = SavedProperty.query.filter(
            getattr(SavedProperty, "investor_profile_id", SavedProperty.borrower_profile_id) == ip.id,
            db.func.lower(SavedProperty.address) == address.lower()
        ).first()

    if existing:
        return jsonify({"status": "ok", "message": "Already saved.", "saved_id": existing.id})

    saved = SavedProperty(
        **fk,
        property_id=str(property_id) if property_id else None,
        address=address,
        price=str(price or ""),
        sqft=sqft,
        zipcode=zipcode,
        saved_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )
    db.session.add(saved)
    db.session.commit()

    return jsonify({"status": "ok", "message": "Saved.", "saved_id": saved.id})


@investor_bp.route("/api/intelligence/save-and-analyze", methods=["POST"])
@investor_bp.route("/api/property_tool_save_and_analyze", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
def api_property_tool_save_and_analyze():
    payload = request.get_json(force=True) or {}
    address = (payload.get("address") or "").strip()
    if not address:
        return jsonify({"status": "error", "message": "Address is required to analyze."}), 400

    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        return jsonify({"status": "error", "message": "Profile not found."}), 400

    zipcode = (payload.get("zip") or "").strip() or None
    price = payload.get("price")
    sqft = payload.get("sqft")
    property_id = payload.get("property_id")

    try:
        sqft = int(float(sqft)) if sqft not in (None, "", "None") else None
    except Exception:
        sqft = None

    fk = _profile_id_filter(SavedProperty, ip.id)

    existing = None
    if property_id:
        existing = SavedProperty.query.filter_by(**fk, property_id=str(property_id)).first()

    if not existing:
        existing = SavedProperty.query.filter(
            getattr(SavedProperty, "investor_profile_id", SavedProperty.borrower_profile_id) == ip.id,
            db.func.lower(SavedProperty.address) == address.lower()
        ).first()

    if not existing:
        existing = SavedProperty(
            **fk,
            property_id=str(property_id) if property_id else None,
            address=address,
            price=str(price or ""),
            sqft=sqft,
            zipcode=zipcode,
            saved_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
        db.session.add(existing)
        db.session.commit()

    deal_url = url_for("investor.deal_workspace", prop_id=existing.id, mode="flip")
    return jsonify({"status": "ok", "saved_id": existing.id, "deal_url": deal_url})

@investor_bp.route("/api/intelligence/card", methods=["POST"])
@investor_bp.route("/api/property_tool_card", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
def api_property_tool_card():
    payload = request.get_json(force=True) or {}

    address = (payload.get("address") or "").strip()
    if not address:
        return jsonify({"status": "error", "message": "Address is required."}), 400

    def _num_or_none(v):
        try:
            if v in (None, "", "None"):
                return None
            return float(v)
        except Exception:
            return None

    beds = _num_or_none(payload.get("beds"))
    baths = _num_or_none(payload.get("baths"))
    sqft = _num_or_none(payload.get("sqft"))
    property_type = (payload.get("property_type") or "").strip() or None

    if beds is not None:
        try:
            beds = int(beds)
        except Exception:
            beds = None

    if sqft is not None:
        try:
            sqft = int(sqft)
        except Exception:
            sqft = None

    card = build_ravlo_property_card(
        address=address,
        beds=beds,
        baths=baths,
        sqft=sqft,
        property_type=property_type,
    )

    if card.get("status") != "ok":
        return jsonify({
            "status": "error",
            "message": card.get("error") or "Unable to load property card."
        }), 400

    return jsonify(card)


@investor_bp.route("/api/property_tool_view_details", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
def api_property_tool_view_details():
    payload = request.get_json(force=True) or {}
    address = (payload.get("address") or "").strip()

    if not address:
        return jsonify({"status": "error", "message": "Address is required."}), 400

    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    if not ip:
        return jsonify({"status": "error", "message": "Investor profile not found."}), 400

    zipcode = (payload.get("zip") or "").strip() or None
    price = payload.get("price")
    sqft = payload.get("sqft")
    property_id = payload.get("property_id")

    try:
        sqft = int(float(sqft)) if sqft not in (None, "", "None") else None
    except Exception:
        sqft = None

    fk = _profile_id_filter(SavedProperty, ip.id)

    existing = None
    if property_id:
        existing = SavedProperty.query.filter_by(**fk, property_id=str(property_id)).first()

    if not existing:
        existing = SavedProperty.query.filter(
            getattr(SavedProperty, "investor_profile_id", SavedProperty.borrower_profile_id) == ip.id,
            db.func.lower(SavedProperty.address) == address.lower()
        ).first()

    if not existing:
        existing = SavedProperty(
            **fk,
            property_id=str(property_id) if property_id else None,
            address=address,
            price=str(price or ""),
            sqft=sqft,
            zipcode=zipcode,
            saved_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
        db.session.add(existing)
        db.session.commit()

    detail_url = url_for(
        "investor.property_explore_plus",
        prop_id=existing.id,
        source="property_tool"
    )

    return jsonify({
        "status": "ok",
        "saved_id": existing.id,
        "detail_url": detail_url
    })
         
# =========================================================
# 💼 INVESTOR • DEAL STUDIO (workspace + deals + visualizer + exports)
# =========================================================

@investor_bp.route("/deal-studio", methods=["GET"])
@login_required
@role_required("investor")
def deal_studio():
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
    # 1) Load by deal_id if provided in URL
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
    # 5) Load comps / property intelligence
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
    # 6) Load saved deal results
    # -----------------------------------------
    if deal:
        results_json = deal.results_json or {}
        strategy_analysis = results_json.get("strategy_analysis", {}) or {}
        rehab_analysis = results_json.get("rehab_analysis", {}) or {}
        workspace_analysis = results_json.get("workspace_analysis", {}) or {}
        optimization = results_json.get("optimization", {}) or {}

    # -----------------------------------------
    # 7) AI summary
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
@csrf.exempt
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
@investor_bp.route("/deals")
@login_required
def deals():

    # Fetch deals owned by the investor
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
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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

    if getattr(deal, "saved_property_id", None):
        return redirect(url_for(
            "investor.deal_workspace",
            prop_id=deal.saved_property_id,
            mode=deal.strategy or "flip"
        ))

    flash("This deal is not linked to a saved property yet.", "warning")
    return redirect(url_for("investor.deal_workspace"))

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
@csrf.exempt
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
@login_required
@role_required("investor")
def deal_rehab(deal_id):
    deal = _get_owned_deal_or_404(deal_id)
    mockups = _get_rehab_mockups_for_deal(deal)

    before_url = ""
    try:
        before_url = ((deal.resolved_json or {}).get("rehab") or {}).get("before_url") or ""
    except Exception:
        before_url = ""

    if not before_url and mockups:
        before_url = mockups[0].before_url or ""

    featured = _featured_rehab_data(deal)

    return render_template(
        "investor/deal_rehab_studio.html",
        deal=deal,
        mockups=mockups,
        before_url=before_url,
        featured=featured,
    )


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

    if deal_id is None:
        query_deal_id = request.args.get("deal_id", type=int)
        if query_deal_id:
            deal_id = query_deal_id

    if deal_id is not None:
        deal = _get_owned_deal_or_404(deal_id)
        project = _safe_first_related(deal, "projects")

    build_analysis = {}
    build_preview = ""
    build_mockups = []
    build_reference_image = ""

    if deal:
        results = deal.results_json or {}
        build_analysis = results.get("build_analysis", {}) or {}
        build_preview = results.get("build_preview_url", "") or ""
        build_mockups = results.get("build_mockups", []) or []
        build_reference_image = results.get("build_reference_image", "") or ""

    return render_template(
        "investor/build_studio.html",
        deal=deal,
        project=project,
        deal_id=deal.id if deal else None,
        build_analysis=build_analysis,
        build_preview=build_preview,
        build_mockups=build_mockups,
        build_reference_image=build_reference_image,
        page_title="Build Studio",
        page_subtitle="Design and visualize new construction projects.",
    )

# =========================================================
# 🏗️ BUILD STUDIO — GENERATE CONCEPT
# =========================================================

@investor_bp.route("/deal-studio/build-studio/generate", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
def generate_build_studio():
    deal = None

    try:
        data = request.get_json(silent=True) or {}

        deal_id = _normalize_int(data.get("deal_id"))

        if deal_id:
            deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first()
            if not deal:
                return jsonify({"status": "error", "message": "Deal not found or not authorized."}), 404

            if _deal_render_lock_active(deal):
                return jsonify({
                    "status": "error",
                    "message": "A build render is already in progress for this deal."
                }), 409

            _set_deal_render_processing(deal)
            db.session.commit()

        project_name = (data.get("project_name") or "").strip()
        property_type = (data.get("property_type") or "single_family").strip()
        style = (data.get("style") or "modern_farmhouse").strip()
        description = (data.get("description") or "").strip()
        lot_size = (data.get("lot_size") or "").strip()
        zoning = (data.get("zoning") or "").strip()
        location = (data.get("location") or "").strip()
        notes = (data.get("notes") or "").strip()
        save_to_deal = str(data.get("save_to_deal") or "").lower() in ("1", "true", "yes", "on")

        image_url = (data.get("image_url") or "").strip()
        image_base64 = (data.get("image_base64") or "").strip()

        if not image_url and not image_base64 and deal is not None:
            results = deal.results_json or {}
            image_url = (results.get("build_reference_image") or "").strip()

        if not image_url and not image_base64:
            return jsonify({
                "status": "error",
                "message": "Build Studio requires an uploaded site image, lot photo, or reference image."
            }), 400

        payload = {
            "project_name": project_name,
            "property_type": property_type,
            "style": style,
            "description": description,
            "lot_size": lot_size,
            "zoning": zoning,
            "image_base64": image_base64,
            "image_url": image_url,
            "count": 1,
            "steps": 6,
            "guidance": 7.5,
            "strength": 0.75,
            "width": 640,
            "height": 640,
        }

        current_app.logger.warning(f"BUILD ENGINE PAYLOAD: {payload}")

        engine_json = _post_renovation_engine_json(
            "/v1/build_concept",
            payload,
            timeout=RENDER_TIMEOUT,
        )

        current_app.logger.warning(f"BUILD ENGINE JSON: {engine_json}")

        images_b64 = engine_json.get("images_base64", []) or []
        if not images_b64:
            return jsonify({
                "status": "error",
                "message": "Build engine returned no images."
            }), 502

        render_batch_id = uuid.uuid4().hex
        build_urls = _upload_build_images_from_b64(images_b64, render_batch_id)

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
            results["build_analysis"] = {
                "project_name": project_name,
                "property_type": property_type,
                "style": style,
                "description": description,
                "lot_size": lot_size,
                "zoning": zoning,
                "location": location,
                "notes": notes,
                "images": build_urls,
                "meta": meta,
                "seed": seed,
                "job_id": job_id,
                "build_reference_image": image_url,
            }
            results["build_mockups"] = build_urls
            results["build_preview_url"] = build_urls[0] if build_urls else ""
            _set_deal_results(deal, results)

        if deal is not None:
            _clear_deal_render_processing(deal)

        db.session.commit()

        return jsonify({
            "status": "ok",
            "images": build_urls,
            "meta": meta,
            "seed": seed,
            "job_id": job_id,
            "deal_id": deal.id if deal else None,
            "saved_to_deal": bool(save_to_deal and deal is not None),
            "mode": "url",
        })

    except Exception as e:
        current_app.logger.exception("Build Studio generation error")

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
@csrf.exempt
@login_required
@role_required("investor")
def ai_build_scope():
    data = request.get_json(silent=True) or {}

    description = (data.get("description") or "").strip()
    property_type = (data.get("property_type") or "").strip()
    lot_size = (data.get("lot_size") or "").strip()
    zoning = (data.get("zoning") or "").strip()

    if not description:
        return jsonify({"status": "error", "message": "description is required."}), 400

    try:
        if not SCOPE_ENGINE_URL:
            return jsonify({"status": "error", "message": "Scope engine is not configured."}), 500

        res = requests.post(
            _scope_engine_url("/v1/build_scope"),
            json={
                "description": description,
                "property_type": property_type,
                "lot_size": lot_size,
                "zoning": zoning,
            },
            headers=_scope_engine_headers(),
            timeout=60,
        )
        res.raise_for_status()

        engine_data = res.json() or {}
        build_analysis = engine_data.get("build_analysis") or {}

        return jsonify({
            "status": "ok",
            "build_analysis": {
                "summary": build_analysis.get("summary", ""),
                "key_points": build_analysis.get("key_points", []),
                "estimated_build_cost": build_analysis.get("estimated_build_cost", 0),
            }
        })

    except Exception as e:
        current_app.logger.exception("ai_build_scope failed")
        return jsonify({"status": "error", "message": str(e)}), 500
        
@investor_bp.route("/deal-studio/build-studio/generate-upload", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
def generate_build_studio_upload():
    deal = None

    try:
        deal_id = _normalize_int(request.form.get("deal_id"))

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

        reference_image_url = _upload_before_image(raw)

        payload = {
            "project_name": project_name,
            "property_type": property_type,
            "style": style,
            "description": description,
            "lot_size": lot_size,
            "zoning": zoning,
            "image_base64": base64.b64encode(raw).decode("utf-8"),
            "image_url": "",
            "width": 640,
            "height": 640,
            "steps": 6,
            "guidance": 7.0,
            "strength": 0.70,
            "count": 1,
        }

        seed = request.form.get("seed")
        if seed not in (None, "", "None"):
            payload["seed"] = int(seed)

        current_app.logger.warning(f"BUILD UPLOAD ENGINE PAYLOAD: {payload}")

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

        if save_to_deal and deal is not None:
            results = _deal_results(deal)
            results["build_analysis"] = {
                "project_name": project_name,
                "property_type": property_type,
                "description": description,
                "lot_size": lot_size,
                "zoning": zoning,
                "location": location,
                "notes": notes,
                "style": style,
                "images": build_urls,
                "meta": meta,
                "seed": seed,
                "job_id": job_id,
                "build_reference_image": reference_image_url,
            }
            results["build_mockups"] = build_urls
            results["build_preview_url"] = build_urls[0] if build_urls else ""
            results["build_reference_image"] = reference_image_url
            _set_deal_results(deal, results)

        if deal is not None:
            _clear_deal_render_processing(deal)

        db.session.commit()

        return jsonify({
            "status": "ok",
            "images": build_urls,
            "meta": meta,
            "seed": seed,
            "job_id": job_id,
            "deal_id": deal.id if deal else None,
            "saved_to_deal": bool(save_to_deal and deal is not None),
            "reference_image_url": reference_image_url,
            "mode": "upload",
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
@csrf.exempt
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

    project = BuildProject(
        user_id=current_user.id,
        project_name=data.get("project_name"),
        property_type=data.get("property_type"),
        description=data.get("description"),
        lot_size=data.get("lot_size"),
        zoning=data.get("zoning"),
        location=data.get("location"),
        notes=data.get("notes"),
        concept_render_url=data.get("concept_render_url"),
        blueprint_url=data.get("blueprint_url"),
        site_plan_url=data.get("site_plan_url"),
        presentation_url=data.get("presentation_url")
    )

    if hasattr(project, "investor_profile_id"):
        project.investor_profile_id = investor_profile.id if investor_profile else None

    if hasattr(project, "deal_id"):
        project.deal_id = deal.id if deal else None

    db.session.add(project)
    db.session.flush()

    if deal is not None:
        results = _deal_results(deal)
        results["build_project"] = {
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


@investor_bp.route("/build-projects/<int:project_id>/convert-to-deal", methods=["POST"])
@csrf.exempt
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
@csrf.exempt
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
            return redirect(url_for("investor.deal_finder"))

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
    
@investor_bp.route("/deal-architect/analyze", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
def deal_architect_analyze():
    try:
        deal_id = _normalize_int(request.form.get("deal_id"))
        deal = None

        if deal_id:
            deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first()
            if not deal:
                return jsonify({"status": "error", "message": "Deal not found"}), 404

        def _pick_str(name, fallback=""):
            val = (request.form.get(name) or "").strip()
            if val:
                return val
            if deal is not None:
                return str(getattr(deal, name, "") or fallback).strip()
            return fallback

        def _pick_float(form_key, *deal_attrs):
            raw = request.form.get(form_key)
            val = safe_float(raw)
            if val is not None:
                return val
            if deal is not None:
                for attr in deal_attrs:
                    existing = safe_float(getattr(deal, attr, None))
                    if existing is not None:
                        return existing
            return 0.0

        address = _pick_str("address") or (
            (
                getattr(deal, "property_address", None)
                or getattr(deal, "address", None)
                or getattr(deal, "street_address", None)
                or ""
            ).strip()
            if deal is not None else ""
        )

        property_type = (
            (request.form.get("property_type") or "").strip().lower()
            or (
                (
                    getattr(deal, "property_type", None)
                    or getattr(deal, "asset_type", None)
                    or ""
                ).strip().lower()
                if deal is not None else ""
            )
        )

        description = (request.form.get("description") or "").strip()
        if not description and deal is not None:
            description = (getattr(deal, "notes", None) or "").strip()

        price = _pick_float("price", "purchase_price")
        rehab = _pick_float("rehab", "rehab_cost", "estimated_rehab_cost")
        arv = _pick_float("arv", "arv")
        estimated_rent = _pick_float("estimated_rent", "estimated_rent")

        total_basis = price + rehab
        flip_profit = arv - total_basis if arv else 0.0
        flip_margin = (flip_profit / arv * 100) if arv else 0.0

        if not estimated_rent and arv:
            estimated_rent = arv * 0.008

        annual_rent = estimated_rent * 12
        gross_yield = (annual_rent / total_basis * 100) if total_basis else 0.0
        monthly_carry_proxy = total_basis * 0.01 if total_basis else 0.0
        dscr_proxy = (estimated_rent / monthly_carry_proxy) if monthly_carry_proxy else 0.0

        strategies = []

        if arv > 0:
            flip_score = 0
            if flip_profit >= 25000:
                flip_score += 35
            elif flip_profit >= 15000:
                flip_score += 25
            elif flip_profit > 0:
                flip_score += 10

            if flip_margin >= 18:
                flip_score += 30
            elif flip_margin >= 12:
                flip_score += 20
            elif flip_margin >= 8:
                flip_score += 10

            if rehab <= (price * 0.25 if price else rehab):
                flip_score += 15

            strategies.append({
                "name": "Fix & Flip",
                "score": min(round(flip_score), 100),
                "profit": round(flip_profit, 2),
                "margin_pct": round(flip_margin, 2),
                "risk": "Medium" if (price and rehab <= price * 0.35) else "High",
                "summary": "Renovate and sell for a near-term capital gain.",
                "best_for": "Deals with healthy spread between total basis and ARV."
            })

        rental_score = 0
        if gross_yield >= 10:
            rental_score += 35
        elif gross_yield >= 8:
            rental_score += 25
        elif gross_yield >= 6:
            rental_score += 15

        if dscr_proxy >= 1.25:
            rental_score += 30
        elif dscr_proxy >= 1.1:
            rental_score += 20
        elif dscr_proxy >= 1.0:
            rental_score += 10

        if rehab <= (price * 0.30 if price else rehab):
            rental_score += 15

        strategies.append({
            "name": "Buy & Hold Rental",
            "score": min(round(rental_score), 100),
            "rent_estimate": round(estimated_rent, 2),
            "annual_rent": round(annual_rent, 2),
            "gross_yield_pct": round(gross_yield, 2),
            "dscr_proxy": round(dscr_proxy, 2),
            "risk": "Low" if dscr_proxy >= 1.2 else "Medium",
            "summary": "Renovate and hold for recurring long-term rental income.",
            "best_for": "Deals with stable rent coverage and durable cash flow."
        })

        if property_type in ["land", "lot", "vacant land"]:
            dev_score = 55
            if arv > 0 and total_basis > 0 and flip_margin >= 15:
                dev_score += 15

            strategies.append({
                "name": "Ground-Up Development",
                "score": min(round(dev_score), 100),
                "risk": "High",
                "summary": "Construct a new property for resale, refinance, or long-term hold.",
                "best_for": "Land or teardown opportunities with strong end-value potential."
            })

        recommended_strategy = None
        if strategies:
            strategies = sorted(strategies, key=lambda s: s.get("score", 0), reverse=True)
            recommended_strategy = strategies[0]["name"]

        analysis = {
            "address": address,
            "property_type": property_type,
            "description": description,
            "price": round(price, 2),
            "rehab": round(rehab, 2),
            "arv": round(arv, 2),
            "estimated_rent": round(estimated_rent, 2),
            "metrics": {
                "total_basis": round(total_basis, 2),
                "flip_profit": round(flip_profit, 2),
                "flip_margin_pct": round(flip_margin, 2),
                "annual_rent": round(annual_rent, 2),
                "gross_yield_pct": round(gross_yield, 2),
                "dscr_proxy": round(dscr_proxy, 2),
            },
            "recommended_strategy": recommended_strategy,
            "strategies": strategies,
        }

        if deal:
            results = _deal_results(deal)
            results["strategy_analysis"] = analysis

            if recommended_strategy:
                deal.recommended_strategy = recommended_strategy
                if not deal.strategy:
                    deal.strategy = recommended_strategy

            _set_deal_results(deal, results)
            db.session.commit()

        return jsonify({
            "status": "ok",
            "saved_to_deal": bool(deal),
            "deal_id": deal.id if deal else None,
            **analysis,
        })

    except Exception as e:
        current_app.logger.exception("deal_architect_analyze failed")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@investor_bp.route("/deal-architect/strategy", methods=["POST"])
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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

@investor_bp.route("/deal-studio/rehab/render", methods=["POST"])
@investor_bp.route("/deals/visualizer", methods=["POST"])
@investor_bp.route("/renovation_visualizer", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
def renovation_visualizer():
    deal = None

    try:
        image_file = request.files.get("image_file")
        image_url = (request.form.get("image_url") or "").strip()

        style_prompt = (
            request.form.get("style_prompt")
            or request.form.get("prompt_notes")
            or ""
        ).strip()

        requested_style_preset = (
            request.form.get("style_preset")
            or request.form.get("preset")
            or ""
        ).strip()

        variations_raw = (
            request.form.get("variations")
            or request.form.get("count")
            or "1"
        )

        try:
            variations = max(1, min(int(variations_raw), 4))
        except (TypeError, ValueError):
            variations = 1

        save_to_deal = (request.form.get("save_to_deal") or "").lower() in (
            "1", "true", "yes", "on"
        )
        mode = (request.form.get("mode") or "photo").strip().lower()

        saved_property_id = _normalize_int(
            request.form.get("saved_property_id") or request.form.get("prop_id")
        )
        deal_id = _normalize_int(request.form.get("deal_id"))
        property_id = (request.form.get("property_id") or "").strip() or None

        if not image_file and not image_url:
            return jsonify({
                "status": "error",
                "message": "Provide image_file or image_url.",
            }), 400

        if image_url.startswith("blob:"):
            return jsonify({
                "status": "error",
                "message": "Browser preview URL detected. Please upload the image file.",
            }), 400

        if image_url and not (
            image_url.startswith("http://") or image_url.startswith("https://")
        ):
            return jsonify({
                "status": "error",
                "message": "image_url must start with http:// or https://",
            }), 400

        if not style_prompt and not requested_style_preset:
            return jsonify({
                "status": "error",
                "message": "Add a style prompt or choose a preset.",
            }), 400
 
        if deal_id:
            deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first()
            if not deal:
                return jsonify({
                    "status": "error",
                    "message": "Deal not found or not authorized.",
                }), 404

            if _deal_render_lock_active(deal):
                return jsonify({
                    "status": "error",
                    "message": "A renovation render is already in progress for this deal.",
                }), 409

            _set_deal_render_processing(deal)
            db.session.commit()

            if saved_property_id is None and getattr(deal, "saved_property_id", None):
                saved_property_id = deal.saved_property_id

            if not property_id and getattr(deal, "property_id", None):
                property_id = deal.property_id

        raw = image_file.read() if image_file else download_image_bytes(image_url)

        if not raw:
            return jsonify({
                "status": "error",
                "message": "Empty image input.",
            }), 400

        # ✅ FIX ROTATION HERE
        from PIL import Image, ImageOps
        import io

        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img)  # 🔥 fixes sideways images

        # Convert back to bytes
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        raw = buf.getvalue()

        before_url = _upload_before_image(raw)

        if deal is not None:
            _save_before_url_to_deal(deal, before_url)

        style_preset = _normalize_style_preset(requested_style_preset)
        final_prompt = _compose_style_prompt(
            style_prompt,
            requested_style_preset,
            keep_layout=False,
        )
        render_batch_id = uuid.uuid4().hex

        payload = {
            "image_base64": base64.b64encode(raw).decode("utf-8") if image_file else "",
            "image_url": "" if image_file else before_url,
            "mode": mode,
            "preset": style_preset,
            "prompt": final_prompt,
            "count": 1,
            "steps": 24,
            "strength": 0.65,
            "controlnet_scale": 0.80,
            "guidance": 8.0,
            "width": 640,
            "height": 640,
        }

        current_app.logger.warning(f"RENOVATION ENGINE PAYLOAD: {payload}")

        engine_json = _post_renovation_engine_json(
            "/v1/renovate",
            payload,
            timeout=UPLOAD_TIMEOUT if image_file else RENDER_TIMEOUT,
        )

        current_app.logger.warning(f"ENGINE JSON: {engine_json}")
        current_app.logger.warning(
            f"images_base64 count: {len(engine_json.get('images_base64', []) or [])}"
        )

        images_b64 = engine_json.get("images_base64", []) or []

        if not images_b64:
            return jsonify({
                "status": "error",
                "message": "GPU engine returned no images.",
            }), 502

        after_urls = _upload_after_images_from_b64(images_b64, render_batch_id)

        if not after_urls:
            return jsonify({
                "status": "error",
                "message": "Render completed but uploads failed.",
            }), 500

        saved_count = 0
        if save_to_deal and deal is not None:
            saved_count = _save_mockups_for_deal(
                deal=deal,
                before_url=before_url,
                after_urls=after_urls,
                style_prompt=style_prompt,
                style_preset=style_preset,
                mode=mode,
                saved_property_id=saved_property_id,
                property_id=property_id,
            )

        if deal is not None:
            _clear_deal_render_processing(deal)
            db.session.commit()

        return jsonify({
            "status": "ok",
            "render_batch_id": render_batch_id,
            "mode": mode,
            "before_url": before_url,
            "images": after_urls,
            "style_preset": style_preset,
            "style_prompt": final_prompt,
            "variations": len(after_urls),
            "save_to_deal": save_to_deal,
            "saved_count": saved_count,
            "deal_id": deal.id if deal else None,
            "saved_property_id": saved_property_id,
            "property_id": property_id,
        })

    except Exception as e:
        current_app.logger.exception("renovation_visualizer failed")

        if deal is not None:
            try:
                _clear_deal_render_processing(deal)
                db.session.commit()
            except Exception:
                db.session.rollback()

        return jsonify({
            "status": "error",
            "message": f"Renovation generator failed: {e}",
        }), 500


# =========================================================
# BLUEPRINT TO CONCEPT
# =========================================================

@investor_bp.route("/deal-studio/rehab/blueprint-render", methods=["POST"])
@investor_bp.route("/blueprint_to_room", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
def blueprint_to_room():
    deal = None

    try:
        blueprint_file = request.files.get("blueprint_file")
        blueprint_url = (request.form.get("blueprint_url") or "").strip()

        requested_style_preset = (request.form.get("style_preset") or "luxury_modern").strip().lower()
        renovation_level = (request.form.get("renovation_level") or "medium").strip().lower()

        deal_id = _normalize_int(request.form.get("deal_id"))
        saved_property_id = _normalize_int(request.form.get("saved_property_id"))

        if not blueprint_file and not blueprint_url:
            return jsonify({"status": "error", "message": "Provide blueprint_file or blueprint_url."}), 400

        style_preset = _normalize_style_preset(requested_style_preset)
        render_batch_id = uuid.uuid4().hex
        structure = None
        room_type = "room"
        parse_warning = None

        if deal_id:
            deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first()
            if not deal:
                return jsonify({"status": "error", "message": "Deal not found or not authorized."}), 404

            if _deal_render_lock_active(deal):
                return jsonify({
                    "status": "error",
                    "message": "A blueprint render is already in progress for this deal."
                }), 409

            _set_deal_render_processing(deal)
            db.session.commit()

            if saved_property_id is None and getattr(deal, "saved_property_id", None):
                saved_property_id = deal.saved_property_id

        raw = blueprint_file.read() if blueprint_file else download_image_bytes(blueprint_url)
        if not raw:
            return jsonify({"status": "error", "message": "Empty blueprint input."}), 400

        blueprint_webp = to_webp_bytes(raw, max_size=2000, quality=90)
        uploaded = spaces_put_bytes(
            blueprint_webp,
            subdir=f"blueprints/{current_user.id}",
            content_type="image/webp",
            filename=f"{render_batch_id}_blueprint.webp",
        )
        blueprint_url = uploaded["url"]

        try:
            structure = extract_blueprint_structure(blueprint_url)
            room_type = infer_room_type(structure) or "room"
        except Exception as e:
            parse_warning = str(e)
            current_app.logger.warning(f"Blueprint parsing warning: {e}")

        style_prompt = build_blueprint_prompt(room_type, style_preset, renovation_level)

        payload = {
            "image_url": blueprint_url,
            "mode": "blueprint",
            "preset": style_preset,
            "prompt": style_prompt,
            "count": 2,
            "steps": 35,
            "strength": 0.40,
            "controlnet_scale": 0.85,
            "guidance": 6.5,
            "width": 1024,
            "height": 1024,
        }

        engine_json = _post_renovation_engine_json(
            "/v1/renovate",
            payload,
            timeout=RENDER_TIMEOUT,
        )

        returned_urls = engine_json.get("saved_paths", []) or []
        images_b64 = engine_json.get("images_base64", []) or []

        if returned_urls:
            after_urls = returned_urls
        else:
            if not images_b64:
                return jsonify({"status": "error", "message": "GPU engine returned no images."}), 502

            after_urls = _upload_after_images_from_b64(images_b64, render_batch_id)
            if not after_urls:
                return jsonify({"status": "error", "message": "Render completed but uploads failed."}), 500

        saved_count = 0
        if deal is not None:
            saved_count = _save_mockups_for_deal(
                deal=deal,
                before_url=blueprint_url,
                after_urls=after_urls,
                style_prompt=style_prompt,
                style_preset=style_preset,
                mode="blueprint",
                saved_property_id=saved_property_id,
            )

        if deal is not None:
            _clear_deal_render_processing(deal)
            db.session.commit()

        return jsonify({
            "status": "ok",
            "render_batch_id": render_batch_id,
            "blueprint_url": blueprint_url,
            "room_type": room_type,
            "structure": structure,
            "style_preset": style_preset,
            "renovation_level": renovation_level,
            "style_prompt": style_prompt,
            "images": after_urls,
            "count": len(after_urls),
            "saved_count": saved_count,
            "deal_id": deal.id if deal else None,
            "saved_property_id": saved_property_id,
            "warning": parse_warning,
        })

    except Exception as e:
        current_app.logger.exception("blueprint_to_room failed")

        if deal is not None:
            try:
                _clear_deal_render_processing(deal)
                db.session.commit()
            except Exception:
                db.session.rollback()

        return jsonify({"status": "error", "message": f"Blueprint render failed: {e}"}), 500

# =========================================================
# SAVE MOCKUPS MANUALLY
# =========================================================

@investor_bp.route("/deals/<int:deal_id>/mockups/save", methods=["POST"])
@investor_bp.route("/deals/<int:deal_id>/mockups/save_legacy", methods=["POST"])
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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

        res = requests.post(
            _scope_engine_url("/v1/rehab_scope"),
            json={"image_url": image_url},
            headers=_scope_engine_headers(),
            timeout=60,
        )
        res.raise_for_status()
        return jsonify(res.json())

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
@csrf.exempt
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
@csrf.exempt
@login_required
@role_required("investor")
def ask_ai_post():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    question = request.form.get("question") or ""
    parent_id = request.form.get("parent_id")

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
@csrf.exempt
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
@csrf.exempt
@login_required
@role_required("investor")
def budget():
    ip = InvestorProfile.query.filter_by(user_id=current_user.id).first()
    assistant = AIAssistant()

    if request.method == "POST":
        expenses = request.form.to_dict()
        ai_tip = assistant.generate_reply(
            f"Analyze investor expenses: {expenses}",
            "investor_budget",
        )
        return render_template(
            "investor/budget_result.html",
            investor=ip,
            ai_tip=ai_tip,
            title="Budget Results",
            active_tab="budget"
        )

    return render_template(
        "investor/budget.html",
        investor=ip,
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

    if deal_id is None:
        query_deal_id = request.args.get("deal_id", type=int)
        if query_deal_id:
            deal_id = query_deal_id

    if deal_id:
        deal = Deal.query.filter_by(
            id=deal_id,
            user_id=current_user.id
        ).first_or_404()

        results = deal.results_json or {}

    purchase_price = float(getattr(deal, "purchase_price", 0) or 0) if deal else 0
    arv = float(getattr(deal, "arv", 0) or 0) if deal else 0
    rehab_cost = float(getattr(deal, "rehab_cost", 0) or 0) if deal else 0

    return render_template(
        "investor/budget_studio.html",
        deal=deal,
        results=results,
        purchase_price=purchase_price,
        arv=arv,
        rehab_cost=rehab_cost,
        page_title="Budget Studio",
        page_subtitle="Control your numbers, track execution, and stay profitable."
    )


@investor_bp.route("/budget-studio/create", methods=["GET", "POST"])
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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

@investor_bp.route("/billing", methods=["GET"])
@investor_bp.route("/payments", methods=["GET"])
@login_required
@role_required("investor")
def payments():
    user = current_user
    subscription_plan = getattr(user, "subscription_plan", "Free")

    payments = (PaymentRecord.query
        .filter_by(user_id=user.id)
        .order_by(PaymentRecord.timestamp.desc())
        .all())

    return render_template(
        "investor/payments.html",
        user=user,
        subscription_plan=subscription_plan,
        payments=payments,
        title="Billing",
        active_tab="billing"
    )


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
@csrf.exempt
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

@investor_bp.route("/resources/request-connection", methods=["POST"])
@csrf.exempt
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

    category = (request.args.get("category") or "").strip()
    city = (request.args.get("city") or "").strip()
    state = (request.args.get("state") or "").strip()
    zip_code = (request.args.get("zip_code") or "").strip()

    internal_results = []
    external_results = []
    fallback_used = False

    if category and (city or state or zip_code):
        internal_results = search_internal_partners(
            Partner,
            category=category,
            city=city,
            state=state,
            zip_code=zip_code,
        )

        if not internal_results:
            fallback_used = True
            location_text = ", ".join([x for x in [city, state, zip_code] if x])
            external_results = search_google_places(location_text, category)

    recent_requests = []
    if ip:
        recent_requests = (
            PartnerConnectionRequest.query
            .filter_by(investor_profile_id=ip.id)
            .order_by(PartnerConnectionRequest.created_at.desc())
            .limit(10)
            .all()
        )

    return render_template(
        "investor/partner_marketplace.html",
        category=category,
        city=city,
        state=state,
        zip_code=zip_code,
        internal_results=internal_results,
        external_results=external_results,
        fallback_used=fallback_used,
        recent_requests=recent_requests,
        active_tab="partners",
        title="Ravlo Partner Marketplace",
    )


@investor_bp.route("/partners/request", methods=["POST"])
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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

@investor_bp.route("/partners/request", methods=["POST"])
@csrf.exempt
@login_required
@role_required("investor")
def create_partner_connection_request():
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

@investor_bp.route("/partners/save-external", methods=["POST"])
@csrf.exempt
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
@csrf.exempt
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
