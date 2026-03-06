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

    # -----------------------------------
    # Replace this with your real AI flow
    # -----------------------------------

    concept_prompt = f"""
    Create a polished exterior concept rendering for a {payload.get('property_type', 'residential project')}.
    Project name: {payload.get('project_name', '')}
    Description: {payload.get('description', '')}
    Lot size: {payload.get('lot_size', '')}
    Zoning: {payload.get('zoning', '')}
    Location: {payload.get('location', '')}
    Notes: {payload.get('notes', '')}
    """

    blueprint_prompt = f"""
    Create a draft floor plan for a {payload.get('property_type', 'residential project')}.
    Description: {payload.get('description', '')}
    """

    site_plan_prompt = f"""
    Create a conceptual site layout showing building placement, driveway, access, open space, and orientation.
    Lot size: {payload.get('lot_size', '')}
    Zoning: {payload.get('zoning', '')}
    """

    presentation_prompt = f"""
    Create an architect-ready presentation board summarizing the project concept, build type, lot details, and visuals.
    """

    # Placeholder returns
    return {
        "concept_render_url": "/static/img/placeholders/build_render_placeholder.jpg",
        "blueprint_url": "/static/img/placeholders/blueprint_placeholder.jpg",
        "site_plan_url": "/static/img/placeholders/siteplan_placeholder.jpg",
        "presentation_url": "/static/img/placeholders/presentation_placeholder.jpg",
        "prompts": {
            "concept_prompt": concept_prompt,
            "blueprint_prompt": blueprint_prompt,
            "site_plan_prompt": site_plan_prompt,
            "presentation_prompt": presentation_prompt,
        }
    }