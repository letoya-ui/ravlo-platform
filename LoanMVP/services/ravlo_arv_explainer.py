"""
Ravlo ARV Explainer
-------------------
Uses OpenAI to generate a plain-English explanation of the ARV analysis.
Explains why the estimate may differ from provider AVMs.
"""

from __future__ import annotations

import json
import os
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def generate_explanation(
    subject: Dict[str, Any],
    arv_result: Dict[str, Any],
    included_comps: List[Dict[str, Any]],
    rejected_comps: List[Dict[str, Any]],
    provider_estimates: Dict[str, Dict[str, Any]],
) -> str:
    """
    Call OpenAI to produce a 2-5 sentence explanation of the ARV analysis.
    Falls back to a template explanation if the API is unavailable.
    """
    try:
        import openai
    except ImportError:
        logger.warning("openai package not installed; using template explanation")
        return _template_explanation(subject, arv_result, included_comps, rejected_comps, provider_estimates)

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        logger.warning("OPENAI_API_KEY not set; using template explanation")
        return _template_explanation(subject, arv_result, included_comps, rejected_comps, provider_estimates)

    prompt = _build_prompt(subject, arv_result, included_comps, rejected_comps, provider_estimates)

    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Ravlo, a real estate investment analyst. "
                        "Write a concise, transparent explanation of an ARV (After Repair Value) analysis. "
                        "Be specific about which comps were strongest, which were weak, "
                        "and why the ARV differs from provider AVMs. "
                        "Use plain English. 2-5 sentences max. "
                        "Do not use bullet points. Do not repeat the numbers from the data — just explain the reasoning."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error("OpenAI explanation failed: %s", e)
        return _template_explanation(subject, arv_result, included_comps, rejected_comps, provider_estimates)


def _build_prompt(
    subject: Dict[str, Any],
    arv_result: Dict[str, Any],
    included: List[Dict[str, Any]],
    rejected: List[Dict[str, Any]],
    providers: Dict[str, Dict[str, Any]],
) -> str:
    top_comps = included[:5]
    top_rejected = rejected[:3]

    comp_summaries = []
    for c in top_comps:
        comp_summaries.append({
            "address": c.get("address") or c.get("formattedAddress"),
            "price": c.get("price"),
            "price_per_sqft": c.get("price_per_sqft"),
            "status": c.get("status_normalized"),
            "score": c.get("comp_score"),
            "months_ago": c.get("months_ago"),
            "distance_miles": c.get("distance") or c.get("distance_miles"),
        })

    rejected_summaries = []
    for c in top_rejected:
        rejected_summaries.append({
            "address": c.get("address") or c.get("formattedAddress"),
            "price": c.get("price"),
            "score": c.get("comp_score"),
            "rejection_reason": c.get("rejection_reason"),
        })

    provider_summary = {}
    for name, data in providers.items():
        if isinstance(data, dict):
            provider_summary[name] = {
                k: v for k, v in data.items()
                if k in ("avm", "market_value", "assessed_value", "value", "rent", "traditional_rent")
                and v is not None
            }

    data = {
        "subject": {
            "address": subject.get("address"),
            "property_type": subject.get("property_type"),
            "is_vacant_lot": subject.get("is_vacant_lot"),
            "beds": subject.get("beds"),
            "baths": subject.get("baths"),
            "living_sqft": subject.get("living_sqft"),
            "lot_sqft": subject.get("lot_sqft"),
        },
        "arv": {
            "conservative": arv_result.get("conservative"),
            "base": arv_result.get("base"),
            "aggressive": arv_result.get("aggressive"),
            "confidence": arv_result.get("confidence"),
            "land_value": arv_result.get("land_value"),
            "method": arv_result.get("method"),
        },
        "strongest_comps": comp_summaries,
        "rejected_comps": rejected_summaries,
        "provider_estimates": provider_summary,
        "warnings": arv_result.get("warnings", []),
    }

    return (
        "Analyze this ARV report and explain the estimate to a real estate investor.\n\n"
        "Answer these questions naturally in paragraph form:\n"
        "1. Which comps were strongest and why?\n"
        "2. Which comps were weak or rejected?\n"
        "3. Why is the ARV higher or lower than provider AVMs?\n"
        "4. Is the property valued as-is or as a finished project?\n"
        "5. What assumptions are being made?\n"
        "6. What risks could make the ARV wrong?\n\n"
        f"Data:\n{json.dumps(data, indent=2, default=str)}"
    )


def _template_explanation(
    subject: Dict[str, Any],
    arv_result: Dict[str, Any],
    included: List[Dict[str, Any]],
    rejected: List[Dict[str, Any]],
    providers: Dict[str, Dict[str, Any]],
) -> str:
    """Deterministic fallback when OpenAI is unavailable."""
    parts = []

    n_included = len(included)
    n_rejected = len(rejected)
    confidence = arv_result.get("confidence", "low")
    method = arv_result.get("method", "")
    base = arv_result.get("base", 0)

    if subject.get("is_vacant_lot"):
        parts.append(
            "This is a vacant lot. The finished-home ARV is estimated using "
            "nearby completed single-family home sales."
        )

    if n_included > 0:
        best = included[0]
        best_addr = best.get("address") or best.get("formattedAddress") or "a nearby comp"
        best_ppsf = best.get("price_per_sqft")
        parts.append(
            f"The strongest comp is {best_addr}"
            + (f" at ${best_ppsf:,.0f}/sqft" if best_ppsf else "")
            + f" (score {best.get('comp_score', '?')}/100)."
        )

    sold = [c for c in included if c.get("status_normalized") == "sold"]
    active = [c for c in included if c.get("status_normalized") == "active"]
    if active and not sold:
        parts.append(
            "No sold comps were strong enough; active listings are used "
            "as market indicators but not treated as proof of value."
        )
    elif active:
        parts.append(
            "Active listings support the upper end of the range "
            "but are not weighted as heavily as sold comps."
        )

    # Provider comparison
    _compare_providers(parts, base, providers)

    if n_rejected > 0:
        parts.append(
            f"{n_rejected} comp(s) were rejected due to low similarity scores."
        )

    parts.append(f"Overall confidence: {confidence}.")

    return " ".join(parts)


def _compare_providers(
    parts: List[str],
    base_arv: float,
    providers: Dict[str, Dict[str, Any]],
) -> None:
    for name, data in providers.items():
        if not isinstance(data, dict):
            continue
        for field in ("avm", "market_value", "value"):
            val = data.get(field)
            if val and isinstance(val, (int, float)) and val > 0 and base_arv > 0:
                diff_pct = (base_arv - val) / val * 100
                if abs(diff_pct) > 10:
                    direction = "higher" if diff_pct > 0 else "lower"
                    parts.append(
                        f"Ravlo's estimate is {abs(diff_pct):.0f}% {direction} than "
                        f"{name}'s AVM of ${val:,.0f}, adjusted based on comp evidence."
                    )
                break
