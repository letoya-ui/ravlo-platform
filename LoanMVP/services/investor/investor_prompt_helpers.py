def _clean_prompt_fragment(value: str, *, max_chars: int = 220) -> str:
    text = " ".join(str(value or "").replace("_", " ").split())
    if len(text) <= max_chars:
        return text
    clipped = text[:max_chars].rsplit(" ", 1)[0].strip()
    return clipped or text[:max_chars].strip()


def build_exterior_concept_prompt(property_type: str, style: str, description: str = "") -> str:
    property_label = _clean_prompt_fragment(property_type or "residential property", max_chars=60)
    style_label = _clean_prompt_fragment(style or "modern", max_chars=60)
    extra = _clean_prompt_fragment(description, max_chars=180)

    parts = [
        f"Photorealistic exterior concept for a {style_label} {property_label}.",
        "Front elevation, natural daylight, real construction materials, strong curb appeal, realistic landscaping, luxury real estate photography.",
        "Keep architecture believable, proportions clean, and structure buildable.",
        "No blueprint lines, no warped geometry, no people, no watermark, no logo.",
    ]
    if extra:
        parts.insert(2, f"Project intent: {extra}.")
    return " ".join(parts)


def build_rehab_concept_prompt(
    room_type: str,
    style_preset: str,
    rehab_level: str,
    property_type: str,
    notes: str = "",
) -> str:
    room_label = _clean_prompt_fragment(room_type or "room", max_chars=50)
    style_label = _clean_prompt_fragment(style_preset or "luxury_modern", max_chars=60)
    property_label = _clean_prompt_fragment(property_type or "residential property", max_chars=60)
    notes_label = _clean_prompt_fragment(notes, max_chars=180)
    level = (rehab_level or "medium").lower()
    level_map = {
        "light": "Light cosmetic upgrades with better finishes and lighting.",
        "medium": "Meaningful renovation with upgraded surfaces, fixtures, and millwork.",
        "heavy": "High-end transformation with premium finishes while preserving structure.",
    }

    parts = [
        f"Photorealistic rehab concept for a {room_label} in a {property_label}.",
        f"Design direction: {style_label}.",
        level_map.get(level, level_map["medium"]),
        "Preserve the existing layout, walls, windows, doors, and camera angle.",
        "Use realistic materials, accurate lighting, and buildable detailing.",
        "No warped geometry, no duplicate fixtures, no people, no text, no watermark, no logo.",
    ]
    if notes_label:
        parts.insert(3, f"Requested upgrades: {notes_label}.")
    return " ".join(parts)
