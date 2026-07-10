"""Regression tests for the gpt-image-1 fallback used by Design Studio.

dalle_generate_images() always called client.images.generate() -- pure
text-to-image -- even when the caller supplied a real reference photo
(payload["image_base64"]), so a "redesign this room" request produced an
image with no relation to the actual property photo at all (wrong camera
angle, wrong windows, wrong layout), and lost the "keep the structure"
requirement entirely.

Separately, _dalle_prompt()'s interior/exterior prompt selection was keyed
strictly on mode == "interior", but callers like Design Studio's
generate-variant route only ever set payload["mode"] to a design preset
(e.g. "hgtv"), never the literal string "interior" -- so the prompt
silently fell back to an exterior-elevation template for what was supposed
to be an interior room redesign.
"""
import base64
from unittest.mock import MagicMock, patch

from LoanMVP.services.llm_studio_service import _dalle_prompt, dalle_generate_images


def test_dalle_prompt_uses_interior_template_when_mode_is_a_preset_not_literal_interior():
    prompt = _dalle_prompt("hgtv", {"room_type": "kitchen", "finish_level": "standard"})

    assert "interior design rendering" in prompt
    assert "kitchen room" in prompt
    assert "exterior" not in prompt.lower()


def test_dalle_prompt_falls_back_to_exterior_template_with_no_room_type():
    prompt = _dalle_prompt("hgtv", {"style": "modern", "bedrooms": 4})

    assert "exterior" in prompt.lower()


def test_dalle_prompt_still_honors_literal_interior_mode():
    prompt = _dalle_prompt("interior", {"room_type": "primary bedroom"})

    assert "interior design rendering" in prompt
    assert "primary bedroom room" in prompt


def _fake_image_response(b64_payload="ZmFrZQ=="):
    resp = MagicMock()
    item = MagicMock()
    item.b64_json = b64_payload
    resp.data = [item]
    return resp


def test_uses_images_edit_with_input_fidelity_when_reference_photo_present():
    fake_client = MagicMock()
    fake_client.images.edit.return_value = _fake_image_response()

    with patch("LoanMVP.services.llm_studio_service._openai_client", return_value=fake_client):
        result = dalle_generate_images({
            "mode": "hgtv",
            "room_type": "kitchen",
            "image_base64": base64.b64encode(b"fake photo bytes").decode(),
        })

    fake_client.images.edit.assert_called_once()
    fake_client.images.generate.assert_not_called()
    call_kwargs = fake_client.images.edit.call_args.kwargs
    assert call_kwargs["model"] == "gpt-image-1"
    assert call_kwargs["input_fidelity"] == "high"
    assert call_kwargs["quality"] == "high"
    assert result["ok"] is True


def test_uses_images_generate_when_no_reference_photo():
    fake_client = MagicMock()
    fake_client.images.generate.return_value = _fake_image_response()

    with patch("LoanMVP.services.llm_studio_service._openai_client", return_value=fake_client):
        result = dalle_generate_images({"mode": "exterior_front", "style": "modern"})

    fake_client.images.generate.assert_called_once()
    fake_client.images.edit.assert_not_called()
    assert result["ok"] is True


def test_reference_image_base64_field_also_triggers_edit():
    fake_client = MagicMock()
    fake_client.images.edit.return_value = _fake_image_response()

    with patch("LoanMVP.services.llm_studio_service._openai_client", return_value=fake_client):
        dalle_generate_images({
            "mode": "interior",
            "room_type": "bathroom",
            "reference_image_base64": base64.b64encode(b"fake photo bytes").decode(),
        })

    fake_client.images.edit.assert_called_once()


def test_blueprint_image_base64_field_also_triggers_edit():
    """investor_routes.py's floor-plan heuristic can misfire on an ordinary
    bright real estate photo and store the upload under
    "blueprint_image_base64" instead of "image_base64" -- this must still
    edit the real photo, not silently fall through to a blind generate()
    that ignores it entirely.
    """
    fake_client = MagicMock()
    fake_client.images.edit.return_value = _fake_image_response()

    with patch("LoanMVP.services.llm_studio_service._openai_client", return_value=fake_client):
        result = dalle_generate_images({
            "mode": "interior",
            "room_type": "kitchen",
            "blueprint_image_base64": base64.b64encode(b"fake photo bytes").decode(),
        })

    fake_client.images.edit.assert_called_once()
    fake_client.images.generate.assert_not_called()
    assert result["ok"] is True


def test_image_url_field_is_fetched_and_triggers_edit():
    """Design Studio's "pick a photo from this property" gallery selects an
    existing saved photo by URL -- it's never re-uploaded as base64. That
    URL has to be downloaded and edited from, not silently ignored just
    because it isn't already base64.
    """
    fake_client = MagicMock()
    fake_client.images.edit.return_value = _fake_image_response()

    with patch("LoanMVP.services.llm_studio_service._openai_client", return_value=fake_client), \
         patch(
             "LoanMVP.services.llm_studio_service._fetch_reference_b64_from_url",
             return_value=base64.b64encode(b"downloaded photo bytes").decode(),
         ) as mock_fetch:
        result = dalle_generate_images({
            "mode": "interior",
            "room_type": "living room",
            "image_url": "https://cdn.example.com/property-photos/abc123.jpg",
        })

    mock_fetch.assert_called_once_with("https://cdn.example.com/property-photos/abc123.jpg")
    fake_client.images.edit.assert_called_once()
    fake_client.images.generate.assert_not_called()
    assert result["ok"] is True


def test_falls_back_to_generate_when_image_url_fetch_fails():
    fake_client = MagicMock()
    fake_client.images.generate.return_value = _fake_image_response()

    with patch("LoanMVP.services.llm_studio_service._openai_client", return_value=fake_client), \
         patch("LoanMVP.services.llm_studio_service._fetch_reference_b64_from_url", return_value=None):
        result = dalle_generate_images({
            "mode": "interior",
            "room_type": "living room",
            "image_url": "https://cdn.example.com/unreachable.jpg",
        })

    fake_client.images.generate.assert_called_once()
    fake_client.images.edit.assert_not_called()
    assert result["ok"] is True
