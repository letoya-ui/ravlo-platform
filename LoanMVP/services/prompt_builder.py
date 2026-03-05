def build_blueprint_prompt(room_type: str, style_preset: str, level: str) -> str:
    # Normalize
    rt = (room_type or "room").replace("_", " ")
    sp = (style_preset or "luxury_modern").replace("_", " ")
    lvl = (level or "medium").lower()

    # Renovation intensity text
    level_map = {
        "light": "light cosmetic renovation, paint, fixtures, minor upgrades",
        "medium": "moderate renovation, new flooring, cabinets/vanity, updated lighting, premium finishes",
        "heavy": "full gut renovation, high-end finishes, redesigned surfaces while preserving layout"
    }
    lvl_text = level_map.get(lvl, level_map["medium"])

    # SDXL-friendly prompt
    return (
        f"Photorealistic HGTV-grade {rt} renovation in {sp} style. "
        f"{lvl_text}. "
        "Use a realistic wide-angle interior photo perspective, natural daylight plus architectural lighting, "
        "premium materials, crisp details, realistic shadows. "
        "STRICT: preserve the blueprint layout exactly — same wall positions, room proportions, door/window openings. "
        "No warped geometry, no melted lines, no text, no watermark, no logo."
    )