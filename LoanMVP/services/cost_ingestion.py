"""
Cost-observation ingestion helpers.

Every real dollar figure that passes through Ravlo — a contractor bid, an
investor's actual rehab cost on a saved deal, a closed loan — should land
here and become a row in ``cost_observations``. That table then feeds the
learning layer in ``cost_index.get_learned_multiplier``.

This module is intentionally low-ceremony:
  * ``record_observation`` never raises. Worst case it rolls back and logs.
  * It computes ``cost_per_sqft`` and ``zip3`` automatically from the
    inputs it's given.
  * Callers that want to tie an observation to a deal (for traceability)
    can pass ``deal_id``; others can omit it.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from LoanMVP.extensions import db
from LoanMVP.models.cost_models import (
    SOURCE_CONFIDENCE,
    CATEGORY_REHAB,
    CostObservation,
)

logger = logging.getLogger(__name__)


def _digits(v: Any) -> str:
    return "".join(ch for ch in str(v or "") if ch.isdigit())


def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        if isinstance(v, str):
            cleaned = v.replace("$", "").replace(",", "").strip()
            return float(cleaned) if cleaned else None
        return float(v)
    except (TypeError, ValueError):
        return None


def record_observation(
    *,
    source: str,
    category: str = CATEGORY_REHAB,
    total_cost: Any = None,
    sqft: Any = None,
    cost_per_sqft: Any = None,
    zip_code: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None,
    scope: Optional[str] = None,
    asset_type: Optional[str] = None,
    user_id: Optional[int] = None,
    deal_id: Optional[int] = None,
    partner_id: Optional[int] = None,
    confidence: Optional[float] = None,
    status: str = "verified",
    notes: Optional[str] = None,
) -> Optional[CostObservation]:
    """Persist a single cost observation. Returns the row, or None on failure.

    Requires enough signal to compute a ``cost_per_sqft``: either a
    ``cost_per_sqft`` directly, or both ``total_cost`` and ``sqft``.
    """
    cpsf = _to_float(cost_per_sqft)
    tc = _to_float(total_cost)
    sq = _to_float(sqft)

    if cpsf is None and tc is not None and sq and sq > 0:
        cpsf = tc / sq

    if cpsf is None or cpsf <= 0:
        return None

    if confidence is None:
        confidence = SOURCE_CONFIDENCE.get(source, 0.5)

    zip_digits = _digits(zip_code)
    zip3 = zip_digits[:3] if len(zip_digits) >= 3 else None
    state_code = (state or "").strip().upper()[:2] or None

    try:
        row = CostObservation(
            source=source,
            user_id=user_id,
            deal_id=deal_id,
            partner_id=partner_id,
            zip_code=(zip_digits[:10] or None),
            zip3=zip3,
            state=state_code,
            city=(city or None),
            category=category,
            asset_type=asset_type,
            scope=scope,
            sqft=sq,
            total_cost=tc,
            cost_per_sqft=cpsf,
            confidence=float(confidence),
            status=status,
            notes=notes,
        )
        db.session.add(row)
        db.session.commit()
        return row
    except Exception as e:
        logger.warning("cost_ingestion: failed to record observation: %s", e)
        try:
            db.session.rollback()
        except Exception:
            pass
        return None


def record_from_deal(deal, *, source: str = "investor_input") -> Optional[CostObservation]:
    """Convenience: pull fields off a Deal and record a rehab observation.

    Re-saves of the same deal should not inflate the learning layer. If a
    prior rehab observation for this deal already exists we mark it
    ``superseded`` and point the new row at it via ``supersedes_id`` so
    ``_collect_observations`` counts only the latest figure.
    """
    if deal is None:
        return None

    total = getattr(deal, "rehab_cost", None)
    if not total or total <= 0:
        return None

    sqft = None
    for container in (getattr(deal, "inputs_json", None),
                      getattr(deal, "resolved_json", None)):
        if isinstance(container, dict):
            sqft = sqft or container.get("sqft") or container.get("property_sqft")

    scope = None
    rehab_scope = getattr(deal, "rehab_scope_json", None)
    if isinstance(rehab_scope, dict):
        scope = rehab_scope.get("scope") or scope

    deal_id = getattr(deal, "id", None)
    prior_id: Optional[int] = None
    if deal_id is not None:
        try:
            prior = (
                CostObservation.query
                .filter_by(deal_id=deal_id, category=CATEGORY_REHAB, status="verified")
                .order_by(CostObservation.id.desc())
                .first()
            )
            if prior is not None:
                prior.status = "superseded"
                prior_id = prior.id
                db.session.add(prior)
                db.session.commit()
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("cost_ingestion: supersede lookup failed: %s", e)
            try:
                db.session.rollback()
            except Exception:
                pass

    row = record_observation(
        source=source,
        category=CATEGORY_REHAB,
        total_cost=total,
        sqft=sqft,
        scope=scope,
        zip_code=getattr(deal, "zip_code", None),
        state=getattr(deal, "state", None),
        city=getattr(deal, "city", None),
        user_id=getattr(deal, "user_id", None),
        deal_id=deal_id,
    )

    if row is not None and prior_id is not None:
        try:
            row.supersedes_id = prior_id
            db.session.add(row)
            db.session.commit()
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("cost_ingestion: supersedes_id set failed: %s", e)
            try:
                db.session.rollback()
            except Exception:
                pass

    return row
