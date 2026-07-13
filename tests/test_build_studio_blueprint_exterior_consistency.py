"""Regression tests for Build Studio's blueprint/exterior layout
consistency fix and the removal of "Floor 1" for multi-story projects.

Two related problems, both from the same root gap: generate_build_exterior()
never read bedrooms/bathrooms/square_feet from the form (generate_build_blueprint()
did), never conditioned on the deal's own generated blueprint image (a
"fallback_blueprint_url" variable was computed but never actually used --
dead code), and always passed blueprint_constrained=False so the one prompt
sentence telling the model to treat the blueprint as a binding constraint on
footprint/massing/floor count never made it into any prompt. The result:
blueprint and exterior were two independent text-to-image calls with no
shared image-level grounding, so they could depict different-looking houses.

Separately, "Floor 1" blueprint generation was unreliable for 2+ story
projects -- its single generated image would come back showing both floors'
rooms merged together. generate_full_build() now skips generating it for
2+ story projects, promoting Floor 2 to the canonical "blueprint" reference
instead (used by both interior room generation and the new exterior
conditioning above).
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


def test_generate_build_exterior_falls_back_to_floor2_blueprint(db_session, client):
    """For a 2+ story project where Floor 1 was skipped, exterior
    conditioning should fall back to Floor 2's saved blueprint."""
    user, profile = _make_investor(db_session, email="investor3@example.com")
    deal = Deal(
        user_id=user.id,
        title="Floor2 Ref Deal",
        results_json={"build_project": {"blueprint_floor2": {"image_url": "https://example.com/floor2.png"}}},
    )
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
    assert payload["reference_image_url"] == "https://example.com/floor2.png"


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
# generate_full_build(): Floor 1 removed for 2+ story projects
# ---------------------------------------------------------------------------

def test_full_build_skips_floor1_for_two_story_project(db_session, client):
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

    updated = Deal.query.get(deal.id)
    build_project = (updated.results_json or {}).get("build_project", {})
    assert "blueprint_first" not in build_project
    assert "blueprint_second" in build_project
    # Floor 2 becomes the canonical "blueprint" reference used elsewhere.
    assert build_project["blueprint"]["image_url"] == build_project["blueprint_second"]["image_url"]


def test_full_build_keeps_floor1_for_single_story_project(db_session, client):
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

    updated = Deal.query.get(deal.id)
    build_project = (updated.results_json or {}).get("build_project", {})
    assert "blueprint_first" in build_project
    assert "blueprint_second" not in build_project
    assert build_project["blueprint"]["image_url"] == build_project["blueprint_first"]["image_url"]


# ---------------------------------------------------------------------------
# project_build.html: Floor 1 card/summary row hidden for multi-story
# ---------------------------------------------------------------------------

def test_floor1_card_hidden_for_multi_story_project(db_session, client):
    user, profile = _make_investor(db_session, email="investor7@example.com")
    deal = Deal(
        user_id=user.id,
        title="Multi Story Display Deal",
        results_json={"build_project": {
            "number_of_floors": 2,
            "blueprint": {"image_url": "https://example.com/floor2.png"},
            "blueprint_second": {"image_url": "https://example.com/floor2.png"},
        }},
    )
    db_session.add(deal)
    db_session.commit()
    login_as(client, user)

    resp = client.get(f"/investor/deals/{deal.id}/build")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'class="ravlo-card pad hidden" id="floor1Card"' in body
    assert 'id="floor1SummaryRow" class="hidden"' in body


def test_floor1_card_shown_for_single_story_project(db_session, client):
    user, profile = _make_investor(db_session, email="investor8@example.com")
    deal = Deal(
        user_id=user.id,
        title="Single Story Display Deal",
        results_json={"build_project": {
            "number_of_floors": 1,
            "blueprint_first": {"image_url": "https://example.com/floor1.png"},
        }},
    )
    db_session.add(deal)
    db_session.commit()
    login_as(client, user)

    resp = client.get(f"/investor/deals/{deal.id}/build")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'class="ravlo-card pad hidden" id="floor1Card"' not in body
    assert 'id="floor1SummaryRow" class="hidden"' not in body
