"""Regression tests for the Ravlo Sales Certification curriculum: the
Account Executive track in Ravlo University (LoanMVP/static/js/
ravlo_university.jsx) rewritten into the 8-module structure from the
Ravlo Pricing Playbook proposal, plus Bronze/Silver/Gold certification
tiers tied to module completion. The JSX has no other test coverage
today, so this both pins the expected content and (via Babel) guards
against a syntax error silently shipping in a large hand-edited file.
"""
import os
import shutil
import subprocess

import pytest

_JSX_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "LoanMVP", "static", "js", "ravlo_university.jsx",
)
_BABEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "LoanMVP", "static", "js", "vendors", "babel.min.js",
)


def _read_jsx():
    with open(_JSX_PATH, encoding="utf-8") as f:
        return f.read()


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed in this environment")
def test_jsx_still_parses_as_valid_react_via_babel():
    script = f"""
const Babel = require({_BABEL_PATH!r});
const fs = require('fs');
const code = fs.readFileSync({_JSX_PATH!r}, 'utf8');
Babel.transform(code, {{ presets: ['react'] }});
console.log('OK');
"""
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_all_eight_certification_modules_are_present():
    body = _read_jsx()
    for title in [
        "Welcome to Ravlo",
        "Product Knowledge",
        "Discovery Certification",
        "Demo Certification",
        "Pricing Certification",
        "Objection Handling",
        "Proposal Certification",
        "Closing Certification",
    ]:
        assert title in body, f"missing module: {title}"


def test_certification_tiers_are_present():
    body = _read_jsx()
    assert "Certified Sales Associate" in body
    assert "Certified Solutions Consultant" in body
    assert "Enterprise Solutions Architect" in body
    assert "certifications:" in body


def test_stale_pre_playbook_pricing_language_is_gone():
    """The old copy referenced a two-tier Starter/Growth price list that
    predates the Standard/Enterprise pricing structure encoded into the
    AE deal tool this session -- it must not still be taught here."""
    body = _read_jsx()
    assert "Starter is $149/mo" not in body
    assert "Growth is $799/mo" not in body


def test_seven_ravlo_products_are_covered_in_product_knowledge():
    body = _read_jsx()
    for product in [
        "Ravlo Partners", "Ravlo Lending OS", "Ravlo Investor",
        "Ravlo Academy", "Ravlo Marketplace", "Ravlo Property Management",
        "Ravlo AI Copilot",
    ]:
        assert product in body, f"missing product lesson: {product}"
