from flask import Blueprint, request, jsonify, render_template
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

elena_bp = Blueprint("elena", __name__, url_prefix="/elena")


# ---------------- TEMPLATE LIST (JSON) ----------------
@elena_bp.get("/templates")
def list_templates():
    return jsonify({"templates": [t.value for t in TemplateType]})


# ---------------- CRM AUTO-FILL (JSON) ----------------
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


# ---------------- LISTING AUTO-FILL (JSON) ----------------
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


# ---------------- TEMPLATE PREVIEW (JSON) ----------------
@elena_bp.post("/templates/preview")
def template_preview():
    data = request.json or {}
    template_type = data.get("template_type")
    variables = data.get("variables", {})

    if not template_type:
        return jsonify({"error": "template_type is required"}), 400

    prompt = render_elena_template(TemplateType(template_type), **variables)

    return jsonify({"template_type": template_type, "prompt": prompt})


# ---------------- TEMPLATE GENERATE (JSON) ----------------
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


# ---------------- TEMPLATE GENERATE + LOG (JSON) ----------------
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


# ---------------- MLS IMPORT + AUTO FLYER ----------------
@elena_bp.post("/mls/import")
def mls_import():
    data = request.json or {}
    mls_number = data.get("mls_number")
    auto_generate_flyer = data.get("auto_generate_flyer", False)

    if not mls_number:
        return jsonify({"error": "mls_number is required"}), 400

    # Replace this with your real MLS/ATTOM integration
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


# ---------------- TEMPLATE STUDIO UI (GET) ----------------
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
    )


# ---------------- TEMPLATE STUDIO PREVIEW (FORM POST) ----------------
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
    )


# ---------------- TEMPLATE STUDIO GENERATE (FORM POST) ----------------
@elena_bp.post("/template-studio/generate")
def template_studio_generate():
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
    )


# ---------------- TEMPLATE STUDIO GENERATE + SAVE (FORM POST) ----------------
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
            )
