"""Regression test for a production crash: Build Studio's cloud-generation
fallback logged "Cloud deal analysis (Claude) failed:
'ThinkingBlock' object has no attribute 'text'".

_run_deal_analysis() (cloud_studio_service.py) called client.messages.create()
and blindly read message.content[0].text, assuming the first content block
in Claude's response is always the text block. Claude can return other block
types (e.g. a ThinkingBlock) ahead of the text block, so indexing [0] isn't
reliable -- the fix scans for the first block with type == "text" instead.
"""
import json
from types import SimpleNamespace
from unittest.mock import patch

from LoanMVP.services.cloud_studio_service import _run_deal_analysis


def _fake_message(blocks):
    return SimpleNamespace(content=blocks)


def test_run_deal_analysis_skips_leading_thinking_block():
    expected = {
        "scope": {"intent": "build_package", "property_type": "single family"},
        "materials": [],
        "phases": [],
        "timeline": {},
        "risks": [],
    }
    thinking_block = SimpleNamespace(type="thinking", thinking="reasoning about the project...")
    text_block = SimpleNamespace(type="text", text=json.dumps(expected))

    fake_client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: _fake_message([thinking_block, text_block])))

    with patch("LoanMVP.services.cloud_studio_service._anthropic_client", return_value=fake_client):
        result = _run_deal_analysis({"property_type": "single_family", "style": "modern"})

    assert result == expected


def test_run_deal_analysis_works_with_text_only_response():
    expected = {"scope": {"intent": "build_package"}, "materials": [], "phases": [], "timeline": {}, "risks": []}
    text_block = SimpleNamespace(type="text", text=json.dumps(expected))

    fake_client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: _fake_message([text_block])))

    with patch("LoanMVP.services.cloud_studio_service._anthropic_client", return_value=fake_client):
        result = _run_deal_analysis({"property_type": "single_family"})

    assert result == expected


def test_run_deal_analysis_raises_clear_error_when_no_text_block():
    thinking_block = SimpleNamespace(type="thinking", thinking="only reasoning, no answer")
    fake_client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: _fake_message([thinking_block])))

    with patch("LoanMVP.services.cloud_studio_service._anthropic_client", return_value=fake_client):
        try:
            _run_deal_analysis({"property_type": "single_family"})
            assert False, "expected RuntimeError"
        except RuntimeError as exc:
            assert "no text block" in str(exc)
