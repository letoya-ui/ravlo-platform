"""Regression test for the Business Plan tool's "messing up" bug.

ravlo_business_plan.jsx hardcoded model: "claude-opus-4-5" in both the
initial plan-generation request and the follow-up chat request. That model
ID doesn't exist -- Anthropic's API rejected every request with an error
response, which the JSX's generic `data.content?.map(...) || "Unable to
generate plan. Please try again."` fallback then silently swallowed,
making every single business plan request appear to fail with a generic
error. university_routes.py's own server-side default
(`_DEFAULT_MODEL = "claude-opus-4-8"`) is a valid model and is what the
working Academy chat feature (ravlo_university.jsx) relies on by sending
a real model id instead of a fabricated one -- so the fix is simply for
the client to stop sending a bogus override.
"""
import os

_JSX_PATH = os.path.join(
    os.path.dirname(__file__), "..", "LoanMVP", "static", "js", "ravlo_business_plan.jsx"
)


def _read_jsx():
    with open(_JSX_PATH, "r") as f:
        return f.read()


def test_business_plan_jsx_does_not_send_invalid_model_id():
    source = _read_jsx()
    assert "claude-opus-4-5" not in source


def test_business_plan_jsx_sends_valid_model_id():
    source = _read_jsx()
    assert source.count('"claude-opus-4-8"') == 2
