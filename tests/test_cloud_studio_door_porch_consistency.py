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
# Multi-floor blueprint: a 2-story project's blueprint only ever showed the
# first floor, because _blueprint_prompt just said "{stories}-story" in
# passing text rather than explicitly instructing a multi-panel sheet --
# meanwhile the exterior render correctly showed two stories, since massing
# height is a much easier default for an image model to get right than an
# instruction it was never given for the floor plan.
# ---------------------------------------------------------------------------

def test_single_story_blueprint_has_no_multi_panel_instruction():
    prompt = _blueprint_prompt({"property_type": "single_family", "stories": "1"})
    assert "each floor drawn as its own top-down floor plan panel" not in prompt


def test_two_story_blueprint_requires_all_floor_panels():
    prompt = _blueprint_prompt({"property_type": "single_family", "stories": "2"})
    assert "one single architectural sheet showing all 2 floors" in prompt
    assert "each floor drawn as its own top-down floor plan panel" in prompt


def test_three_story_blueprint_requires_all_floor_panels():
    prompt = _blueprint_prompt({"property_type": "single_family", "stories": 3})
    assert "one single architectural sheet showing all 3 floors" in prompt
