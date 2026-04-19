"""
Regional Construction Cost Index
---------------------------------

Turns national-average cost numbers (flat $/sqft rehab, hardcoded build
costs, per-line-item rehab prices) into locally-adjusted numbers based on
the property's ZIP code or state.

Data source: RSMeans Location Factors, loaded from
``LoanMVP/data/regional_cost_index.json``. Baseline = 1.00 (U.S. average).

Typical use::

    from LoanMVP.services.cost_index import get_local_multiplier, describe_local_index

    factor = get_local_multiplier(zip_code="12401", state="NY")
    local_cost = base_cost * factor

    info = describe_local_index(zip_code="12401", state="NY")
    # {"factor": 1.12, "label": "Kingston / Hudson Valley, NY",
    #  "delta_pct": 12, "source": "zip3", "baseline": 1.00}

Design notes:
  * We do not crash on bad input. Missing ZIP / state / unknown value
    falls back cleanly to the national baseline of 1.00.
  * Callers that want to *snapshot* the factor onto a record (e.g. the
    Deal model) should call ``get_local_multiplier(...)`` once at
    creation time and store the float. Reprinting from a saved factor
    stays stable even when this table is refreshed next year.
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "regional_cost_index.json",
)

NATIONAL_BASELINE = 1.00


@lru_cache(maxsize=1)
def _load_index() -> Dict[str, Any]:
    """Load and cache the cost-index JSON. Safe on bad file — returns empty."""
    try:
        with open(_DATA_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        logger.warning("cost_index: %s not found, using baseline only", _DATA_PATH)
        return {"states": {}, "zip3": {}, "national_baseline": NATIONAL_BASELINE}
    except (OSError, ValueError) as exc:
        logger.warning("cost_index: could not load %s: %s", _DATA_PATH, exc)
        return {"states": {}, "zip3": {}, "national_baseline": NATIONAL_BASELINE}

    # Defensive defaults so callers can .get() blindly.
    data.setdefault("states", {})
    data.setdefault("zip3", {})
    data.setdefault("national_baseline", NATIONAL_BASELINE)
    return data


def _normalize_zip3(zip_code: Optional[str]) -> Optional[str]:
    if not zip_code:
        return None
    s = str(zip_code).strip()
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) < 3:
        return None
    return digits[:3]


def _normalize_state(state: Optional[str]) -> Optional[str]:
    if not state:
        return None
    s = str(state).strip().upper()
    return s[:2] if len(s) >= 2 else None


def get_local_multiplier(
    zip_code: Optional[str] = None,
    state: Optional[str] = None,
    default: float = NATIONAL_BASELINE,
) -> float:
    """Return a cost multiplier for the given location.

    Lookup order: ZIP3 → state → default (1.00). Never raises.
    """
    data = _load_index()

    zip3 = _normalize_zip3(zip_code)
    if zip3:
        entry = data.get("zip3", {}).get(zip3)
        if isinstance(entry, dict):
            try:
                value = float(entry.get("factor"))
                if value > 0:
                    return value
            except (TypeError, ValueError):
                pass

    st = _normalize_state(state)
    if st:
        try:
            value = float(data.get("states", {}).get(st))
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass

    return default


def describe_local_index(
    zip_code: Optional[str] = None,
    state: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a structured, UI-friendly description of the local factor.

    Always returns a dict of the same shape, even when we fell back to
    baseline. Callers can render ``info["delta_pct"]`` and ``info["label"]``
    without null-checking.
    """
    data = _load_index()
    baseline = float(data.get("national_baseline", NATIONAL_BASELINE) or NATIONAL_BASELINE)

    zip3 = _normalize_zip3(zip_code)
    st = _normalize_state(state)

    factor: Optional[float] = None
    label: Optional[str] = None
    source: str = "baseline"

    if zip3:
        entry = data.get("zip3", {}).get(zip3)
        if isinstance(entry, dict):
            try:
                f = float(entry.get("factor"))
                if f > 0:
                    factor = f
                    label = entry.get("label") or f"ZIP {zip3}xx"
                    source = "zip3"
            except (TypeError, ValueError):
                pass

    if factor is None and st:
        try:
            f = float(data.get("states", {}).get(st))
            if f > 0:
                factor = f
                label = st
                source = "state"
        except (TypeError, ValueError):
            pass

    if factor is None:
        factor = baseline
        label = "U.S. average"
        source = "baseline"

    delta_pct = round((factor - baseline) * 100)
    if delta_pct > 0:
        sign_label = f"+{delta_pct}% vs. national"
    elif delta_pct < 0:
        sign_label = f"{delta_pct}% vs. national"
    else:
        sign_label = "at national average"

    return {
        "factor": round(factor, 3),
        "label": label,
        "delta_pct": delta_pct,
        "signed_label": sign_label,
        "source": source,
        "baseline": baseline,
    }


def apply_multiplier(value: Any, factor: float) -> float:
    """Multiply a value by the factor, tolerating strings like '$1,250'."""
    try:
        if isinstance(value, str):
            cleaned = value.replace("$", "").replace(",", "").strip()
            v = float(cleaned) if cleaned else 0.0
        else:
            v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return v * (factor if factor and factor > 0 else 1.0)


# ---------------------------------------------------------------------------
# Learning layer — blends the seed factor with real CostObservation rows.
# ---------------------------------------------------------------------------
#
# How the blend works:
#   * Each CostObservation carries a cost_per_sqft and a confidence 0..1.
#   * We convert each observation to an "implied factor" by dividing its
#     cost_per_sqft by a national baseline ($/sqft for that category+scope).
#   * We take a confidence-weighted average of those implied factors.
#   * We then blend that observed factor with the seed factor using a
#     pseudocount prior (k=5): learned = (k·seed + n_eff·obs) / (k + n_eff).
#     This shrinks to the seed when observations are sparse and to the
#     observed mean as data accumulates — no cliff, no "one weird deal
#     breaks the whole ZIP" scenario.
#
# National baselines are the same flat numbers today's rehab_service uses,
# extracted here so the conversion obs→factor is explicit and tweakable.

NATIONAL_COST_PER_SQFT = {
    "rehab": {
        "light":  15.0,
        "medium": 30.0,
        "heavy":  50.0,
        "luxury": 85.0,
        # Used when a rehab observation / lookup comes through without a
        # specific scope. Picks "medium" as the most representative rate;
        # prevents accidental 2x skew from falling through to "light".
        "default": 30.0,
    },
    "new_build": {
        None: 225.0,      # category-level fallback if no sub-scope
        "default": 225.0,
    },
}

# Prior pseudocount for the shrinkage blend. Higher → trust the seed more;
# lower → learn faster from real data. 5 means "five pseudo-observations at
# the seed value", which is a reasonable default for most ZIPs.
_PRIOR_PSEUDOCOUNT = 5.0


def national_baseline_cost_per_sqft(category: str = "rehab", scope: Optional[str] = None) -> float:
    """Return the flat national $/sqft for a (category, scope) pair."""
    table = NATIONAL_COST_PER_SQFT.get(category) or NATIONAL_COST_PER_SQFT["rehab"]
    if scope and scope in table:
        return float(table[scope])
    if "default" in table:
        return float(table["default"])
    # Fallback to whatever the first value is, never raise.
    return float(next(iter(table.values())))


def _collect_observations(
    zip3: Optional[str],
    state: Optional[str],
    category: str,
    scope: Optional[str],
):
    """Pull CostObservations relevant to this ZIP3/state/category/scope.

    Widens progressively: exact ZIP3 match first, then state-level. Never
    raises — if the table is missing or the query fails we return ``[]``
    so callers fall back to the seed-only factor.
    """
    try:
        from LoanMVP.models.cost_models import CostObservation
        from LoanMVP.extensions import db  # noqa: F401  (ensure session is wired)
    except Exception as e:
        logger.warning("cost_index: could not import CostObservation: %s", e)
        return []

    try:
        from sqlalchemy import or_

        q = CostObservation.query.filter(
            CostObservation.category == category,
            CostObservation.status.notin_(["rejected", "superseded"]),
            CostObservation.cost_per_sqft.isnot(None),
        )
        if scope:
            q = q.filter(CostObservation.scope == scope)

        # Prefer ZIP3 matches; fall back to state matches if sparse.
        # SQL "zip3 != zip3" is NULL-unsafe, so state-level observations
        # without a ZIP (admin-seeded or contractor-wide data) would be
        # silently dropped. OR with IS NULL to keep them.
        rows = []
        if zip3:
            rows = q.filter(CostObservation.zip3 == zip3).all()
        if len(rows) < 3 and state:
            state_q = q.filter(CostObservation.state == state)
            if zip3:
                state_q = state_q.filter(
                    or_(CostObservation.zip3 != zip3, CostObservation.zip3.is_(None))
                )
            rows = rows + state_q.all()
        return rows
    except Exception as e:
        # cost_observations may not exist yet in the DB on a cold boot
        # before migrations run. The app's schema self-heal will create it,
        # but until then just behave as "no observations".
        logger.warning("cost_index: observation query failed: %s", e)
        return []


def _weighted_average_factor(rows, category: str, scope: Optional[str]) -> Tuple[float, float]:
    """Return (observed_factor, n_effective) weighted by observation confidence."""
    total_w = 0.0
    total_wx = 0.0
    for r in rows or []:
        try:
            cpsf = float(r.cost_per_sqft or 0)
        except (TypeError, ValueError):
            continue
        if cpsf <= 0:
            continue

        baseline_cpsf = national_baseline_cost_per_sqft(
            category, r.scope or scope
        )
        if baseline_cpsf <= 0:
            continue

        implied = cpsf / baseline_cpsf
        # Outlier clamp — anything past [0.4x, 2.5x] is almost certainly a
        # data-entry error ($50 "total rehab cost" or $2M line item).
        if implied < 0.4 or implied > 2.5:
            continue

        w = float(r.confidence if r.confidence is not None else 0.5)
        if w <= 0:
            continue
        total_w += w
        total_wx += w * implied

    if total_w <= 0:
        return 0.0, 0.0
    return total_wx / total_w, total_w


def get_learned_multiplier(
    zip_code: Optional[str] = None,
    state: Optional[str] = None,
    category: str = "rehab",
    scope: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a blend of seed + observation-based cost multiplier.

    Always returns a dict (never raises) so callers can render it directly::

        {"factor": 1.13, "seed": 1.14, "observed": 1.10, "n_effective": 2.3,
         "source": "blended", "category": "rehab", "scope": "medium"}

    ``source`` will be one of: ``baseline``, ``seed``, ``blended``.
    """
    seed = get_local_multiplier(zip_code=zip_code, state=state)
    zip3 = _normalize_zip3(zip_code)
    st = _normalize_state(state)

    rows = _collect_observations(zip3, st, category, scope)
    observed, n_eff = _weighted_average_factor(rows, category, scope)

    if n_eff <= 0:
        blended = seed
        source = "seed"
    else:
        k = _PRIOR_PSEUDOCOUNT
        blended = (k * seed + n_eff * observed) / (k + n_eff)
        source = "blended"

    return {
        "factor":      round(blended, 3),
        "seed":        round(seed, 3),
        "observed":    round(observed, 3) if n_eff > 0 else None,
        "n_effective": round(n_eff, 2),
        "source":      source,
        "category":    category,
        "scope":       scope,
    }


def describe_learned_index(
    zip_code: Optional[str] = None,
    state: Optional[str] = None,
    category: str = "rehab",
    scope: Optional[str] = None,
) -> Dict[str, Any]:
    """UI-ready description that merges ``describe_local_index`` with the
    learned blend."""
    seed_info = describe_local_index(zip_code=zip_code, state=state)
    learned = get_learned_multiplier(zip_code=zip_code, state=state,
                                     category=category, scope=scope)

    factor = learned["factor"] or seed_info["factor"]
    baseline = seed_info["baseline"]
    delta_pct = round((factor - baseline) * 100)
    if delta_pct > 0:
        signed = f"+{delta_pct}% vs. national"
    elif delta_pct < 0:
        signed = f"{delta_pct}% vs. national"
    else:
        signed = "at national average"

    n_eff = learned["n_effective"] or 0
    if learned["source"] == "blended":
        detail = f"RSMeans seed + {int(round(n_eff))} local observation(s)"
    else:
        detail = "RSMeans seed only"

    return {
        "factor":       round(factor, 3),
        "label":        seed_info["label"],
        "delta_pct":    delta_pct,
        "signed_label": signed,
        "detail":       detail,
        "source":       learned["source"],
        "baseline":     baseline,
        "category":     category,
        "scope":        scope,
        "seed":         learned["seed"],
        "observed":     learned["observed"],
        "n_effective":  n_eff,
    }
