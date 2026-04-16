from flask import Blueprint, request, jsonify
from LoanMVP.extensions import db
from LoanMVP.models.elena_models import (
    ElenaClient,
    ElenaListing,
    ElenaFlyer,
    ElenaInteraction,
    InteractionType
)
from LoanMVP.services.ai_service import generate_text
from LoanMVP.services.elena_templates import (
    render_template,
    TemplateType
)

elena_bp = Blueprint("elena", __name__, url_prefix="/elena")


# ---------------------------------------------------------
# TEMPLATE LISTING
# ---------------------------------------------------------
@elena_bp.get("/templates")
def list_templates():
    return jsonify({
        "templates": [t.value for t in TemplateType]
    })


# ---------------------------------------------------------
# TEMPLATE PREVIEW
# ---------------------------------------------------------
@elena_bp.post("/templates/preview")
def template_preview():
    data = request.json or {}
    template_type = data.get("template_type")
    variables = data.get("variables", {})

    if not template_type:
        return jsonify({"error": "template_type is required"}), 400

    try:
        prompt = render_template(TemplateType(template_type), **variables)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "template_type": template_type,
        "prompt": prompt
    })


# ---------------------------------------------------------
# TEMPLATE → AI GENERATION
# ---------------------------------------------------------
@elena_bp.post("/templates/generate")
def template_generate():
    data = request.json or {}
    template_type = data.get("template_type")
    variables = data.get("variables", {})

    if not template_type:
        return jsonify({"error": "template_type is required"}), 400

    try:
        prompt = render_template(TemplateType(template_type), **variables)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    ai_output = generate_text(prompt)

    return jsonify({
        "template_type": template_type,
        "prompt": prompt,
        "output": ai_output
    })


# ---------------------------------------------------------
# TEMPLATE → AI → LOG INTERACTION
# ---------------------------------------------------------
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

    try:
        prompt = render_template(TemplateType(template_type), **variables)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    ai_output = generate_text(prompt)

    interaction = ElenaInteraction(
        client_id=client.id,
        interaction_type=InteractionType.EMAIL,
        content=ai_output,
        meta=f"template:{template_type}"
    )
    db.session.add(interaction)
    db.session.commit()

    return jsonify({
        "client_id": client.id,
        "template_type": template_type,
        "output": ai_output,
        "interaction_id": interaction.id
    })


# ---------------------------------------------------------
# MLS IMPORT (kept from your existing route)
# ---------------------------------------------------------
@elena_bp.post("/mls/import")
def mls_import():
    data = request.json or {}
    mls_number = data.get("mls_number")
    auto_generate_flyer = data.get("auto_generate_flyer", False)

    if not mls_number:
        return jsonify({"error": "mls_number is required"}), 400

    # TODO: Replace with your ATTOM wrapper call
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
        "photos_json": "[]"
    }

    listing = ElenaListing(
        mls_number=mls_number,
        **listing_data
    )
    db.session.add(listing)
    db.session.commit()

    flyer_output = None

    if auto_generate_flyer:
        prompt = render_template(
            TemplateType.JUST_LISTED,
            **listing_data
        )
        flyer_output = generate_text(prompt)

        flyer = ElenaFlyer(
            flyer_type="just_listed",
            property_address=listing.address,
            property_id=str(listing.id),
            body=flyer_output,
            listing_id=listing.id
        )
        db.session.add(flyer)
        db.session.commit()

    return jsonify({
        "listing_id": listing.id,
        "flyer": flyer_output
    })
@elena_bp.get("/templates/auto_fill/<int:client_id>/<template_type>")
def template_auto_fill(client_id, template_type):
    client = ElenaClient.query.get(client_id)
    if not client:
        return jsonify({"error": "Client not found"}), 404

    # Base variables from CRM
    variables = {
        "client_name": client.name,
        "email": client.email,
        "phone": client.phone,
        "pipeline_stage": client.pipeline_stage,
        "context": client.notes or "",
        "areas": client.preferred_areas or "",
        "budget": client.budget or "",
    }

    # Add last interaction if exists
    last_interaction = (
        ElenaInteraction.query
        .filter_by(client_id=client_id)
        .order_by(ElenaInteraction.created_at.desc())
        .first()
    )

    if last_interaction:
        variables["last_contact"] = last_interaction.created_at.strftime("%Y-%m-%d")
        variables["last_message"] = last_interaction.content[:200]

    # Template-specific auto-fill
    if template_type == "followup_after_showing":
        last_showing = (
            ElenaInteraction.query
            .filter_by(client_id=client_id, interaction_type="showing")
            .order_by(ElenaInteraction.created_at.desc())
            .first()
        )
        if last_showing:
            variables["address"] = last_showing.meta or ""
        else:
            variables["address"] = ""

    return jsonify({
        "client_id": client_id,
        "template_type": template_type,
        "variables": variables
    })
