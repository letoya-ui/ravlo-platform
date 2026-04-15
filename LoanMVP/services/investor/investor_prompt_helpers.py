CLIP_MAX_TOKENS = 77

_REHAB_NEGATIVE = (
    "warped geometry, duplicate fixtures, unfinished construction, "
    "people, text, watermark, logo, blueprint lines"
)

_EXTERIOR_NEGATIVE = (
    "blueprint lines, warped geometry, people, text, watermark, logo, "
    "unfinished construction"
)


def _clean_prompt_fragment(value: str, *, max_chars: int = 220) -> str:
    text = " ".join(str(value or "").replace("_", " ").split())
    if len(text) <= max_chars:
        return text
    clipped = text[:max_chars].rsplit(" ", 1)[0].strip()
    return clipped or text[:max_chars].strip()


def _clip_safe(prompt: str, *, max_tokens: int = CLIP_MAX_TOKENS) -> str:
    """Trim a prompt to stay within CLIP's token window.

    Uses whitespace-split word count as a rough proxy for CLIP tokens.
    """
    words = prompt.split()
    if len(words) <= max_tokens:
        return prompt
    return " ".join(words[:max_tokens])


def build_exterior_concept_prompt(property_type: str, style: str, description: str = "") -> str:
    property_label = _clean_prompt_fragment(property_type or "residential property", max_chars=40)
    style_label = _clean_prompt_fragment(style or "modern", max_chars=30)
    extra = _clean_prompt_fragment(description, max_chars=80)

    parts = [
        f"photorealistic real estate exterior, {style_label} {property_label}",
        "front elevation, natural daylight, real materials, curb appeal, luxury photography",
    ]
    if extra:
        parts.append(extra)
    return _clip_safe(", ".join(parts))


def build_exterior_negative_prompt() -> str:
    return _EXTERIOR_NEGATIVE


def build_rehab_concept_prompt(
    room_type: str,
    style_preset: str,
    rehab_level: str,
    property_type: str,
    notes: str = "",
) -> str:
    room_label = _clean_prompt_fragment(room_type or "room", max_chars=30)
    style_label = _clean_prompt_fragment(style_preset or "luxury", max_chars=30)
    property_label = _clean_prompt_fragment(property_type or "residential property", max_chars=40)
    notes_label = _clean_prompt_fragment(notes, max_chars=80)
    level = (rehab_level or "medium").lower()
    level_map = {
        "light": "light cosmetic upgrades, better finishes and lighting",
        "medium": "meaningful visible upgrades, updated materials throughout",
        "heavy": "high-end transformation, premium finishes, preserve structure",
        "luxury": "luxury renovation, premium stone and wood finishes, bespoke cabinetry, high-end lighting",
    }

    level_phrase = level_map.get(level, level_map["medium"])

    parts = [
        f"photorealistic real estate renovation, {room_label} renovation concept for a {property_label},",
        "same room footprint and believable architecture, preserve geometry and layout unless small refinements improve realism,",
        f"fully finished space, real materials, natural lighting, {style_label} renovation, {level_phrase}",
    ]
    if notes_label:
        parts.append(f", {notes_label}")
    prompt = " ".join(parts)
    return _clip_safe(prompt)


def build_rehab_negative_prompt() -> str:
    return _REHAB_NEGATIVE
