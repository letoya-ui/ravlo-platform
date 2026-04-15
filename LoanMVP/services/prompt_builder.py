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
