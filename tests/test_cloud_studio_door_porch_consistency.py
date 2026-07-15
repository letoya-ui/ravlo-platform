"""Regression test: the chat-based Build Studio flow ("Tell Ravlo What To
Build") falls back to cloud_studio_service.py's own prompt builders when the
RunPod engine is unreachable -- a separate code path from
investor_routes.py's _compose_build_studio_prompt (fixed for the same class
of bug in a prior change). This one had the identical problem: the blueprint
prompt never said where the front door should go, and the rear exterior
prompt had no porch/patio guidance at all, so the model would default to
inventing a rear patio even when the floor plan had none and nothing in the
project requested one.
"""
from io import BytesIO

from LoanMVP.services import cloud_studio_service
from LoanMVP.services.cloud_studio_service import (
    _blueprint_prompt,
    _exterior_prompt,
    _is_garage_requested,
    _mentions_rear_outdoor_living,
)


def test_mentions_rear_outdoor_living_detects_keywords():
    assert _mentions_rear_outdoor_living("add a covered back porch") is True
    assert _mentions_rear_outdoor_living(None, "rear patio with outdoor kitchen") is True
    assert _mentions_rear_outdoor_living("modern farmhouse, 4 bed 3 bath") is False


def test_blueprint_prompt_places_front_door_facing_porch():
    prompt = _blueprint_prompt({"property_type": "single_family", "style": "modern_farmhouse"})
    assert "front-facing wall" in prompt
    assert "front porch" in prompt


def test_exterior_front_prompt_centers_entry_door():
    prompt = _exterior_prompt({"property_type": "single_family", "style": "modern_farmhouse"}, view="front")
    assert "centered and forward-facing" in prompt


def test_exterior_back_prompt_has_no_porch_by_default():
    prompt = _exterior_prompt({"property_type": "single_family", "description": "modern farmhouse"}, view="back")
    assert "no covered porch, deck, or patio" in prompt


def test_exterior_back_prompt_allows_porch_when_requested():
    prompt = _exterior_prompt({"notes": "please add a covered back porch"}, view="back")
    assert "covered porch/deck/patio connecting to the yard" in prompt
    assert "no covered porch, deck, or patio" not in prompt


def test_is_garage_requested_handles_bool_and_string_values():
    assert _is_garage_requested({"garage": True}) is True
    assert _is_garage_requested({"garage": "true"}) is True
    assert _is_garage_requested({"garage": False}) is False
    assert _is_garage_requested({"garage": "false"}) is False
    assert _is_garage_requested({}) is False


def test_blueprint_prompt_mentions_garage_when_requested():
    prompt = _blueprint_prompt({"property_type": "single_family", "garage": True})
    assert "attached garage" in prompt


def test_blueprint_prompt_omits_garage_when_not_requested():
    prompt = _blueprint_prompt({"property_type": "single_family", "garage": False})
    assert "garage" not in prompt


def test_exterior_front_prompt_includes_garage_when_requested():
    prompt = _exterior_prompt({"property_type": "single_family", "garage": True}, view="front")
    assert "attached garage with a visible garage door" in prompt


def test_exterior_front_prompt_omits_garage_when_not_requested():
    prompt = _exterior_prompt({"property_type": "single_family", "garage": False}, view="front")
    assert "garage" not in prompt


# ---------------------------------------------------------------------------
# Multi-floor blueprint: asking a single generation to draw a multi-panel
# sheet covering every floor was unreliable in practice -- a 2-story
# project's blueprint kept coming back showing only the first floor, even
# with an explicit "show all N floors side by side" instruction in the
# prompt (the exterior render had no such problem, since stacking two
# stories of massing is a much easier default for an image model to get
# right without being told explicitly).
#
# The fix generates each floor as its own image with a floor-specific
# prompt, then composites them into one sheet deterministically via PIL --
# so the floor count is guaranteed correct instead of hoped-for.
# ---------------------------------------------------------------------------

def test_single_floor_prompt_has_no_multi_floor_language():
    prompt = _blueprint_prompt({"property_type": "single_family"})
    assert "floor 1 of 1" not in prompt
    assert "do not include any other floor" not in prompt


def test_ground_floor_prompt_includes_garage_and_door_note():
    prompt = _blueprint_prompt({"property_type": "single_family", "garage": True}, floor_number=1, total_floors=2)
    assert "ground floor (1 of 2)" in prompt
    assert "attached garage" in prompt
    assert "front-facing wall" in prompt
    assert "do not include any other floor's rooms" in prompt


def test_upper_floor_prompt_omits_garage_and_door_note_but_lists_bedrooms():
    prompt = _blueprint_prompt(
        {"property_type": "single_family", "garage": True, "bedrooms": "4", "bathrooms": "3"},
        floor_number=2,
        total_floors=2,
    )
    assert "floor 2 (2 of 2)" in prompt
    assert "attached garage" not in prompt
    assert "front-facing wall" not in prompt
    assert "4 bedrooms" in prompt


def test_generate_blueprint_url_single_story_makes_one_call(monkeypatch):
    calls = []

    def fake_generate_image_url(prompt, size="1024x1024"):
        calls.append(prompt)
        return "https://example.com/blueprint.png"

    monkeypatch.setattr(cloud_studio_service, "_generate_image_url", fake_generate_image_url)

    url = cloud_studio_service._generate_blueprint_url({"property_type": "single_family", "stories": "1"})

    assert url == "https://example.com/blueprint.png"
    assert len(calls) == 1


def test_generate_blueprint_url_multi_story_composites_one_image_per_floor(monkeypatch):
    generated_prompts = []

    def fake_generate_image_bytes(prompt, size="1024x1024"):
        generated_prompts.append(prompt)
        return f"fake-bytes-{len(generated_prompts)}".encode()

    composited = {}

    def fake_composite(floor_images):
        composited["images"] = floor_images
        return b"combined-bytes"

    def fake_persist_image_bytes(img_bytes):
        composited["persisted"] = img_bytes
        return "https://example.com/combined-blueprint.png"

    monkeypatch.setattr(cloud_studio_service, "_generate_image_bytes", fake_generate_image_bytes)
    monkeypatch.setattr(cloud_studio_service, "_composite_floor_plans", fake_composite)
    monkeypatch.setattr(cloud_studio_service, "_persist_image_bytes", fake_persist_image_bytes)

    url = cloud_studio_service._generate_blueprint_url({"property_type": "single_family", "stories": "3"})

    assert url == "https://example.com/combined-blueprint.png"
    assert len(generated_prompts) == 3
    assert "1 of 3" in generated_prompts[0]
    assert "2 of 3" in generated_prompts[1]
    assert "3 of 3" in generated_prompts[2]
    assert composited["images"] == [b"fake-bytes-1", b"fake-bytes-2", b"fake-bytes-3"]
    assert composited["persisted"] == b"combined-bytes"


def test_composite_floor_plans_produces_wider_image_than_a_single_floor():
    from PIL import Image as PILImage

    def _solid_png(width, height):
        buf = BytesIO()
        PILImage.new("RGB", (width, height), "white").save(buf, format="PNG")
        return buf.getvalue()

    floor1 = _solid_png(400, 400)
    floor2 = _solid_png(400, 400)

    combined_bytes = cloud_studio_service._composite_floor_plans([floor1, floor2])
    combined_img = PILImage.open(BytesIO(combined_bytes))

    assert combined_img.width > 400
    assert combined_img.height == 400


def test_composite_floor_plans_returns_input_unchanged_for_single_floor():
    single = b"not-really-png-but-unused-in-this-branch"
    assert cloud_studio_service._composite_floor_plans([single]) == single
