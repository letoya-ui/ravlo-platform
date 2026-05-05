def build_blueprint_prompt(room_type: str, style_preset: str, level: str) -> str:
    focus = (room_type or "room").replace("_", " ")
    style = (style_preset or "luxury_modern").replace("_", " ")
    intensity = (level or "medium").lower()

    level_map = {
        "light": "clean and efficient build concept with straightforward materials and simple detailing",
        "medium": "refined build concept with upgraded materials, clear room definition, and polished presentation",
        "heavy": "high-design build concept with richer detailing, stronger material contrast, and more dramatic architectural expression",
        "luxury": "luxury-level architectural concept with premium finishes, elevated composition, and presentation-ready detail",
    }
    level_text = level_map.get(intensity, level_map["medium"])

    return (
        f"Blueprint-guided residential architectural concept for a {focus}. "
        f"Style direction: {style}. "
        f"{level_text}. "
        "Honor the source layout and room relationships, keep the plan buildable, and preserve believable wall, door, and window placement. "
        "Generate an architectural presentation image with coherent circulation, realistic scale, clean geometry, and crisp material definition. "
        "No warped lines, no melted structure, no random furniture clutter, no text labels, no watermark, no logo."
    )


def build_design_prompt(
    room_type: str,
    style_preset: str,
    target_materials: str = "",
    design_notes: str = "",
    engine_prompt: str = "",
) -> str:
    focus = (room_type or "room").replace("_", " ")
    style = (style_preset or "modern_luxury").replace("_", " ")

    materials = (target_materials or "").strip()
    notes = (design_notes or "").strip()
    chat_prompt = (engine_prompt or "").strip()

    mandatory = (
        f"MANDATORY DESIGN REDESIGN: The final image must visibly use {materials}. "
        if materials
        else "MANDATORY DESIGN REDESIGN: The final image must visibly follow the user's requested design direction. "
    )

    return (
        f"Photorealistic interior design concept for a {focus}. "
        f"Style direction: {style}. "
        f"{mandatory}"
        f"{chat_prompt + '. ' if chat_prompt else ''}"
        f"{notes + '. ' if notes else ''}"
        "Create a finished, realistic, high-quality interior with strong material clarity, believable lighting, and cohesive styling. "
        "Use the reference image only for camera angle, room shell, wall placement, window placement, door placement, and basic geometry. "
        "Do not preserve existing cabinet color, countertops, backsplash, appliances, lighting, furniture, paint colors, decor, or styling unless explicitly requested. "
        "No warped walls, no distorted counters, no melted cabinets, no text labels, no watermark, no logo."
    )