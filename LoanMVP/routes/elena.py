from datetime import datetime, timedelta
from flask import (
    Blueprint,
    request,
    jsonify,
    render_template,
    redirect,
    url_for,
    flash,
    session,
)
from sqlalchemy import or_
import pandas as pd
from LoanMVP.extensions import db

from LoanMVP.models.vip_models import VIPProfile, VIPAssistantSuggestion

from LoanMVP.models.vip_models import VIPProfile, VIPAssistantSuggestion
from LoanMVP.models.elena_models import (
    ElenaClient,
    ElenaListing,
    ElenaFlyer,
    ElenaInteraction,
    InteractionType,
)

from LoanMVP.services.vip_ai_pilot import parse_vip_command
from LoanMVP.services.ai_service import generate_text
from LoanMVP.services.elena_templates import (
    render_template as render_elena_template,
    TemplateType,
)
from LoanMVP.utils.decorators import role_required

from LoanMVP.routes.canva import get_valid_access_token
from LoanMVP.services.canva_service import (
    create_design,
    create_export_job,
    get_export_job,
)

elena_bp = Blueprint("elena", __name__, url_prefix="/elena")


PIPELINE_STAGES = [
    ("new", "New"),
    ("warm", "Warm"),
    ("active", "Active"),
    ("under_contract", "Under Contract"),
    ("closed", "Closed"),
]

LISTING_STATUSES = [
    ("active", "Active"),
    ("pending", "Pending"),
    ("sold", "Sold"),
    ("withdrawn", "Withdrawn"),
]

CLIENT_ROLES = [
    "realtor",
    "investor",
    "contractor",
    "partner",
    "student",
    "buyer",
    "seller",
    "other",
]

INTERACTION_TYPES = [
    InteractionType.EMAIL,
    InteractionType.CALL,
    InteractionType.TEXT,
    InteractionType.MEETING,
    InteractionType.SHOWING,
    InteractionType.NOTE,
    InteractionType.FOLLOW_UP,
]


FRANK_MARKETS = ["Hudson Valley", "Sarasota"]


def get_current_market():
    return session.get("elena_market", "All Markets")


def set_current_market(value):
    allowed = {"All Markets", *FRANK_MARKETS}
    session["elena_market"] = value if value in allowed else "All Markets"


def infer_market_from_listing_data(data):
    market = (data.get("market") or "").strip()
    if market:
        return market

    city = (data.get("city") or "").strip().lower()
    state = (data.get("state") or "").strip().lower()

    if state == "ny":
        return "Hudson Valley"
    if state == "fl" and "sarasota" in city:
        return "Sarasota"
    if state == "fl":
        return "Sarasota"

    return None


def _clean_listing_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _to_int(value):
    value = _clean_listing_value(value)
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return int(digits) if digits else None


def _parse_due_at(raw):
    if not raw:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _template_defaults():
    return {
        "address": "",
        "city": "",
        "state": "",
        "zip_code": "",
        "beds": "",
        "baths": "",
        "sqft": "",
        "price": "",
        "description": "",
        "status": "",
        "days_on_market": "",
        "offer_details": "",
        "date": "",
        "time": "",
        "old_price": "",
        "new_price": "",
        "buyer_type": "",
        "budget": "",
        "areas": "",
        "area": "",
        "timeframe": "",
        "stats": "",
        "client_name": "",
        "pipeline_stage": "",
        "context": "",
        "source": "",
        "email": "",
        "phone": "",
        "title": "",
        "cta": "",
    }


def _get_template_enum(template_type_value):
    if not template_type_value:
        return None
    try:
        return TemplateType(template_type_value)
    except ValueError:
        return None

def upsert_listing_from_feed(data):
    mls_number = _clean_listing_value(data.get("mls_number"))
    listing_id = data.get("listing_id")

    listing = None

    if mls_number:
        listing = ElenaListing.query.filter_by(mls_number=mls_number).first()

    if not listing and listing_id:
        listing = ElenaListing.query.get(listing_id)

    if not listing:
        listing = ElenaListing()
        db.session.add(listing)

    listing.mls_number = mls_number
    listing.address = _clean_listing_value(data.get("address")) or listing.address
    listing.city = _clean_listing_value(data.get("city")) or listing.city
    listing.state = _clean_listing_value(data.get("state")) or listing.state
    listing.zip_code = _clean_listing_value(data.get("zip_code") or data.get("zip")) or listing.zip_code
    listing.market = infer_market_from_listing_data(data) or listing.market

    listing.price = _to_int(data.get("price"))
    listing.beds = _to_int(data.get("beds"))
    listing.baths = _to_int(data.get("baths"))
    listing.sqft = _to_int(data.get("sqft"))

    listing.description = _clean_listing_value(data.get("description")) or listing.description
    listing.photos_json = data.get("photos_json") or listing.photos_json
    listing.status = _clean_listing_value(data.get("status")) or listing.status or "active"

    db.session.flush()
    return listing


def upsert_flyer_for_listing(listing):
    flyer = ElenaFlyer.query.filter_by(listing_id=listing.id).first()

    body_parts = []
    if listing.price:
        body_parts.append(f"${listing.price:,}")
    if listing.beds is not None:
        body_parts.append(f"{listing.beds} bd")
    if listing.baths is not None:
        body_parts.append(f"{listing.baths} ba")
    if listing.sqft:
        body_parts.append(f"{listing.sqft:,} sqft")
    if listing.market:
        body_parts.append(listing.market)

    summary_line = " • ".join(body_parts)
    if listing.description:
        body = f"{summary_line}\n\n{listing.description}" if summary_line else listing.description
    else:
        body = summary_line

    if not flyer:
        flyer = ElenaFlyer(
            flyer_type="listing",
            property_address=listing.address,
            property_id=str(listing.id),
            body=body,
            listing_id=listing.id,
        )
        db.session.add(flyer)
    else:
        flyer.flyer_type = flyer.flyer_type or "listing"
        flyer.property_address = listing.address
        flyer.property_id = str(listing.id)
        flyer.body = body or flyer.body

    if hasattr(flyer, "canva_status") and not getattr(flyer, "canva_status", None):
        flyer.canva_status = "draft"

    db.session.flush()
    return flyer


def process_listing_import(data):
    listing = upsert_listing_from_feed(data)
    flyer = upsert_flyer_for_listing(listing)
    db.session.commit()
    return listing, flyer

def get_or_create_realtor_vip_profile():
    profile = VIPProfile.query.filter_by(display_name="Elena").first()
    if profile:
        return profile

    profile = VIPProfile(
        user_id=1,  # replace later if you want true current-user binding
        display_name="Elena",
        role_type="realtor",
        assistant_name="Copilot",
    )
    db.session.add(profile)
    db.session.commit()
    return profile

@elena_bp.get("/")
@role_required("partner_group", "admin")
def dashboard():
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    current_market = get_current_market()

    total_clients = ElenaClient.query.count()
    new_leads = ElenaClient.query.filter(ElenaClient.created_at >= week_ago).count()

    active_listings_query = ElenaListing.query.filter_by(status="active")
    if current_market != "All Markets":
        active_listings_query = active_listings_query.filter(
            ElenaListing.market == current_market
        )
    active_listings = active_listings_query.count()

    followups_due = ElenaInteraction.query.filter(
        ElenaInteraction.due_at.isnot(None),
        ElenaInteraction.due_at >= now,
        ElenaInteraction.due_at <= now + timedelta(days=7),
    ).count()

    summary = {
        "total_clients": total_clients,
        "new_leads": new_leads,
        "active_listings": active_listings,
        "followups_due": followups_due,
    }

    PIPELINE_STAGES = [
        ("new", "New"),
        ("warm", "Warm"),
        ("active", "Active"),
        ("under_contract", "Under Contract"),
        ("closed", "Closed"),
    ]
    LISTING_STATUSES = [
        ("active", "Active"),
        ("pending", "Pending"),
        ("sold", "Sold"),
        ("withdrawn", "Withdrawn"),
    ]

    pipeline_groups = []
    for stage_key, stage_label in PIPELINE_STAGES:
        stage_query = ElenaClient.query.filter(
            ElenaClient.pipeline_stage == stage_key
        )
        stage_total = stage_query.count()
        clients = (
            stage_query
            .order_by(ElenaClient.updated_at.desc())
            .limit(12)
            .all()
        )
        pipeline_groups.append(
            {
                "key": stage_key,
                "label": stage_label,
                "clients": clients,
                "count": stage_total,
            }
        )

    canonical_keys = {s[0] for s in PIPELINE_STAGES}
    unstaged_filter = or_(
        ElenaClient.pipeline_stage.is_(None),
        ~ElenaClient.pipeline_stage.in_(canonical_keys),
    )
    unstaged_total = ElenaClient.query.filter(unstaged_filter).count()
    unstaged = (
        ElenaClient.query
        .filter(unstaged_filter)
        .order_by(ElenaClient.updated_at.desc())
        .limit(12)
        .all()
    )
    if unstaged_total:
        pipeline_groups.insert(
            0,
            {
                "key": "unstaged",
                "label": "Unstaged",
                "clients": unstaged,
                "count": unstaged_total,
            },
        )

    recent_interactions = (
        ElenaInteraction.query
        .order_by(ElenaInteraction.created_at.desc())
        .limit(10)
        .all()
    )

    status_filter = (request.args.get("listing_status") or "").strip().lower()
    listings_query = ElenaListing.query

    if current_market != "All Markets":
        listings_query = listings_query.filter(ElenaListing.market == current_market)

    if status_filter and status_filter in {s[0] for s in LISTING_STATUSES}:
        listings_query = listings_query.filter_by(status=status_filter)

    listings = listings_query.order_by(ElenaListing.updated_at.desc()).limit(12).all()

    recent_flyers_query = ElenaFlyer.query
    if current_market != "All Markets":
        recent_flyers_query = (
            recent_flyers_query
            .join(ElenaListing, ElenaFlyer.listing_id == ElenaListing.id)
            .filter(ElenaListing.market == current_market)
        )

    recent_flyers = (
        recent_flyers_query
        .order_by(ElenaFlyer.created_at.desc())
        .limit(5)
        .all()
    )

    copilot_suggestions = (
        VIPAssistantSuggestion.query
        .order_by(VIPAssistantSuggestion.created_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "elena/dashboard.html",
        summary=summary,
        pipeline_groups=pipeline_groups,
        pipeline_stages=PIPELINE_STAGES,
        recent_interactions=recent_interactions,
        listings=listings,
        listing_statuses=LISTING_STATUSES,
        listing_status_filter=status_filter,
        recent_flyers=recent_flyers,
        template_types=[t.value for t in TemplateType],
        current_market=current_market,
        available_markets=FRANK_MARKETS,
        copilot_suggestions=copilot_suggestions,
        portal="elena",
        portal_name="Elena",
        portal_home=url_for("elena.dashboard"),
    )

@elena_bp.route("/clients/new", methods=["GET", "POST"])
@role_required("partner_group", "admin")
def client_new():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Client name is required.", "warning")
            return redirect(url_for("elena.client_new"))

        client = ElenaClient(
            name=name,
            email=(request.form.get("email") or None),
            phone=(request.form.get("phone") or None),
            role=(request.form.get("role") or None),
            tags=(request.form.get("tags") or None),
            pipeline_stage=(request.form.get("pipeline_stage") or "new"),
            notes=(request.form.get("notes") or None),
            preferred_areas=(request.form.get("preferred_areas") or None),
            budget=(request.form.get("budget") or None),
        )
        db.session.add(client)
        db.session.commit()
        flash(f"Client '{client.name}' added.", "success")
        return redirect(url_for("elena.dashboard"))

    return render_template(
        "elena/client_form.html",
        client=None,
        pipeline_stages=PIPELINE_STAGES,
        client_roles=CLIENT_ROLES,
        portal="elena",
        portal_name="Elena",
        portal_home=url_for("elena.dashboard"),
    )


@elena_bp.route("/listings/new", methods=["GET", "POST"])
@role_required("partner_group", "admin")
def listing_new():
    LISTING_STATUSES = [
        ("active", "Active"),
        ("pending", "Pending"),
        ("sold", "Sold"),
        ("withdrawn", "Withdrawn"),
    ]

    if request.method == "POST":
        address = (request.form.get("address") or "").strip()
        city = (request.form.get("city") or "").strip()
        state = (request.form.get("state") or "").strip()
        zip_code = (request.form.get("zip_code") or "").strip()
        market = (request.form.get("market") or "").strip() or None

        missing = [
            f for f, v in [
                ("address", address),
                ("city", city),
                ("state", state),
                ("zip_code", zip_code),
            ] if not v
        ]
        if missing:
            flash(f"Missing required fields: {', '.join(missing)}", "warning")
            return redirect(url_for("elena.listing_new"))

        def _int(val):
            try:
                return int(val) if val not in (None, "") else None
            except (TypeError, ValueError):
                return None

        client_id = _int(request.form.get("client_id"))
        listing = ElenaListing(
            mls_number=(request.form.get("mls_number") or None),
            address=address,
            city=city,
            state=state,
            zip_code=zip_code,
            market=market,
            beds=_int(request.form.get("beds")),
            baths=_int(request.form.get("baths")),
            sqft=_int(request.form.get("sqft")),
            price=_int(request.form.get("price")),
            description=(request.form.get("description") or None),
            status=(request.form.get("status") or "active"),
            client_id=client_id,
        )
        db.session.add(listing)
        db.session.commit()
        flash(f"Listing at {listing.address} added.", "success")
        return redirect(url_for("elena.dashboard"))

    clients = ElenaClient.query.order_by(ElenaClient.name.asc()).all()
    return render_template(
        "elena/listing_form.html",
        listing=None,
        listing_statuses=LISTING_STATUSES,
        available_markets=FRANK_MARKETS,
        current_market=get_current_market(),
        clients=clients,
        portal="elena",
        portal_name="Elena",
        portal_home=url_for("elena.dashboard"),
    )

@elena_bp.route("/interactions/new", methods=["GET", "POST"])
@role_required("partner_group", "admin")
def interaction_new():
    if request.method == "POST":
        try:
            client_id = int(request.form.get("client_id") or 0)
        except ValueError:
            client_id = 0

        interaction_type = (request.form.get("interaction_type") or "").strip()
        content = (request.form.get("content") or "").strip()

        if not client_id or not interaction_type or not content:
            flash(
                "client_id, interaction_type, and content are required.",
                "warning",
            )
            return redirect(url_for("elena.interaction_new"))

        client = ElenaClient.query.get(client_id)
        if not client:
            flash("Client not found.", "danger")
            return redirect(url_for("elena.interaction_new"))

        interaction = ElenaInteraction(
            client_id=client.id,
            interaction_type=interaction_type,
            content=content,
            meta=(request.form.get("meta") or None),
            due_at=_parse_due_at(request.form.get("due_at")),
        )
        db.session.add(interaction)
        db.session.commit()
        flash(
            f"Interaction logged for {client.name} ({interaction.interaction_type}).",
            "success",
        )
        return redirect(url_for("elena.dashboard"))

    clients = ElenaClient.query.order_by(ElenaClient.name.asc()).all()
    return render_template(
        "elena/interaction_form.html",
        interaction=None,
        clients=clients,
        interaction_types=INTERACTION_TYPES,
        portal="elena",
        portal_name="Elena",
        portal_home=url_for("elena.dashboard"),
    )


@elena_bp.get("/templates")
def list_templates():
    return jsonify({"templates": [t.value for t in TemplateType]})


@elena_bp.get("/templates/auto_fill/<int:client_id>/<template_type>")
def template_auto_fill(client_id, template_type):
    client = ElenaClient.query.get(client_id)
    if not client:
        return jsonify({"error": "Client not found"}), 404

    variables = {
        "client_name": client.name,
        "email": getattr(client, "email", "") or "",
        "phone": getattr(client, "phone", "") or "",
        "pipeline_stage": getattr(client, "pipeline_stage", "") or "",
        "context": getattr(client, "notes", "") or "",
        "areas": getattr(client, "preferred_areas", "") or "",
        "budget": getattr(client, "budget", "") or "",
    }

    last_interaction = (
        ElenaInteraction.query.filter_by(client_id=client_id)
        .order_by(ElenaInteraction.created_at.desc())
        .first()
    )

    if last_interaction:
        variables["last_contact"] = last_interaction.created_at.strftime("%Y-%m-%d")
        variables["last_message"] = (last_interaction.content or "")[:200]

    return jsonify(
        {
            "client_id": client_id,
            "template_type": template_type,
            "variables": variables,
        }
    )


@elena_bp.get("/templates/listing_auto_fill/<int:listing_id>/<template_type>")
def template_listing_auto_fill(listing_id, template_type):
    listing = ElenaListing.query.get(listing_id)
    if not listing:
        return jsonify({"error": "Listing not found"}), 404

    variables = {
        "address": listing.address,
        "city": listing.city,
        "state": listing.state,
        "zip_code": listing.zip_code,
        "beds": listing.beds,
        "baths": listing.baths,
        "sqft": listing.sqft,
        "price": listing.price,
        "description": getattr(listing, "description", "") or "",
    }

    return jsonify(
        {
            "listing_id": listing_id,
            "template_type": template_type,
            "variables": variables,
        }
    )


@elena_bp.post("/templates/preview")
def template_preview():
    data = request.json or {}
    template_type = data.get("template_type")
    variables = data.get("variables", {})

    if not template_type:
        return jsonify({"error": "template_type is required"}), 400

    prompt = render_elena_template(TemplateType(template_type), **variables)

    return jsonify({"template_type": template_type, "prompt": prompt})


@elena_bp.post("/templates/generate")
def template_generate():
    data = request.json or {}
    template_type = data.get("template_type")
    variables = data.get("variables", {})

    if not template_type:
        return jsonify({"error": "template_type is required"}), 400

    prompt = render_elena_template(TemplateType(template_type), **variables)
    output = generate_text(prompt)

    return jsonify(
        {
            "template_type": template_type,
            "prompt": prompt,
            "output": output,
        }
    )


@elena_bp.post("/templates/generate_and_log")
def template_generate_and_log():
    data = request.json or {}
    client_id = data.get("client_id")
    template_type = data.get("template_type")
    variables = data.get("variables", {})

    if not client_id:
        return jsonify({"error": "client_id is required"}), 400
    if not template_type:
        return jsonify({"error": "template_type is required"}), 400

    client = ElenaClient.query.get(client_id)
    if not client:
        return jsonify({"error": "Client not found"}), 404

    prompt = render_elena_template(TemplateType(template_type), **variables)
    output = generate_text(prompt)

    interaction = ElenaInteraction(
        client_id=client.id,
        interaction_type=InteractionType.EMAIL,
        content=output,
        meta=f"template:{template_type}",
    )
    db.session.add(interaction)
    db.session.commit()

    return jsonify(
        {
            "client_id": client.id,
            "template_type": template_type,
            "output": output,
            "interaction_id": interaction.id,
        }
    )


@elena_bp.post("/mls/import")
def mls_import():
    data = request.json or {}
    mls_number = data.get("mls_number")
    auto_generate_flyer = data.get("auto_generate_flyer", False)

    if not mls_number:
        return jsonify({"error": "mls_number is required"}), 400

    listing_data = {
        "address": "123 Main St",
        "city": "Beacon",
        "state": "NY",
        "zip_code": "12508",
        "beds": 3,
        "baths": 2,
        "sqft": 1800,
        "price": 549000,
        "description": "Sample listing description",
        "photos_json": "[]",
    }

    listing = ElenaListing(mls_number=mls_number, **listing_data)
    db.session.add(listing)
    db.session.commit()

    flyer_output = None
    flyer_id = None

    if auto_generate_flyer:
        prompt = render_elena_template(TemplateType.JUST_LISTED, **listing_data)
        flyer_output = generate_text(prompt)

        flyer = ElenaFlyer(
            flyer_type="just_listed",
            property_address=listing.address,
            property_id=str(listing.id),
            body=flyer_output,
            listing_id=listing.id,
        )
        db.session.add(flyer)
        db.session.commit()
        flyer_id = flyer.id

    return jsonify(
        {
            "listing_id": listing.id,
            "flyer_id": flyer_id,
            "flyer": flyer_output,
        }
    )


@elena_bp.get("/template-studio")
def template_studio():
    template_type = request.args.get("template_type")
    client_id = request.args.get("client_id")
    listing_id = request.args.get("listing_id")

    variables = {}

    if client_id and template_type:
        client = ElenaClient.query.get(client_id)
        if client:
            variables.update(
                {
                    "client_name": client.name,
                    "email": getattr(client, "email", "") or "",
                    "phone": getattr(client, "phone", "") or "",
                    "pipeline_stage": getattr(client, "pipeline_stage", "") or "",
                    "context": getattr(client, "notes", "") or "",
                    "areas": getattr(client, "preferred_areas", "") or "",
                    "budget": getattr(client, "budget", "") or "",
                }
            )

    if listing_id and template_type:
        listing = ElenaListing.query.get(listing_id)
        if listing:
            variables.update(
                {
                    "address": listing.address,
                    "city": listing.city,
                    "state": listing.state,
                    "zip_code": listing.zip_code,
                    "beds": listing.beds,
                    "baths": listing.baths,
                    "sqft": listing.sqft,
                    "price": listing.price,
                    "description": getattr(listing, "description", "") or "",
                }
            )

    return render_template(
        "elena/template_studio.html",
        templates=[t.value for t in TemplateType],
        selected_template=template_type,
        variables=variables,
        client_id=client_id,
        listing_id=listing_id,
        preview=None,
        output=None,
        saved_interaction_id=None,
        portal="elena",
        portal_name="Elena",
        portal_home=url_for("elena.dashboard"),
    )


@elena_bp.post("/template-studio/preview")
@role_required("partner_group", "admin")
def template_studio_preview():
    template_type_value = request.form.get("template_type")
    client_id = request.form.get("client_id")
    listing_id = request.form.get("listing_id")

    template_enum = _get_template_enum(template_type_value)
    if not template_enum:
        flash("Please choose a valid template.", "warning")
        return redirect(url_for("elena.template_studio"))

    variables = _template_defaults()
    variables.update({
        k: v
        for k, v in request.form.items()
        if k not in ["template_type", "client_id", "listing_id", "action", "csrf_token"]
    })

    prompt = render_elena_template(template_enum, **variables)

    return render_template(
        "elena/template_studio.html",
        templates=[t.value for t in TemplateType],
        selected_template=template_type_value,
        variables=variables,
        client_id=client_id,
        listing_id=listing_id,
        preview=prompt,
        output=None,
        saved_interaction_id=None,
        saved_flyer_id=None,
        portal="elena",
        portal_name="Elena",
        portal_home=url_for("elena.dashboard"),
    )

@elena_bp.post("/template-studio/generate")
@role_required("partner_group", "admin")
def template_studio_generate():
    template_type = request.form.get("template_type")
    client_id = request.form.get("client_id")
    listing_id = request.form.get("listing_id")

    variables = {
        k: v
        for k, v in request.form.items()
        if k not in ["template_type", "client_id", "listing_id", "action", "csrf_token"]
    }

    template_enum = _get_template_enum(template_type)
    if not template_enum:
        flash("Please choose a valid template.", "warning")
        return redirect(url_for("elena.template_studio"))

    prompt = render_elena_template(template_enum, **variables)
    output = generate_text(prompt)

    return render_template(
        "elena/template_studio.html",
        templates=[t.value for t in TemplateType],
        selected_template=template_type,
        variables=variables,
        client_id=client_id,
        listing_id=listing_id,
        preview=prompt,
        output=output,
        saved_interaction_id=None,
        saved_flyer_id=None,
        portal="elena",
        portal_name="Elena",
        portal_home=url_for("elena.dashboard"),
    )

@elena_bp.post("/template-studio/generate_and_save")
def template_studio_generate_and_save():
    template_type = request.form.get("template_type")
    client_id = request.form.get("client_id")
    listing_id = request.form.get("listing_id")

    variables = {
        k: v
        for k, v in request.form.items()
        if k not in ["template_type", "client_id", "listing_id", "action", "csrf_token"]
    }

    template_enum = _get_template_enum(template_type)
    if not template_enum:
        flash("Please choose a valid template.", "warning")
        return redirect(url_for("elena.template_studio"))

    prompt = render_elena_template(template_enum, **variables)
    output = generate_text(prompt)

    saved_interaction_id = None
    saved_flyer_id = None

    if client_id:
        client = ElenaClient.query.get(client_id)
        if client:
            interaction = ElenaInteraction(
                client_id=client.id,
                interaction_type=InteractionType.EMAIL,
                content=output,
                meta=f"template:{template_type}",
            )
            db.session.add(interaction)
            db.session.commit()
            saved_interaction_id = interaction.id

    if listing_id:
        listing = ElenaListing.query.get(listing_id)
        if listing:
            flyer = ElenaFlyer(
                flyer_type=template_type,
                property_address=listing.address,
                property_id=str(listing.id),
                body=output,
                listing_id=listing.id,
            )
            db.session.add(flyer)
            db.session.commit()
            saved_flyer_id = flyer.id

    return render_template(
        "elena/template_studio.html",
        templates=[t.value for t in TemplateType],
        selected_template=template_type,
        variables=variables,
        client_id=client_id,
        listing_id=listing_id,
        preview=prompt,
        output=output,
        saved_interaction_id=saved_interaction_id,
        saved_flyer_id=saved_flyer_id,
        portal="elena",
        portal_name="Elena",
        portal_home=url_for("elena.dashboard"),
    )


@elena_bp.post("/flyers/<int:listing_id>/create-canva")
@role_required("partner_group", "admin")
def create_canva_flyer(listing_id):
    access_token = get_valid_access_token()
    if not access_token:
        return jsonify({"error": "Canva not connected"}), 400

    listing = ElenaListing.query.get(listing_id)
    if not listing:
        return jsonify({"error": "Listing not found"}), 404

    data = request.json or {}
    template_type = data.get("template_type") or TemplateType.JUST_LISTED.value

    template_enum = _get_template_enum(template_type)
    if not template_enum:
        return jsonify({"error": "Invalid template_type"}), 400

    variables = {
        "address": listing.address,
        "city": listing.city,
        "state": listing.state,
        "zip_code": listing.zip_code,
        "beds": listing.beds,
        "baths": listing.baths,
        "sqft": listing.sqft,
        "price": listing.price,
        "description": getattr(listing, "description", "") or "",
        "status": getattr(listing, "status", "") or "",
        "days_on_market": "",
        "offer_details": "",
        "date": "",
        "time": "",
        "old_price": "",
        "new_price": "",
        "buyer_type": "",
        "budget": "",
        "areas": "",
        "area": "",
        "timeframe": "",
        "stats": "",
        "client_name": "",
        "pipeline_stage": "",
        "context": "",
        "source": "",
        "email": "",
        "phone": "",
        "title": "",
        "cta": "",
    }

    prompt = render_elena_template(template_enum, **variables)
    output = generate_text(prompt)

    flyer = ElenaFlyer(
        flyer_type=template_type,
        property_address=listing.address,
        property_id=str(listing.id),
        body=output,
        listing_id=listing.id,
    )
    db.session.add(flyer)
    db.session.flush()

    design_title = f"{listing.address} - {template_type.replace('_', ' ').title()}"
    design = create_design(access_token, title=design_title)

    flyer.canva_design_id = design.get("id") or design.get("design_id")
    flyer.canva_edit_url = design.get("edit_url") or design.get("urls", {}).get("edit_url")
    flyer.canva_status = "created"
    flyer.canva_last_synced_at = datetime.utcnow()

    db.session.commit()

    return jsonify(
        {
            "flyer_id": flyer.id,
            "listing_id": listing.id,
            "template_type": template_type,
            "prompt": prompt,
            "output": output,
            "canva_design_id": flyer.canva_design_id,
            "canva_edit_url": flyer.canva_edit_url,
            "canva_status": flyer.canva_status,
        }
    ), 201


@elena_bp.post("/flyers/<int:flyer_id>/export-canva")
@role_required("partner_group", "admin")
def export_canva_flyer(flyer_id):
    access_token = get_valid_access_token()
    if not access_token:
        return jsonify({"error": "Canva not connected"}), 400

    flyer = ElenaFlyer.query.get(flyer_id)
    if not flyer:
        return jsonify({"error": "Flyer not found"}), 404

    if not getattr(flyer, "canva_design_id", None):
        return jsonify({"error": "Flyer has no Canva design"}), 400

    export_type = (request.json or {}).get("export_type") or "pdf"
    job = create_export_job(access_token, flyer.canva_design_id, export_type=export_type)

    flyer.canva_export_job_id = job.get("id") or job.get("job_id")
    flyer.canva_status = "export_pending"
    flyer.canva_last_synced_at = datetime.utcnow()
    db.session.commit()

    return jsonify(
        {
            "flyer_id": flyer.id,
            "canva_design_id": flyer.canva_design_id,
            "canva_export_job_id": flyer.canva_export_job_id,
            "canva_status": flyer.canva_status,
        }
    ), 202


@elena_bp.get("/flyers/<int:flyer_id>/export-canva-status")
@role_required("partner_group", "admin")
def export_canva_flyer_status(flyer_id):
    access_token = get_valid_access_token()
    if not access_token:
        return jsonify({"error": "Canva not connected"}), 400

    flyer = ElenaFlyer.query.get(flyer_id)
    if not flyer:
        return jsonify({"error": "Flyer not found"}), 404

    if not getattr(flyer, "canva_export_job_id", None):
        return jsonify({"error": "No Canva export job found"}), 400

    job = get_export_job(access_token, flyer.canva_export_job_id)

    status = job.get("status", "unknown")
    download_url = (
        job.get("download_url")
        or job.get("urls", {}).get("download_url")
        or job.get("result", {}).get("url")
    )

    flyer.canva_status = status
    if download_url:
        flyer.canva_export_url = download_url
    flyer.canva_last_synced_at = datetime.utcnow()
    db.session.commit()

    return jsonify(
        {
            "flyer_id": flyer.id,
            "canva_export_job_id": flyer.canva_export_job_id,
            "canva_status": flyer.canva_status,
            "canva_export_url": flyer.canva_export_url,
        }
    )

@elena_bp.route("/ai-pilot/suggestions/<int:suggestion_id>/approve")
@role_required("partner_group", "admin")
def approve_suggestion(suggestion_id):
    profile = get_or_create_vip_profile()

    suggestion = VIPAssistantSuggestion.query.get_or_404(suggestion_id)

    if suggestion.vip_profile_id != profile.id:
        flash("Not authorized.", "danger")
        return redirect(url_for("vip.ai_pilot"))

    # mark approved
    suggestion.status = "approved"

    # execute action based on type
    if suggestion.suggestion_type == "expense":
        expense = VIPExpense(
            vip_profile_id=profile.id,
            category="general",
            description=suggestion.title,
            amount=suggestion.proposed_amount or 0,
        )
        db.session.add(expense)

    elif suggestion.suggestion_type == "follow_up":
        interaction = VIPInteraction(
            vip_profile_id=profile.id,
            interaction_type="follow_up",
            content=suggestion.body or suggestion.title,
        )
        db.session.add(interaction)

    elif suggestion.suggestion_type in ["email", "text"]:
        action = VIPAssistantAction(
            vip_profile_id=profile.id,
            action_type=suggestion.suggestion_type,
            content=suggestion.body,
            status="draft",
        )
        db.session.add(action)

    suggestion.status = "completed"

    db.session.commit()

    flash("Suggestion applied.", "success")
    return redirect(url_for("vip.ai_pilot"))


@elena_bp.route("/contacts/import", methods=["GET", "POST"])
@role_required("partner_group", "admin")
def import_contacts():
    if request.method == "POST":
        file = request.files.get("file")

        if not file:
            flash("No file uploaded", "warning")
            return redirect(request.url)

        filename = file.filename.lower()

        try:
            if filename.endswith(".csv"):
                df = pd.read_csv(file)
            elif filename.endswith(".xlsx"):
                df = pd.read_excel(file, engine="openpyxl")
            elif filename.endswith(".xls"):
                df = pd.read_excel(file)
            else:
                flash("Unsupported file type.", "danger")
                return redirect(request.url)

        except Exception as e:
            flash(f"Error reading file: {str(e)}", "danger")
            return redirect(request.url)

        # CLEAN DATA
        df.columns = df.columns.str.strip().str.lower()
        df = df.fillna("")

        # AUTO MAP
        column_map = {
            "name": next((c for c in df.columns if "name" in c), None),
            "email": next((c for c in df.columns if "email" in c), None),
            "phone": next((c for c in df.columns if "phone" in c), None),
            "role": next((c for c in df.columns if "role" in c or "type" in c), None),
            "tags": next((c for c in df.columns if "tag" in c), None),
            "notes": next((c for c in df.columns if "note" in c), None),
        }

        session["import_preview"] = df.head(50).to_dict(orient="records")
        session["import_columns"] = list(df.columns)
        session["import_full"] = df.to_dict(orient="records")
        session["column_map"] = column_map

        return redirect(url_for("elena.import_preview"))

    return render_template("elena/import_contacts.html")


@elena_bp.route("/contacts/import/preview", methods=["GET", "POST"])
@role_required("partner_group", "admin")
def import_preview():
    if request.method == "POST":
        mapping = request.form.to_dict()
        data = session.get("import_full", [])

        skip_duplicates = request.form.get("skip_duplicates")

        created = 0
        updated = 0
        skipped = 0

        for row in data:
            email = (row.get(mapping.get("email")) or "").strip().lower()
            phone = (row.get(mapping.get("phone")) or "").strip()

            # skip empty rows
            if not email and not phone:
                skipped += 1
                continue

            existing = None

            if email:
                existing = ElenaClient.query.filter_by(email=email).first()

            if not existing and phone:
                existing = ElenaClient.query.filter_by(phone=phone).first()

            if existing:
                if skip_duplicates:
                    skipped += 1
                    continue

                # UPDATE
                existing.name = row.get(mapping.get("name")) or existing.name
                existing.role = row.get(mapping.get("role")) or existing.role
                existing.tags = row.get(mapping.get("tags")) or existing.tags
                existing.notes = row.get(mapping.get("notes")) or existing.notes

                updated += 1

            else:
                # CREATE
                client = ElenaClient(
                    name=row.get(mapping.get("name")),
                    email=email,
                    phone=phone,
                    role=row.get(mapping.get("role")),
                    tags=row.get(mapping.get("tags")),
                    notes=row.get(mapping.get("notes")),
                )

                db.session.add(client)
                created += 1

        db.session.commit()

        flash(f"{created} created • {updated} updated • {skipped} skipped", "success")
        return redirect(url_for("elena.clients"))

    return render_template(
        "elena/import_preview.html",
        preview=session.get("import_preview"),
        columns=session.get("import_columns"),
        column_map=session.get("column_map"),
    )


@elena_bp.post("/listings/import")
@role_required("partner_group", "admin")
def import_listing():
    data = request.get_json(silent=True) or request.form.to_dict()

    required_fields = ["address", "city", "state", "zip_code"]
    missing = [field for field in required_fields if not _clean_listing_value(data.get(field))]
    if missing:
        return jsonify({
            "error": "Missing required listing fields",
            "missing_fields": missing,
        }), 400

    listing, flyer = process_listing_import(data)

    return jsonify({
        "message": "Listing imported successfully",
        "listing": {
            "id": listing.id,
            "mls_number": listing.mls_number,
            "address": listing.address,
            "city": listing.city,
            "state": listing.state,
            "zip_code": listing.zip_code,
            "market": listing.market,
            "price": listing.price,
            "beds": listing.beds,
            "baths": listing.baths,
            "sqft": listing.sqft,
            "status": listing.status,
            "description": listing.description,
        },
        "flyer": {
            "id": flyer.id,
            "flyer_type": flyer.flyer_type,
            "property_address": flyer.property_address,
            "listing_id": flyer.listing_id,
            "body": flyer.body,
            "canva_status": getattr(flyer, "canva_status", None),
            "canva_design_id": getattr(flyer, "canva_design_id", None),
            "canva_edit_url": getattr(flyer, "canva_edit_url", None),
        }
    }), 201

@elena_bp.post("/market/switch")
@role_required("partner_group", "admin")
def switch_market():
    selected_market = (request.form.get("market") or "All Markets").strip()
    set_current_market(selected_market)

    next_url = request.form.get("next") or url_for("elena.dashboard")
    return redirect(next_url)


@elena_bp.get("/copilot")
@role_required("partner_group", "admin")
def copilot():
    profile = get_or_create_realtor_vip_profile()

    suggestions = (
        VIPAssistantSuggestion.query
        .filter_by(vip_profile_id=profile.id)
        .order_by(VIPAssistantSuggestion.created_at.desc())
        .limit(20)
        .all()
    )

    return render_template(
        "elena/copilot.html",
        vip_profile=profile,
        header_name="Copilot",
        suggestions=suggestions,
        current_market=get_current_market(),
        available_markets=FRANK_MARKETS,
        portal="elena",
        portal_name="Elena",
        portal_home=url_for("elena.dashboard"),
    )


@elena_bp.post("/copilot/command")
@role_required("partner_group", "admin")
def copilot_command():
    profile = get_or_create_realtor_vip_profile()

    command = (request.form.get("command") or "").strip()
    if not command:
        flash("Please enter a command.", "warning")
        return redirect(url_for("elena.copilot"))

    result = parse_vip_command(command)

    suggestion = VIPAssistantSuggestion(
        vip_profile_id=profile.id,
        suggestion_type=result["suggestion_type"],
        title=result["title"],
        body=result.get("body"),
        source="elena_manual",
    )
    db.session.add(suggestion)
    db.session.commit()

    flash("Copilot suggestion created.", "success")
    return redirect(url_for("elena.copilot"))