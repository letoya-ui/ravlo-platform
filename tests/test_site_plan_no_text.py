"""Regression tests for Build Studio's site plan hallucinating text labels.

A live-recording review showed the AI-generated site plan rendering
architectural-looking annotations the model was never asked for -- a
"MODERN FARMHOUSE" title, a "DRIVEWAY" label, and a misspelled "PROPORTY
BOUNDARY" label. Text-to-image models can't be made to reliably avoid or
correctly spell hallucinated text, but two real, fixable gaps in this
codebase were making it worse:

1. concept_build_service.py's siteplan_payload never set a
   "negative_prompt" at all, unlike its sibling front/rear/blueprint
   payloads, which all do.
2. Even where a caller did set payload["negative_prompt"] (rear, blueprint,
   and now siteplan), llm_studio_service.py's OpenAI fallback path
   (_dalle_prompt) never read it -- gpt-image-1 has no separate
   negative-prompt field, but the caller's avoid-list still needs to be
   woven into the text prompt, and it never was.
"""
from unittest.mock import patch

from LoanMVP.services.concept_build_service import run_concept_build
from LoanMVP.services.llm_studio_service import _dalle_prompt


def _fake_engine_response(*_args, **_kwargs):
    return {"images": ["https://cdn.example.com/generated.png"]}


def test_siteplan_payload_has_a_negative_prompt_against_text():
    with patch(
        "LoanMVP.services.concept_build_service._post_engine",
        side_effect=_fake_engine_response,
    ) as mock_post_engine:
        run_concept_build(description="modern farmhouse", style="modern_farmhouse")

    siteplan_call = next(
        call for call in mock_post_engine.call_args_list
        if call.args[1].get("mode") == "siteplan"
    )
    siteplan_payload = siteplan_call.args[1]

    assert "negative_prompt" in siteplan_payload
    negative = siteplan_payload["negative_prompt"].lower()
    for term in ("text", "words", "letters", "labels", "title block", "watermark"):
        assert term in negative

    assert "absolutely no text" in siteplan_payload["prompt"].lower()


def test_dalle_prompt_weaves_in_caller_negative_prompt():
    """gpt-image-1 has no separate negative-prompt API field -- avoid-
    concepts only work woven into the main text prompt. This must not be
    silently dropped for any mode, not just siteplan.
    """
    prompt = _dalle_prompt("siteplan", {
        "negative_prompt": "text, words, letters, labels, title block, watermark",
    })

    assert "Avoid: text, words, letters, labels, title block, watermark" in prompt


def test_dalle_prompt_omits_avoid_section_when_no_negative_prompt_given():
    prompt = _dalle_prompt("exterior_front", {"style": "modern"})

    assert "Avoid:" not in prompt
