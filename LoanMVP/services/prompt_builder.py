def build_blueprint_prompt(room_type, style_preset, level):
    return (
        f"Generate a photorealistic {room_type} renovation in {style_preset} style. "
        f"Renovation level: {level}. "
        "Respect the blueprint layout, wall positions, and openings. "
        "Keep the same room geometry. No text overlays."
    )
