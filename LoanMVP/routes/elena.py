from datetime import datetime, timedelta
from flask import (
    Blueprint,
    request,
    jsonify,
    render_template,
    redirect,
    url_for,
    flash,
)
from sqlalchemy import or_

from LoanMVP.extensions import db
from LoanMVP.models.elena_models import (
    ElenaClient,
    ElenaListing,
    ElenaFlyer,
    ElenaInteraction,
    InteractionType,
)
from LoanMVP.services.ai_service import generate_text
from LoanMVP.services.elena_templates import (
    render_template as render_elena_template,
    TemplateType,
)
from LoanMVP.utils.decorators import role_required

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
        
@elena_bp.get("/")
@role_required("partner_group", "admin")
def dashboard():
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)

    total_clients = ElenaClient.query.count()
    new_leads = ElenaClient.query.filter(ElenaClient.created_at >= week_ago).count()
    active_listings = ElenaListing.query.filter_by(status="active").count()
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
    if status_filter and status_filter in {s[0] for s in LISTING_STATUSES}:
        listings_query = listings_query.filter_by(status=status_filter)
    listings = listings_query.order_by(ElenaListing.updated_at.desc()).limit(12).all()

    recent_flyers = (
        ElenaFlyer.query.order_by(ElenaFlyer.created_at.desc()).limit(5).all()
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
    if request.method == "POST":
        address = (request.form.get("address") or "").strip()
        city = (request.form.get("city") or "").strip()
        state = (request.form.get("state") or "").strip()
        zip_code = (request.form.get("zip_code") or "").strip()

        missing = [
            f
            for f, v in [
                ("address", address),
                ("city", city),
                ("state", state),
                ("zip_code", zip_code),
            ]
            if not v
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
def template_studio_preview():
    template_type = request.form.get("template_type")
    client_id = request.form.get("client_id")
    listing_id = request.form.get("listing_id")

    variables = {
        k: v
        for k, v in request.form.items()
        if k not in ["template_type", "client_id", "listing_id", "action"]
    }

    prompt = render_elena_template(TemplateType(template_type), **variables)

    return render_template(
        "elena/template_studio.html",
        templates=[t.value for t in TemplateType],
        selected_template=template_type,
        variables=variables,
        client_id=client_id,
        listing_id=listing_id,
        preview=prompt,
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


@elena_bp.post("/template-studio/generate_and_save")
def template_studio_generate_and_save():
    template_type = request.form.get("template_type")
    client_id = request.form.get("client_id")
    listing_id = request.form.get("listing_id")

    variables = {
        k: v
        for k, v in request.form.items()
        if k not in ["template_type", "client_id", "listing_id", "action"]
    }

    prompt = render_elena_template(TemplateType(template_type), **variables)
    output = generate_text(prompt)

    saved_interaction_id = None

        
        
