import os
import uuid
from flask import current_app


def save_generated_image(image_bytes, folder="uploads/studios"):
    filename = f"{uuid.uuid4().hex}.png"
    relative_path = f"{folder}/{filename}"
    absolute_path = os.path.join(current_app.root_path, "static", relative_path)

    os.makedirs(os.path.dirname(absolute_path), exist_ok=True)

    with open(absolute_path, "wb") as f:
        f.write(image_bytes)

    return relative_path


def run_build_concept(payload):
    """
    payload keys:
      - project_name
      - property_type
      - description
      - lot_size
      - zoning
      - location
      - notes
      - land_image_path
    """

    concept_prompt = f"""
    Create a polished exterior concept rendering for a {payload.get('property_type', 'residential project')}.
    Project name: {payload.get('project_name', '')}
    Description: {payload.get('description', '')}
    Lot size: {payload.get('lot_size', '')}
    Zoning: {payload.get('zoning', '')}
    Location: {payload.get('location', '')}
    Notes: {payload.get('notes', '')}
    """

    # -------------------------------
    # CONTROLNET / IMAGE GENERATION
    # -------------------------------

    land_image_path = payload.get("land_image_path")
    generated_concept_path = None

    try:
        if land_image_path:
            # 👉 replace this block with your real ControlNet call
            # Example placeholder for now:

            with open(os.path.join(current_app.root_path, "static", land_image_path), "rb") as f:
                input_image = f.read()

            # ⚠️ Replace this with real AI response
            fake_ai_output = input_image  # placeholder

            generated_concept_path = save_generated_image(fake_ai_output)

    except Exception as e:
        print("Build Studio generation error:", str(e))

    # -------------------------------
    # FALLBACKS
    # -------------------------------

    concept_render_url = (
        f"/static/{generated_concept_path}"
        if generated_concept_path
        else "/static/img/placeholders/build_render_placeholder.jpg"
    )

    return {
        "concept_render_url": concept_render_url,
        "blueprint_url": "/static/img/placeholders/blueprint_placeholder.jpg",
        "site_plan_url": "/static/img/placeholders/siteplan_placeholder.jpg",
        "presentation_url": "/static/img/placeholders/presentation_placeholder.jpg",
        "prompts": {
            "concept_prompt": concept_prompt,
        }
    }