"""Regression tests for Build Studio's blueprint/exterior layout
consistency fix and the combined multi-floor blueprint sheet.

Three related problems, all from the same root gap: generate_build_exterior()
never read bedrooms/bathrooms/square_feet from the form (generate_build_blueprint()
did), never conditioned on the deal's own generated blueprint image (a
"fallback_blueprint_url" variable was computed but never actually used --
dead code), and always passed blueprint_constrained=False so the one prompt
sentence telling the model to treat the blueprint as a binding constraint on
footprint/massing/floor count never made it into any prompt. The result:
blueprint and exterior were two independent text-to-image calls with no
shared image-level grounding, so they could depict different-looking houses.

Separately, generating a separate image per floor ("Blueprint - First Floor",
"Blueprint - Second Floor", ...) was unreliable for 2+ story projects -- a
single floor's image would come back showing multiple floors' rooms merged
together at inconsistent scale. generate_full_build() and
generate_build_blueprint() now always produce exactly one blueprint image per
project: for single-story projects it's that one floor's plan; for 2+ story
projects it's a single sheet with every floor's plan shown side by side in
its own panel, all under one canonical build_project["blueprint"] key.
"""
from unittest.mock import patch

from LoanMVP.models.admin import Company
from LoanMVP.models.borrowers import Deal
from LoanMVP.models.investor_models import InvestorProfile
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_investor(db_session, email="investor@example.com"):
    company = Company(name="Build Consistency Co", is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role="investor", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    profile = InvestorProfile(user_id=user.id, full_name="Ivy Vestor")
    db_session.add(profile)
    db_session.commit()
    return user, profile


def _engine_response():
    return {"images_base64": ["ZmFrZQ=="], "seed": 1, "job_id": "abc", "meta": {}}


# ---------------------------------------------------------------------------
# generate_build_exterior(): structured facts + blueprint conditioning
# ---------------------------------------------------------------------------

def test_generate_build_exterior_includes_bedrooms_bathrooms_square_feet(db_session, client):
    user, profile = _make_investor(db_session)
    deal = Deal(user_id=user.id, title="Consistency Deal")
    db_session.add(deal)
    db_session.commit()
    login_as(client, user)

    with patch("LoanMVP.routes.investor_routes._engine_or_dalle") as mock_engine, \
         patch("LoanMVP.routes.investor_routes._upload_after_images_from_b64", return_value=["https://example.com/ext.png"]):
        mock_engine.return_value = _engine_response()

        client.post("/investor/deal-studio/build-studio/generate-exterior", data={
            "deal_id": str(deal.id),
            "property_type": "single_family",
            "style": "modern_farmhouse",
            "bedrooms": "4",
            "bathrooms": "3",
            "square_feet": "2400",
        })

    assert mock_engine.called
    payload = mock_engine.call_args.args[1]
    assert payload["bedrooms"] == 4
    assert payload["bathrooms"] == 3
    assert payload["square_feet"] == 2400


def test_generate_build_exterior_conditions_on_saved_blueprint(db_session, client):
    """With no land/site photo, exterior generation should still ground
    itself in the deal's own already-saved blueprint image rather than
    being a completely independent text-to-image call."""
    user, profile = _make_investor(db_session, email="investor2@example.com")
    deal = Deal(
        user_id=user.id,
        title="Blueprint Ref Deal",
        results_json={"build_project": {"blueprint": {"image_url": "https://example.com/blueprint.png"}}},
    )
    db_session.add(deal)
    db_session.commit()
    login_as(client, user)

    with patch("LoanMVP.routes.investor_routes._engine_or_dalle") as mock_engine, \
         patch("LoanMVP.routes.investor_routes._upload_after_images_from_b64", return_value=["https://example.com/ext.png"]):
        mock_engine.return_value = _engine_response()

        client.post("/investor/deal-studio/build-studio/generate-exterior", data={
            "deal_id": str(deal.id),
            "property_type": "single_family",
            "style": "modern_farmhouse",
        })

    payload = mock_engine.call_args.args[1]
    assert payload["reference_image_url"] == "https://example.com/blueprint.png"
    assert payload["strength"] == 0.3


def test_generate_build_exterior_text_only_when_no_blueprint_saved(db_session, client):
    """No saved blueprint at all -- falls back to the original text-only
    behavior rather than erroring."""
    user, profile = _make_investor(db_session, email="investor4@example.com")
    deal = Deal(user_id=user.id, title="No Blueprint Deal")
    db_session.add(deal)
    db_session.commit()
    login_as(client, user)

    with patch("LoanMVP.routes.investor_routes._engine_or_dalle") as mock_engine, \
         patch("LoanMVP.routes.investor_routes._upload_after_images_from_b64", return_value=["https://example.com/ext.png"]):
        mock_engine.return_value = _engine_response()

        client.post("/investor/deal-studio/build-studio/generate-exterior", data={
            "deal_id": str(deal.id),
        })

    payload = mock_engine.call_args.args[1]
    assert "reference_image_url" not in payload
    assert payload["strength"] == 0.25


# ---------------------------------------------------------------------------
# generate_full_build(): one combined blueprint sheet for all floors
# ---------------------------------------------------------------------------

def test_full_build_combines_all_floors_into_one_blueprint(db_session, client):
    user, profile = _make_investor(db_session, email="investor5@example.com")
    deal = Deal(user_id=user.id, title="Two Story Deal")
    db_session.add(deal)
    db_session.commit()
    login_as(client, user)

    with patch("LoanMVP.routes.investor_routes._engine_or_dalle") as mock_engine, \
         patch("LoanMVP.routes.investor_routes._upload_after_images_from_b64", return_value=["https://example.com/img.png"]):
        mock_engine.return_value = _engine_response()

        client.post("/investor/deal-studio/build-studio/generate-full-build", data={
            "deal_id": str(deal.id),
            "property_type": "single_family",
            "style": "modern_farmhouse",
            "number_of_floors": "2",
            "save_to_deal": "1",
        })

    # Exactly one blueprint call regardless of floor count: exterior_front,
    # blueprint, siteplan, exterior_back.
    blueprint_calls = [
        call for call in mock_engine.call_args_list
        if call.args[1].get("output_mode") == "blueprint"
    ]
    assert len(blueprint_calls) == 1
    assert blueprint_calls[0].args[1]["combine_floors"] is True

    updated = Deal.query.get(deal.id)
    build_project = (updated.results_json or {}).get("build_project", {})
    assert "blueprint_first" not in build_project
    assert "blueprint_second" not in build_project
    assert "blueprint_third" not in build_project
    assert build_project["blueprint"]["combined_floors"] is True


def test_full_build_single_floor_not_combined(db_session, client):
    user, profile = _make_investor(db_session, email="investor6@example.com")
    deal = Deal(user_id=user.id, title="Single Story Deal")
    db_session.add(deal)
    db_session.commit()
    login_as(client, user)

    with patch("LoanMVP.routes.investor_routes._engine_or_dalle") as mock_engine, \
         patch("LoanMVP.routes.investor_routes._upload_after_images_from_b64", return_value=["https://example.com/img.png"]):
        mock_engine.return_value = _engine_response()

        client.post("/investor/deal-studio/build-studio/generate-full-build", data={
            "deal_id": str(deal.id),
            "property_type": "single_family",
            "style": "modern_farmhouse",
            "number_of_floors": "1",
            "save_to_deal": "1",
        })

    blueprint_calls = [
        call for call in mock_engine.call_args_list
        if call.args[1].get("output_mode") == "blueprint"
    ]
    assert len(blueprint_calls) == 1
    assert blueprint_calls[0].args[1]["combine_floors"] is False

    updated = Deal.query.get(deal.id)
    build_project = (updated.results_json or {}).get("build_project", {})
    assert build_project["blueprint"]["combined_floors"] is False


def test_full_build_clears_stale_legacy_per_floor_keys(db_session, client):
    """Deals from before this change may still carry the retired
    blueprint_first/second/third keys -- regenerating should clean them up
    rather than leaving stale per-floor images alongside the new combined
    blueprint."""
    user, profile = _make_investor(db_session, email="investor9@example.com")
    deal = Deal(
        user_id=user.id,
        title="Legacy Data Deal",
        results_json={"build_project": {
            "blueprint_first": {"image_url": "https://example.com/stale-floor1.png"},
            "blueprint_second": {"image_url": "https://example.com/stale-floor2.png"},
        }},
    )
    db_session.add(deal)
    db_session.commit()
    login_as(client, user)

    with patch("LoanMVP.routes.investor_routes._engine_or_dalle") as mock_engine, \
         patch("LoanMVP.routes.investor_routes._upload_after_images_from_b64", return_value=["https://example.com/img.png"]):
        mock_engine.return_value = _engine_response()

        client.post("/investor/deal-studio/build-studio/generate-full-build", data={
            "deal_id": str(deal.id),
            "property_type": "single_family",
            "style": "modern_farmhouse",
            "number_of_floors": "2",
            "save_to_deal": "1",
        })

    updated = Deal.query.get(deal.id)
    build_project = (updated.results_json or {}).get("build_project", {})
    assert "blueprint_first" not in build_project
    assert "blueprint_second" not in build_project


# ---------------------------------------------------------------------------
# project_build.html: single blueprint card, labeled for multi-story
# ---------------------------------------------------------------------------

def test_blueprint_card_labeled_all_floors_for_multi_story_project(db_session, client):
    user, profile = _make_investor(db_session, email="investor7@example.com")
    deal = Deal(
        user_id=user.id,
        title="Multi Story Display Deal",
        results_json={"build_project": {
            "number_of_floors": 2,
            "blueprint": {"image_url": "https://example.com/combined.png", "combined_floors": True},
        }},
    )
    db_session.add(deal)
    db_session.commit()
    login_as(client, user)

    resp = client.get(f"/investor/deals/{deal.id}/build")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Blueprint - All Floors" in body
    assert 'id="floor1Card"' in body
    assert "https://example.com/combined.png" in body


def test_blueprint_card_labeled_first_floor_for_single_story_project(db_session, client):
    user, profile = _make_investor(db_session, email="investor8@example.com")
    deal = Deal(
        user_id=user.id,
        title="Single Story Display Deal",
        results_json={"build_project": {
            "number_of_floors": 1,
            "blueprint": {"image_url": "https://example.com/floor1.png", "combined_floors": False},
        }},
    )
    db_session.add(deal)
    db_session.commit()
    login_as(client, user)

    resp = client.get(f"/investor/deals/{deal.id}/build")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Blueprint - First Floor" in body
    assert "Blueprint - All Floors" not in body
