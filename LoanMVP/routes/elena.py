from flask import Blueprint, request, jsonify, render_template
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
    render_template as render_elena_template,
    TemplateType
)

elena_bp = Blueprint("elena", __name__, url_prefix="/elena")


# ---------- TEMPLATE LIST ----------
@elena_bp.get("/templates")
def list_templates():
    return jsonify({
        "templates": [t.value for t in TemplateType]
    })


# ---------- CRM AUTO-FILL ----------
@elena_bp.get("/templates/auto_fill/<int:client_id>/<template_type>")
def template_auto_fill(client_id, template_type):
    client = ElenaClient.query.get(client_id)
    if not client:
        return jsonify({"error": "Client not found"}), 404

    variables = {
        "client_name": client.name,
        "email": client.email,
        "phone": client.phone,
        "pipeline_stage": getattr(client, "pipeline_stage", "") or "",
        "context": getattr(client, "notes", "") or "",
        "areas": getattr(client, "preferred_areas", "") or "",
        "budget": getattr(client, "budget", "") or "",
    }

    last_interaction = (
        ElenaInteraction.query
        .filter_by(client_id=client_id)
        .order_by(ElenaInteraction.created_at.desc())
        .first()
    )

    if last_interaction:
        variables["last_contact"] = last_interaction.created_at.strftime("%Y-%m-%d")
        variables["last_message"] = (last_interaction.content or "")[:200]

    return jsonify({
        "client_id": client_id,
        "template_type": template_type,
        "variables": variables
    })


# ---------- TEMPLATE PREVIEW (JSON) ----------
@elena_bp.post("/templates/preview")
def template_preview():
    data = request.json or {}
    template_type = data.get("template_type")
    variables = data.get("variables", {})

    prompt = render_elena_template(TemplateType(template_type), **variables)

    return jsonify({
        "template_type": template_type,
        "prompt": prompt
    })


# ---------- TEMPLATE GENERATE (JSON) ----------
@elena_bp.post("/templates/generate")
def template_generate():
    data = request.json or {}
    template_type = data.get("template_type")
    variables = data.get("variables", {})

    prompt = render_elena_template(TemplateType(template_type), **variables)
    output = generate_text(prompt)

    return jsonify({
        "template_type": template_type,
        "prompt": prompt,
        "output": output
    })


# ---------- TEMPLATE GENERATE + LOG (JSON) ----------
@elena_bp.post("/templates/generate_and_log")
def template_generate_and_log():
    data = request.json or {}
    client_id = data.get("client_id")
    template_type = data.get("template_type")
    variables = data.get("variables", {})

    client = ElenaClient.query.get(client_id)
    if not client:
        return jsonify({"error": "Client not found"}), 404

    prompt = render_elena_template(TemplateType(template_type), **variables)
    output = generate_text(prompt)

    interaction = ElenaInteraction(
        client_id=client.id,
        interaction_type=InteractionType.EMAIL,
        content=output,
        meta=f"template:{template_type}"
    )
    db.session.add(interaction)
    db.session.commit()

    return jsonify({
        "client_id": client.id,
        "template_type": template_type,
        "output": output,
        "interaction_id": interaction.id
    })


# ---------- TEMPLATE STUDIO UI (GET) ----------
@elena_bp.get("/template-studio")
def template_studio():
    template_type = request.args.get("template_type")
    client_id = request.args.get("client_id")
    variables = {}

    if client_id and template_type:
        client = ElenaClient.query.get(client_id)
        if client:
            variables = {
                "client_name": client.name,
                "email": client.email,
                "phone": client.phone,
                "pipeline_stage": getattr(client, "pipeline_stage", "") or "",
                "context": getattr(client, "notes", "") or "",
                "areas": getattr(client, "preferred_areas", "") or "",
                "budget": getattr(client, "budget", "") or "",
            }

    return render_template(
        "elena/template_studio.html",
        templates=[t.value for t in TemplateType],
        selected_template=template_type,
        variables=variables,
        client_id=client_id,
        preview=None,
        output=None
    )


# ---------- TEMPLATE STUDIO PREVIEW (FORM POST) ----------
@elena_bp.post("/template-studio/preview")
def template_studio_preview():
    template_type = request.form.get("template_type")
    client_id = request.form.get("client_id")
    variables = {k: v for k, v in request.form.items() if k not in ["template_type", "client_id"]}

    prompt = render_elena_template(TemplateType(template_type), **variables)

    return render_template(
        "elena/template_studio.html",
        templates=[t.value for t in TemplateType],
        selected_template=template_type,
        variables=variables,
        client_id=client_id,
        preview=prompt,
        output=None
    )


# ---------- TEMPLATE STUDIO GENERATE (FORM POST) ----------
@elena_bp.post("/template-studio/generate")
def template_studio_generate():
    template_type = request.form.get("template_type")
    client_id = request.form.get("client_id")
    variables = {k: v for k, v in request.form.items() if k not in ["template_type", "client_id"]}

    prompt = render_elena_template(TemplateType(template_type), **variables)
    output = generate_text(prompt)

    return render_template(
        "elena/template_studio.html",
        templates=[t.value for t in TemplateType],
        selected_template=template_type,
        variables=variables,
        client_id=client_id,
        preview=prompt,
        output=output
    )
