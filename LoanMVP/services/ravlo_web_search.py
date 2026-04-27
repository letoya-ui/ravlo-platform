"""
Ravlo Web Search Fallback
--------------------------
Uses OpenAI with web search to validate unusual or questionable comps
when structured provider data is insufficient.
"""

from __future__ import annotations

import json
import os
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def should_trigger_web_search(
    subject: Dict[str, Any],
    arv_result: Dict[str, Any],
    included_comps: List[Dict[str, Any]],
    provider_estimates: Dict[str, Dict[str, Any]],
) -> bool:
    """
    Returns True if conditions warrant supplemental web search.
    """
    # Vacant land always benefits from more data
    if subject.get("is_vacant_lot"):
        return True

    # Fewer than 3 good sold comps
    sold = [c for c in included_comps if c.get("status_normalized") == "sold"]
    if len(sold) < 3:
        return True

    # Provider AVMs disagree by more than 15%
    if _providers_disagree(provider_estimates, threshold=0.15):
        return True

    # Property appears luxury, waterfront, or niche
    if _is_niche_property(subject):
        return True

    # Low confidence
    if arv_result.get("confidence") == "low":
        return True

    return False


def search_comps_web(
    subject: Dict[str, Any],
    arv_result: Dict[str, Any],
    included_comps: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Use OpenAI with web search to find supplemental comp data.

    Returns:
    {
        "searched": True/False,
        "results": [
            {
                "address": str,
                "price": float,
                "status": str,
                "sqft": float,
                "beds": int,
                "baths": float,
                "year_built": int,
                "lot_sqft": float,
                "days_on_market": int,
                "source": str,
                "source_url": str,
            }
        ],
        "market_context": str,
        "error": str | None,
    }
    """
    try:
        import openai
    except ImportError:
        return {"searched": False, "results": [], "market_context": "", "error": "openai not installed"}

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {"searched": False, "results": [], "market_context": "", "error": "OPENAI_API_KEY not set"}

    address = subject.get("address") or "Unknown"
    base_arv = arv_result.get("base", 0)
    is_lot = subject.get("is_vacant_lot", False)
    sqft = subject.get("living_sqft") or 0
    beds = subject.get("beds") or "?"
    baths = subject.get("baths") or "?"

    query = _build_search_query(address, is_lot, sqft, beds, baths, base_arv)

    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.responses.create(
            model="gpt-4o-mini",
            tools=[{"type": "web_search_preview"}],
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are a real estate comp researcher. Search the web for recent property sales "
                        "and active listings near the subject property. Return structured data as JSON. "
                        "Focus on sold comps within the last 24 months and active listings on the same "
                        "or nearby streets. Include source URLs when available."
                    ),
                },
                {"role": "user", "content": query},
            ],
        )

        raw_text = ""
        for item in response.output:
            if hasattr(item, "content"):
                for block in item.content:
                    if hasattr(block, "text"):
                        raw_text += block.text

        parsed = _parse_web_results(raw_text)
        return {
            "searched": True,
            "results": parsed.get("comps", []),
            "market_context": parsed.get("market_context", ""),
            "error": None,
        }

    except Exception as e:
        logger.error("Web search failed: %s", e)
        # Fallback: try with standard chat completions
        return _fallback_search(api_key, query)


def _build_search_query(
    address: str,
    is_lot: bool,
    sqft: float,
    beds: Any,
    baths: Any,
    base_arv: float,
) -> str:
    if is_lot:
        return (
            f"Find recent sold comps and active listings of completed single-family homes "
            f"near {address}. I need finished-home comps because the subject is a vacant lot. "
            f"Look for homes sold within the last 24 months, preferably on the same street or "
            f"in the same neighborhood. For each comp, provide: address, sale price, sqft, "
            f"beds, baths, year built, lot size, sale date, days on market, status (sold/active), "
            f"and source URL. Return as JSON with keys: comps (array), market_context (string)."
        )

    return (
        f"Find recent sold comps and active listings near {address}. "
        f"Subject is approximately {sqft:,.0f} sqft, {beds} beds, {baths} baths. "
        f"Current estimated value is around ${base_arv:,.0f}. "
        f"Look for properties sold within the last 24 months in the same neighborhood. "
        f"For each comp, provide: address, sale price, sqft, beds, baths, year built, "
        f"lot size, sale date, days on market, status (sold/active), and source URL. "
        f"Return as JSON with keys: comps (array), market_context (string)."
    )


def _parse_web_results(raw_text: str) -> Dict[str, Any]:
    """Extract JSON from OpenAI response, handling markdown code blocks."""
    text = raw_text.strip()

    # Try to find JSON in code blocks
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start)
        text = text[start:end].strip()
    elif "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        text = text[start:end].strip()

    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {"comps": [], "market_context": text[:500] if text else ""}


def _fallback_search(api_key: str, query: str) -> Dict[str, Any]:
    """Try standard chat completions if responses API fails."""
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a real estate comp researcher. Based on your knowledge, "
                        "provide recent comparable property data. Return JSON with keys: "
                        "comps (array of objects with address, price, sqft, beds, baths, "
                        "year_built, status, source), market_context (string)."
                    ),
                },
                {"role": "user", "content": query},
            ],
            temperature=0.2,
            max_tokens=800,
        )
        raw = response.choices[0].message.content.strip()
        parsed = _parse_web_results(raw)
        return {
            "searched": True,
            "results": parsed.get("comps", []),
            "market_context": parsed.get("market_context", ""),
            "error": None,
        }
    except Exception as e:
        logger.error("Fallback search failed: %s", e)
        return {"searched": False, "results": [], "market_context": "", "error": str(e)}


def _providers_disagree(
    providers: Dict[str, Dict[str, Any]],
    threshold: float = 0.15,
) -> bool:
    values = []
    for name, data in providers.items():
        if not isinstance(data, dict):
            continue
        for field in ("avm", "market_value", "value", "estimatedValue"):
            val = data.get(field)
            if isinstance(val, (int, float)) and val > 0:
                values.append(val)
                break
    if len(values) < 2:
        return False

    max_val = max(values)
    min_val = min(values)
    if min_val == 0:
        return True
    return (max_val - min_val) / min_val > threshold


def _is_niche_property(subject: Dict[str, Any]) -> bool:
    address = str(subject.get("address") or "").lower()
    niche_keywords = [
        "waterfront", "beachfront", "oceanfront", "bayfront",
        "lakefront", "canal", "island", "penthouse",
        "beach", "ocean", "bay",
    ]
    if any(kw in address for kw in niche_keywords):
        return True

    # Luxury by price
    values = subject.get("estimated_value_by_source") or {}
    for v in values.values():
        if isinstance(v, (int, float)) and v > 1_500_000:
            return True

    return False
