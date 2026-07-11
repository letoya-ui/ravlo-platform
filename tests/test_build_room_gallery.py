"""Regression tests for Build Studio's Room Gallery feature.

generate_build_room() already existed and worked, but was orphaned from
any UI: build_studio() computed interior_result/interior_rooms from
deal.results_json but never passed them into the rendered template, so
even already-generated rooms never showed up on the page. Separately,
re-generating a photo for the same room slot (same room_type/floor/style)
overwrote the previous entry's "images" list instead of accumulating onto
it, which would have made "a handful of stills at different angles" for
one room impossible -- each new angle would have deleted the last one.
"""
from unittest.mock import patch

from LoanMVP.models.admin import Company
from LoanMVP.models.borrowers import Deal
from LoanMVP.models.investor_models import InvestorProfile
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_investor(db_session, email="investor@example.com"):
    company = Company(name="Build Gallery Co", is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role="investor", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    profile = InvestorProfile(user_id=user.id, full_name="Ivy Vestor")
    db_session.add(profile)
    db_session.commit()
    return user, profile


def _make_deal_with_blueprint(db_session, user, existing_rooms=None):
    build_project = {
        "blueprint": {"image_url": "https://example.com/blueprint.png"},
        "blueprint_first": {"image_url": "https://example.com/blueprint.png"},
    }
    if existing_rooms is not None:
        build_project["interior"] = {
            "latest": existing_rooms[-1] if existing_rooms else {},
            "rooms": existing_rooms,
        }
    deal = Deal(
        user_id=user.id,
        title="Test Build Deal",
        results_json={"build_project": build_project},
    )
    db_session.add(deal)
    db_session.commit()
    return deal


def test_build_studio_passes_interior_rooms_to_template(db_session, client):
    user, profile = _make_investor(db_session)
    existing_room = {
        "room_type": "kitchen",
        "floor": "main",
        "style": "modern_farmhouse",
        "image_url": "https://example.com/kitchen-1.png",
        "images": ["https://example.com/kitchen-1.png", "https://example.com/kitchen-2.png"],
    }
    deal = _make_deal_with_blueprint(db_session, user, existing_rooms=[existing_room])
    login_as(client, user)

    with patch("LoanMVP.routes.investor_routes.render_template") as mock_render:
        mock_render.return_value = "ok"
        client.get(f"/investor/deals/{deal.id}/build")

    assert mock_render.called
    call_kwargs = mock_render.call_args.kwargs
    assert "interior_rooms" in call_kwargs
    assert call_kwargs["interior_rooms"] == [existing_room]
    assert call_kwargs["interior_result"] == existing_room


def test_build_studio_passes_empty_interior_rooms_when_none_generated(db_session, client):
    user, profile = _make_investor(db_session, email="investor2@example.com")
    deal = _make_deal_with_blueprint(db_session, user)
    login_as(client, user)

    with patch("LoanMVP.routes.investor_routes.render_template") as mock_render:
        mock_render.return_value = "ok"
        client.get(f"/investor/deals/{deal.id}/build")

    call_kwargs = mock_render.call_args.kwargs
    assert call_kwargs["interior_rooms"] == []
    assert call_kwargs["interior_result"] == {}


def test_generate_build_room_accumulates_images_for_same_room_slot(db_session, client):
    user, profile = _make_investor(db_session, email="investor3@example.com")
    existing_room = {
        "room_type": "kitchen",
        "floor": "main",
        "style": "modern_farmhouse",
        "image_url": "https://example.com/kitchen-1.png",
        "images": ["https://example.com/kitchen-1.png"],
    }
    deal = _make_deal_with_blueprint(db_session, user, existing_rooms=[existing_room])
    login_as(client, user)

    with patch("LoanMVP.routes.investor_routes._engine_or_dalle") as mock_engine, \
         patch("LoanMVP.routes.investor_routes._upload_after_images_from_b64", return_value=["https://example.com/kitchen-2.png"]), \
         patch("LoanMVP.routes.investor_routes.download_image_bytes", return_value=b"fake blueprint bytes"):
        mock_engine.return_value = {"images_base64": ["ZmFrZQ=="], "seed": 2, "job_id": "def", "meta": {}}

        resp = client.post(
            "/investor/deal-studio/build-studio/generate-room",
            data={
                "deal_id": str(deal.id),
                "room_type": "kitchen",
                "floor": "main",
                "style": "modern_farmhouse",
                "notes": "wide angle from the entry",
            },
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    # Both the original image and the newly generated one must be present --
    # regenerating the same room slot must not delete the prior angle.
    assert data["room_result"]["images"] == [
        "https://example.com/kitchen-1.png",
        "https://example.com/kitchen-2.png",
    ]
    # The cover thumbnail stays the first-ever image so it doesn't jump
    # around as more angles get added.
    assert data["room_result"]["image_url"] == "https://example.com/kitchen-1.png"


def test_generate_build_room_first_call_has_single_image(db_session, client):
    user, profile = _make_investor(db_session, email="investor4@example.com")
    deal = _make_deal_with_blueprint(db_session, user)
    login_as(client, user)

    with patch("LoanMVP.routes.investor_routes._engine_or_dalle") as mock_engine, \
         patch("LoanMVP.routes.investor_routes._upload_after_images_from_b64", return_value=["https://example.com/bathroom-1.png"]), \
         patch("LoanMVP.routes.investor_routes.download_image_bytes", return_value=b"fake blueprint bytes"):
        mock_engine.return_value = {"images_base64": ["ZmFrZQ=="], "seed": 1, "job_id": "abc", "meta": {}}

        resp = client.post(
            "/investor/deal-studio/build-studio/generate-room",
            data={
                "deal_id": str(deal.id),
                "room_type": "bathroom",
                "floor": "main",
            },
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["room_result"]["images"] == ["https://example.com/bathroom-1.png"]
