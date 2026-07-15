"""Regression tests for a Build Studio inconsistency: the AI-generated
blueprint placed the front entry door on a side wall instead of facing the
front porch, and the exterior_back render always invented a recessed back
porch/patio even when the floor plan (and the user's project description)
never asked for one.

_compose_build_studio_prompt() (investor_routes.py) builds each of the 4
full-build renders (blueprint, siteplan, exterior_front, exterior_back) as
independent text-to-image prompts with no shared fact about door placement
or rear porch existence -- the blueprint prompt never said where the front
door should go relative to the porch, and the rear exterior prompt
unconditionally told the model to add "patio or deck" regardless of whether
one was ever requested. This adds an explicit front-door/porch directive to
the blueprint and exterior_front prompts, and makes the rear porch/patio
language conditional on the project's own notes/description actually
requesting one.
"""
from LoanMVP.routes.investor_routes import _compose_build_studio_prompt, _mentions_rear_outdoor_living


def test_mentions_rear_outdoor_living_detects_keywords():
    assert _mentions_rear_outdoor_living("add a covered back porch", "") is True
    assert _mentions_rear_outdoor_living("", "rear patio with outdoor kitchen") is True
    assert _mentions_rear_outdoor_living("modern farmhouse, 4 bed 3 bath", "single family home") is False


def test_blueprint_prompt_places_front_door_facing_porch():
    prompt = _compose_build_studio_prompt(mode="blueprint", floor="first")
    assert "front-facing exterior wall" in prompt
    assert "front porch" in prompt


def test_combined_blueprint_prompt_places_front_door_facing_porch():
    prompt = _compose_build_studio_prompt(mode="blueprint", floors=2, combine_floors=True)
    assert "front-facing exterior wall" in prompt
    assert "front porch" in prompt


def test_exterior_front_prompt_centers_entry_door():
    prompt = _compose_build_studio_prompt(mode="exterior_front")
    assert "centered and forward-facing" in prompt
    assert "matching the entry location shown in the floor plan" in prompt


def test_exterior_back_prompt_has_no_porch_by_default():
    prompt = _compose_build_studio_prompt(mode="exterior_back", notes="", description="modern farmhouse single family")
    assert "no covered porch, deck, patio" in prompt


def test_exterior_back_prompt_allows_porch_when_requested():
    prompt = _compose_build_studio_prompt(
        mode="exterior_back", notes="please add a covered back porch", description=""
    )
    assert "covered porch/deck/patio connecting to the yard" in prompt
    assert "no covered porch, deck, patio" not in prompt
