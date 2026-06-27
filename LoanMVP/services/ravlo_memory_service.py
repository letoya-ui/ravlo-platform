"""Ravlo AI memory logging helpers.

This service gives every Ravlo module one safe place to record normalized
platform events for future analytics, retrieval, and reviewed model improvement.

Important: rows are not considered model-ready by default. Use
approved_for_training=True only after review/sanitization.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

log = logging.getLogger(__name__)


def _truncate(value: Optional[str], limit: int) -> Optional[str]:
    if value is None:
        return None
    return str(value)[:limit]


def _metadata_json(metadata: Optional[dict], limit: int = 10000) -> Optional[str]:
    if metadata is None:
        return None
    try:
        return json.dumps(metadata, default=str)[:limit]
    except Exception:
        return json.dumps({"error": "metadata_not_serializable", "repr": repr(metadata)[:1000]})[:limit]


def log_ravlo_memory(
    module: str,
    event_type: str,
    feature: Optional[str] = None,
    source: Optional[str] = None,
    role_view: Optional[str] = None,
    prompt: Optional[str] = None,
    response: Optional[str] = None,
    summary: Optional[str] = None,
    metadata: Optional[dict] = None,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    object_type: Optional[str] = None,
    object_id: Optional[str] = None,
    user_id: Optional[int] = None,
    company_id: Optional[int] = None,
    session_key: Optional[str] = None,
    contains_sensitive_data: bool = True,
    approved_for_training: bool = False,
) -> Optional[int]:
    """Write one Ravlo AI memory event. Never raises."""
    try:
        from LoanMVP.extensions import db
        from LoanMVP.models.training_models import RavloAIMemoryLog

        entry = RavloAIMemoryLog(
            user_id=user_id,
            company_id=company_id,
            module=_truncate(module or "unknown", 80) or "unknown",
            feature=_truncate(feature, 100),
            event_type=_truncate(event_type or "event", 80) or "event",
            source=_truncate(source, 80),
            role_view=_truncate(role_view, 80),
            session_key=_truncate(session_key, 120),
            prompt=_truncate(prompt, 4000),
            response=_truncate(response, 8000),
            summary=_truncate(summary, 4000),
            metadata_json=_metadata_json(metadata),
            model=_truncate(model, 100),
            provider=_truncate(provider, 50),
            object_type=_truncate(object_type, 80),
            object_id=_truncate(object_id, 80),
            contains_sensitive_data=bool(contains_sensitive_data),
            approved_for_training=bool(approved_for_training),
            created_at=datetime.utcnow(),
        )
        db.session.add(entry)
        db.session.commit()
        return entry.id
    except Exception as exc:
        log.warning("Ravlo memory log failed: %s", exc)
        return None


def log_ai_exchange(
    module: str,
    feature: str,
    prompt: str,
    response: str,
    user_id: Optional[int] = None,
    company_id: Optional[int] = None,
    role_view: Optional[str] = None,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Optional[int]:
    """Convenience wrapper for AI request/response exchanges."""
    return log_ravlo_memory(
        module=module,
        feature=feature,
        event_type="ai_exchange",
        source="ravlo_memory_service.log_ai_exchange",
        role_view=role_view,
        prompt=prompt,
        response=response,
        summary=f"{module} {feature} AI exchange",
        metadata=metadata,
        model=model,
        provider=provider,
        user_id=user_id,
        company_id=company_id,
        contains_sensitive_data=True,
        approved_for_training=False,
    )


def log_user_action(
    module: str,
    action: str,
    summary: str,
    user_id: Optional[int] = None,
    company_id: Optional[int] = None,
    role_view: Optional[str] = None,
    object_type: Optional[str] = None,
    object_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Optional[int]:
    """Convenience wrapper for non-AI user actions Ravlo should remember."""
    return log_ravlo_memory(
        module=module,
        feature=action,
        event_type="user_action",
        source="ravlo_memory_service.log_user_action",
        role_view=role_view,
        summary=summary,
        metadata=metadata,
        object_type=object_type,
        object_id=object_id,
        user_id=user_id,
        company_id=company_id,
        contains_sensitive_data=True,
        approved_for_training=False,
    )
